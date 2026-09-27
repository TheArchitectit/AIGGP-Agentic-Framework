import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { BaselineSpec, Finding } from '../types.js';
import { isDriftRelevant } from './drift.js';
import { buildIndex, mapFileToCapability } from './drift.js';

const exec = promisify(execFile);

/** Get all tracked files in the repo (respecting .gitignore). */
export async function getAllTrackedFiles(projectRoot: string): Promise<string[]> {
  try {
    const out = await exec('git', ['ls-files', '-z'], { cwd: projectRoot, maxBuffer: 16 * 1024 * 1024, timeout: 30_000 });
    const files = out.stdout.split('\0').filter(Boolean);
    if (files.length > 50_000) {
      console.error(`stitcher-codereview: warning: too many tracked files (${files.length}), truncating to 50k`);
      return files.slice(0, 50_000);
    }
    return files;
  } catch {
    return [];
  }
}

/** Read file content as lines (bounded: 256 KB max). */
async function readFileLines(projectRoot: string, path: string, maxBytes = 256 * 1024): Promise<string[]> {
  try {
    const { stat } = await import('node:fs/promises');
    const st = await stat(join(projectRoot, path)).catch(() => null);
    if (st && st.size > maxBytes) return []; // skip large binaries/generated
    const content = await readFile(join(projectRoot, path), 'utf8');
    if (content.includes('\0')) return [];
    if (content.length > maxBytes) return content.slice(0, maxBytes).split('\n');
    return content.split('\n');
  } catch {
    return [];
  }
}

/** Build a pseudo-diff for a whole file (all lines are "added" for scanning). */
function fileToDiffFile(path: string, lines: string[]): { path: string; addedLines: { n: number; text: string }[] } {
  return { path, addedLines: lines.map((text, i) => ({ n: i + 1, text })) };
}

/**
 * Scan the entire repository against baseline specs.
 * Returns findings for capabilities that have code but no covering spec.
 * This is the "out-of-band drift scan" — what shipped without a spec?
 */
export async function scanRepository(baseline: BaselineSpec[], projectRoot: string): Promise<Finding[]> {
  if (baseline.length === 0) {
    return [
      {
        severity: 'info',
        category: 'spec-compliance',
        checkId: 'scan-no-baseline',
        message: 'No baseline specs (openspec/specs/) — scan cannot map capabilities.',
        suggestion: 'Add baseline specs for stable capabilities so whole-tree drift can be detected.'
      }
    ];
  }

  const deltaCaps: string[] = []; // scan uses all baselines, no delta
  const index = buildIndex(baseline, deltaCaps);

  const allFiles = await getAllTrackedFiles(projectRoot);
  const relevant = allFiles.filter((p) => isDriftRelevant(p));

  // Bounded-parallel reads (I/O bound); results are consumed in the ORIGINAL
  // file order so findings stay deterministic across runs and machines.
  const SCAN_CONCURRENCY = 8;
  const lineBuckets: string[][] = new Array(relevant.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(SCAN_CONCURRENCY, relevant.length) }, async () => {
      for (;;) {
        const i = next++;
        if (i >= relevant.length) return;
        lineBuckets[i] = await readFileLines(projectRoot, relevant[i]);
      }
    })
  );

  const findings: Finding[] = [];
  const capabilityFiles = new Map<string, string[]>();

  for (let i = 0; i < relevant.length; i++) {
    const p = relevant[i];
    const lines = lineBuckets[i];
    if (!lines || lines.length === 0) continue;

    const match = mapFileToCapability(p, index);
    if (match) {
      const arr = capabilityFiles.get(match.capability) ?? [];
      arr.push(p);
      capabilityFiles.set(match.capability, arr);
    } else {
      findings.push({
        severity: 'low',
        category: 'spec-compliance',
        checkId: 'scan-uncategorized',
        file: p,
        message: `\`${p}\` touches no known capability (baseline).`,
        suggestion: 'Add it to a baseline spec if it represents product behavior.'
      });
    }
  }

  // For each capability with code, check if there's an active delta spec covering it.
  // Since scan mode has no change, we flag ALL baseline capabilities with code.
  // In practice, the user runs this periodically; the report shows what areas exist.
  // Severity is `info`: this is capability inventory, not a defect — a stable
  // repo scans PASS instead of screaming N mediums (audit-run lesson).
  for (const [capability, files] of capabilityFiles) {
    findings.push({
      severity: 'info',
      category: 'spec-compliance',
      checkId: 'scan-capability-drift',
      file: files[0], // anchor to first file
      message: `Capability \`${capability}\` has ${files.length} file(s) but no active delta spec in this review cycle.`,
      suggestion: `Ensure ongoing work in \`${capability}\` is tracked via an OpenSpec change, or declare it stable.`
    });
  }

  return findings.slice(0, 50);
}

/**
 * Scan a specific change's delta against the whole tree: for each ADDED/MODIFIED
 * requirement, find all code in the repo matching that capability, not just the diff.
 * This complements the PR diff view by showing the full capability footprint.
 */
export async function scanChangeRequirements(
  change: { requirements: { id: string; capability: string; operation: 'ADDED' | 'MODIFIED' | 'REMOVED'; text: string }[] },
  baseline: BaselineSpec[],
  projectRoot: string
): Promise<Finding[]> {
  if (change.requirements.length === 0) return [];

  const deltaCaps = [...new Set(change.requirements.map((r) => r.capability))];
  const index = buildIndex(baseline, deltaCaps);

  const allFiles = await getAllTrackedFiles(projectRoot);
  const relevant = allFiles.filter((p) => isDriftRelevant(p));

  // Bounded-parallel reads, deterministic original-order classification.
  const SCAN_CONCURRENCY = 8;
  const lineBuckets: string[][] = new Array(relevant.length);
  let cursor = 0;
  await Promise.all(
    Array.from({ length: Math.min(SCAN_CONCURRENCY, relevant.length) }, async () => {
      for (;;) {
        const i = cursor++;
        if (i >= relevant.length) return;
        lineBuckets[i] = await readFileLines(projectRoot, relevant[i]);
      }
    })
  );

  const findings: Finding[] = [];
  for (let i = 0; i < relevant.length; i++) {
    const p = relevant[i];
    const lines = lineBuckets[i];
    if (!lines || lines.length === 0) continue;

    const match = mapFileToCapability(p, index);
    if (match && deltaCaps.includes(match.capability)) {
      // File belongs to a capability this change touches — check if it's in the diff
      // This would need the actual diff to compare; for now, report the capability footprint
      findings.push({
        severity: 'info',
        category: 'spec-compliance',
        checkId: 'scan-capability-footprint',
        file: p,
        message: `\`${p}\` belongs to capability \`${match.capability}\` (via ${match.via.join(', ')}).`,
        suggestion: 'Review the full capability footprint, not just the PR diff.'
      });
    }
  }

  return findings.slice(0, 30);
}