import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import type { ProjectTemplate, ResolvedTemplate } from './types.js';

async function exists(root: string, rel: string): Promise<boolean> {
  try {
    await stat(join(root, rel));
    return true;
  } catch {
    return false;
  }
}

interface Pkg {
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
  [k: string]: unknown;
}

async function readPkg(root: string): Promise<Pkg> {
  try {
    return JSON.parse(await readFile(join(root, 'package.json'), 'utf8')) as Pkg;
  } catch {
    return {};
  }
}

/** Score-based detection: each matching signal adds its weight; highest wins, ties keep builtin order. */
export async function detectTemplate(
  projectRoot: string,
  all: ProjectTemplate[]
): Promise<ResolvedTemplate> {
  const pkg = await readPkg(projectRoot);
  const deps = new Set([...Object.keys(pkg.dependencies ?? {}), ...Object.keys(pkg.devDependencies ?? {})]);
  const generic = all.find((t) => t.id === 'generic') ?? all[0];

  let best: { t: ProjectTemplate; score: number; hits: string[] } | null = null;
  for (const t of all) {
    if (t.id === 'generic') continue;
    let score = 0;
    const hits: string[] = [];
    for (const m of t.matchers) {
      const w = m.weight ?? 1;
      if (m.file && (await exists(projectRoot, m.file))) {
        score += w;
        hits.push(m.file);
      } else if (m.dep && deps.has(m.dep)) {
        score += w;
        hits.push(`dep:${m.dep}`);
      } else if (m.pkgField && pkg[m.pkgField] !== undefined) {
        score += w;
        hits.push(`package.json#${m.pkgField}`);
      }
    }
    if (score > 0 && (!best || score > best.score)) best = { t, score, hits };
  }
  if (!best) return { template: generic, reason: 'auto: no archetype signals matched — using generic' };
  return { template: best.t, reason: `auto: ${best.hits.slice(0, 3).join(', ')} matched (+${best.score})` };
}

/** Explicit `--template <id>` wins over detection; unknown ids are fatal with a helpful list. */
export async function resolveTemplate(
  projectRoot: string,
  requested: string | undefined,
  all: ProjectTemplate[]
): Promise<ResolvedTemplate> {
  if (!requested || requested === 'auto') return detectTemplate(projectRoot, all);
  const found = all.find((t) => t.id === requested);
  if (!found) {
    throw new Error(
      `Unknown template "${requested}". Available: ${all.map((t) => t.id).join(', ')} (or "auto").`
    );
  }
  return { template: found, reason: `explicit: --template ${found.id}${found.custom ? ' (custom)' : ''}` };
}
