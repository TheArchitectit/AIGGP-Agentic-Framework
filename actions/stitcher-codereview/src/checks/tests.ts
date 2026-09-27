import type { Diff, Finding, OpenSpecChange } from '../types.js';

const TEST_RE = /(\.test\.|\.spec\.|__tests__|test\/|tests\/|e2e)/;

export interface TestsOptions {
  /** Extra regex sources recognizing test files for this project archetype. */
  testFileRes?: string[];
  /** Archetype-specific guidance appended to the no-tests suggestion. */
  testHint?: string;
}

export function checkTests(change: OpenSpecChange, diff: Diff, opts: TestsOptions = {}): Finding[] {
  const findings: Finding[] = [];
  const extraRes = (opts.testFileRes ?? []).map((s) => {
    try {
      return new RegExp(s);
    } catch {
      return null;
    }
  }).filter((r): r is RegExp => r !== null);
  const isTest = (p: string) => TEST_RE.test(p) || extraRes.some((r) => r.test(p));
  const touched = diff.files.map((f) => f.path);
  const touchedTests = touched.filter(isTest);
  const touchedSrc = touched.filter((p) => !isTest(p) && !p.startsWith('openspec/') && !p.endsWith('.md'));

  const addedReqs = change.requirements.filter((r) => r.operation !== 'REMOVED');
  if (addedReqs.length > 0 && touchedSrc.length > 0 && touchedTests.length === 0) {
    const base = `Add tests covering: ${addedReqs.slice(0, 3).map((r) => `"${r.id}"`).join(', ')}.`;
    findings.push({
      severity: 'high',
      category: 'tests',
      checkId: 'no-tests-touched',
      message: `Spec change touches ${touchedSrc.length} source file(s) but no test file was modified.`,
      suggestion: opts.testHint ? `${base} ${opts.testHint}` : base
    });
  }
  // Scenario → test mapping: filename, explicit `// scenario: <name>` reference,
  // or shared vocabulary (scenario WHEN/THEN keywords vs test content).
  const testLines = diff.files
    .filter((f) => touchedTests.includes(f.path))
    .flatMap((f) => f.addedLines.map((l) => l.text));
  const testContent = testLines.join('\n').toLowerCase().replace(/[^a-z0-9]+/g, '');
  const testWords = new Set(
    testLines
      .join(' ')
      .toLowerCase()
      .replace(/[^a-z0-9_\-/ ]/g, ' ')
      .split(/[\s/_\-]+/)
      .filter((w) => w.length > 3)
  );
  for (const r of addedReqs) {
    for (const s of r.scenarios) {
      const slug = s.name.toLowerCase().replace(/[^a-z0-9]+/g, '');
      const pathHit = touchedTests.some((t) => t.toLowerCase().replace(/[^a-z0-9]+/g, '').includes(slug.slice(0, 12)));
      const contentHit = slug.length > 4 && testContent.includes(slug);
      const scenarioWords = new Set(
        `${s.name} ${s.whenThen.join(' ')}`
          .toLowerCase()
          .replace(/[^a-z0-9_\-/ ]/g, ' ')
          .split(/[\s/_\-]+/)
          .filter((w) => w.length > 3)
      );
      let shared = 0;
      for (const w of scenarioWords) if (testWords.has(w)) shared++;
      const vocabHit = shared >= 3;
      if (!pathHit && !contentHit && !vocabHit && slug.length > 4) {
        findings.push({
          severity: 'medium',
          category: 'tests',
          checkId: 'scenario-unmatched',
          requirementId: r.id,
          message: `Scenario "${s.name}" (req "${r.id}") has no obviously matching test file.`,
          suggestion: 'Name a test after the scenario or reference the requirement id in a comment.'
        });
        break; // one finding per requirement max
      }
    }
  }
  return findings.slice(0, 30);
}
