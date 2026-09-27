import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { Diff, Finding, ReviewResult } from './types.js';
import { VcsProvider, MrContext, InlineComment, PostOptions, VcsRunner, glabRunner, decodeMarker } from './vcs.js';

export class GitLabProvider implements VcsProvider {
  readonly name = 'gitlab' as const;

  detectContext(env: NodeJS.ProcessEnv, _readEvent?: (p: string) => string | null): MrContext | null {
    const projectId = env.CI_PROJECT_ID;
    const mrIid = env.CI_MERGE_REQUEST_IID;
    const mrProjectUrl = env.CI_MERGE_REQUEST_PROJECT_URL;
    const commitSha = env.CI_COMMIT_SHA;
    const mrTitle = env.CI_MERGE_REQUEST_TITLE;
    const mrSourceBranch = env.CI_MERGE_REQUEST_SOURCE_BRANCH_NAME;
    const mrTargetBranch = env.CI_MERGE_REQUEST_TARGET_BRANCH_NAME;

    if (!projectId || !mrIid) return null;

    let owner = '';
    let repo = '';
    if (mrProjectUrl) {
      try {
        const url = new URL(mrProjectUrl);
        const pathParts = url.pathname.split('/').filter(Boolean);
        if (pathParts.length >= 2) {
          owner = pathParts.slice(0, -1).join('/');
          repo = pathParts[pathParts.length - 1];
        } else if (pathParts.length === 1) {
          repo = pathParts[0];
        }
      } catch {
        // fallback
      }
    }
    if (!owner) owner = env.CI_PROJECT_NAMESPACE ?? '';
    if (!repo) repo = env.CI_PROJECT_NAME ?? '';

    const mrNumber = Number(mrIid);
    const headSha = commitSha;

    return {
      provider: 'gitlab',
      owner,
      repo,
      mrNumber,
      headSha,
      projectId: Number(projectId)
    };
  }

  /** Cached authenticated username (null = lookup failed → fail-open mode). */
  private viewerCache: string | null | undefined;

  private async viewer(run: VcsRunner): Promise<string | null> {
    if (this.viewerCache !== undefined) return this.viewerCache;
    try {
      const out = await run(['user', '--jq', '.username']);
      this.viewerCache = out.trim() || null;
    } catch {
      this.viewerCache = null;
    }
    return this.viewerCache;
  }

