import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { join, relative, isAbsolute } from 'node:path';
import { promisify } from 'node:util';
import type { Diff, ReviewResult } from './types.js';
import type { Dirent } from 'node:fs';

const exec = promisify(execFile);

/**
 * Verification semantics — a claim about completed work can only ever be as
 * strong as the mechanism that produced it. `VERIFIED` / `TESTED` require
 * executable observations; nothing derived from keyword heuristics may claim
 * them.
 */
export type VerificationStatus = 'ATTEMPTED' | 'COMPLETED' | 'TESTED' | 'VERIFIED' | 'BLOCKED' | 'FAILED' | 'UNKNOWN';

/** Deterministic fingerprint of the repo state a review's evidence refers to. */
export interface RepoFingerprint {
  head: string | null;
  /** sha256 of sorted "path:blob" pairs of the diff-touched files under root. */
  touchedHash: string | null;
  files: string[];
  capturedAt: string;
}

export interface EvidenceBundle {
  fingerprint: RepoFingerprint;
  /** Which changed files the review based evidence on. */
  changedFiles: string[];
  /** True when the review invoked an executable observation (test/scanner/LLM). */
  executable: boolean;
}

export interface StatusInput {
  /** True if evidence was gathered but nothing was actually executed. */
  heuristicOnly?: boolean;
  /** True if a test/scanner/LLM execution completed. */
  executed?: boolean;
  /** True if the execution outcome matched the claim. */
  matched?: boolean;
  /** Set when a required precondition failed (e.g. no git repo). */
  blockedBy?: string;
  /** Set when the producing mechanism threw. */
  failedBy?: string;
}

/** SHA-256 hex of a file's bytes. */
export async function sha256File(file: string): Promise<string> {
  const buf = await readFile(file);
  return createHash('sha256').update(buf).digest('hex');
}

/** Hash a sorted list of "relpath:sha256" lines over existing files. */
export async function hashTree(root: string, paths: string[]): Promise<string | null> {
  const rows: string[] = [];
  for (const p of paths) {
    const full = join(root, p);
    try {
      rows.push(`${p}:${await sha256File(full)}`);
    } catch {
      rows.push(`${p}:<missing>`);
    }
  }
  rows.sort();
  return rows.length === 0 ? null : createHash('sha256').update(rows.join('\n')).digest('hex');
}

/** Current HEAD of a git repo, or null when not a repo / git unavailable. */
export async function gitHead(root: string): Promise<string | null> {
  try {
    const { stdout } = await exec('git', ['rev-parse', 'HEAD'], { cwd: root });
    return stdout.trim() || null;
  } catch {
    return null;
  }
}

/** Build a fingerprint for the given diff within a project root. */
export async function fingerprintDiff(root: string, diff: Diff): Promise<RepoFingerprint> {
  const rel = diff.files
    .map((f) => (isAbsolute(f.path) ? relative(root, f.path) : f.path))
    .filter((p) => !p.startsWith('..'));
  const touchedHash = await hashTree(root, rel);
  return {
    head: await gitHead(root),
    touchedHash,
    files: rel,
    capturedAt: new Date().toISOString()
  };
}

/**
 * Evidence is stale when the repo moved underneath it: HEAD changed, or any
 * diff-touched file's content changed. Cross-check with the CURRENT state.
 */
export async function evidenceIsStale(bundle: EvidenceBundle, root: string, diff: Diff): Promise<boolean> {
  const now = await fingerprintDiff(root, diff);
  const was = bundle.fingerprint;
  if (was.head !== null && now.head !== null && was.head !== now.head) return true;
  if (was.touchedHash !== now.touchedHash) return true;
  return false;
}

/**
 * Honest status classifier. A keyword heuristic may at most be COMPLETED
 * (mechanism ran, produced a claim); nothing upgrades to TESTED/VERIFIED
 * without an executable observation, and nothing upgrades to VERIFIED without
 * a match between claim and observation.
 */
export function classifyStatus(i: StatusInput): VerificationStatus {
  if (i.failedBy) return 'FAILED';
  if (i.blockedBy) return 'BLOCKED';
  if (i.executed) {
    return i.matched ? 'VERIFIED' : 'TESTED';
  }
  if (i.heuristicOnly) return 'COMPLETED';
  if (i.matched !== undefined) return 'ATTEMPTED';
  return 'UNKNOWN';
}

/**
 * Map a finished review to an honest verification status based only on what
 * actually ran. Heuristic keyword coverage is COMPLETED; an executed mechanism
 * (LLM rescore, external scanner) is TESTED. The review tool never emits
 * VERIFIED because it has no independent behavioral observation.
 */
export function statusForReview(result: ReviewResult): VerificationStatus {
  if (!result.verification) return 'UNKNOWN';
  const executed = result.verification.executable === true;
  if (executed) return 'TESTED';
  if (result.requirementCoverage.length > 0 || result.findings.length > 0) return 'COMPLETED';
  return 'UNKNOWN';
}

/** Attach verification metadata to a finished review (post-finalize). */
export async function attachEvidence(result: ReviewResult, diff: Diff, root: string | undefined): Promise<ReviewResult> {
  if (!root) return result;
  let fingerprint: RepoFingerprint;
  let changedFiles: string[];
  let executable = false;
  try {
    fingerprint = await fingerprintDiff(root, diff);
    changedFiles = diff.files.map((f) => f.path);
    executable =
      result.requirementCoverage.some((c) => c.llmScore !== undefined && c.llmScore !== null) ||
      result.findings.some((f) => /^scanner-|^osv|^trivy|^semgrep/.test(f.checkId));
  } catch {
    return result;
  }
  return {
    ...result,
    verification: { fingerprint, changedFiles, executable }
  };
}

/** Recomputed staleness status for a result previously augmented with evidence. */
export async function resultEvidenceIsStale(result: ReviewResult, root: string, diff: Diff): Promise<boolean> {
  const v = result.verification;
  if (!v) return false;
  return evidenceIsStale({ fingerprint: v.fingerprint, changedFiles: v.changedFiles, executable: v.executable }, root, diff);
}

/** Recursively list files under a directory (relative paths) for corpus/bench scanning. */
export async function listFilesRecursive(dir: string): Promise<string[]> {
  const out: string[] = [];
  let entries: Dirent[];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    const full = join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await listFilesRecursive(full)));
    } else if (e.isFile()) {
      out.push(relative(dir, full));
    }
  }
  return out;
}