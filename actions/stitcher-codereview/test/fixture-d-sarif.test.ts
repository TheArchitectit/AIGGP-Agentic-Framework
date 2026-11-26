import { describe, expect, it } from 'vitest';
import { toSarif } from '../src/sarif.js';
import { attachEvidenceRefs, isEvidenceRef } from '../src/evidenceRef.js';
import type { Finding, ReviewResult } from '../src/types.js';
import { executablePass } from './helpers.js';

const REF = /^coh-ev-[0-9a-f]{16}$/;

interface SarifResult {
  ruleId?: string;
  ruleIndex?: number;
  level?: string;
  message?: { text?: string };
  locations?: { physicalLocation?: { artifactLocation?: { uri?: string }; region?: { startLine?: number } } }[];
  properties?: { evidenceRef?: string };
}

interface SarifDoc {
  $schema?: string;
  version?: string;
  runs?: {
    tool?: { driver?: { name?: string; version?: string; rules?: { id?: string }[] } };
    results?: SarifResult[];
  }[];
}

/** Minimal SARIF 2.1.0 validity check for the shape the emitter promises. */
function validateSarif(doc: SarifDoc): string[] {
  const errors: string[] = [];
  if (doc.version !== '2.1.0') errors.push('version is not 2.1.0');
  if (!doc.$schema) errors.push('missing $schema');
  const run = doc.runs?.[0];
  if (!run) return [...errors, 'no runs[0]'];
  const driver = run.tool?.driver;
  if (!driver?.name) errors.push('no tool.driver.name');
  if (!driver?.version) errors.push('no tool.driver.version');
  const ruleIds = new Set((driver?.rules ?? []).map((r) => r.id));
  if (ruleIds.size === 0) errors.push('no rules');
  for (const [i, r] of (run.results ?? []).entries()) {
    if (!r.ruleId) errors.push(`results[${i}] has no ruleId`);
    else if (!ruleIds.has(r.ruleId)) errors.push(`results[${i}] ruleId not declared in rules`);
    if (typeof r.message?.text !== 'string' || r.message.text.length === 0) {
      errors.push(`results[${i}] has no message.text`);
    }
    if (!['error', 'warning', 'note'].includes(r.level ?? '')) errors.push(`results[${i}] has an invalid level`);
    if (!REF.test(r.properties?.evidenceRef ?? '')) errors.push(`results[${i}] has no evidence reference`);
    const uri = r.locations?.[0]?.physicalLocation?.artifactLocation?.uri;
    if (uri !== undefined) {
      try {
        decodeURI(uri);
      } catch {
        errors.push(`results[${i}] uri does not decode`);
      }
    }
  }
  return errors;
}

function review(): ReviewResult {
  const findings: Finding[] = [
    { severity: 'high', category: 'spec-compliance', checkId: 'requirement-missing', requirementId: 'Refund ledger', file: 'src/billing/refund.ts', line: 12, message: 'Requirement has no evidence', suggestion: 'Implement it' },
    { severity: 'low', category: 'tasks', checkId: 'task-progress', message: 'Progress: 1/2 tasks checked' },
    { severity: 'medium', category: 'security', checkId: 'guardrails-scan/PREVENT-003', file: 'src/dir with space/config.py', line: 3, message: 'guardrails finding', tool: { name: 'guardrails-scan.mjs', version: 'sha256:0123456789ab', rawOutputDigest: 'f'.repeat(64) } }
  ];
  return executablePass({ verdict: 'CHANGES_REQUESTED', findings: attachEvidenceRefs('fixture-change', findings) });
}

describe('Fixture D - SARIF round-trips schema-valid with evidence links', () => {
  it('emits valid SARIF where every result renders with location and evidence link', () => {
    const doc = JSON.parse(toSarif(review())) as SarifDoc;
    expect(validateSarif(doc)).toEqual([]);
    const results = doc.runs?.[0]?.results ?? [];
    expect(results).toHaveLength(3);
    expect(results[0].locations?.[0]?.physicalLocation?.region?.startLine).toBe(12);
    expect(results[0].properties?.evidenceRef).toMatch(REF);
    // An adapter-ingested finding keeps its source identity through SARIF.
    expect(results[2].ruleId).toBe('stitcher-codereview/security/guardrails-scan/PREVENT-003');
  });

  it('round-trips: refs and rule ids survive a serialize/parse cycle unchanged', () => {
    const first = JSON.parse(toSarif(review())) as SarifDoc;
    const second = JSON.parse(JSON.stringify(first)) as SarifDoc;
    const refs = (d: SarifDoc) => (d.runs?.[0]?.results ?? []).map((r) => r.properties?.evidenceRef);
    expect(refs(second)).toEqual(refs(first));
    expect(second.runs?.[0]?.tool?.driver?.rules).toEqual(first.runs?.[0]?.tool?.driver?.rules);
  });

  it('negative control: the validator rejects a result with no message or rule id', () => {
    const doc = JSON.parse(toSarif(review())) as SarifDoc;
    const results = doc.runs?.[0]?.results ?? [];
    delete results[0].message;
    delete results[1].ruleId;
    const errors = validateSarif(doc);
    expect(errors.length).toBeGreaterThanOrEqual(2);
    expect(errors.join(' ')).toContain('message.text');
    expect(errors.join(' ')).toContain('ruleId');
  });

  it('the emitter attaches a reference even to findings that arrive without one', () => {
    const r = review();
    r.findings = r.findings.map((f) => ({ ...f, evidenceRef: undefined }));
    const doc = JSON.parse(toSarif(r)) as SarifDoc;
    for (const result of doc.runs?.[0]?.results ?? []) {
      expect(isEvidenceRef(result.properties?.evidenceRef)).toBe(true);
    }
  });
});
