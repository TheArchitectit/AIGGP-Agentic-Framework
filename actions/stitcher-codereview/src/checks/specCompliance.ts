import type { Diff, Finding, OpenSpecChange, Requirement, ReviewResult } from '../types.js';
import { keywords } from '../spec/parser.js';

export type CoverageEntry = ReviewResult['requirementCoverage'][number];

interface ScoreResult {
  score: number;
  evidence: string[];
  locations: { file: string; startLine: number; endLine: number }[];
}

function mergeRanges(
  ranges: { file: string; startLine: number; endLine: number }[]
): { file: string; startLine: number; endLine: number }[] {
  const byFile = new Map<string, { start: number; end: number }[]>();
  for (const r of ranges) {
    const arr = byFile.get(r.file) ?? [];
    arr.push({ start: r.startLine, end: r.endLine });
    byFile.set(r.file, arr);
  }
  const merged: { file: string; startLine: number; endLine: number }[] = [];
  for (const [file, rs] of byFile) {
    rs.sort((a, b) => a.start - b.start);
    let cur = rs[0];
    for (let i = 1; i < rs.length; i++) {
      if (rs[i].start <= cur.end + 3) {
        cur.end = Math.max(cur.end, rs[i].end);
      } else {
        merged.push({ file, startLine: cur.start, endLine: cur.end });
        cur = rs[i];
      }
    }
    merged.push({ file, startLine: cur.start, endLine: cur.end });
  }
  return merged;
}

export function scoreRequirement(req: Requirement, diff: Diff): ScoreResult {
  const evidence: string[] = [];
  const locations: { file: string; startLine: number; endLine: number }[] = [];
  const reqKeys = keywords(`${req.id} ${req.text} ${req.scenarios.map((s) => `${s.name} ${s.whenThen.join(' ')}`).join(' ')}`);
  if (reqKeys.size === 0) return { score: 0, evidence, locations };

  const hayLow = diff.evidenceText.toLowerCase();
  const capTokens = req.capability.toLowerCase().split(/[/_-]/).filter((t) => t.length > 2);

  let hits = 0;
  for (const k of reqKeys) {
    if (hayLow.includes(k)) {
      hits++;
      if (evidence.length < 5) evidence.push(`keyword \`${k}\` in diff`);
    }
  }

  // Find line ranges in diff files where keywords appear
  for (const f of diff.files) {
    const fp = f.path.toLowerCase();
    const fileHits: { file: string; startLine: number; endLine: number }[] = [];
    let currentRange: { start: number; end: number } | null = null;
    for (const l of f.addedLines) {
      const lineLow = l.text.toLowerCase();
      let lineHasKey = false;
      for (const k of reqKeys) {
        if (lineLow.includes(k)) {
          lineHasKey = true;
          break;
        }
      }
      if (lineHasKey) {
        if (!currentRange) currentRange = { start: l.n, end: l.n };
        else currentRange.end = l.n;
      } else if (currentRange) {
        fileHits.push({ file: f.path, startLine: currentRange.start, endLine: currentRange.end });
        currentRange = null;
      }
    }
    if (currentRange) fileHits.push({ file: f.path, startLine: currentRange.start, endLine: currentRange.end });
    locations.push(...fileHits);

    // Capability path mentioned in changed file paths = strong signal
    if (capTokens.some((t) => fp.includes(t))) {
      hits += 2;
      evidence.push(`file \`${f.path}\` matches capability \`${req.capability}\``);
      // Also add the whole file as a location if we don't have specific lines
      if (fileHits.length === 0 && f.addedLines.length > 0) {
        locations.push({ file: f.path, startLine: f.addedLines[0].n, endLine: f.addedLines[f.addedLines.length - 1].n });
      }
    }
  }

  const score = hits / (reqKeys.size + 2);
  return { score, evidence, locations: mergeRanges(locations) };
}

/** Coverage thresholds — configurable via review.yaml `covered-at` / `partial-at`. */
export interface CoverageThresholds {
  coveredAt?: number;
  partialAt?: number;
}

function statusForHeuristic(score: number, t: CoverageThresholds = {}): CoverageEntry['status'] {
  if (score >= (t.coveredAt ?? 0.3)) return 'covered';
  if (score >= (t.partialAt ?? 0.12)) return 'partial';
  return 'missing';
}

