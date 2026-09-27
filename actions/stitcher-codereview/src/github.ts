import { readFileSync, statSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Diff, Finding, ReviewResult } from './types.js';
import { VcsProvider, MrContext, InlineComment, PostOptions, VcsRunner, ghRunner, decodeMarker } from './vcs.js';

export class GitHubProvider implements VcsProvider {
  readonly name = 'github' as const;

  detectContext(env: NodeJS.ProcessEnv, readEvent?: (p: string) => string | null): MrContext | null {
    const repo = env.GITHUB_REPOSITORY;
    if (!repo || !repo.includes('/')) return null;
    const [owner, repoName] = repo.split('/');
    if (!owner || !repoName) return null;

    let mrNumber: number | undefined;
    let headSha: string | undefined;

    const eventPath = env.GITHUB_EVENT_PATH;
    if (eventPath) {
      let raw: string | null = null;
      try {
        // Cap event payload reads: GITHUB_EVENT_PATH is env-controlled and
        // read synchronously, so refuse absurd sizes instead of OOMing.
        if (!readEvent) {
          const st = statSync(eventPath, { throwIfNoEntry: false });
          if (st && st.size > 1024 * 1024) return null;
        }
        // Default to reading the payload from disk so local runs simulating a
        // PR event (GITHUB_EVENT_PATH set) work without injecting readEvent.
        raw = readEvent ? readEvent(eventPath) : readFileSync(eventPath, 'utf8');
      } catch {
        raw = null;
      }
      if (raw) {
        try {
          const payload = JSON.parse(raw) as {
            pull_request?: { number?: number; head?: { sha?: string } };
          };
          mrNumber = payload.pull_request?.number;
          headSha = payload.pull_request?.head?.sha;
        } catch {
          /* malformed payload — fall through to GITHUB_REF */
        }
      }
    }
    if (!mrNumber) {
      const m = /^refs\/pull\/(\d+)(\/merge)?$/.exec(env.GITHUB_REF ?? '');
      if (m) mrNumber = Number(m[1]);
    }
    if (!mrNumber) return null;
    return { provider: 'github', owner, repo: repoName, mrNumber, headSha: headSha ?? env.GITHUB_SHA };
  }

  /** Cached authenticated login (null = lookup failed → fail-open mode). */
  private viewerCache: string | null | undefined;

  /** Resolve the authenticated account so dedup markers are only trusted from our own comments. */
  private async viewer(run: VcsRunner): Promise<string | null> {
    if (this.viewerCache !== undefined) return this.viewerCache;
    try {
      const out = await run(['user', '--jq', '.login']);
      this.viewerCache = out.trim() || null;
    } catch {
      this.viewerCache = null;
    }
    return this.viewerCache;
  }

  async listPostedKeys(ctx: MrContext, run: VcsRunner): Promise<string[]> {
    try {
      // Identity-scoped dedup (audit F9): a forged marker in someone else's
      // comment must not suppress our findings, so only bodies authored by the
      // authenticated account are decoded. Without a resolvable identity we
      // fail open to legacy behavior (accept all) and warn.
      const viewer = await this.viewer(run);
      if (!viewer) {
        console.error('stitcher-codereview: warning: could not resolve authenticated GitHub login; accepting dedup markers from all comment authors (forgeable — audit F9).');
      }
      const out = await run([
        '--paginate',
        `repos/${ctx.owner}/${ctx.repo}/pulls/${ctx.mrNumber}/comments`,
        '--jq',
        viewer ? '.[] | {b: .body, u: .user.login}' : '.[].body'
      ]);
      const keys = new Set<string>();
      if (viewer) {
        for (const line of out.split('\n')) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const o = JSON.parse(trimmed) as { b?: unknown; u?: unknown };
            if (o.u !== viewer || typeof o.b !== 'string') continue;
            for (const k of decodeMarker(o.b)) keys.add(k);
          } catch {
            /* non-JSON line — ignore */
          }
        }
      } else {
        for (const body of out.split('\n')) {
          for (const k of decodeMarker(body)) keys.add(k);
        }
      }
      return [...keys];
    } catch {
      return [];
    }
  }

  async postReview(ctx: MrContext, opts: PostOptions): Promise<{ reviewId?: string }> {
    const run = opts.run ?? ghRunner();
    const payload: Record<string, unknown> = {
      body: opts.body,
      event: 'COMMENT',
      comments: opts.comments
    };
    if (opts.commitId) payload.commit_id = opts.commitId;
    const dir = await mkdtemp(join(tmpdir(), 'stitcher-'));
    try {
      const payloadFile = join(dir, 'review.json');
      await writeFile(payloadFile, JSON.stringify(payload));
      await run([`repos/${ctx.owner}/${ctx.repo}/pulls/${ctx.mrNumber}/reviews`, '--method', 'POST', '--input', payloadFile]);
      return {};
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }

  async postIssueComment(ctx: MrContext, body: string, run?: VcsRunner): Promise<void> {
    const gh = run ?? ghRunner();
    const dir = await mkdtemp(join(tmpdir(), 'stitcher-'));
    try {
      const bodyFile = join(dir, 'comment.json');
      await writeFile(bodyFile, JSON.stringify({ body }));
      await gh([`repos/${ctx.owner}/${ctx.repo}/issues/${ctx.mrNumber}/comments`, '--method', 'POST', '--input', bodyFile]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }
}

/** Re-export shared utilities from vcs.ts */
export {
  MrContext,
  InlineComment,
  PostOptions,
  VcsRunner,
  MARKER_PREFIX,
  encodeMarker,
  decodeMarker,
  findingKey,
  buildReviewBody,
  partitionInline,
  ghRunner
} from './vcs.js';