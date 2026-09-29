import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { isAbsolute, relative } from 'node:path';
import type { Finding, Severity } from '../types.js';

const execFileP = promisify(execFile);

type ParseFn = (raw: string, projectRoot: string) => Finding[];

export interface ToolCheckConfig {
  /** Tool name: 'semgrep' | 'osv-scanner' | 'trivy' */
  tool: 'semgrep' | 'osv-scanner' | 'trivy';
  /** Arguments to pass to the tool ({projectRoot} is substituted). */
  args: string[];
  /** Parse the tool's JSON stdout into findings. */
  parse: ParseFn;
  /** Category for findings. */
  category: 'security' | 'dependency';
  /** Check ID for findings. */
  checkId: string;
}

function clampSeverity(s: string | undefined, fallback: Severity): Severity {
  switch ((s ?? '').toUpperCase()) {
    case 'CRITICAL': return 'blocker';
    case 'ERROR':
    case 'HIGH': return 'high';
    case 'WARNING':
    case 'MODERATE':
    case 'MEDIUM': return 'medium';
    case 'INFO':
    case 'LOW': return 'low';
    default: return fallback;
  }
}

/** Strip an absolute prefix so scanner paths anchor against the diff. */
function relativize(p: string, projectRoot: string): string {
  if (!p) return p;
  if (!isAbsolute(p)) return p;
  const rel = relative(projectRoot, p);
  return rel.startsWith('..') ? p : rel;
}

interface SemgrepResult {
  check_id?: string;
  path?: string;
  start?: { line?: number };
  extra?: { message?: string; severity?: string };
}

/** semgrep --json: results[].{check_id, path, start.line, extra.message, extra.severity} */
export function parseSemgrep(raw: string, _projectRoot: string): Finding[] {
  let parsed: { results?: SemgrepResult[] };
  try { parsed = JSON.parse(raw); } catch { return []; }
  const out: Finding[] = [];
  for (const r of parsed.results ?? []) {
    if (!r.path || !r.extra?.message) continue;
    out.push({
      severity: clampSeverity(r.extra.severity, 'medium'),
      category: 'security',
      checkId: 'semgrep-security',
      file: r.path,
      line: r.start?.line,
      message: `Semgrep (${r.check_id ?? 'unknown'}): ${r.extra.message}`
    });
  }
  return out;
}

interface TrivyResult {
  Target?: string;
  Vulnerabilities?: {
    VulnerabilityID?: string;
    PkgName?: string;
    Severity?: string;
    Title?: string;
  }[];
  Secrets?: {
    RuleID?: string;
    Category?: string;
    Severity?: string;
    Title?: string;
    StartLine?: number;
    EndLine?: number;
    Match?: string;
  }[];
}

/** trivy fs --format json: Results[].Vulnerabilities[] and Results[].Secrets[] */
export function parseTrivy(raw: string, projectRoot: string): Finding[] {
  let parsed: { Results?: TrivyResult[] };
  try { parsed = JSON.parse(raw); } catch { return []; }
  const out: Finding[] = [];
  for (const r of parsed.Results ?? []) {
    const file = relativize(r.Target ?? '', projectRoot);
    for (const v of r.Vulnerabilities ?? []) {
      if (!v.VulnerabilityID) continue;
      out.push({
        severity: clampSeverity(v.Severity, 'medium'),
        category: 'dependency',
        checkId: 'trivy-fs',
        file: file || undefined,
        line: undefined,
        message: `Trivy ${v.VulnerabilityID} in ${v.PkgName ?? 'unknown pkg'}: ${v.Title ?? 'no title'}`
      });
    }
    for (const s of r.Secrets ?? []) {
      if (!s.RuleID) continue;
      out.push({
        severity: clampSeverity(s.Severity, 'high'),
        category: 'security',
        checkId: 'trivy-secrets',
        file: file || undefined,
        line: s.StartLine,
        message: `Trivy secret: ${s.Title} (${s.RuleID})${s.Match ? ` - ${s.Match.slice(0, 100)}` : ''}`
      });
    }
  }
  return out;
}

interface OsvVulnerability {
  id?: string;
  summary?: string;
  database_specific?: { severity?: string };
  details?: string;
  aliases?: string[];
  modified?: string;
  published?: string;
  references?: { type?: string; url?: string }[];
  schema_version?: string;
  severity?: { score?: string; type?: string }[];
  affected?: { package?: { ecosystem?: string; name?: string; purl?: string }; ranges?: { events?: { introduced?: string; fixed?: string }[]; type?: string }[] }[];
}

