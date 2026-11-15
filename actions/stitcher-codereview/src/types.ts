export type Severity = 'blocker' | 'high' | 'medium' | 'low' | 'info';
export type Category = 'spec-compliance' | 'tasks' | 'correctness' | 'security' | 'tests' | 'style' | 'template' | 'dependency';
export type Verdict = 'PASS' | 'CHANGES_REQUESTED';

export interface Scenario {
  name: string;
  whenThen: string[]; // raw WHEN/THEN lines
}

export interface Requirement {
  id: string; // e.g. "Theme selection"
  capability: string; // e.g. "theming/dark-mode"
  operation: 'ADDED' | 'MODIFIED' | 'REMOVED';
  text: string;
  scenarios: Scenario[];
  sourceFile: string;
}

export interface TaskItem {
  id: string; // "1.1"
  group: string;
  text: string;
  done: boolean;
}

export interface OpenSpecChange {
  name: string;
  dir: string;
  proposal: string; // raw markdown
  design: string | null;
  requirements: Requirement[];
  tasks: TaskItem[];
  baselineCaps: string[]; // capability dirs present under openspec/specs
  /** Parsed baseline specs (source of truth); empty when openspec/specs/ is absent. */
  baseline?: BaselineSpec[];
}

/** One baseline capability from openspec/specs/<capability>/spec.md. */
export interface BaselineSpec {
  capability: string;
  requirements: Requirement[];
}

export interface DiffFile {
  path: string;
  addedLines: { n: number; text: string }[];
  removedLines: { n: number; text: string }[];
  hunks: string[];
  isNew: boolean;
  isDeleted: boolean;
}

export interface Diff {
  files: DiffFile[];
  /** concatenated added-line text for cheap keyword search */
  addedText: string;
  /** added-line text minus lockfiles/bundles — used for spec/task evidence */
  evidenceText: string;
}

/**
 * Provenance of an externally-produced finding. An adapter records the source
 * tool's identity, its version (or content digest), the digest of the input it
 * scanned and the digest of the raw output it returned, so the finding is never
 * re-issued as an AIGGP-originated check (ADR-004).
 */
export interface ToolProvenance {
  /** Tool name as the source reports it, e.g. `guardrails-scan.mjs`. */
  name: string;
  /** Version string, or `sha256:<12 hex>` of the scanner file. */
  version: string;
  /** Path/URL of the scanner, when known. */
  vendor?: string;
  /** sha256 of the input the tool scanned (tree digest or report digest). */
  inputDigest?: string;
  /** sha256 of the raw output the adapter parsed. */
  rawOutputDigest: string;
}

export interface Finding {
  severity: Severity;
  category: Category;
  /** Stable per-check id, e.g. `eval-call` or `game-2d-3d/binary-asset`. Drives SARIF rule ids. */
  checkId: string;
  requirementId?: string;
  file?: string;
  line?: number;
  message: string;
  suggestion?: string;
  /**
   * Evidence reference (`coh-ev-<digest>`) the finding is anchored to. Review
   * comments are refused without one (reviewer-surfaces spec: "A comment
   * without an evidence link SHALL NOT be posted").
   */
  evidenceRef?: string;
  /** Present only for adapter-ingested external findings. */
  tool?: ToolProvenance;
}

export interface ReviewResult {
  change: string;
  verdict: Verdict;
  summary: string;
  /** Project-type template applied (lens + heuristic pack). */
  template: { id: string; label: string; reason: string };
  requirementCoverage: {
    requirementId: string;
    capability: string;
    operation: string;
    status: 'covered' | 'partial' | 'missing' | 'removed-still-present';
    evidence: string[];
    /** File:line ranges that provided evidence for this requirement. */
    locations: { file: string; startLine: number; endLine: number }[];
    /** Coherence evidence reference (`coh-ev-<digest>`) for this verdict. */
    evidenceRef?: string;
    /** Blended-review diagnostics (present when --llm auto|require rescored). */
    heuristicScore?: number;
    llmScore?: number | null;
    blendedScore?: number;
    llmRationale?: string;
  }[];
  findings: Finding[];
  stats: {
    filesChanged: number;
    linesAdded: number;
    requirementsTotal: number;
    requirementsCovered: number;
    /** Per-category wall-clock durations in ms — present only with --timing. */
    durationsMs?: Record<string, number>;
  };
  /** Verification metadata (present when the review ran inside a project root). */
  verification?: {
    fingerprint: {
      head: string | null;
      touchedHash: string | null;
      files: string[];
      capturedAt: string;
    };
    changedFiles: string[];
    executable: boolean;
  };
}
