import { loadBaseline } from './spec/loader.js';
import { getDiff } from './diff/git.js';
import { checkReverseDrift, type ReverseDriftOptions } from './checks/drift.js';
import { decideVerdict, toJson, toMarkdown } from './reporter.js';
import { toSarif } from './sarif.js';
import { attachEvidenceRefs } from './evidenceRef.js';
import type { Finding, ReviewResult, Severity } from './types.js';
import { decideSubjectVerdict, type VerdictRecord, type VerdictSubject } from './verdict.js';

const RANK = { blocker: 0, high: 1, medium: 2, low: 3, info: 4, never: 99 } as const;

/** Serialize a result in the requested format. */
export function formatResult(result: ReviewResult, format: string): string {
  if (format === 'json') return toJson(result);
  if (format === 'sarif') return toSarif(result);
  return toMarkdown(result);
}

/** Exit 1 when the worst finding meets the --fail-on threshold (same contract as the CLI). */
export function exitForFindings(findings: Finding[], failOn: string): never {
  if (failOn === 'never') process.exit(0);
  const threshold = RANK[failOn as keyof typeof RANK];
  if (threshold === undefined) {
    console.error(`stitcher-codereview: invalid --fail-on \"${failOn}\" (want blocker|high|medium|low|never).`);
    process.exit(2);
  }
  const worst = findings.length === 0 ? 99 : Math.min(...findings.map((f) => RANK[f.severity]));
  process.exit(worst <= threshold ? 1 : 0);
}

export interface DriftOnlyOptions {
  root: string;
  base: string;
  change?: string;
  /** Severity declared by the bundle for an uncovered behavior change. */
  severity?: Severity;
  maxFindings?: number;
}

/** Reverse-drift gate mode (Stage 3): behavior changed with no spec update. */
export async function driftOnlyFindings(opts: DriftOnlyOptions): Promise<Finding[]> {
  const baseline = await loadBaseline(opts.root);
  const diff = await getDiff(opts.root, opts.base);
  const driftOpts: ReverseDriftOptions = {
    severity: (opts.severity as ReverseDriftOptions['severity']) ?? 'medium',
    maxFindings: opts.maxFindings
  };
  return attachEvidenceRefs(opts.change ?? 'reverse-drift', checkReverseDrift(baseline, diff, driftOpts));
}

export function driftOnlyResult(findings: Finding[], change: string): ReviewResult {
  return {
    change,
    verdict: decideVerdict(findings),
    summary:
      findings.length === 0
        ? 'No reverse drift detected: every changed behavior file has a spec update in range.'
        : `${findings.length} reverse-drift finding(s): behavior changed without a spec update.`,
    template: { id: 'drift', label: 'Reverse drift', reason: '--drift-only gate mode' },
    requirementCoverage: [],
    findings,
    stats: { filesChanged: 0, linesAdded: 0, requirementsTotal: 0, requirementsCovered: 0 }
  };
}

/** Agent-loop verdict endpoint (Stage 9): promote/halt keyed to a subject digest. */
export function verdictRecord(subject: VerdictSubject, result: ReviewResult): VerdictRecord {
  return decideSubjectVerdict(result, subject);
}
