import { describe, expect, it } from 'vitest';
import { decideSubjectVerdict, subjectDigestOf } from '../src/verdict.js';
import { verdictRecord } from '../src/modes.js';
import { attachEvidenceRefs } from '../src/evidenceRef.js';
import { executablePass } from './helpers.js';
import type { ReviewResult } from '../src/types.js';

const DIGEST = 'b'.repeat(64);

function passWithEvidence(): ReviewResult {
  return executablePass({
    findings: attachEvidenceRefs('fixture-change', [
      { severity: 'info', category: 'tasks', checkId: 'task-progress', message: 'progress' }
    ])
  });
}

describe('Fixture H - a loop self-certification is treated as unverified', () => {
  it('halts when a loop presents its own prior output as verified input', () => {
    const record = decideSubjectVerdict(passWithEvidence(), {
      subjectDigest: DIGEST,
      producer: 'claude-code-loop',
      priorLoopOutputs: [DIGEST],
      claimedStatus: 'VERIFIED'
    });
    expect(record.verdict).toBe('halt');
    expect(record.verification).toBe('UNKNOWN');
    expect(record.reasons).toContain('loop-self-certification');
  });

  it('keys on the digest: a different digest from the same loop is judged on its own evidence', () => {
    const record = decideSubjectVerdict(passWithEvidence(), {
      subjectDigest: DIGEST,
      producer: 'claude-code-loop',
      priorLoopOutputs: ['c'.repeat(64)]
    });
    expect(record.verdict).toBe('promote');
    expect(record.verification).toBe('TESTED');
  });

  it('an independent observer of the same subject promotes', () => {
    const record = verdictRecord(
      { subjectDigest: DIGEST, producer: 'ci-gate' },
      passWithEvidence()
    );
    expect(record.verdict).toBe('promote');
    expect(record.reviewVerdict).toBe('PASS');
    expect(record.evidenceRefs.length).toBeGreaterThan(0);
  });

  it('halts on a missing/invalid subject digest', () => {
    const record = decideSubjectVerdict(passWithEvidence(), { subjectDigest: 'not-a-digest' });
    expect(record.verdict).toBe('halt');
    expect(record.reasons).toContain('missing-or-invalid-subject-digest');
  });

  it('halts on CHANGES_REQUESTED and on an unobserved (heuristic) subject', () => {
    const changes = decideSubjectVerdict(executablePass({ verdict: 'CHANGES_REQUESTED' }), { subjectDigest: DIGEST });
    expect(changes.verdict).toBe('halt');
    expect(changes.reasons).toContain('review-changes-requested');

    const heuristic = executablePass({ verification: undefined });
    const unverified = decideSubjectVerdict(heuristic, { subjectDigest: DIGEST });
    expect(unverified.verdict).toBe('halt');
    expect(unverified.reasons.join(' ')).toContain('unverified-subject');
  });

  it('subjectDigestOf falls back from touchedHash to head', () => {
    expect(subjectDigestOf(executablePass())).toBe('b'.repeat(64));
  });
});