/** Heuristic-only coverage entry for one requirement (no findings). */
export function coverageForRequirement(req: Requirement, diff: Diff, t: CoverageThresholds = {}): { entry: CoverageEntry; score: number } {
  const { score, evidence, locations } = scoreRequirement(req, diff);
  if (req.operation === 'REMOVED') {
    if (score > 0.25) {
      return {
        score,
        entry: {
          requirementId: req.id,
          capability: req.capability,
          operation: req.operation,
          status: 'removed-still-present',
          evidence,
          locations
        }
      };
    }
    return {
      score,
      entry: {
        requirementId: req.id,
        capability: req.capability,
        operation: req.operation,
        status: 'covered',
        evidence: ['no matching code in diff — removal holds'],
        locations
      }
    };
  }
  return {
    score,
    entry: {
      requirementId: req.id,
      capability: req.capability,
      operation: req.operation,
      status: statusForHeuristic(score, t),
      evidence,
      locations,
      heuristicScore: score
    }
  };
}

/** Regenerate blocker/high findings from coverage entries (heuristic or blended). */
export function findingsForCoverage(change: OpenSpecChange, coverage: CoverageEntry[]): Finding[] {
  const byId = new Map(change.requirements.map((r) => [r.id, r]));
  const findings: Finding[] = [];
  for (const c of coverage) {
    const req = byId.get(c.requirementId);
    if (!req) continue;
    const blendedNote =
      c.blendedScore !== undefined && c.llmScore !== undefined && c.llmScore !== null
        ? ` (heuristic ${c.heuristicScore?.toFixed(2)}, LLM ${c.llmScore.toFixed(2)} → blended ${c.blendedScore.toFixed(2)}${c.llmRationale ? `: ${c.llmRationale}` : ''})`
        : '';
    if (c.status === 'removed-still-present') {
      findings.push({
        severity: 'high',
        category: 'spec-compliance',
        checkId: 'removed-still-present',
        requirementId: req.id,
        message: `REMOVED requirement "${req.id}" still has matching code in diff (${c.evidence.slice(0, 2).join('; ')}).`,
        suggestion: 'Delete the deprecated behavior and its tests.'
      });
    } else if (c.status === 'partial') {
      findings.push({
        severity: 'high',
        category: 'spec-compliance',
        checkId: 'requirement-partial',
        requirementId: req.id,
        message: `Requirement "${req.id}" (${req.operation}, cap: ${req.capability}) is only partially evidenced in diff. Scenarios: ${req.scenarios.map((s) => s.name).join(', ') || 'none'}.${blendedNote}`,
        suggestion: `Check that every Scenario (WHEN/THEN) in ${req.sourceFile} has a corresponding code path + test.`
      });
    } else if (c.status === 'missing') {
      findings.push({
        severity: 'blocker',
        category: 'spec-compliance',
        checkId: 'requirement-missing',
        requirementId: req.id,
        message: `Requirement "${req.id}" (${req.operation}, cap: ${req.capability}) has no evidence in diff. Expected behavior: "${req.text.slice(0, 160)}".${blendedNote}`,
        suggestion: `Implement it or narrow the spec. Source: ${req.sourceFile}.`
      });
    }
  }
  return findings;
}

export function checkSpecCompliance(change: OpenSpecChange, diff: Diff, t: CoverageThresholds = {}): {
  findings: Finding[];
  coverage: CoverageEntry[];
} {
  if (change.requirements.length === 0) {
    return {
      coverage: [],
      findings: [
        {
          severity: 'medium',
          category: 'spec-compliance',
          checkId: 'no-delta-specs',
          message: `Change \`${change.name}\` has no delta specs (no specs/*/spec.md with ADDED/MODIFIED/REMOVED Requirements). Review falls back to general checks only.`,
          suggestion: 'Run `/opsx:propose` to draft specs, or set skip_specs only for pure chores.'
        }
      ]
    };
  }
  const coverage: CoverageEntry[] = [];
  for (const req of change.requirements) {
    coverage.push(coverageForRequirement(req, diff, t).entry);
  }
  return { findings: findingsForCoverage(change, coverage), coverage };
}
