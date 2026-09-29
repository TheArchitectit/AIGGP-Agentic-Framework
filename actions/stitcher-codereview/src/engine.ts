import type { Diff, Finding, OpenSpecChange, Requirement, ReviewResult, Severity } from './types.js';
import { checkSpecCompliance, coverageForRequirement, findingsForCoverage } from './checks/specCompliance.js';
import { checkDrift } from './checks/drift.js';
import { checkTasks } from './checks/tasks.js';
import { checkCorrectness } from './checks/correctness.js';
import { checkSecurity } from './checks/security.js';
import { checkTests } from './checks/tests.js';
import { checkStyle } from './checks/style.js';
import { decideVerdict, sortFindings } from './reporter.js';
import { attachEvidence } from './evidence.js';
import { runTemplateChecks, type ResolvedTemplate } from './templates/types.js';
import {
  blendScores,
  buildDiffSlice,
  statusForScore,
  type LLMMode,
  type LLMProvider,
  type LLMConfig,
  type GapFinding,
  Semaphore,
  withRetry
} from './llm/provider.js';

export interface ReviewOptions {
  categories: Set<string>; // e.g. spec-compliance, correctness...
  /** Resolved project-type template (lens + heuristic pack). Null = generic. */
  template?: ResolvedTemplate | null;
  /** Git base ref, used only to explain an empty diff. */
  base?: string;
  /** Project root (for external tools that need to run in the repo). */
  root?: string;
  /** Repo config policy: dropped check ids and severity remaps (all categories). */
  config?: {
    disable?: string[];
    severities?: Partial<Record<string, Severity>>;
    ignore?: string | string[];
    include?: string | string[];
    rules?: Record<string, { severity?: string; paths?: string | string[] }>;
    /** Style: flag added lines longer than this (default 140, conventions may lower to 120). */
    maxLineLength?: number;
    /** Spec-coverage thresholds (default 0.3 / 0.12). */
    coveredAt?: number;
    partialAt?: number;
    /** Total findings cap applied after sort (per-check caps still apply first). */
    maxFindings?: number;
  };
  /** Record per-category durations into stats.durationsMs (opt-in; keeps default output byte-stable). */
  timing?: boolean;
}

export interface LLMBlendOptions {
  provider: LLMProvider;
  mode: LLMMode;
  /** Weight of the LLM score in the blend (0 = heuristic only, 1 = LLM only). */
  weight: number;
  maxConcurrency?: number;
  maxRetries?: number;
}

