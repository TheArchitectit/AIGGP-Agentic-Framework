#!/usr/bin/env node
import { Command } from 'commander';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadChange, loadConventions, loadBaseline } from './spec/loader.js';
import { getDiff } from './diff/git.js';
import { runReview, runReviewAsync } from './engine.js';
import { scanRepository } from './checks/scan.js';
import { providerFromEnv } from './llm/provider.js';
import { loadConfig } from './config.js';
import { toSarif } from './sarif.js';
import { builtinTemplates } from './templates/registry.js';
import { loadCustomTemplates } from './templates/parser.js';
import { resolveTemplate } from './templates/detect.js';
import type { ProjectTemplate } from './templates/types.js';
import type { Diff, ReviewResult, Severity, Finding } from './types.js';
import { decodeMarker, findingKey, ghRunner, glabRunner } from './vcs.js';
import { toJson, toMarkdown } from './reporter.js';

/** Build a ReviewResult from scan findings. */
function buildScanResult(changeName: string, findings: Finding[]): ReviewResult {
  const blockers = findings.filter((f) => f.severity === 'blocker' || f.severity === 'high').length;
  return {
    change: changeName,
    verdict: findings.length === 0 ? 'PASS' : blockers > 0 ? 'CHANGES_REQUESTED' : 'PASS',
    summary: findings.length === 0
      ? 'No drift detected — all capabilities have active specs.'
      : `${blockers} blocking finding(s) across all capabilities.`,
    template: { id: 'scan', label: 'Repository Scan', reason: '--scan mode' },
    requirementCoverage: [],
    findings,
    stats: {
      filesChanged: 0,
      linesAdded: 0,
      requirementsTotal: 0,
      requirementsCovered: 0
    }
  };
}

/** Output result and exit per --fail-on. */
function outputAndExit(result: ReviewResult, fmt: string, failOn: string): never {
  const rank = { blocker: 0, high: 1, medium: 2, low: 3, info: 4, never: 99 } as const;
  if (!(failOn in rank)) {
    console.error(`stitcher-codereview: invalid --fail-on "${failOn}" (want blocker|high|medium|low|never).`);
    process.exit(2);
  }
  if (failOn === 'never') process.exit(0);
  const threshold = rank[failOn as keyof typeof rank];
  const worst = result.findings.length === 0 ? 99 : Math.min(...result.findings.map((f) => rank[f.severity]));
  if (fmt === 'json') console.log(toJson(result));
  else if (fmt === 'sarif') console.log(toSarif(result));
  else if (fmt !== 'markdown') {
    console.error(`stitcher-codereview: invalid --format "${fmt}" (want markdown|json|sarif).`);
    process.exit(2);
  } else console.log(toMarkdown(result));
  // Exit 0 = success (PASS), 1 = findings at/above --fail-on (CHANGES_REQUESTED).
  process.exit(worst <= threshold ? 1 : 0);
}

/**
 * Post the review as GitHub/GitLab PR/MR inline comments (new findings only — existing
 * markers on the PR/MR are de-duplicated) + one walkthrough body, when running
 * inside a pull_request/merge_request event. Non-fatal: any posting failure only warns.
 */
async function postVcs(result: ReviewResult, diff: Diff): Promise<void> {
  const { detectVcsProvider, getVcsProvider, partitionInline, buildReviewBody, findingKey, decodeMarker } = await import('./vcs.js');
  const providerName = detectVcsProvider(process.env);
  if (!providerName) {
    console.error('stitcher-codereview: --post vcs but no pull_request/merge_request event detected; nothing posted.');
    return;
  }
  const provider = await getVcsProvider(providerName);
  const ctx = provider.detectContext(process.env);
  if (!ctx) {
    console.error(`stitcher-codereview: --post vcs but no ${providerName} merge_request/pull_request event detected; nothing posted.`);
    return;
  }
  const token = providerName === 'github'
    ? (process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN)
    : (process.env.GITLAB_TOKEN ?? process.env.GLAB_TOKEN);
  const run = providerName === 'github' ? ghRunner(token) : glabRunner(token);
  try {
    const { comments, bodyOnly } = partitionInline(result, diff);
    const existing = new Set(await provider.listPostedKeys(ctx, run));
    const fresh = comments.filter((c) => !decodeMarker(c.body).some((k) => existing.has(k)));
    const currentKeys = new Set(result.findings.map((f) => findingKey(f)));
    const stale = [...existing].filter((k) => !currentKeys.has(k)).length;
    if (fresh.length === 0 && bodyOnly.length === 0 && stale === 0) {
      console.error('stitcher-codereview: no posting — all findings already posted on the MR/PR.');
      return;
    }
    const body = buildReviewBody(result, bodyOnly, stale);
    await provider.postReview(ctx, { body, comments: fresh, commitId: ctx.headSha, run });
    console.error(`stitcher-codereview: posted ${fresh.length} inline comment(s)${stale > 0 ? `, ${stale} resolved` : ''} on ${providerName}.`);
  } catch (err) {
    console.error(`stitcher-codereview: posting failed (non-fatal): ${(err as Error).message}`);
  }
}

