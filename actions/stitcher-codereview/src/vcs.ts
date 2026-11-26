import { execFile } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Diff, Finding, ReviewResult } from './types.js';
import { bodyHasEvidenceLink, isEvidenceRef } from './evidenceRef.js';

/** Generic PR/MR context parsed from CI env. */
export interface MrContext {
  /** Provider: 'github' | 'gitlab' */
  provider: 'github' | 'gitlab';
  /** Owner/namespace (GitHub owner, GitLab group/user) */
  owner: string;
  /** Repository name */
  repo: string;
  /** PR/MR number */
  mrNumber: number;
  /** Head commit SHA */
  headSha?: string;
  /** Base commit SHA (for GitLab) */
  baseSha?: string;
  /** Project ID (GitLab numeric ID) */
  projectId?: number;
}

/** One inline thread posted via the VCS reviews API. */
export interface InlineComment {
  path: string;
  line: number;
  side: 'RIGHT';
  body: string;
}

/** Options for posting a review with inline comments. */
export interface PostOptions {
  body: string;
  comments: InlineComment[];
  commitId?: string;
  run?: VcsRunner;
}

/** Runner for VCS API calls (shelling to gh/glab or direct HTTP). */
export type VcsRunner = (args: string[]) => Promise<string>;

/** Marker embedded in each inline-comment body for de-dup. */
export const MARKER_PREFIX = 'stitch-t:';

export function encodeMarker(key: string): string {
  return `<!-- ${MARKER_PREFIX}${Buffer.from(key).toString('base64url')} -->`;
}

export function decodeMarker(body: string): string[] {
  const re = new RegExp(`<!--\\s*${MARKER_PREFIX}([A-Za-z0-9_-]+)\\s*-->`, 'g');
  const keys: string[] = [];
  for (const m of body.matchAll(re)) {
    try {
      keys.push(Buffer.from(m[1], 'base64url').toString('utf8'));
    } catch {
      /* unreadable marker — ignore */
    }
  }
  return keys;
}

/** Stable identity for a finding: check id + path + line. */
export function findingKey(f: Finding): string {
  return `${f.checkId}\u0000${f.file ?? ''}\u0000${f.line ?? 0}`;
}

/**
 * Strip HTML comments from finding-derived text before embedding it in an
 * inline body. Finding text can originate from untrusted sources (LLM gap
 * messages, custom template DSL); without this, a crafted message containing
 * `<!-- stitch-t:... -->` would forge a dedup marker and suppress findings.
 */
export function sanitizeInlineText(s: string): string {
  return s.replace(/<!--[\s\S]*?-->/g, '').replace(/<!--[\s\S]*$/g, '');
}

/**
 * Abstract VCS provider interface.
 * Implementations handle provider-specific API calls.
 */
export interface VcsProvider {
  /** Provider name for logging/debugging. */
  readonly name: 'github' | 'gitlab';

  /** Detect PR/MR context from CI environment variables. */
  detectContext(env: NodeJS.ProcessEnv, readEvent?: (p: string) => string | null): MrContext | null;

  /** List already-posted marker keys from existing comments on the MR/PR. */
  listPostedKeys(ctx: MrContext, run: VcsRunner): Promise<string[]>;

  /** Post a review with inline threads + walkthrough body. */
  postReview(ctx: MrContext, opts: PostOptions): Promise<{ reviewId?: string }>;

  /** Post a single body comment (fallback when no inline anchors). */
  postIssueComment(ctx: MrContext, body: string, run?: VcsRunner): Promise<void>;
}

/**
 * Raised when a provider is asked to post a comment that carries no evidence
 * link. The requirement is a refusal, not a warning: "A comment without an
 * evidence link SHALL NOT be posted" (reviewer-surfaces spec).
 */
export class MissingEvidenceError extends Error {
  constructor(keys: string[]) {
    super(
      `refusing to post ${keys.length} review comment(s) without an evidence link ` +
        `(${keys.slice(0, 3).join(', ')}); each comment must reference a coh-ev-* record`
    );
    this.name = 'MissingEvidenceError';
  }
}

/** Enforce the refusal at the provider boundary, before any API call. */
export function assertEvidenceLinked(comments: InlineComment[]): void {
  const unlinked = comments.filter((c) => !bodyHasEvidenceLink(c.body)).map((c) => `${c.path}:${c.line}`);
  if (unlinked.length > 0) throw new MissingEvidenceError(unlinked);
}

/** Render the evidence link appended to an inline comment. */
export function evidenceLink(f: Finding, baseUrl?: string): string | null {
  if (!isEvidenceRef(f.evidenceRef)) return null;
  const ref = f.evidenceRef;
  if (!baseUrl) return `\n\nEvidence: \`${ref}\``;
  return `\n\nEvidence: [${ref}](${baseUrl.replace(/\/+$/, '')}/${ref})`;
}

/**
 * Build a walkthrough body: verdict + stats + body-only findings + stale count.
 */
export function buildReviewBody(result: ReviewResult, bodyOnly: Finding[], staleCount: number): string {
  const icon = result.verdict === 'PASS' ? '✅' : '🔁';
  const lines: string[] = [`## ${icon} stitcher-codereview: ${result.verdict} — \`${result.change}\``, ''];
  lines.push(result.summary);
  lines.push('');
  lines.push(
    `**Stats:** ${result.stats.filesChanged} files, +${result.stats.linesAdded} lines, ` +
      `${result.stats.requirementsCovered}/${result.stats.requirementsTotal} requirements covered.`
  );
  if (staleCount > 0) lines.push(`\n_Resolved since last review: ${staleCount} inline finding(s) no longer present._`);
  if (bodyOnly.length > 0) {
    lines.push('', '### No inline anchor', '');
    for (const f of bodyOnly) {
      const loc = f.file ? ` \`${f.file}${f.line ? ':' + f.line : ''}\`` : '';
      const req = f.requirementId ? ` [req: ${f.requirementId}]` : '';
      lines.push(`- **[${f.category}]**${req} ${f.message}${loc}`);
      if (f.suggestion) lines.push(`  - 💡 ${f.suggestion}`);
      if (isEvidenceRef(f.evidenceRef)) lines.push(`  - Evidence: \`${f.evidenceRef}\``);
    }
  }
  return lines.join('\n');
}

