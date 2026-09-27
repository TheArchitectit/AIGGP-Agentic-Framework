import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { ProjectTemplate, TemplateCheck } from './types.js';
import type { Severity } from '../types.js';

const SECTIONS = ['Match', 'Lens', 'Checks', 'Tests'] as const;

/**
 * Custom template format (`openspec/review-templates/<id>.md`):
 *
 *   # Label
 *   Optional description paragraph.
 *   ## Match
 *   file: project.godot
 *   dep: bevy
 *   pkgField: bin
 *   ## Lens
 *   Extra prompt paragraph for the LLM rescore...
 *   ## Checks
 *   medium | path | \.psd$ | Raw asset added | Compress it
 *   low | line | Instantiate\( | Runtime instantiate | Pool it
 *   low | line | foo | Foo used | Bar it | (cli|main)
 *
 * Check columns: severity | target | pattern | message | suggestion? | scope? | scope-mode?
 * Targets: path (added file path), line (added lines), removed (removed lines),
 *   absent (fire when pattern is missing). scope is a path regex narrowing line/
 *   removed/absent checks; for absent, scope-mode `diff` searches the whole diff
 *   instead of just the scope-matched files (default `scoped`), and `new`
 *   restricts the trigger to new files (existing entries are assumed handled).
 *   ## Tests
 *   pattern: EditMode
 *   hint: Unity projects should cover EditMode and PlayMode tests.
 */
export function parseCustomTemplate(id: string, raw: string): ProjectTemplate {
  const label = raw.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? id;
  const blocks = splitSections(raw);
  const description =
    raw
      .slice(raw.indexOf('\n') + 1)
      .split(/^##\s/m)[0]
      ?.split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .join(' ') ?? '';

  const matchers = (blocks.Match ?? '')
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#') && !l.startsWith('<!--'))
    .map((l) => {
      const m = l.match(/^(file|dep|pkgField)\s*:\s*(.+)$/);
      if (!m) throw new Error(`Bad Match line in template ${id}: "${l}" (want "file:|dep:|pkgField:")`);
      return { [m[1]]: m[2].trim(), weight: 3 } as ProjectTemplate['matchers'][number];
    });

  const lens = (blocks.Lens ?? '').trim();

  const checks: TemplateCheck[] = (blocks.Checks ?? '')
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#') && !l.startsWith('<!--'))
    .map((l, i) => parseCheckLine(id, i, l));

  const { testFileRes, testHint } = parseTestsBlock(blocks.Tests ?? '');

  return { id, label, description, matchers, lens, checks, testFileRes, testHint, custom: true };
}

function parseTestsBlock(raw: string): { testFileRes?: string[]; testHint?: string } {
  const patterns: string[] = [];
  let hint: string | undefined;
  for (const line of raw.split('\n').map((l) => l.trim().replace(/^-\s+/, ''))) {
    if (!line || line.startsWith('#') || line.startsWith('<!--')) continue;
    const m = line.match(/^(pattern|hint)\s*:\s*(.+)$/);
    if (!m) throw new Error(`Bad Tests line: "${line}" (want "pattern: <regex>" or "hint: <text>")`);
    if (m[1] === 'pattern') {
      try {
        void new RegExp(m[2].trim());
      } catch {
        throw new Error(`Bad Tests pattern regex: "${m[2].trim()}"`);
      }
      patterns.push(m[2].trim());
    } else {
      hint = m[2].trim();
    }
  }
  return {
    testFileRes: patterns.length > 0 ? patterns : undefined,
    testHint: hint
  };
}

function splitSections(raw: string): Partial<Record<(typeof SECTIONS)[number], string>> {
  const out: Partial<Record<(typeof SECTIONS)[number], string>> = {};
  const parts = raw.split(/^##\s+(.+?)\s*$/m);
  for (let i = 1; i < parts.length; i += 2) {
    const name = parts[i].trim() as (typeof SECTIONS)[number];
    if ((SECTIONS as readonly string[]).includes(name)) out[name] = parts[i + 1] ?? '';
  }
  return out;
}

const SEVERITIES: Severity[] = ['blocker', 'high', 'medium', 'low', 'info'];

function parseCheckLine(templateId: string, i: number, line: string): TemplateCheck {
  // Allow leading "- " list markers. Split on unescaped pipes so patterns
  // like (Assets|Packages) survive; write \| for a literal pipe.
  const clean = line.replace(/^-\s+/, '');
  const parts = clean.split(/(?<!\\)\|/).map((p) => p.replace(/\\\|/g, '|').trim());
  if (parts.length < 4) {
    throw new Error(
      `Bad Checks line ${i + 1} in template ${templateId}: ` +
        `"severity | path|line|removed|absent | pattern | message [| suggestion [| scope [| scoped|diff|new]]]"`
    );
  }
  const [sev, target, pattern, message, suggestion, scope, scopeMode] = parts;
  if (!SEVERITIES.includes(sev as Severity)) {
    throw new Error(`Bad severity "${sev}" in template ${templateId} (want ${SEVERITIES.join('/')})`);
  }
  try {
    void new RegExp(pattern);
    if (scope) void new RegExp(scope);
  } catch {
    throw new Error(
      `Bad regex in template ${templateId} line ${i + 1}: "${line}" (escape literal pipes as \\|)`
    );
  }
  if (target === 'path') {
    return { id: `custom-${i}`, severity: sev as Severity, pathRe: pattern, message, suggestion: suggestion || undefined };
  }
  if (target === 'line') {
    return {
      id: `custom-${i}`,
      severity: sev as Severity,
      contentRe: pattern,
      pathRe: scope || undefined,
      message,
      suggestion: suggestion || undefined
    };
  }
  if (target === 'removed') {
    return {
      id: `custom-${i}`,
      severity: sev as Severity,
      removedRe: pattern,
      pathRe: scope || undefined,
      message,
      suggestion: suggestion || undefined
    };
  }
  if (target === 'absent') {
    if (scopeMode && scopeMode !== 'scoped' && scopeMode !== 'diff' && scopeMode !== 'new') {
      throw new Error(`Bad scope-mode "${scopeMode}" in template ${templateId} (want scoped|diff|new)`);
    }
    return {
      id: `custom-${i}`,
      severity: sev as Severity,
      absentRe: pattern,
      pathRe: scope || undefined,
      absentScope: scopeMode === 'diff' ? 'diff' : undefined,
      newFilesOnly: scopeMode === 'new',
      message,
      suggestion: suggestion || undefined
    };
  }
  if (target === 'tool') {
    return {
      id: `custom-${i}`,
      severity: sev as Severity,
      tool: pattern, // tool name: semgrep|osv-scanner|trivy
      message,
      suggestion: suggestion || undefined
    };
  }
  throw new Error(`Bad target "${target}" in template ${templateId} (want path|line|removed|absent|tool)`);
}

/** Load `openspec/review-templates/*.md`. Invalid files are skipped with a warning, never fatal. */
export async function loadCustomTemplates(projectRoot: string): Promise<{ templates: ProjectTemplate[]; warnings: string[] }> {
  const dir = join(projectRoot, 'openspec', 'review-templates');
  const templates: ProjectTemplate[] = [];
  const warnings: string[] = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return { templates, warnings };
  }
  for (const e of entries) {
    if (!e.isFile() || !e.name.endsWith('.md')) continue;
    const id = e.name.slice(0, -3);
    try {
      const raw = await readFile(join(dir, e.name), 'utf8');
      templates.push(parseCustomTemplate(id, raw));
    } catch (err) {
      warnings.push(`Skipping review template ${e.name}: ${(err as Error).message}`);
    }
  }
  return { templates, warnings };
}
