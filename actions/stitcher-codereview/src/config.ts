import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { parse as parseYaml } from 'yaml';
import type { Severity } from './types.js';

export interface FileLLMConfig {
  mode?: string;
  provider?: string;
  model?: string;
  'base-url'?: string;
  weight?: number | string;
  maxConcurrency?: number | string;
  maxRetries?: number | string;
}

export interface FileConfig {
  'fail-on'?: string;
  template?: string;
  only?: string | string[];
  format?: string;
  llm?: FileLLMConfig;
  'sarif-file'?: string;
  disable?: string[];
  severities?: Record<string, string>;
  post?: string;
  scan?: string;
  ignore?: string | string[];
  include?: string | string[];
  rules?: Record<string, { severity?: string; paths?: string | string[] }>;
  baselines?: string | string[];
  'max-line-length'?: number | string;
  'covered-at'?: number | string;
  'partial-at'?: number | string;
  'max-findings'?: number | string;
}

export interface LoadedConfig {
  config: FileConfig;
  path: string | null;
  warnings: string[];
}

const KNOWN_KEYS = new Set([
  'fail-on', 'template', 'only', 'format', 'llm', 'sarif-file', 'disable', 'severities', 'post', 'scan',
  'ignore', 'include', 'rules', 'baselines', 'max-line-length', 'covered-at', 'partial-at', 'max-findings'
]);
const FAIL_LEVELS = ['blocker', 'high', 'medium', 'low', 'never'];
const SEVERITIES: Severity[] = ['blocker', 'high', 'medium', 'low', 'info'];

function fail(msg: string): never {
  throw new Error(`Invalid review config: ${msg}`);
}

