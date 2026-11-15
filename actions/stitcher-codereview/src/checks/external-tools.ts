import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { promisify } from 'node:util';
import { isAbsolute, relative } from 'node:path';
import type { Finding, Severity, ToolProvenance } from '../types.js';
import { evidenceRefFor } from '../evidenceRef.js';
import { gitHead, hashTree } from '../evidence.js';
import { getAllTrackedFiles } from './scan.js';

const execFileP = promisify(execFile);

type ParseFn = (raw: string, projectRoot: string) => Finding[];

export interface ToolCheckConfig {
  /** Tool name: 'semgrep' | 'osv-scanner' | 'trivy' | adapter ids. */
  tool: string;
  /** Identity recorded on every ingested finding, e.g. `guardrails-scan.mjs`. */
  displayName?: string;
  /** Arguments to pass to the tool ({projectRoot} is substituted). */
  args: string[];
  /** Parse the tool's JSON stdout into findings. */
  parse: ParseFn;
  /** Category for findings. */
  category: Finding['category'];
  /** Check ID prefix for findings. */
  checkId: string;
  /** Arguments that print the tool version (default ['--version']). */
  versionArgs?: string[];
  /** Scanner file whose content digest is the version (for in-repo tools). */
  versionFromFile?: string;
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

/** sha256 hex of a string (raw-output and input digests). */
export function sha256Text(text: string): string {
  return createHash('sha256').update(text, 'utf8').digest('hex');
}

/**
 * Stamp adapter findings with their source identity. A finding that cannot
 * name its tool and version is not ingested at all: identity is the whole
 * anti-laundering contract (ADR-004, Fixture G).
 */
export function stampFindings(findings: Finding[], prov: ToolProvenance): Finding[] {
  const ref = evidenceRefFor(['external', prov.name, prov.version, prov.rawOutputDigest]);
  return findings.map((f) => ({
    ...f,
    tool: { ...prov },
    evidenceRef: f.evidenceRef ?? ref
  }));
}

/** Validate that an ingested finding still carries a complete identity. */
export function missingIdentity(f: Pick<Finding, 'tool' | 'evidenceRef'>): string[] {
  const missing: string[] = [];
  if (!f.tool?.name) missing.push('tool.name');
  if (!f.tool?.version) missing.push('tool.version');
  if (!f.tool?.rawOutputDigest) missing.push('tool.rawOutputDigest');
  if (!f.evidenceRef) missing.push('evidenceRef');
  return missing;
}

/** Bounded tree digest: HEAD plus the tracked-file hashes, as the tool's input. */
export async function treeInputDigest(projectRoot: string): Promise<string> {
  try {
    const files = (await getAllTrackedFiles(projectRoot)).slice(0, 5000);
    const tree = await hashTree(projectRoot, files);
    return sha256Text(`${(await gitHead(projectRoot)) ?? 'no-git'}\n${tree ?? 'empty-tree'}`);
  } catch {
    return sha256Text(`unavailable:${projectRoot}`);
  }
}

async function toolVersion(config: ToolCheckConfig, projectRoot: string): Promise<string> {
  if (config.versionFromFile) {
    try {
      const { readFile } = await import('node:fs/promises');
      const { join } = await import('node:path');
      const buf = await readFile(join(projectRoot, config.versionFromFile));
      return `sha256:${createHash('sha256').update(buf).digest('hex').slice(0, 12)}`;
    } catch {
      return 'unknown';
    }
  }
  try {
    const { stdout } = await execFileP(config.tool, config.versionArgs ?? ['--version'], {
      cwd: projectRoot,
      timeout: 5000,
      maxBuffer: 1024 * 1024
    });
    const first = stdout.split('\n').map((l) => l.trim()).filter(Boolean)[0] ?? '';
    return first.slice(0, 200) || 'unknown';
  } catch {
    return 'unknown';
  }
}

/** Resolve the provenance of one adapter run (identity, version, input and output digests). */
export async function resolveProvenance(
  config: ToolCheckConfig,
  projectRoot: string,
  rawOutput: string
): Promise<ToolProvenance> {
  return {
    name: config.displayName ?? config.tool,
    version: await toolVersion(config, projectRoot),
    vendor: config.versionFromFile,
    inputDigest: await treeInputDigest(projectRoot),
    rawOutputDigest: sha256Text(rawOutput)
  };
}

interface GuardrailsLine {
  severity: string;
  ruleId: string;
  file: string;
  line: number;
  message: string;
}

const GUARDRAILS_LINE = /^\[GUARDRAILS\]\[([a-z]+)\]\s+([A-Z0-9-]+)\s+(.+?):(\d+)\s+.\s+(.*)$/;

/** Parse guardrails-scan.mjs console output (`[GUARDRAILS][sev] RULE file:line - message`). */
export function parseGuardrailsScan(raw: string, _projectRoot: string, prov?: ToolProvenance): Finding[] {
  const hits: GuardrailsLine[] = [];
  for (const line of raw.split('\n')) {
    const m = GUARDRAILS_LINE.exec(line.trim());
    if (!m) continue;
    hits.push({ severity: m[1], ruleId: m[2], file: m[3], line: Number(m[4]), message: m[5] });
  }
  const findings: Finding[] = hits.map((h) => ({
    severity: clampSeverity(h.severity, 'medium'),
    category: h.severity === 'warning' ? 'style' : 'security',
    // Source-attributed check id: never renamed to an AIGGP-native check.
    checkId: `guardrails-scan/${h.ruleId}`,
    file: h.file,
    line: Number.isFinite(h.line) && h.line > 0 ? h.line : undefined,
    message: `guardrails-scan ${h.ruleId}: ${h.message}`
  }));
  return prov ? stampFindings(findings, prov) : findings;
}

/** Parse secret-scan-declared.sh output (one repository URL per line). */
export function parseSecretScanDeclared(raw: string, _projectRoot: string, prov?: ToolProvenance): Finding[] {
  const findings: Finding[] = [];
  for (const line of raw.split('\n')) {
    const url = line.trim();
    if (!url || url.startsWith('#')) continue;
    if (!/^https?:\/\//.test(url)) continue;
    findings.push({
      severity: 'info',
      category: 'security',
      checkId: 'secret-scan-declared/declared-repo',
      message: `Repository declared for the fleet secret scan: ${url}`
    });
  }
  return prov ? stampFindings(findings, prov) : findings;
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
  },
  // Q12.2 first adapter combo: the per-repo scanner and the fleet-wide
  // declaration sweep. Both keep their own names; neither becomes an AIGGP check.
  'guardrails-scan': {
    tool: 'node',
    displayName: 'guardrails-scan.mjs',
    args: ['scripts/guardrails-scan.mjs'],
    parse: (raw, root) => parseGuardrailsScan(raw, root),
    category: 'security',
    checkId: 'guardrails-scan',
    versionFromFile: 'scripts/guardrails-scan.mjs'
  },
  'secret-scan-declared': {
    tool: 'bash',
    displayName: 'secret-scan-declared.sh',
    args: ['scripts/secret-scan-declared.sh', '--out', '/dev/stdout'],
    parse: (raw, root) => parseSecretScanDeclared(raw, root),
    category: 'security',
    checkId: 'secret-scan-declared',
    versionFromFile: 'scripts/secret-scan-declared.sh'
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
    const e = err as { stdout?: string; stderr?: string; code?: string };
    // Some tools exit non-zero while still emitting findings (osv-scanner
    // exits 1 when vulns are found; guardrails-scan prints findings to
    // stderr). Parse whatever the tool actually produced.
    const produced = [e.stdout, e.stderr]
      .filter((s): s is string => Boolean(s && s.trim()))
      .join('\n');
    if (!produced) return [];
    stdout = produced;
  }
  try {
    const parsed = config.parse(stdout, projectRoot).slice(0, 50);
    if (parsed.length === 0) return [];
    // Identity-preserving ingestion (Stage 8): tool name, version, input
    // digest and raw-output digest ride every finding; the raw output is
    // referenced, never re-labeled.
    const prov = await resolveProvenance(config, projectRoot, stdout);
    return stampFindings(parsed, prov);
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
