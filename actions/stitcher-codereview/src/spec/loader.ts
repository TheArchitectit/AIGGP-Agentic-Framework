import { readFile, readdir, stat } from 'node:fs/promises';
import { join, dirname, resolve, isAbsolute } from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { BaselineSpec, OpenSpecChange, Requirement, TaskItem } from '../types.js';
import { parseDeltaSpec, parseTasks } from './parser.js';

const MAX_SPEC_BYTES = 256 * 1024;
const MAX_REMOTE_BYTES = 1 * 1024 * 1024;

async function readIfExists(p: string, maxBytes = MAX_SPEC_BYTES): Promise<string | null> {
  try {
    const { stat } = await import('node:fs/promises');
    const st = await stat(p).catch(() => null);
    if (st && st.size > maxBytes) {
      console.error(`stitcher-codereview: warning: file too large, truncated: ${p} (${st.size} bytes)`);
    }
    const raw = await readFile(p, 'utf8');
    return raw.length > maxBytes ? raw.slice(0, maxBytes) : raw;
  } catch {
    return null;
  }
}

async function listDirs(p: string): Promise<string[]> {
  try {
    const entries = await readdir(p, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory()).map((e) => e.name);
  } catch {
    return [];
  }
}

async function listFilesRecursive(dir: string, acc: string[] = [], depth = 0, seen: Set<string> = new Set()): Promise<string[]> {
  if (depth > 12 || acc.length > 5000) return acc;
  let entries;
  try {
    const { realpath } = await import('node:fs/promises');
    const real = await realpath(dir).catch(() => dir);
    if (seen.has(real)) return acc; // symlink loop guard
    seen.add(real);
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    const full = join(dir, e.name);
    if (e.isDirectory()) await listFilesRecursive(full, acc, depth + 1, seen);
    else if (e.isFile() && e.name === 'spec.md') {
      acc.push(full);
      if (acc.length > 5000) break;
    }
  }
  return acc;
}

/** Find openspec/specs dirs by walking up parent directories (monorepo support). */
async function findSpecsDirs(projectRoot: string): Promise<string[]> {
  const dirs: string[] = [];
  let current = resolve(projectRoot);
  const root = fileURLToPath(new URL('file:///'));
  while (current !== root) {
    const specsDir = join(current, 'openspec', 'specs');
    if (existsSync(specsDir)) {
      const hasSpecs = (await listDirs(specsDir)).length > 0;
      if (hasSpecs) dirs.push(specsDir);
    }
    const parent = dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return dirs;
}

/** Load specs from a local specs directory (<dir>/<capability>/spec.md). */
async function loadSpecsFromDir(specsDir: string): Promise<BaselineSpec[]> {
  const specFiles = await listFilesRecursive(specsDir);
  const out: BaselineSpec[] = [];
  for (const f of specFiles) {
    const rel = f.slice(specsDir.length + 1, -'/spec.md'.length);
    const raw = (await readIfExists(f)) ?? '';
    out.push({ capability: rel || 'default', requirements: parseDeltaSpec(raw, rel || 'default', f) });
  }
  return out;
}

function validateBaselineUrl(url: string): { owner: string; repo: string; ref: string; subpath: string } {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    throw new Error(`Invalid baseline URL: ${url}`);
  }
  if (u.protocol !== 'https:' || u.hostname !== 'github.com') {
    throw new Error(`Baseline URLs must be https://github.com/<owner>/<repo>/tree/<ref>/<path>: ${url}`);
  }
  const parts = u.pathname.split('/').filter(Boolean);
  // owner/repo/tree/ref/...path
  if (parts.length < 4 || parts[2] !== 'tree') {
    throw new Error(`Baseline URL must look like https://github.com/<owner>/<repo>/tree/<ref>/openspec/specs: ${url}`);
  }
  const [owner, repo, , ref, ...rest] = parts;
  return { owner, repo, ref, subpath: rest.join('/') };
}

