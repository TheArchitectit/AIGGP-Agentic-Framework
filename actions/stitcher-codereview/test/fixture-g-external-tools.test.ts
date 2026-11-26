import { afterAll, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
  parseGuardrailsScan,
  parseSecretScanDeclared,
  runToolCheck,
  missingIdentity,
  sha256Text,
  type ToolCheckConfig
} from '../src/checks/external-tools.js';
import { isEvidenceRef } from '../src/evidenceRef.js';
import type { ToolProvenance } from '../src/types.js';

const dirs: string[] = [];
afterAll(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true });
});

const GUARDRAILS_OUTPUT = [
  '[GUARDRAILS][critical] PREVENT-003 src/config.py:12 - Possible hardcoded credential detected',
  '[GUARDRAILS][warning] PREVENT-012 src/app.ts:5 - console.log left in production code',
  'GUARDRAILS: 1 violation(s) found.'
].join('\n');

const PROV: ToolProvenance = {
  name: 'guardrails-scan.mjs',
  version: 'sha256:0123456789ab',
  vendor: 'scripts/guardrails-scan.mjs',
  inputDigest: 'a'.repeat(64),
  rawOutputDigest: sha256Text(GUARDRAILS_OUTPUT)
};

describe('Fixture G - an ingested external result keeps its identity', () => {
  it('preserves tool name, version and raw-output digest on every finding', () => {
    const findings = parseGuardrailsScan(GUARDRAILS_OUTPUT, process.cwd(), PROV);
    expect(findings).toHaveLength(2);
    for (const f of findings) {
      expect(f.tool?.name).toBe('guardrails-scan.mjs');
      expect(f.tool?.version).toBe('sha256:0123456789ab');
      expect(f.tool?.vendor).toBe('scripts/guardrails-scan.mjs');
      expect(f.tool?.rawOutputDigest).toBe(PROV.rawOutputDigest);
      expect(isEvidenceRef(f.evidenceRef)).toBe(true);
    }
    // Findings stay attributed to the source tool, never renamed to an AIGGP check.
    expect(findings[0].checkId).toBe('guardrails-scan/PREVENT-003');
    expect(findings[0].severity).toBe('blocker');
    expect(findings[1].severity).toBe('medium');
    expect(missingIdentity(findings[0])).toEqual([]);
  });

  it('negative control: identity laundering is detected when name/version/digest are dropped', () => {
    const raw = parseGuardrailsScan(GUARDRAILS_OUTPUT, process.cwd());
    expect(missingIdentity(raw[0])).toEqual(
      expect.arrayContaining(['tool.name', 'tool.version', 'tool.rawOutputDigest', 'evidenceRef'])
    );
  });

  it('ingests the fleet secret declaration with the same identity contract', () => {
    const raw = [
      '# declaration',
      'https://github.com/org/one',
      'https://github.com/org/two'
    ].join('\n');
    const prov = { ...PROV, name: 'secret-scan-declared.sh', version: 'sha256:fedcba987654', rawOutputDigest: sha256Text(raw) };
    const findings = parseSecretScanDeclared(raw, process.cwd(), prov);
    expect(findings).toHaveLength(2);
    for (const f of findings) {
      expect(f.tool?.name).toBe('secret-scan-declared.sh');
      expect(f.tool?.version).toBe('sha256:fedcba987654');
      expect(f.checkId).toBe('secret-scan-declared/declared-repo');
    }
  });

  it('the live run path stamps provenance and the raw-output digest', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'stitcher-tool-'));
    dirs.push(dir);
    const script = join(dir, 'scan.js');
    writeFileSync(script, [
      'process.stderr.write("[GUARDRAILS][error] PREVENT-001 src/x.ts:9 - JSON.parse without null check\\n");',
      'process.exit(1);'
    ].join('\n'));
    const config: ToolCheckConfig = {
      tool: 'node',
      displayName: 'guardrails-scan.mjs',
      args: ['{projectRoot}/scan.js'],
      parse: (raw, root) => parseGuardrailsScan(raw, root),
      category: 'security',
      checkId: 'guardrails-scan',
      versionFromFile: 'scan.js'
    };
    const findings = await runToolCheck(config, dir);
    expect(findings).toHaveLength(1);
    expect(findings[0].tool?.name).toBe('guardrails-scan.mjs');
    expect(findings[0].tool?.version).toMatch(/^sha256:[0-9a-f]{12}$/);
    expect(findings[0].tool?.inputDigest).toMatch(/^[0-9a-f]{64}$/);
    expect(findings[0].tool?.rawOutputDigest).toMatch(/^[0-9a-f]{64}$/);
  }, 30_000);
});