/** Validate raw parsed YAML into a FileConfig; throws on invalid values. */
export function validateConfig(raw: unknown, path: string): { config: FileConfig; warnings: string[] } {
  if (raw === null || raw === undefined) return { config: {}, warnings: [] };
  if (typeof raw !== 'object' || Array.isArray(raw)) fail(`${path}: top level must be a mapping`);
  const obj = raw as Record<string, unknown>;
  const warnings: string[] = [];
  for (const k of Object.keys(obj)) {
    if (!KNOWN_KEYS.has(k)) warnings.push(`${path}: unknown key "${k}" ignored`);
  }
  const config: FileConfig = {};
  if (obj['fail-on'] !== undefined) {
    if (typeof obj['fail-on'] !== 'string' || !FAIL_LEVELS.includes(obj['fail-on'])) {
      fail(`${path}: "fail-on" wants ${FAIL_LEVELS.join('/')}`);
    }
    config['fail-on'] = obj['fail-on'] as string;
  }
  for (const k of ['template', 'format', 'sarif-file'] as const) {
    if (obj[k] !== undefined) {
      if (typeof obj[k] !== 'string') fail(`${path}: "${k}" wants a string`);
      config[k] = obj[k] as string;
    }
  }
  if (obj.post !== undefined) {
    if (typeof obj.post !== 'string' || !['none', 'github', 'gitlab', 'vcs'].includes(obj.post)) {
      fail(`${path}: "post" wants none|github|gitlab|vcs`);
    }
    config.post = obj.post as string;
  }
  if (obj.only !== undefined) {
    if (typeof obj.only !== 'string' && !Array.isArray(obj.only)) fail(`${path}: "only" wants a string or list`);
    config.only = obj.only as string | string[];
  }
  if (obj.llm !== undefined) {
    if (typeof obj.llm !== 'object' || obj.llm === null || Array.isArray(obj.llm)) fail(`${path}: "llm" wants a mapping`);
    const llm = obj.llm as Record<string, unknown>;
    const out: FileLLMConfig = {};
    for (const k of ['mode', 'provider', 'model', 'base-url'] as const) {
      if (llm[k] !== undefined) {
        if (typeof llm[k] !== 'string') fail(`${path}: "llm.${k}" wants a string`);
        out[k] = llm[k] as string;
      }
    }
    if (llm.weight !== undefined) {
      const w = typeof llm.weight === 'string' ? parseFloat(llm.weight) : llm.weight;
      if (typeof w !== 'number' || !Number.isFinite(w) || w < 0 || w > 1) {
        fail(`${path}: "llm.weight" wants a number 0..1`);
      }
      out.weight = w;
    }
    for (const k of ['maxConcurrency', 'maxRetries'] as const) {
      if (llm[k] !== undefined) {
        const n = typeof llm[k] === 'string' ? parseInt(llm[k] as string, 10) : llm[k];
        const max = k === 'maxConcurrency' ? 32 : 10;
        if (typeof n !== 'number' || !Number.isFinite(n) || n < 1 || n > max) {
          fail(`${path}: "llm.${k}" wants an integer 1..${max}`);
        }
        (out as Record<string, unknown>)[k] = n;
      }
    }
    if (out.mode !== undefined && !['off', 'auto', 'require', 'gap'].includes(out.mode)) {
      fail(`${path}: "llm.mode" wants off|auto|require|gap`);
    }
    config.llm = out;
  }
  if (obj.disable !== undefined) {
    if (!Array.isArray(obj.disable) || !obj.disable.every((d) => typeof d === 'string')) {
      fail(`${path}: "disable" wants a list of check ids`);
    }
    config.disable = obj.disable as string[];
  }
  if (obj.severities !== undefined) {
    if (typeof obj.severities !== 'object' || obj.severities === null || Array.isArray(obj.severities)) {
      fail(`${path}: "severities" wants a mapping of check id to level`);
    }
    for (const [k, v] of Object.entries(obj.severities as Record<string, unknown>)) {
      if (typeof v !== 'string' || !SEVERITIES.includes(v as Severity)) {
        fail(`${path}: "severities.${k}" wants ${SEVERITIES.join('/')}`);
      }
    }
    config.severities = obj.severities as Record<string, string>;
  }
  if (obj.scan !== undefined) {
    const v = typeof obj.scan === 'boolean' ? String(obj.scan) : obj.scan;
    if (typeof v !== 'string' || !['true', 'false', 'repository', 'off'].includes(v)) {
      fail(`${path}: "scan" wants true|false|repository|off`);
    }
    // Normalize: true -> repository, false/off -> off-equivalent handled by caller.
    config.scan = v === 'true' ? 'repository' : v === 'false' ? 'off' : (v as string);
  }
  if (obj.ignore !== undefined) {
    if (typeof obj.ignore !== 'string' && !Array.isArray(obj.ignore)) {
      fail(`${path}: "ignore" wants a string or list of glob patterns`);
    }
    config.ignore = obj.ignore as string | string[];
  }
  if (obj.include !== undefined) {
    if (typeof obj.include !== 'string' && !Array.isArray(obj.include)) {
      fail(`${path}: "include" wants a string or list of glob patterns`);
    }
    config.include = obj.include as string | string[];
  }
  if (obj.rules !== undefined) {
    if (typeof obj.rules !== 'object' || obj.rules === null || Array.isArray(obj.rules)) {
      fail(`${path}: "rules" wants a mapping of check-id to { severity?, paths? }`);
    }
    for (const [checkId, rule] of Object.entries(obj.rules as Record<string, unknown>)) {
      if (typeof rule !== 'object' || rule === null || Array.isArray(rule)) {
        fail(`${path}: "rules.${checkId}" wants an object`);
      }
      const r = rule as Record<string, unknown>;
      if (r.severity !== undefined && (typeof r.severity !== 'string' || !(SEVERITIES as string[]).includes(r.severity as string))) {
        fail(`${path}: "rules.${checkId}.severity" wants ${SEVERITIES.join('/')}`);
      }
      if (r.paths !== undefined && typeof r.paths !== 'string' && !Array.isArray(r.paths)) {
        fail(`${path}: "rules.${checkId}.paths" wants a string or list`);
      }
    }
    config.rules = obj.rules as Record<string, { severity?: string; paths?: string | string[] }>;
  }
  if (obj.baselines !== undefined) {
    if (typeof obj.baselines !== 'string' && !Array.isArray(obj.baselines)) {
      fail(`${path}: "baselines" wants a string or list of paths/URLs`);
    }
    config.baselines = obj.baselines as string | string[];
  }
  // Fine-tuning knobs: number-typed, each with a bounded range.
  const numKeys: [string, number, number][] = [
    ['max-line-length', 20, 10_000],
    ['covered-at', 0, 1],
    ['partial-at', 0, 1],
    ['max-findings', 1, 100_000]
  ];
  for (const [key, min, max] of numKeys) {
    const rawVal = obj[key];
    if (rawVal === undefined) continue;
    const n = typeof rawVal === 'string' ? parseFloat(rawVal) : rawVal;
    if (typeof n !== 'number' || !Number.isFinite(n) || n < min || n > max) {
      fail(`${path}: "${key}" wants a number ${min}..${max}`);
    }
    (config as Record<string, unknown>)[key] = n;
  }
  return { config, warnings };
}