async function fetchJsonCapped(url: string, maxBytes = MAX_REMOTE_BYTES, timeoutMs = 15_000): Promise<unknown> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { Accept: 'application/vnd.github+json' };
    const token = process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN;
    if (token) headers.authorization = `Bearer ${token}`;
    const response = await fetch(url, { headers, signal: ctrl.signal });
    if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
    const len = response.headers.get('content-length');
    if (len && Number(len) > maxBytes) throw new Error(`Remote baseline too large (${len} bytes): ${url}`);
    const text = await response.text();
    if (text.length > maxBytes) throw new Error(`Remote baseline too large (${text.length} chars): ${url}`);
    return JSON.parse(text);
  } finally {
    clearTimeout(t);
  }
}

async function fetchTextCapped(url: string, maxBytes = MAX_REMOTE_BYTES, timeoutMs = 15_000): Promise<string> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = {};
    const token = process.env.GITHUB_TOKEN ?? process.env.GH_TOKEN;
    if (token) headers.authorization = `Bearer ${token}`;
    const resp = await fetch(url, { headers, signal: ctrl.signal });
    if (!resp.ok) throw new Error(`Failed to fetch ${url}: ${resp.status}`);
    const len = resp.headers.get('content-length');
    if (len && Number(len) > maxBytes) throw new Error(`Remote file too large: ${url}`);
    const text = await resp.text();
    return text.length > maxBytes ? text.slice(0, maxBytes) : text;
  } finally {
    clearTimeout(t);
  }
}

/** Load specs from a remote GitHub tree URL (e.g. https://github.com/org/repo/tree/main/openspec/specs). */
async function loadSpecsFromRemote(url: string, depth = 0): Promise<BaselineSpec[]> {
  if (depth > 6) {
    console.error(`stitcher-codereview: warning: remote baseline recursion too deep, stopping: ${url}`);
    return [];
  }
  // Forks are allowed: any public github.com tree URL works. Private repos need GITHUB_TOKEN.
  // Internal recursion uses api.github.com contents URLs — accept those directly.
  // Validation lives INSIDE the try: a hostile/mistyped URL must degrade to []
  // (fail-safe), never abort the review.
  try {
    const isApiUrl = url.startsWith('https://api.github.com/');
    if (!isApiUrl) {
      validateBaselineUrl(url); // throws on non-github.com invariants
    }
    const apiUrl = isApiUrl
      ? url.replace('/tree/', '/contents/').replace('/blob/', '/contents/')
      : url.replace('github.com', 'api.github.com/repos').replace('/tree/', '/contents/').replace('/blob/', '/contents/');
    const data = (await fetchJsonCapped(apiUrl)) as unknown;
    if (!Array.isArray(data)) throw new Error('Unexpected response format');
    if (data.length > 1000) throw new Error(`Remote tree too large (${data.length} entries)`);
    const out: BaselineSpec[] = [];
    for (const item of data as { type?: string; url?: string; name?: string; path?: string; download_url?: string }[]) {
      if (item.type === 'dir' && item.url) {
        out.push(...(await loadSpecsFromRemote(item.url, depth + 1)));
      } else if (item.name === 'spec.md' && item.download_url) {
        const raw = await fetchTextCapped(item.download_url);
        const capPath = (item.path ?? '').replace('/spec.md', '').replace('openspec/specs/', '');
        out.push({ capability: capPath || 'default', requirements: parseDeltaSpec(raw, capPath || 'default', item.path ?? item.url ?? 'remote') });
      }
    }
    return out;
  } catch (err) {
    console.error(`Failed to load remote baseline from ${url}: ${(err as Error).message}`);
    return [];
  }
}

