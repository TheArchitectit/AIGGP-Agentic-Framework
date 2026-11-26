import { createHash } from 'node:crypto';
import type { Finding, ReviewResult } from './types.js';

/** Prefix DevGate's coherence evidence records use (`coh-ev-*`). */
export const EVIDENCE_REF_PREFIX = 'coh-ev-';

const REF_RE = new RegExp(`^${EVIDENCE_REF_PREFIX}[0-9a-f]{16}$`);
const LINK_RE = new RegExp(`\\b${EVIDENCE_REF_PREFIX}[0-9a-f]{16}\\b`);

/** Deterministic reference for a set of evidence parts (order-sensitive). */
export function evidenceRefFor(parts: readonly string[]): string {
  const digest = createHash('sha256').update(parts.join('\n'), 'utf8').digest('hex');
  return `${EVIDENCE_REF_PREFIX}${digest.slice(0, 16)}`;
}

export function isEvidenceRef(value: unknown): value is string {
  return typeof value === 'string' && REF_RE.test(value);
}

/** True when a rendered comment body carries at least one evidence reference. */
export function bodyHasEvidenceLink(body: string): boolean {
  return LINK_RE.test(body);
}

type CoverageEntry = ReviewResult['requirementCoverage'][number];

/** Evidence reference for one requirement verdict. */
export function coverageEvidenceRef(changeName: string, entry: CoverageEntry): string {
  const locations = entry.locations
    .map((l) => `${l.file}:${l.startLine}-${l.endLine}`)
    .sort()
    .join(',');
  return evidenceRefFor([
    'requirement',
    changeName,
    entry.requirementId,
    entry.capability,
    entry.operation,
    entry.status,
    locations
  ]);
}

/**
 * Evidence reference for one finding. External findings keep the reference the
 * adapter derived from the raw output digest; everything else is keyed to the
 * change and the finding's identity so the same review always cites the same
 * record.
 */
export function findingEvidenceRef(changeName: string, f: Finding): string {
  if (isEvidenceRef(f.evidenceRef)) return f.evidenceRef;
  return evidenceRefFor([
    'finding',
    changeName,
    f.category,
    f.checkId,
    f.requirementId ?? '',
    f.file ?? '',
    String(f.line ?? 0),
    f.message
  ]);
}

/** Attach a reference to every finding that does not already carry one. */
export function attachEvidenceRefs(changeName: string, findings: Finding[]): Finding[] {
  return findings.map((f) =>
    isEvidenceRef(f.evidenceRef) ? f : { ...f, evidenceRef: findingEvidenceRef(changeName, f) }
  );
}

/** Attach a reference to every coverage entry. */
export function attachCoverageRefs(
  changeName: string,
  coverage: CoverageEntry[]
): CoverageEntry[] {
  return coverage.map((entry) =>
    isEvidenceRef(entry.evidenceRef)
      ? entry
      : { ...entry, evidenceRef: coverageEvidenceRef(changeName, entry) }
  );
}