interface OsvPackage {
  package?: { name?: string; version?: string; ecosystem?: string };
  dependency_groups?: string[];
  groups?: {
    ids?: string[];
    aliases?: string[];
    max_severity?: string;
    vulnerabilities?: OsvVulnerability[];
  }[];
  vulnerabilities?: OsvVulnerability[];
}

/** osv-scanner --format=json: results[].packages[].groups[].vulnerabilities[] or results[].packages[].vulnerabilities[] */
export function parseOsv(raw: string, projectRoot: string): Finding[] {
  let parsed: {
    results?: {
      source?: { path?: string; type?: string };
      packages?: OsvPackage[];
    }[];
  };
  try { parsed = JSON.parse(raw); } catch { return []; }
  const out: Finding[] = [];
  for (const result of parsed.results ?? []) {
    const file = relativize(result.source?.path ?? '', projectRoot);
    for (const pkg of result.packages ?? []) {
      const pkgName = pkg.package?.name ?? 'unknown pkg';
      const pkgVersion = pkg.package?.version ?? '?';
      // Handle new format with groups
      for (const group of pkg.groups ?? []) {
        for (const v of group.vulnerabilities ?? []) {
          if (!v.id) continue;
          out.push({
            severity: clampSeverity(v.database_specific?.severity ?? v.severity?.[0]?.score, 'medium'),
            category: 'dependency',
            checkId: 'osv-scanner',
            file: file || undefined,
            message: `OSV ${v.id} in ${pkgName}@${pkgVersion}: ${v.summary ?? v.details?.slice(0, 200) ?? 'no summary'}`
          });
        }
      }
      // Handle legacy format with direct vulnerabilities
      for (const v of pkg.vulnerabilities ?? []) {
        if (!v.id) continue;
        out.push({
          severity: clampSeverity(v.database_specific?.severity ?? v.severity?.[0]?.score, 'medium'),
          category: 'dependency',
          checkId: 'osv-scanner',
          file: file || undefined,
          message: `OSV ${v.id} in ${pkgName}@${pkgVersion}: ${v.summary ?? v.details?.slice(0, 200) ?? 'no summary'}`
        });
      }
    }
  }
  return out;
}

/** Built-in tool configurations. */
export const BUILTIN_TOOLS: Record<string, ToolCheckConfig> = {
  'semgrep-security': {
    tool: 'semgrep',
    args: ['scan', '--json', '--quiet', '{projectRoot}'],
    parse: parseSemgrep,
    category: 'security',
    checkId: 'semgrep-security'
  },
  'semgrep-secrets': {
    tool: 'semgrep',
    args: ['scan', '--config=p/secrets', '--json', '--quiet', '{projectRoot}'],
    parse: parseSemgrep,
    category: 'security',
    checkId: 'semgrep-secrets'
  },
  'osv-scanner': {
    tool: 'osv-scanner',
    args: ['scan', '--format=json', '{projectRoot}'],
    parse: parseOsv,
    category: 'dependency',
    checkId: 'osv-scanner'
  },
  'trivy-fs': {
    tool: 'trivy',
    args: ['fs', '--format', 'json', '--quiet', '{projectRoot}'],
    parse: parseTrivy,
    category: 'dependency',
    checkId: 'trivy-fs'
  }
};

/** Run one tool and parse its JSON output. Missing/failed tools yield no findings (opt-in, fail-open). */
export async function runToolCheck(
  config: ToolCheckConfig,
  projectRoot: string
): Promise<Finding[]> {
  let stdout: string;
  try {
    const args = config.args.map((a) => a.replace('{projectRoot}', projectRoot));
    ({ stdout } = await execFileP(config.tool, args, {
      cwd: projectRoot,
      maxBuffer: 32 * 1024 * 1024,
      timeout: 120_000
    }));
  } catch (err) {
    const e = err as { stdout?: string; code?: string };
    // Some tools exit non-zero while still emitting findings JSON (osv-scanner
    // exits 1 when vulns are found) — parse stdout if it looks usable.
    if (!e.stdout || !e.stdout.trim().startsWith('{')) return [];
    stdout = e.stdout;
  }
  try {
    return config.parse(stdout, projectRoot).slice(0, 50);
  } catch {
    return [];
  }
}

/** Run all enabled tool checks for a template. */
export async function runToolChecks(
  toolIds: string[],
  projectRoot: string
): Promise<Finding[]> {
  const findings: Finding[] = [];
  for (const id of toolIds) {
    const config = BUILTIN_TOOLS[id];
    if (!config) continue;
    findings.push(...(await runToolCheck(config, projectRoot)));
  }
  return findings;
}