/** Append specs from a single baseline source (URL or local path), deduped by capability. */
async function addBaselineSource(
  source: string,
  allSpecs: BaselineSpec[],
  seenCapabilities: Set<string>,
  projectRoot: string
): Promise<void> {
  let specs: BaselineSpec[];
  if (source.startsWith('http://') || source.startsWith('https://')) {
    specs = await loadSpecsFromRemote(source);
  } else {
    const resolved = isAbsolute(source) ? source : resolve(projectRoot, source);
    if (!existsSync(resolved)) return;
    specs = await loadSpecsFromDir(resolved);
  }
  for (const spec of specs) {
    if (!seenCapabilities.has(spec.capability)) {
      seenCapabilities.add(spec.capability);
      allSpecs.push(spec);
    }
  }
}

/**
 * Load baselines with cross-repo/monorepo awareness:
 * 1. Local openspec/specs found by walking up parent dirs (closest wins).
 * 2. Config-specified baselines (paths or GitHub URLs) from openspec/review.yaml.
 * Capabilities dedupe on first occurrence (nearest source wins).
 */
export async function loadBaselinesWithConfig(
  projectRoot: string,
  configBaselines?: string | string[],
  _changeBaselines?: string | string[]
): Promise<BaselineSpec[]> {
  const allSpecs: BaselineSpec[] = [];
  const seenCapabilities = new Set<string>();

  const localSpecsDirs = await findSpecsDirs(projectRoot);
  for (const specsDir of localSpecsDirs) {
    const specs = await loadSpecsFromDir(specsDir);
    for (const spec of specs) {
      if (!seenCapabilities.has(spec.capability)) {
        seenCapabilities.add(spec.capability);
        allSpecs.push(spec);
      }
    }
  }

  const configBaselineList = configBaselines ? (Array.isArray(configBaselines) ? configBaselines : [configBaselines]) : [];
  for (const baseline of configBaselineList) {
    await addBaselineSource(baseline, allSpecs, seenCapabilities, projectRoot);
  }

  return allSpecs;
}

/** Load an OpenSpec change folder: openspec/changes/<name>/ */
export async function loadChange(projectRoot: string, changeName: string, configBaselines?: string | string[]): Promise<OpenSpecChange> {
  const dir = join(projectRoot, 'openspec', 'changes', changeName);
  const st = await stat(dir).catch(() => null);
  if (!st || !st.isDirectory()) {
    throw new Error(
      `OpenSpec change not found: ${dir}\nHint: run \`openspec list\` or check openspec/changes/. ` +
        `To review without a change, create one via \`openspec new change ${changeName}\`.`
    );
  }
  const proposal = (await readIfExists(join(dir, 'proposal.md'))) ?? '';
  const design = await readIfExists(join(dir, 'design.md'));
  const tasksRaw = (await readIfExists(join(dir, 'tasks.md'))) ?? '';
  const tasks: TaskItem[] = parseTasks(tasksRaw);

  const specFiles = await listFilesRecursive(join(dir, 'specs'));
  const requirements: Requirement[] = [];
  for (const f of specFiles) {
    const rel = f.slice(join(dir, 'specs').length + 1, -'/spec.md'.length);
    const raw = (await readIfExists(f)) ?? '';
    requirements.push(...parseDeltaSpec(raw, rel || 'default', f));
  }

  const baselineCaps = await listDirs(join(projectRoot, 'openspec', 'specs'));
  const baseline = await loadBaselinesWithConfig(projectRoot, configBaselines);

  return { name: changeName, dir, proposal, design, requirements, tasks, baselineCaps, baseline };
}

/**
 * Parse the baseline source of truth: openspec/specs/<capability>/spec.md.
 * Delta operation headers are meaningless here — only capability, id, text,
 * and scenarios are used (for drift mapping).
 */
export async function loadBaseline(projectRoot: string, configBaselines?: string | string[]): Promise<BaselineSpec[]> {
  return loadBaselinesWithConfig(projectRoot, configBaselines);
}

/** Load repo conventions for the style checker (AGENTS.md etc). */
export async function loadConventions(projectRoot: string): Promise<string> {
  for (const f of ['AGENTS.md', '.github/copilot-instructions.md', 'CONTRIBUTING.md']) {
    const raw = await readIfExists(join(projectRoot, f));
    if (raw) return raw.slice(0, 4000);
  }
  return '';
}