/**
 * Map findings onto inline threads (new-file lines only, RIGHT side) vs. the
 * body-only remainder. A finding with a `line` that is not an added line in
 * the diff (e.g. a removed line) cannot anchor an inline comment.
 */
export function partitionInline(result: ReviewResult, diff: Diff, opts: { evidenceBaseUrl?: string } = {}): {
  comments: InlineComment[];
  bodyOnly: Finding[];
  /** Findings deliberately not posted because they carry no evidence link. */
  unlinked: Finding[];
} {
  const addedByPath = new Map<string, Set<number>>();
  for (const f of diff.files) {
    addedByPath.set(f.path, new Set(f.addedLines.map((l) => l.n)));
  }
  const comments: InlineComment[] = [];
  const bodyOnly: Finding[] = [];
  const unlinked: Finding[] = [];
  const seen = new Set<string>();
  for (const f of result.findings) {
    const link = evidenceLink(f, opts.evidenceBaseUrl);
    if (!link) {
      // No evidence record, no comment: the finding stays in the machine
      // output but is never posted to a forge surface.
      unlinked.push(f);
      continue;
    }
    const anchorable = f.file !== undefined && f.line !== undefined && addedByPath.get(f.file)?.has(f.line) === true;
    if (!anchorable) {
      bodyOnly.push(f);
      continue;
    }
    const key = findingKey(f);
    if (seen.has(key)) continue;
    seen.add(key);
    comments.push({
      path: f.file!,
      line: f.line!,
      side: 'RIGHT',
      body:
        `${encodeMarker(key)}\n**${f.severity}** ${sanitizeInlineText(f.message)}` +
        `${f.requirementId ? ` — [req: ${sanitizeInlineText(f.requirementId)}]` : ''}` +
        `${f.suggestion ? `\n\n💡 ${sanitizeInlineText(f.suggestion)}` : ''}` +
        link
    });
  }
  return { comments, bodyOnly, unlinked };
}

/** Default runner using `gh` CLI (GitHub). */
export function ghRunner(token?: string): VcsRunner {
  return async (args) => {
    const { execFile } = await import('node:child_process');
    const { promisify } = await import('node:util');
    const execFileP = promisify(execFile);
    const baseUrl = process.env.GITHUB_API_URL ?? process.env.GH_HOST;
    void baseUrl; // gh CLI reads GH_HOST/GITHUB_API_URL from env automatically
    let lastErr: unknown;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { stdout } = await execFileP('gh', ['api', ...args], {
          maxBuffer: 16 * 1024 * 1024,
          timeout: 30_000,
          env: token ? { ...process.env, GH_TOKEN: token } : process.env
        });
        return stdout;
      } catch (err) {
        lastErr = err;
        if (attempt < 2) await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
      }
    }
    throw lastErr;
  };
}

/** Default runner using `glab` CLI (GitLab). */
export function glabRunner(token?: string): VcsRunner {
  return async (args) => {
    const { execFile } = await import('node:child_process');
    const { promisify } = await import('node:util');
    const execFileP = promisify(execFile);
    let lastErr: unknown;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { stdout } = await execFileP('glab', ['api', ...args], {
          maxBuffer: 16 * 1024 * 1024,
          timeout: 30_000,
          env: token ? { ...process.env, GITLAB_TOKEN: token, GLAB_TOKEN: token } : process.env
        });
        return stdout;
      } catch (err) {
        lastErr = err;
        if (attempt < 2) await new Promise((r) => setTimeout(r, 500 * 2 ** attempt));
      }
    }
    throw lastErr;
  };
}

/** Unified token lookup (single source of truth). */
export function vcsToken(provider: 'github' | 'gitlab', env: NodeJS.ProcessEnv = process.env): string | undefined {
  return provider === 'github' ? (env.GITHUB_TOKEN ?? env.GH_TOKEN) : (env.GITLAB_TOKEN ?? env.GLAB_TOKEN);
}

/**
 * Detect which VCS provider to use based on CI environment.
 * Returns 'github' | 'gitlab' | null.
 */
export function detectVcsProvider(env: NodeJS.ProcessEnv): 'github' | 'gitlab' | null {
  if (env.GITHUB_REPOSITORY || env.GITHUB_EVENT_PATH || env.GITHUB_REF?.startsWith('refs/pull/')) {
    return 'github';
  }
  if (env.CI_PROJECT_ID || env.CI_MERGE_REQUEST_IID || env.GITLAB_CI || env.CI_SERVER_NAME === 'GitLab') {
    return 'gitlab';
  }
  return null;
}

/**
 * Get the appropriate VcsProvider instance for the detected provider.
 */
export async function getVcsProvider(provider: 'github' | 'gitlab'): Promise<VcsProvider> {
  if (provider === 'github') {
    const { GitHubProvider } = await import('./github.js');
    return new GitHubProvider();
  } else {
    const { GitLabProvider } = await import('./gitlab.js');
    return new GitLabProvider();
  }
}