  async listPostedKeys(ctx: MrContext, run: VcsRunner): Promise<string[]> {
    try {
      // Identity-scoped dedup (audit F9) — see GitHubProvider for rationale.
      const viewer = await this.viewer(run);
      if (!viewer) {
        console.error('stitcher-codereview: warning: could not resolve authenticated GitLab username; accepting dedup markers from all note authors (forgeable — audit F9).');
      }
      const projectId = await this.resolveProjectId(ctx, run);
      const out = await run([
        '--paginate',
        `projects/${projectId}/merge_requests/${ctx.mrNumber}/notes`,
        '--jq',
        viewer ? '.[] | {b: .body, u: .author.username}' : '.[].body'
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

  private projectIdCache: { mrNumber: number; projectId: number } | null = null;
  private diffRefsCache: { mrNumber: number; refs: { base_sha: string; head_sha: string; start_sha: string } } | null = null;

  private async resolveProjectId(ctx: MrContext, run: VcsRunner): Promise<number> {
    if (this.projectIdCache && this.projectIdCache.mrNumber === ctx.mrNumber) return this.projectIdCache.projectId;
    if (ctx.projectId) {
      this.projectIdCache = { mrNumber: ctx.mrNumber, projectId: ctx.projectId };
      return ctx.projectId;
    }
    const projectPath = `${ctx.owner}/${ctx.repo}`.replace(/^\//, '');
    const out = await run([`projects/${encodeURIComponent(projectPath)}`, '--jq', '.id']);
    this.projectIdCache = { mrNumber: ctx.mrNumber, projectId: Number(out.trim()) };
    return this.projectIdCache.projectId;
  }

  /**
   * Fetch the MR's diff_refs (base/head/start shas) — GitLab validates inline
   * note positions against these, so guessing (e.g. head for base) 400s.
   * Falls back to ctx values when the API call fails.
   */
  async resolveDiffRefs(ctx: MrContext, run: VcsRunner): Promise<{ base_sha: string; head_sha: string; start_sha: string }> {
    if (this.diffRefsCache && this.diffRefsCache.mrNumber === ctx.mrNumber) return this.diffRefsCache.refs;
    const fallback = {
      base_sha: ctx.baseSha ?? ctx.headSha ?? '',
      head_sha: ctx.headSha ?? '',
      start_sha: ctx.baseSha ?? ctx.headSha ?? ''
    };
    try {
      const projectId = await this.resolveProjectId(ctx, run);
      const out = await run([`projects/${projectId}/merge_requests/${ctx.mrNumber}`, '--jq', '.diff_refs']);
      const refs = JSON.parse(out) as { base_sha?: string; head_sha?: string; start_sha?: string };
      if (refs.base_sha && refs.head_sha && refs.start_sha) {
        this.diffRefsCache = { mrNumber: ctx.mrNumber, refs: { base_sha: refs.base_sha, head_sha: refs.head_sha, start_sha: refs.start_sha } };
        return this.diffRefsCache.refs;
      }
    } catch {
      /* fall through to ctx fallback */
    }
    return fallback;
  }

  async postReview(ctx: MrContext, opts: PostOptions): Promise<{ reviewId?: string }> {
    const run = opts.run ?? glabRunner();
    const projectId = await this.resolveProjectId(ctx, run);
    const dir = await mkdtemp(join(tmpdir(), 'stitcher-'));

    try {
      const summaryBody = `${opts.body}\n\n---\n*Posted by stitcher-codereview*`;
      const summaryFile = join(dir, 'summary.json');
      await writeFile(summaryFile, JSON.stringify({ body: summaryBody }));
      await run([
        `projects/${projectId}/merge_requests/${ctx.mrNumber}/notes`,
        '--method', 'POST',
        '--input', summaryFile
      ]);

      const diffRefs = opts.comments.length > 0 ? await this.resolveDiffRefs(ctx, run) : null;
      for (const [i, comment] of opts.comments.entries()) {
        const position = {
          position_type: 'text',
          new_path: comment.path,
          new_line: comment.line,
          base_sha: diffRefs!.base_sha,
          head_sha: diffRefs!.head_sha,
          start_sha: diffRefs!.start_sha
        };
        const noteBody = `${comment.body}\n\n---\n*Posted by stitcher-codereview*`;
        const noteFile = join(dir, `note-${i}-${comment.line}.json`);
        await writeFile(noteFile, JSON.stringify({ body: noteBody, position }));
        await run([
          `projects/${projectId}/merge_requests/${ctx.mrNumber}/notes`,
          '--method', 'POST',
          '--input', noteFile
        ]);
      }

      return {};
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }

  async postIssueComment(ctx: MrContext, body: string, run?: VcsRunner): Promise<void> {
    const glab = run ?? glabRunner();
    const projectId = await this.resolveProjectId(ctx, glab);
    const dir = await mkdtemp(join(tmpdir(), 'stitcher-'));

    try {
      const bodyWithFooter = `${body}\n\n---\n*Posted by stitcher-codereview*`;
      const bodyFile = join(dir, 'comment.json');
      await writeFile(bodyFile, JSON.stringify({ body: bodyWithFooter }));
      await glab([
        `projects/${projectId}/merge_requests/${ctx.mrNumber}/notes`,
        '--method', 'POST',
        '--input', bodyFile
      ]);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }
}

// Re-export shared utilities
export {
  decodeMarker,
  findingKey,
  buildReviewBody,
  partitionInline,
  glabRunner
} from './vcs.js';
