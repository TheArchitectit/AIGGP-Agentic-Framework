import type { ReviewResult, Verdict } from './types.js';
import { statusForReview, type VerificationStatus } from './evidence.js';
import { isEvidenceRef } from './evidenceRef.js';

/** Promote/halt contract consumed by coding-agent loops (Stage 9). */
export type AgentDecision = 'promote' | 'halt';

export interface VerdictSubject {
  /** Digest of the exact subject being judged (commit/tree/finding-set digest). */
  subjectDigest: string;
  /** Who produced the subject, e.g. `claude-code-loop` or `ci-gate`. */
  producer?: string;
  /** Digests this producer emitted earlier; loop output re-enters as unverified. */
  priorLoopOutputs?: string[];
  /** Status the subject claims for itself; never trusted without observation. */
  claimedStatus?: VerificationStatus;
}

export interface VerdictRecord {
  verdict: AgentDecision;
  subjectDigest: string;
  reviewVerdict: Verdict;
  /** Honest status after re-entry rules; a self-certified loop is UNKNOWN. */
  verification: VerificationStatus;
  reasons: string[];
  evidenceRefs: string[];
}

const DIGEST_RE = /^[0-9a-f]{8,64}$/i;

function isLoopProducer(producer: string | undefined): boolean {
  return Boolean(producer && /(?:loop|agent|assistant|claude|codex)/i.test(producer));
}

/**
 * Decide promote/halt for one subject.
 *
 * Rules, in order:
 *  1. no valid subject digest -> halt (the verdict has nothing to key to);
 *  2. a loop re-presenting its own prior output as verified input -> halt,
 *     status UNKNOWN (loop self-certification is not verification);
 *  3. a CHANGES_REQUESTED review -> halt;
 *  4. a subject the reviewer could not observe (ATTEMPTED/BLOCKED/FAILED/
 *     UNKNOWN) -> halt as unverified;
 *  5. otherwise promote, citing the findings' evidence records.
 */
export function decideSubjectVerdict(result: ReviewResult, subject: VerdictSubject): VerdictRecord {
  const observed = statusForReview(result);
  const evidenceRefs = [...new Set(
    [...result.findings.map((f) => f.evidenceRef), ...result.requirementCoverage.map((c) => c.evidenceRef)]
      .filter((r): r is string => isEvidenceRef(r))
  )].sort();

  if (!DIGEST_RE.test(subject.subjectDigest ?? '')) {
    return {
      verdict: 'halt',
      subjectDigest: subject.subjectDigest ?? '',
      reviewVerdict: result.verdict,
      verification: 'UNKNOWN',
      reasons: ['missing-or-invalid-subject-digest'],
      evidenceRefs
    };
  }

  const selfCertified =
    isLoopProducer(subject.producer) &&
    (subject.priorLoopOutputs ?? []).some((d) => d.toLowerCase() === subject.subjectDigest.toLowerCase());
  if (selfCertified) {
    return {
      verdict: 'halt',
      subjectDigest: subject.subjectDigest,
      reviewVerdict: result.verdict,
      verification: 'UNKNOWN',
      reasons: [
        'loop-self-certification',
        `producer \"${subject.producer}\" presented its own prior output as verified input; re-entered as an unverified subject`
      ],
      evidenceRefs
    };
  }

  if (result.verdict === 'CHANGES_REQUESTED') {
    return {
      verdict: 'halt',
      subjectDigest: subject.subjectDigest,
      reviewVerdict: result.verdict,
      verification: observed,
      reasons: ['review-changes-requested'],
      evidenceRefs
    };
  }

  const promotable: VerificationStatus[] = ['TESTED', 'VERIFIED'];
  if (!promotable.includes(observed)) {
    return {
      verdict: 'halt',
      subjectDigest: subject.subjectDigest,
      reviewVerdict: result.verdict,
      verification: observed,
      reasons: [`unverified-subject:${observed}`],
      evidenceRefs
    };
  }

  return {
    verdict: 'promote',
    subjectDigest: subject.subjectDigest,
    reviewVerdict: result.verdict,
    verification: observed,
    reasons: [`observed:${observed}`],
    evidenceRefs
  };
}

/** Digest a review result's own subject (tree fingerprint when present). */
export function subjectDigestOf(result: ReviewResult): string {
  const fp = result.verification?.fingerprint;
  if (fp?.touchedHash) return fp.touchedHash;
  if (fp?.head) return fp.head;
  return '';
}
