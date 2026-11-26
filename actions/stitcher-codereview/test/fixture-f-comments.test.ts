import { describe, expect, it } from 'vitest';
import { GitHubProvider } from '../src/github.js';
import { GitLabProvider } from '../src/gitlab.js';
import { MissingEvidenceError, assertEvidenceLinked, partitionInline } from '../src/vcs.js';
import { attachEvidenceRefs } from '../src/evidenceRef.js';
import type { MrContext } from '../src/vcs.js';
import type { ReviewResult } from '../src/types.js';
import { diffFile, executablePass, makeDiff } from './helpers.js';

const GH: MrContext = { provider: 'github', owner: 'org', repo: 'repo', mrNumber: 7, headSha: 'a'.repeat(40) };
const GL: MrContext = { provider: 'gitlab', owner: 'group', repo: 'repo', mrNumber: 8, headSha: 'b'.repeat(40), projectId: 42 };

function reviewWith(linked: boolean): ReviewResult {
  const findings = attachEvidenceRefs('fixture-change', [
    { severity: 'high', category: 'spec-compliance', checkId: 'requirement-missing', file: 'src/billing/refund.ts', line: 1, message: 'no evidence' }
  ]);
  if (!linked) findings[0] = { ...findings[0], evidenceRef: undefined };
  return executablePass({ verdict: 'CHANGES_REQUESTED', findings });
}

describe('Fixture F - a comment without an evidence link is refused', () => {
  it('partitionInline never emits an unlinked comment; it reports it separately', () => {
    const diff = makeDiff([diffFile('src/billing/refund.ts', ['const refund = 1;'])]);
    const unlinked = partitionInline(reviewWith(false), diff);
    expect(unlinked.comments).toHaveLength(0);
    expect(unlinked.unlinked).toHaveLength(1);

    const linked = partitionInline(reviewWith(true), diff);
    expect(linked.comments).toHaveLength(1);
    expect(linked.comments[0].body).toContain('coh-ev-');
    expect(linked.comments[0].body).toContain('Evidence:');
  });

  it('assertEvidenceLinked refuses a body with no reference', () => {
    expect(() => assertEvidenceLinked([{ path: 'a.ts', line: 1, side: 'RIGHT', body: '**high** finding' }]))
      .toThrow(MissingEvidenceError);
    expect(() => assertEvidenceLinked([{ path: 'a.ts', line: 1, side: 'RIGHT', body: 'see `coh-ev-0123456789abcdef`' }]))
      .not.toThrow();
  });

  it('GitHub refuses before touching the API', async () => {
    let called = 0;
    const provider = new GitHubProvider();
    const run = async () => {
      called++;
      return '';
    };
    await expect(
      provider.postReview(GH, { body: 'summary', comments: [{ path: 'a.ts', line: 1, side: 'RIGHT', body: 'no link' }], run })
    ).rejects.toBeInstanceOf(MissingEvidenceError);
    expect(called).toBe(0);
  });

  it('GitLab refuses before touching the API', async () => {
    let called = 0;
    const provider = new GitLabProvider();
    const run = async () => {
      called++;
      return '';
    };
    await expect(
      provider.postReview(GL, { body: 'summary', comments: [{ path: 'a.ts', line: 1, side: 'RIGHT', body: 'no link' }], run })
    ).rejects.toBeInstanceOf(MissingEvidenceError);
    expect(called).toBe(0);
  });

  it('a linked comment is posted (positive control)', async () => {
    const calls: string[][] = [];
    const run = async (args: string[]) => {
      calls.push(args);
      if (args.some((a) => a.includes('.diff_refs'))) {
        return JSON.stringify({ base_sha: 'c'.repeat(40), head_sha: 'b'.repeat(40), start_sha: 'c'.repeat(40) });
      }
      return '';
    };
    const provider = new GitHubProvider();
    await provider.postReview(GH, {
      body: 'summary',
      comments: [{ path: 'a.ts', line: 1, side: 'RIGHT', body: 'finding\n\nEvidence: `coh-ev-0123456789abcdef`' }],
      run
    });
    expect(calls.length).toBe(1);
    expect(calls[0][0]).toContain('/pulls/7/reviews');
  });
});