function templateInfo(opts: ReviewOptions): ReviewResult['template'] {
  if (!opts.template) return { id: 'generic', label: 'Generic', reason: 'no template requested' };
  const { template, reason } = opts.template;
  return { id: template.id, label: template.label, reason };
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function globToRegExp(p: string): RegExp {
  // Escape everything, then restore * and ? wildcards (** collapses to *).
  const esc = escapeRegExp(p).replace(/\\\*\\\*/g, '.*').replace(/\\\*/g, '.*').replace(/\\\?/g, '.');
  return new RegExp('^' + esc + '$');
}

function matchesPattern(path: string, patterns: string[]): boolean {
  return patterns.some((p) => {
    // Guard against pathological glob sources (hostile config): enormous
    // patterns yield enormous .*.* alternations — refuse rather than stall.
    if (typeof p !== 'string' || p.length > 256) {
      console.error(`stitcher-codereview: warning: ignoring oversized/invalid glob pattern (${typeof p === 'string' ? p.length : 'non-string'} chars)`);
      return false;
    }
    try {
      return globToRegExp(p).test(path);
    } catch {
      console.error(`stitcher-codereview: warning: invalid glob pattern "${p}" ignored`);
      return false;
    }
  });
}

function isIgnored(f: Finding, diff: Diff, cfg: ReviewOptions['config']): boolean {
  if (!f.file) return false;
  // Path ignore/include
  const ignore = cfg?.ignore ? (Array.isArray(cfg.ignore) ? cfg.ignore : [cfg.ignore]) : [];
  const include = cfg?.include ? (Array.isArray(cfg.include) ? cfg.include : [cfg.include]) : [];
  if (include.length > 0 && !matchesPattern(f.file, include)) return true;
  if (ignore.length > 0 && matchesPattern(f.file, ignore)) return true;
  // Inline ignore directive on the finding's line
  if (f.line) {
    const file = diff.files.find((df) => df.path === f.file);
    if (file) {
      const line = file.addedLines.find((l) => l.n === f.line);
      if (line && /\b(review|stitcher-codereview)\s*:\s*ignore\b/i.test(line.text)) return true;
    }
  }
  return false;
}

function applyRuleSeverity(f: Finding, cfg: ReviewOptions['config']): Finding {
  if (!cfg?.rules || !f.file) return f;
  const rule = cfg.rules[f.checkId];
  if (!rule) return f;
  if (rule.paths) {
    const paths = Array.isArray(rule.paths) ? rule.paths : [rule.paths];
    if (!matchesPattern(f.file, paths)) return f;
  }
  const valid: Severity[] = ['blocker', 'high', 'medium', 'low', 'info'];
  if (rule.severity && (valid as string[]).includes(rule.severity)) return { ...f, severity: rule.severity as Severity };
  return f;
}

function finalize(
  change: OpenSpecChange,
  diff: Diff,
  coverage: ReviewResult['requirementCoverage'],
  findings: Finding[],
  opts: ReviewOptions,
  durations?: Record<string, number>
): Promise<ReviewResult> {
  // Templates may suppress noisy check ids (cli stdout, ...), but never
  // spec-compliance: the spec verdict is the tool's reason to exist.
  const suppressed = new Set(opts.template?.template.suppress ?? []);
  const kept = findings.filter(
    (f) => f.category === 'spec-compliance' || !suppressed.has(f.checkId)
  );
  // Repo config policy: path ignore/include, inline ignore, disable, severities remap, per-rule paths
  const disabled = new Set(opts.config?.disable ?? []);
  const remap = opts.config?.severities ?? {};
  const tuned = kept
    .filter((f) => !isIgnored(f, diff, opts.config))
    .filter((f) => !disabled.has(f.checkId))
    .map((f) => applyRuleSeverity(f, opts.config))
    .map((f) => (remap[f.checkId] ? { ...f, severity: remap[f.checkId] as Severity } : f));
  // Total findings cap (config `max-findings`) — sort first so the most severe findings survive the cap.
  const sorted = sortFindings(tuned).slice(0, opts.config?.maxFindings ?? Infinity);
  const verdict = decideVerdict(sorted);
  const covered = coverage.filter((c) => c.status === 'covered').length;
  const linesAdded = diff.files.reduce((n, f) => n + f.addedLines.length, 0);
  const blockers = sorted.filter((f) => f.severity === 'blocker' || f.severity === 'high').length;

  const summary =
    coverage.length === 0
      ? `No delta specs found — ran general checks only (${sorted.length} findings).`
      : verdict === 'PASS'
        ? `All ${coverage.length} requirement(s) evidenced in diff; ${sorted.length} minor finding(s).`
        : `${blockers} blocking finding(s) over ${coverage.length} requirement(s); ${covered} fully covered.`;

  const result: ReviewResult = {
    change: change.name,
    verdict,
    summary,
    template: templateInfo(opts),
    requirementCoverage: coverage,
    findings: sorted,
    stats: {
      filesChanged: diff.files.length,
      linesAdded,
      requirementsTotal: coverage.length,
      requirementsCovered: covered,
      ...(durations ? { durationsMs: durations } : {})
    }
  };
  return attachEvidence(result, diff, opts.root);
}

/** Wall-clock accumulator; active only when opts.timing is set. */
class Durations {
  private readonly map: Record<string, number> | undefined;
  constructor(private readonly enabled: boolean) {
    this.map = enabled ? {} : undefined;
  }
  get record(): Record<string, number> | undefined {
    return this.map;
  }
  async run<T>(key: string, fn: () => Promise<T>): Promise<T> {
    if (!this.map) return fn();
    const t0 = performance.now();
    try {
      return await fn();
    } finally {
      this.map[key] = (this.map[key] ?? 0) + (performance.now() - t0);
    }
  }
  runSync<T>(key: string, fn: () => T): T {
    if (!this.map) return fn();
    const t0 = performance.now();
    try {
      return fn();
    } finally {
      this.map[key] = (this.map[key] ?? 0) + (performance.now() - t0);
    }
  }
}

function wantTemplate(opts: ReviewOptions): boolean {
  const want = (c: string) => opts.categories.has('all') || opts.categories.has(c);
  return want('template') && !!opts.template && opts.template.template.checks.length > 0;
}

function checkerFailed(category: string, err: unknown): Finding {
  return {
    severity: 'high',
    category: category as Finding['category'],
    checkId: 'checker-failed',
    message: `Checker "${category}" failed: ${(err as Error)?.message ?? String(err)} (degraded result).`,
    suggestion: 'Re-run with --only to isolate, and report this as a bug with the repo fingerprint.'
  };
}

function safeCheck(category: string, fn: () => Finding[]): Finding[] {
  try {
    return fn();
  } catch (err) {
    console.error(`stitcher-codereview: warning: checker "${category}" threw: ${(err as Error)?.message}`);
    return [checkerFailed(category, err)];
  }
}

async function safeCheckAsync(category: string, fn: () => Promise<Finding[]>): Promise<Finding[]> {
  try {
    return await fn();
  } catch (err) {
    console.error(`stitcher-codereview: warning: checker "${category}" threw: ${(err as Error)?.message}`);
    return [checkerFailed(category, err)];
  }
}

export async function runReview(change: OpenSpecChange, diff: Diff, conventions: string, opts: ReviewOptions): Promise<ReviewResult> {
  const findings: Finding[] = [];
  let coverage: ReviewResult['requirementCoverage'] = [];
  const dur = new Durations(Boolean(opts.timing));

  const want = (c: string) => opts.categories.has('all') || opts.categories.has(c);

  if (diff.files.length === 0 && want('spec-compliance')) {
    findings.push({
      severity: 'high',
      category: 'spec-compliance',
      checkId: 'empty-diff',
      message: `Diff is empty${opts.base ? ` for base \`${opts.base}\`` : ''} — nothing to review.`,
      suggestion: 'Check --base (and commit or stage your changes); an empty range falls back to the working tree.'
    });
  }
  if (want('spec-compliance')) {
    const r = dur.runSync('spec-compliance', () => {
      try {
        return checkSpecCompliance(change, diff, { coveredAt: opts.config?.coveredAt, partialAt: opts.config?.partialAt });
      } catch (err) {
        console.error(`stitcher-codereview: warning: checker "spec-compliance" threw: ${(err as Error)?.message}`);
        return { findings: [checkerFailed('spec-compliance', err)], coverage };
      }
    });
    findings.push(...r.findings);
    coverage = r.coverage;
    findings.push(...dur.runSync('drift', () => safeCheck('spec-compliance', () => checkDrift(change, diff))));
  }
  if (want('tasks')) findings.push(...dur.runSync('tasks', () => safeCheck('tasks', () => checkTasks(change, diff))));
  if (want('correctness')) findings.push(...dur.runSync('correctness', () => safeCheck('correctness', () => checkCorrectness(diff))));
  if (want('security')) findings.push(...dur.runSync('security', () => safeCheck('security', () => checkSecurity(diff))));
  if (want('tests')) findings.push(...dur.runSync('tests', () => safeCheck('tests', () => checkTests(change, diff, {
    testFileRes: opts.template?.template.testFileRes, testHint: opts.template?.template.testHint
  }))));
  if (want('style')) findings.push(...dur.runSync('style', () => safeCheck('style', () => checkStyle(diff, conventions, opts.config?.maxLineLength))));
  if (wantTemplate(opts)) findings.push(...await dur.run('template',
    () => safeCheckAsync('template', () => runTemplateChecks(opts.template!.template, diff, opts.root ?? ''))));

  return await finalize(change, diff, coverage, findings, opts, dur.record);
}

/**
 * Blended review: heuristic keyword score per requirement, rescored by the LLM,
 * combined as `weight * llm + (1 - weight) * heuristic`, then re-thresholded
 * with the same cutoffs (>=0.30 covered, >=0.12 partial).
 * Fail-open: an unreachable provider keeps the heuristic score (info finding in
 * auto mode, blocker in require mode).
 */
export async function runReviewAsync(
  change: OpenSpecChange,
  diff: Diff,
  conventions: string,
  opts: ReviewOptions,
  llm?: LLMBlendOptions
): Promise<ReviewResult> {
  if (!llm || llm.mode === 'off' || llm.provider.name === 'off') {
    return runReview(change, diff, conventions, opts);
  }
  const findings: Finding[] = [];
  let coverage: ReviewResult['requirementCoverage'] = [];
  const dur = new Durations(Boolean(opts.timing));
  const lens = opts.template?.template.lens || undefined;

  const want = (c: string) => opts.categories.has('all') || opts.categories.has(c);

  if (diff.files.length === 0 && want('spec-compliance')) {
    findings.push({
      severity: 'high',
      category: 'spec-compliance',
      checkId: 'empty-diff',
      message: `Diff is empty${opts.base ? ` for base \`${opts.base}\`` : ''} — nothing to review.`,
      suggestion: 'Check --base (and commit or stage your changes); an empty range falls back to the working tree.'
    });
  }

  // Gap analysis mode: line-level requirement-gap findings → inline comments
  if (llm.mode === 'gap' && want('spec-compliance')) {
    if (change.requirements.length === 0) {
      findings.push({
        severity: 'medium',
        category: 'spec-compliance',
        checkId: 'gap-no-delta-specs',
        message: 'Gap analysis requires delta specs (--llm gap needs a change with specs).',
        suggestion: 'Add specs to openspec/changes/<name>/specs/ or use --llm auto|require for rescoring.'
      });
    } else {
      const sem = new Semaphore(llm.maxConcurrency ?? 3);
      const maxRetries = llm.maxRetries ?? 2;
      let gapUnavailable = 0;

      async function gapWithRetry(req: Requirement) {
        const slice = buildDiffSlice(req, diff);
        return withRetry(
          () => llm!.provider.analyzeGaps(req, slice, { lens }),
          maxRetries
        ).catch(() => null);
      }

      const tasks = change.requirements.map(async (req) => {
        if (req.operation === 'REMOVED') return { req, gaps: [] as GapFinding[], unavailable: false };
        const release = await sem.acquire();
        try {
          const gaps = await gapWithRetry(req);
          if (gaps === null) return { req, gaps: [] as GapFinding[], unavailable: true };
          return { req, gaps, unavailable: false };
        } finally {
          release();
        }
      });

      const results = await dur.run('llm-gap', () => Promise.all(tasks));

      for (const { req, gaps, unavailable } of results) {
        if (unavailable && req.operation !== 'REMOVED') gapUnavailable++;
        if (!gaps || gaps.length === 0) continue;
        for (const g of gaps) {
          // Verify the gap anchors to an added line in the diff
          const file = diff.files.find((f) => f.path === g.file);
          const anchored = file?.addedLines.some((l) => l.n === g.line) ?? false;
          if (!anchored) continue; // skip unanchored gaps
          findings.push({
            severity: g.severity,
            category: 'spec-compliance',
            checkId: `gap-${req.id.replace(/\s+/g, '-').toLowerCase()}`,
            requirementId: req.id,
            file: g.file,
            line: g.line,
            message: g.message,
            suggestion: g.suggestion ?? `Gap in requirement "${req.id}": ${req.text.slice(0, 120)}`
          });
        }
      }

      if (gapUnavailable > 0) {
        findings.push({
          severity: 'blocker',
          category: 'spec-compliance',
          checkId: 'gap-required-unavailable',
          message: `LLM gap analysis required but the provider (${llm!.provider.name}) failed for ${gapUnavailable} requirement(s).`,
          suggestion: 'Check STITCHER_CODEREVIEW_LLM_* env / --llm-* flags, network access, and model name.'
        });
      }
      // In gap mode, skip coverage/rescore logic; findings are the primary output
    }
    } else if (want('spec-compliance')) {
      await dur.run('llm-rescore', async () => {
      let unavailable = 0;
      const blended: ReviewResult['requirementCoverage'] = [];
      // Batched LLM rescoring with concurrency control + retry
      const sem = new Semaphore(llm!.maxConcurrency ?? 3);
      const maxRetries = llm!.maxRetries ?? 2;

      async function rescoreWithRetry(req: Requirement) {
        const slice = buildDiffSlice(req, diff);
        return withRetry(
          () => llm!.provider.rescore(req, slice, { lens }),
          maxRetries
        ).catch(() => null);
      }

      // Process requirements with concurrency limit
      const tasks = change.requirements.map(async (req) => {
        const { entry, score } = coverageForRequirement(req, diff, { coveredAt: opts.config?.coveredAt, partialAt: opts.config?.partialAt });
        if (req.operation === 'REMOVED') return { req, entry, score, r: null };
        const release = await sem.acquire();
        try {
          const r = await rescoreWithRetry(req);
          return { req, entry, score, r };
        } finally {
          release();
        }
      });

      const results = await Promise.all(tasks);

      for (const { req, entry, score, r } of results) {
        if (req.operation === 'REMOVED') {
          blended.push(entry); // removals stay heuristic-only
          continue;
        }
        if (!r) {
          unavailable++;
          blended.push(entry);
          continue;
        }
        const blendedScore = blendScores(score, r.score, llm!.weight);
        const status = statusForScore(blendedScore, opts.config?.coveredAt, opts.config?.partialAt);
        blended.push({
          ...entry,
          status,
          heuristicScore: score,
          llmScore: r.score,
          blendedScore,
          llmRationale: r.rationale
        });
        if (status !== entry.status) {
          findings.push({
            severity: 'info',
            category: 'spec-compliance',
            checkId: 'llm-rescore-moved',
            requirementId: req.id,
            message: `LLM rescore (${llm.provider.name}, weight ${llm.weight}) moved "${req.id}" ${entry.status} → ${status}: ${r.rationale || 'no rationale given'}`
          });
        }
      }
      coverage = blended;
      findings.push(...findingsForCoverage(change, coverage));
      findings.push(...checkDrift(change, diff));
      if (unavailable > 0 && llm.mode === 'require') {
        findings.push({
          severity: 'blocker',
          category: 'spec-compliance',
          checkId: 'llm-required-unavailable',
          message: `LLM rescore required but the provider (${llm.provider.name}) failed for ${unavailable} requirement(s); heuristic scores used instead.`,
          suggestion: 'Check STITCHER_CODEREVIEW_LLM_* env / --llm-* flags, network access, and model name.'
        });
      } else if (unavailable > 0) {
        findings.push({
          severity: 'info',
          category: 'spec-compliance',
          checkId: 'llm-unavailable-fallback',
          message: `LLM rescore unavailable for ${unavailable} requirement(s); heuristic scores used.`
        });
      }
      });
    }
  if (want('tasks')) findings.push(...dur.runSync('tasks', () => safeCheck('tasks', () => checkTasks(change, diff))));
  if (want('correctness')) findings.push(...dur.runSync('correctness', () => safeCheck('correctness', () => checkCorrectness(diff))));
  if (want('security')) findings.push(...dur.runSync('security', () => safeCheck('security', () => checkSecurity(diff))));
  if (want('tests')) findings.push(...dur.runSync('tests', () => safeCheck('tests', () => checkTests(change, diff, {
    testFileRes: opts.template?.template.testFileRes, testHint: opts.template?.template.testHint
  }))));
  if (want('style')) findings.push(...dur.runSync('style', () => safeCheck('style', () => checkStyle(diff, conventions, opts.config?.maxLineLength))));
  if (wantTemplate(opts)) findings.push(...await dur.run('template',
    () => safeCheckAsync('template', () => runTemplateChecks(opts.template!.template, diff, opts.root ?? ''))));

  return await finalize(change, diff, coverage, findings, opts, dur.record);
}