function mergeTemplates(builtins: ProjectTemplate[], customs: ProjectTemplate[]): ProjectTemplate[] {
  const customIds = new Set(customs.map((t) => t.id));
  return [...customs, ...builtins.filter((t) => !customIds.has(t.id))];
}

function pkgVersion(): string {
  try {
    const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as { version?: string };
    return pkg.version ?? '0.0.0';
  } catch {
    return '0.0.0';
  }
}

const program = new Command();
program
  .name('stitcher-codereview')
  .version(pkgVersion())
  .description('Spec-aware code review: verify a git diff against an OpenSpec change (proposal/specs/design/tasks) + correctness, security, tests, style.')
  .option('--change <name>', 'OpenSpec change name under openspec/changes/<name>')
  .option('--root <dir>', 'Project root (contains openspec/)', process.cwd())
  .option('--base <ref>', 'Git base ref for diff (range base...HEAD)', 'main')
  .option('--format <fmt>', 'Output format: markdown|json|sarif', 'markdown')
  .option('--sarif-out <path>', 'Additionally write a SARIF 2.1.0 report to this file (for code scanning upload)')
  .option('--only <cats>', 'Comma list: spec-compliance,tasks,correctness,security,tests,style,template (default all)', 'all')
  .option('--fail-on <sev>', 'Exit 1 if findings at/above severity (blocker|high|medium|low|never)', 'high')
  .option('--template <id>', 'Project-type template: auto|generic|cli|web-service|game-2d-3d|<custom> (default auto)', 'auto')
  .option('--list-templates', 'List available review templates for --root and exit')
  .option('--llm <mode>', 'LLM mode: off|auto (fail-open)|require (fail-closed)|gap (line-level gap analysis). Env: STITCHER_CODEREVIEW_LLM', 'off')
  .option('--llm-provider <p>', 'LLM provider: openai|anthropic|custom (OpenAI-compatible). Env: STITCHER_CODEREVIEW_LLM_PROVIDER')
  .option('--llm-model <m>', 'Model name. Env: STITCHER_CODEREVIEW_LLM_MODEL')
  .option('--llm-base-url <url>', 'Custom OpenAI-compatible base URL (e.g. Ollama). Env: STITCHER_CODEREVIEW_LLM_BASE_URL')
  .option('--llm-weight <w>', 'LLM weight in blend 0..1 (0.5 = even). Env: STITCHER_CODEREVIEW_LLM_WEIGHT', '0.5')
  .option('--llm-max-concurrency <n>', 'Max parallel LLM requests (default 3). Env: STITCHER_CODEREVIEW_LLM_MAX_CONCURRENCY', '3')
  .option('--llm-max-retries <n>', 'Max retries per LLM request (default 2). Env: STITCHER_CODEREVIEW_LLM_MAX_RETRIES', '2')
  .option('--config <path>', 'Review policy file (default auto: openspec/review.yaml if present)', 'auto')
  .option('--no-user-config', 'Ignore ~/.config/stitcher-codereview/config.yaml (CI reproducibility)')
  .option('--timing', 'Record per-category durations in stats.durationsMs (JSON output)')
  .option('--post <mode>', 'Post findings: none|github|gitlab|vcs (inline review comments via gh/glab; requires ${{ github.token }} / ${{ gitlab.token }})', 'none')
  .option('--scan <mode>', 'Scan mode: off|repository (whole-tree drift scan, no --change required)', 'off')
  .option('--serve', 'Start webhook server for async reviews (GitHub/GitLab)')
  .option('--serve-port <n>', 'Port for webhook server (default 3000)', '3000')
  .option('--serve-host <h>', 'Host for webhook server (default 0.0.0.0)', '0.0.0.0')
  .option('--serve-secret <s>', 'Webhook secret for signature verification (or STITCHER_WEBHOOK_SECRET)')
  .option('--insecure-dev', 'Allow serve mode without a webhook secret (local dev only, never in production)')
  .action(async (opts) => {
    try {
      if (opts.userConfig === false) process.env.STITCHER_CODEREVIEW_NO_USER_CONFIG = '1';
      const root = resolve(opts.root);
      const { config: fileCfg, warnings: cfgWarnings } = await loadConfig(root, opts.config);
      for (const w of cfgWarnings) console.error(`stitcher-codereview: warning: ${w}`);
      // Precedence: explicit flag > env (LLM) > config file > default.
      const srcOf = (k: string): string => {
        try {
          return program.getOptionValueSource(k) ?? 'default';
        } catch {
          return 'default';
        }
      };
      const eff = (key: string, envName: string | undefined, cfgVal: string | undefined, dflt: string | undefined) => {
        if (srcOf(key) !== 'default') return opts[key] as string | undefined;
        if (envName && process.env[envName]) return process.env[envName];
        if (cfgVal !== undefined) return cfgVal;
        return dflt;
      };
      const onlyRaw = eff('only', undefined, Array.isArray(fileCfg.only) ? fileCfg.only.join(',') : fileCfg.only, 'all') ?? 'all';
      const mcRaw = eff('llmMaxConcurrency', 'STITCHER_CODEREVIEW_LLM_MAX_CONCURRENCY',
        fileCfg.llm?.maxConcurrency?.toString(), '3') ?? '3';
      const mrRaw = eff('llmMaxRetries', 'STITCHER_CODEREVIEW_LLM_MAX_RETRIES',
        fileCfg.llm?.maxRetries?.toString(), '2') ?? '2';
      const llmMaxConcurrency = parseInt(mcRaw, 10);
      const llmMaxRetries = parseInt(mrRaw, 10);
      if (!Number.isFinite(llmMaxConcurrency) || llmMaxConcurrency < 1 || llmMaxConcurrency > 32) {
        console.error(`stitcher-codereview: invalid --llm-max-concurrency "${mcRaw}" (want integer 1..32).`);
        process.exit(2);
      }
      if (!Number.isFinite(llmMaxRetries) || llmMaxRetries < 0 || llmMaxRetries > 10) {
        console.error(`stitcher-codereview: invalid --llm-max-retries "${mrRaw}" (want integer 0..10).`);
        process.exit(2);
      }
      const llmWeightRaw = eff(
        'llmWeight', 'STITCHER_CODEREVIEW_LLM_WEIGHT',
        fileCfg.llm?.weight !== undefined ? String(fileCfg.llm.weight) : undefined, '0.5'
      ) ?? '0.5';
      const llmWeightNum = parseFloat(llmWeightRaw);
      if (!Number.isFinite(llmWeightNum) || llmWeightNum < 0 || llmWeightNum > 1) {
        console.error(`stitcher-codereview: invalid --llm-weight "${llmWeightRaw}" (want number 0..1).`);
        process.exit(2);
      }
      const validLlms = ['off', 'auto', 'require', 'gap'];
      const validPosts = ['none', 'github', 'gitlab', 'vcs'];
      const validFormats = ['markdown', 'json', 'sarif'];
      const effective = {
        format: eff('format', undefined, fileCfg.format, 'markdown') ?? 'markdown',
        only: onlyRaw,
        failOn: eff('failOn', undefined, fileCfg['fail-on'], 'high') ?? 'high',
        template: eff('template', undefined, fileCfg.template, 'auto') ?? 'auto',
        llm: eff('llm', 'STITCHER_CODEREVIEW_LLM', fileCfg.llm?.mode, 'off') ?? 'off',
        llmProvider: eff('llmProvider', 'STITCHER_CODEREVIEW_LLM_PROVIDER', fileCfg.llm?.provider, undefined),
        llmModel: eff('llmModel', 'STITCHER_CODEREVIEW_LLM_MODEL', fileCfg.llm?.model, undefined),
        llmWeight: llmWeightRaw,
        llmBaseUrl: eff('llmBaseUrl', 'STITCHER_CODEREVIEW_LLM_BASE_URL', fileCfg.llm?.['base-url'], undefined),
        llmMaxConcurrency,
        llmMaxRetries,
        sarifOut: eff('sarifOut', undefined, fileCfg['sarif-file'], undefined),
        post: eff('post', undefined, fileCfg.post, 'none') ?? 'none',
        timing: opts.timing === true,
        scan: ['repository', 'true'].includes(eff('scan', undefined, fileCfg.scan, 'off') ?? 'off')
      };
      if (!validLlms.includes(effective.llm)) {
        console.error(`stitcher-codereview: invalid --llm "${effective.llm}" (want ${validLlms.join('|')}).`);
        process.exit(2);
      }
      if (!validPosts.includes(effective.post)) {
        console.error(`stitcher-codereview: invalid --post "${effective.post}" (want ${validPosts.join('|')}).`);
        process.exit(2);
      }
      if (!validFormats.includes(effective.format)) {
        console.error(`stitcher-codereview: invalid --format "${effective.format}" (want ${validFormats.join('|')}).`);
        process.exit(2);
      }
      // Unknown --only categories currently mean "silently run nothing" —
      // reject them so typos fail loudly instead of phantom-PASSing.
      const KNOWN_CATEGORIES = new Set(['all', 'spec-compliance', 'tasks', 'correctness', 'security', 'tests', 'style', 'template']);
      const requested = String(effective.only).split(',').map((s: string) => s.trim()).filter(Boolean);
      const unknown = requested.filter((c: string) => !KNOWN_CATEGORIES.has(c));
      if (requested.length === 0 && String(effective.only) !== 'all') {
        console.error(`stitcher-codereview: --only must name at least one category (got "${effective.only}"); want ${[...KNOWN_CATEGORIES].join(',')}.`);
        process.exit(2);
      }
      if (unknown.length > 0) {
        console.error(`stitcher-codereview: invalid --only "${[...unknown].join(',')}" (want ${[...KNOWN_CATEGORIES].join(',')}).`);
        process.exit(2);
      }
      const { templates: customs, warnings } = await loadCustomTemplates(root);
      for (const w of warnings) console.error(`stitcher-codereview: warning: ${w}`);
      const all = mergeTemplates(builtinTemplates(), customs);

      if (opts.listTemplates) {
        for (const t of all) {
          console.log(`${t.id}${t.custom ? ' (custom)' : ''} — ${t.label}: ${t.description} [${t.checks.length} checks]`);
        }
        process.exit(0);
      }

      // --serve mode: webhook server for async reviews
      if (opts.serve) {
        const { startServe } = await import('./serve.js');
        const port = parseInt(String(opts.servePort ?? '3000'), 10);
        if (!Number.isFinite(port) || port < 1 || port > 65535) {
          console.error(`stitcher-codereview: invalid --serve-port "${opts.servePort}" (want 1..65535).`);
          process.exit(2);
        }
        await startServe({
          port,
          host: String(opts.serveHost ?? '0.0.0.0'),
          secret: (opts.serveSecret as string | undefined) ?? process.env.STITCHER_WEBHOOK_SECRET,
          insecureDev: Boolean(opts.insecureDev),
          root
        });
        // startServe never returns (runs forever)
        return;
      }

      // --scan mode: whole-tree drift scan against baselines (no --change required)
      if (effective.scan) {
        const baseline = await loadBaseline(root, fileCfg.baselines);
        const findings = await scanRepository(baseline, root);
        const result = buildScanResult('repository-scan', findings);
        outputAndExit(result, effective.format, effective.failOn);
      }

      if (!opts.change) {
        console.error('stitcher-codereview: --change <name> is required (or use --list-templates).');
        process.exit(2);
      }

      const change = await loadChange(root, opts.change, fileCfg.baselines);
      const diff = await getDiff(root, opts.base);
      const conventions = await loadConventions(root);
      const template = await resolveTemplate(root, effective.template, all);
      const categories = new Set(
        effective.only === 'all' ? ['all'] : String(effective.only).split(',').map((s: string) => s.trim())
      );
      const engineOpts = {
        categories,
        template,
        base: opts.base,
        root,
        timing: Boolean(effective.timing),
        config: {
          disable: fileCfg.disable,
          severities: fileCfg.severities as Partial<Record<string, Severity>> | undefined,
          ignore: fileCfg.ignore,
          include: fileCfg.include,
          rules: fileCfg.rules,
          maxLineLength: fileCfg['max-line-length'] as number | undefined,
          coveredAt: fileCfg['covered-at'] as number | undefined,
          partialAt: fileCfg['partial-at'] as number | undefined,
          maxFindings: fileCfg['max-findings'] as number | undefined
        }
      };
      const llm = providerFromEnv(process.env, {
        llm: effective.llm,
        provider: effective.llmProvider,
        model: effective.llmModel,
        weight: effective.llmWeight,
        baseUrl: effective.llmBaseUrl,
        maxConcurrency: effective.llmMaxConcurrency.toString(),
        maxRetries: effective.llmMaxRetries.toString()
      });
      const useLlm = llm.mode !== 'off' && (categories.has('all') || categories.has('spec-compliance'));
      const result = useLlm
        ? await runReviewAsync(change, diff, conventions, engineOpts, llm)
        : await runReview(change, diff, conventions, engineOpts);

      if (effective.sarifOut) {
        const { writeFile, mkdir, rm, readdir, stat } = await import('node:fs/promises');
        const { dirname, isAbsolute, join } = await import('node:path');
        const outPath = isAbsolute(effective.sarifOut) ? effective.sarifOut : resolve(root, effective.sarifOut);
        // Containment: keep SARIF inside root or CWD to avoid absolute escape.
        const allowed = [root, process.cwd()];
        if (!allowed.some((base) => outPath === base || outPath.startsWith(base + '/'))) {
          console.error(`stitcher-codereview: refusing --sarif-out outside project root/cwd: ${outPath}`);
          process.exit(2);
        }
        // A directory target is a user mistake (probably meant a file path); fail loudly.
        const existing = await stat(outPath).catch(() => null);
        if (existing?.isDirectory()) {
          console.error(`stitcher-codereview: --sarif-out is a directory, expected a file path: ${outPath}`);
          process.exit(2);
        }
        await mkdir(dirname(outPath), { recursive: true });
        // Collided/abandoned tmp files from prior SIGKILL runs must not exist side-by-side
        // (SARIF consumers resolving the glob could read a half-written file).
        const dir = dirname(outPath);
        const baseName = outPath.slice(dir.length + 1);
        const siblings = await readdir(dir, { withFileTypes: true }).catch(() => []);
        for (const e of siblings) {
          if (!e.isFile()) continue;
          if (!e.name.startsWith(`${baseName}.tmp-`)) continue;
          const full = join(dir, e.name);
          const st = await stat(full).catch(() => null);
          if (st && Date.now() - st.mtimeMs > 60 * 60 * 1000) await rm(full, { force: true });
        }
        const tmp = `${outPath}.tmp-${process.pid}`;
        await writeFile(tmp, toSarif(result));
        await (await import('node:fs/promises')).rename(tmp, outPath);
        console.error(`stitcher-codereview: SARIF written to ${outPath}`);
      }

      if (effective.post === 'github' || effective.post === 'gitlab' || effective.post === 'vcs') {
        await postVcs(result, diff);
      }

      outputAndExit(result, effective.format, effective.failOn);
    } catch (err) {
      console.error(`stitcher-codereview: ${(err as Error).message}`);
      process.exit(2);
    }
  });

program.parse();

// Conventional Ctrl-C exit during long (LLM) reviews.
// Exit code 130 = 128 + SIGINT (standard POSIX convention for signal termination).
process.on('SIGINT', () => {
  console.error('stitcher-codereview: interrupted');
  process.exit(130);
});
