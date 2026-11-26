import { describe, expect, it } from 'vitest';
import { checkSpecCompliance } from '../src/checks/specCompliance.js';
import { decideVerdict } from '../src/reporter.js';
import { classifyStatus, statusForReview } from '../src/evidence.js';
import { isEvidenceRef } from '../src/evidenceRef.js';
import type { ReviewResult } from '../src/types.js';
import { diffFile, makeChange, makeDiff, requirement } from './helpers.js';

describe('Fixture B - an undeclared change is flagged and gets no clean verdict', () => {
  it('flags a change with no declared requirements at high severity', () => {
    const change = makeChange({ requirements: [] });
    const diff = makeDiff([diffFile('src/billing/refund.ts', ['export const refund = 1;'])]);
    const { findings, coverage } = checkSpecCompliance(change, diff);

    expect(coverage).toHaveLength(0);
    const flagged = findings.find((f) => f.checkId === 'no-delta-specs');
    expect(flagged).toBeDefined();
    expect(flagged?.severity).toBe('high');
    expect(isEvidenceRef(flagged?.evidenceRef)).toBe(true);
    // No clean verdict: the flagged change is CHANGES_REQUESTED, not PASS.
    expect(decideVerdict(findings)).toBe('CHANGES_REQUESTED');
  });

  it('attaches a deterministic coherence evidence reference to each verdict', () => {
    const change = makeChange({
      requirements: [
        requirement({
          id: 'Refund ledger',
          capability: 'billing-refunds',
          text: 'The refund ledger SHALL record every refund',
          scenarios: [{ name: 'refund recorded', whenThen: ['WHEN a refund is issued', 'THEN the ledger records it'] }]
        })
      ]
    });
    const diff = makeDiff([
      diffFile('src/billing/refund.ts', ['export function refundLedger() {', '  const ledger = recordRefund();', '}'])
    ]);
    const first = checkSpecCompliance(change, diff);
    const second = checkSpecCompliance(change, diff);

    expect(first.coverage).toHaveLength(1);
    const ref = first.coverage[0].evidenceRef;
    expect(isEvidenceRef(ref)).toBe(true);
    expect(second.coverage[0].evidenceRef).toBe(ref); // deterministic
    expect(first.coverage[0].status).toBe('covered');
    // Any finding derived from the verdict cites the same record.
    for (const f of first.findings) expect(isEvidenceRef(f.evidenceRef)).toBe(true);
  });

  it('negative control: a heuristic verdict never claims VERIFIED', () => {
    expect(classifyStatus({ heuristicOnly: true })).toBe('COMPLETED');
    const heuristicReview: ReviewResult = {
      change: 'fixture-change',
      verdict: 'PASS',
      summary: 'heuristic only',
      template: { id: 'generic', label: 'Generic', reason: 'fixture' },
      requirementCoverage: [],
      findings: [],
      stats: { filesChanged: 1, linesAdded: 1, requirementsTotal: 0, requirementsCovered: 0 }
    };
    expect(statusForReview(heuristicReview)).toBe('UNKNOWN');
    expect(statusForReview(heuristicReview)).not.toBe('VERIFIED');
  });
});
