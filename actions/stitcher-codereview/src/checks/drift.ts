import type { BaselineSpec, Diff, Finding, OpenSpecChange } from '../types.js';
import { keywords } from '../spec/parser.js';

export interface CapabilityIndex {
  capability: string;
  pathTokens: string[];
  keywords: Set<string>;
}

/** Paths that can never be drift: tests, prose, meta, config, generated. */
export function isDriftRelevant(path: string): boolean {
  if (/(\.test\.|\.spec\.|__tests__|test\/|tests\/|e2e)/.test(path)) return false;
  if (/\.(md|mdx|txt|rst)$/.test(path)) return false;
  if (/\.ya?ml$/.test(path)) return false; // CI/action config is not product behavior
  if (/^openspec\//.test(path)) return false;
  if (/(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|bun\.lockb)$/.test(path)) return false;
  if (/(^|\/)(dist|build|coverage|generated)\//.test(path)) return false;
  // Vendored dependency trees are never product behavior.
  if (/(^|\/)(node_modules|\.venv|venv|env|\.tox|site-packages)\//.test(path)) return false;
  if (/(^|\/)(docs|roadmap|evidence)\//.test(path)) return false;
  if (/\.min\.js$/.test(path)) return false;
  return true;
}

function pathTokens(capability: string): string[] {
  return capability.toLowerCase().split(/[/_-]/).filter((t) => t.length > 2);
}

/** Index every known capability (baseline + delta) for file→area mapping. */
export function buildIndex(baseline: BaselineSpec[], deltaCaps: string[]): CapabilityIndex[] {
  const byCap = new Map<string, Set<string>>();
  const ensure = (c: string) => {
    if (!byCap.has(c)) byCap.set(c, new Set());
    return byCap.get(c)!;
  };
  for (const b of baseline) {
    const keys = ensure(b.capability);
    for (const r of b.requirements) {
      for (const k of keywords(`${r.id} ${r.text}`)) {
        keys.add(k);
        if (keys.size > 60) break;
      }
    }
  }
  for (const c of deltaCaps) ensure(c);
  return [...byCap.entries()].map(([capability, kws]) => ({
    capability,
    pathTokens: pathTokens(capability),
    keywords: kws
  }));
}

export interface FileMatch {
  capability: string;
  /** Human-readable match evidence, e.g. `path token 'spec'`. Shown in findings for quick triage. */
  via: string[];
}

/** Best-matching capability for a file path, or null. Threshold keeps strays unmapped. */
export function mapFileToCapability(path: string, index: CapabilityIndex[]): FileMatch | null {
  const low = path.toLowerCase();
  const segments = low.split(/[/_.\-]/).filter((s) => s.length >= 3);
  let best: { cap: string; score: number; via: string[] } | null = null;
  for (const c of index) {
    let score = 0;
    const via: string[] = [];
    for (const t of c.pathTokens) {
      if (low.includes(t)) {
        score += 3;
        via.push(`path token '${t}'`);
        continue;
      }
      // Prefix overlap catches theme/theming, tests/test without stemming.
      const seg = segments.find((s) => commonPrefix(s, t) >= 4);
      if (seg) {
        score += 2;
        via.push(`prefix '${seg}'~'${t}'`);
      }
    }
    if (score === 0) {
      const hitKeys: string[] = [];
      for (const k of c.keywords) if (low.includes(k)) hitKeys.push(k);
      if (hitKeys.length >= 2) {
        score = 2;
        via.push(`keywords '${hitKeys.slice(0, 3).join("', '")}'`);
      }
    }
    if (score >= 2 && (!best || score > best.score)) best = { cap: c.capability, score, via };
  }
  return best ? { capability: best.cap, via: best.via } : null;
}

function commonPrefix(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}

/**
 * Reverse check: every relevant changed file should sit under a capability
 * covered by this change's delta specs. Files in known-but-uncovered areas
 * are drift (behavior shipped without a spec); files nowhere mappable are
 * uncategorized. With no baseline at all, one info finding replaces per-file
 * noise and points at openspec/specs/.
 */
export function checkDrift(change: OpenSpecChange, diff: Diff): Finding[] {
  if (change.requirements.length === 0 || diff.files.length === 0) return [];
  const deltaCaps = [...new Set(change.requirements.map((r) => r.capability))];
  const baseline = change.baseline ?? [];

  const relevant = diff.files.filter((f) => !f.isDeleted && isDriftRelevant(f.path));
  if (relevant.length === 0) return [];

  if (baseline.length === 0) {
    return [
      {
        severity: 'info',
        category: 'spec-compliance',
        checkId: 'drift-no-baseline',
        message: 'No baseline specs (openspec/specs/) — drift mapping unavailable; per-file area checks skipped.',
        suggestion: 'Add baseline specs for stable capabilities so uncovered-area drift can be detected.'
      }
    ];
  }

  const index = buildIndex(baseline, deltaCaps);
  const findings: Finding[] = [];
  for (const f of relevant) {
    const match = mapFileToCapability(f.path, index);
    if (!match) {
      findings.push({
        severity: 'low',
        category: 'spec-compliance',
        checkId: 'drift-uncategorized',
        file: f.path,
        message: `\`${f.path}\` touches no known capability (baseline + delta).`,
        suggestion: 'Add it to a baseline spec, or extend this change with a delta spec if it is new behavior.'
      });
    } else if (!deltaCaps.includes(match.capability)) {
      findings.push({
        severity: 'medium',
        category: 'spec-compliance',
        checkId: 'drift-uncovered',
        file: f.path,
        message: `\`${f.path}\` touches capability \`${match.capability}\`` +
          ` (matched: ${match.via.join(', ')}) with no covering requirement in this change.`,
        suggestion: `Add a delta spec under specs/${match.capability}/ (or narrow the diff) so the behavior is specified.`
      });
    }
  }
  return findings.slice(0, 30);
}