/** Merge configs with later ones taking precedence (shallow merge for objects). */
function mergeConfigs(base: FileConfig, override: FileConfig): FileConfig {
  const out: FileConfig = { ...base };
  for (const [k, v] of Object.entries(override)) {
    if (v === undefined) continue;
    const key = k as keyof FileConfig;
    // Deep merge known object fields
    if (key === 'llm' && base.llm && typeof v === 'object') {
      out.llm = { ...base.llm, ...(v as FileLLMConfig) };
    } else if (key === 'rules' && base.rules && typeof v === 'object') {
      out.rules = { ...base.rules, ...(v as Record<string, { severity?: string; paths?: string | string[] }>) };
    } else {
      out[key] = v;
    }
  }
  return out;
}

/** Load user config from ~/.config/stitcher-codereview/config.yaml */
async function loadUserConfig(): Promise<FileConfig> {
  if (process.env.STITCHER_CODEREVIEW_NO_USER_CONFIG === '1') return {};
  const { homedir } = await import('node:os');
  const { join } = await import('node:path');
  const { readFile } = await import('node:fs/promises');
  const path = join(homedir(), '.config', 'stitcher-codereview', 'config.yaml');
  try {
    const raw = await readFile(path, 'utf8');
    const { config, warnings } = validateConfig(parseYaml(raw), path);
    for (const w of warnings) console.error(`stitcher-codereview: warning: ${w}`);
    return config;
  } catch {
    return {};
  }
}

/**
 * Load review config with layering: user config → repo config → CLI flags.
 * `explicit` is the --config value ('auto' or undefined resolves openspec/review.yaml,
 * silently absent; an explicit path must exist).
 */
export async function loadConfig(root: string, explicit?: string): Promise<LoadedConfig> {
  const userCfg = await loadUserConfig();

  if (!explicit || explicit === 'auto') {
    const auto = join(root, 'openspec', 'review.yaml');
    const raw = await readFile(auto, 'utf8').catch(() => null);
    if (raw === null) return { config: mergeConfigs(userCfg, {}), path: null, warnings: [] };
    try {
      const { config: repoCfg, warnings } = validateConfig(parseYaml(raw), auto);
      return { config: mergeConfigs(userCfg, repoCfg), path: auto, warnings };
    } catch (err) {
      throw new Error((err as Error).message);
    }
  }
  const path = resolve(root, explicit);
  const raw = await readFile(path, 'utf8').catch(() => null);
  if (raw === null) throw new Error(`Config not found: ${path} (pass --config auto to skip)`);
  const { config: explicitCfg, warnings } = validateConfig(parseYaml(raw), path);
  return { config: mergeConfigs(userCfg, explicitCfg), path, warnings };
}
