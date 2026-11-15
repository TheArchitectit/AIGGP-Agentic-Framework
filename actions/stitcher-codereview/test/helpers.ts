import type {
  BaselineSpec,
  Diff,
  DiffFile,
  OpenSpecChange,
  Requirement,
  ReviewResult,
  TaskItem
} from '../src/types.js';

/** Build one diff file from added lines (1-based numbering, like git). */
export function diffFile(path: string, added: string[], opts: { isNew?: boolean; isDeleted?: boolean } = {}): DiffFile {
  return {
    path,
    addedLines: added.map((text, i) => ({ n: i + 1, text })),
    removedLines: [],
    hunks: [],
    isNew: opts.isNew ?? false,
    isDeleted: opts.isDeleted ?? false
  };
}

/** Build a Diff with the same evidence-text filtering the git parser applies. */
export function makeDiff(files: DiffFile[]): Diff {
  const addedText = files.flatMap((f) => f.addedLines.map((l) => l.text)).join('\n');
  const evidenceText = files
    .filter((f) => !/(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb)$/.test(f.path))
    .filter((f) => !/(^|\/)(dist|build|coverage)\//.test(f.path))
    .filter((f) => !/^openspec\//.test(f.path))
    .filter((f) => !/\.min\.js$/.test(f.path))
    .flatMap((f) => f.addedLines.map((l) => l.text))
    .join('\n');
  return { files, addedText, evidenceText };
}

export function requirement(partial: Partial<Requirement> & { id: string; capability: string }): Requirement {
  return {
    operation: 'ADDED',
    text: '',
    scenarios: [],
    sourceFile: `openspec/specs/${partial.capability}/spec.md`,
    ...partial
  };
}

export function task(partial: Partial<TaskItem> & { id: string; text: string }): TaskItem {
  return { group: '1. Group', done: false, ...partial };
}

export function makeChange(partial: Partial<OpenSpecChange> = {}): OpenSpecChange {
  return {
    name: 'fixture-change',
    dir: 'openspec/changes/fixture-change',
    proposal: '',
    design: null,
    requirements: [],
    tasks: [],
    baselineCaps: [],
    baseline: [],
    ...partial
  };
}

/** A PASS result with an executable observation (what a scanner-backed review yields). */
export function executablePass(overrides: Partial<ReviewResult> = {}): ReviewResult {
  return {
    change: 'fixture-change',
    verdict: 'PASS',
    summary: 'all requirements evidenced',
    template: { id: 'generic', label: 'Generic', reason: 'fixture' },
    requirementCoverage: [],
    findings: [],
    stats: { filesChanged: 1, linesAdded: 1, requirementsTotal: 0, requirementsCovered: 0 },
    verification: {
      fingerprint: {
        head: 'a'.repeat(40),
        touchedHash: 'b'.repeat(64),
        files: ['src/billing/refund.ts'],
        capturedAt: '2026-11-15T00:00:00.000Z'
      },
      changedFiles: ['src/billing/refund.ts'],
      executable: true
    },
    ...overrides
  };
}

export function baselineSpec(capability: string, requirements: Requirement[]): BaselineSpec {
  return { capability, requirements };
}
