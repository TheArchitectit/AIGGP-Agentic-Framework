import type { Diff, Finding, Severity } from '../types.js';
import { isGenerated } from '../checks/scope.js';
import { runToolChecks } from '../checks/external-tools.js';

/** A declarative template check evaluated against the diff. */
export interface TemplateCheck {
  id: string;
  severity: Severity;
  /** Match an added file path against this regex. */
  pathRe?: string;
  /** Match added-line content against this regex (only within path-matched files if pathRe set). */
  contentRe?: string;
  /** Match removed-line content (deleted exports, dropped flags, ...). Scoped by pathRe when set. */
  removedRe?: string;
  /**
   * Absence check: if any added file matches `pathRe` (or any file at all when
   * unset) but the `absentRe` pattern is nowhere to be found, emit the finding once.
   * `absentScope: 'diff'` searches all added lines in the diff (e.g. "no CHANGELOG
   * entry anywhere"); default `scoped` searches only the path-matched files.
   */
  absentRe?: string;
  absentScope?: 'scoped' | 'diff';
  /**
   * Absence checks only consider new files (isNew). For capability checks
   * (signal handling exists once per entry point) instead of per-change
   * demands (migrations needed per change).
   */
  newFilesOnly?: boolean;
  /** External tool check (semgrep, osv-scanner, trivy). */
  tool?: string;
  message: string;
  suggestion?: string;
}

export interface TemplateMatcher {
  /** Exact repo-relative file/dir that must exist, e.g. "project.godot". */
  file?: string;
  /** package.json dependency (or devDependency) that must be present. */
  dep?: string;
  /** package.json field that must exist, e.g. "bin". */
  pkgField?: string;
  /** Weight added to this template's score when the signal matches. */
  weight?: number;
}

export interface ProjectTemplate {
  id: string;
  label: string;
  description: string;
  matchers: TemplateMatcher[];
  /** Extra paragraph appended to the LLM rescore system prompt. */
  lens: string;
  checks: TemplateCheck[];
  /** Extra regexes recognizing test files for this archetype (beyond the default test patterns). */
  testFileRes?: string[];
  /** Hint appended when the tests checker finds no test coverage. */
  testHint?: string;
  /**
   * Check ids to skip (noise for this archetype, e.g. cli stdout).
   * Never applies to spec-compliance findings.
   */
  suppress?: string[];
  custom?: boolean;
}

export interface ResolvedTemplate {
  template: ProjectTemplate;
  /** Human-readable reason, e.g. "auto: project.godot found (+3)". */
  reason: string;
}

const DEFAULT_TEST_RE = /(\.test\.|\.spec\.|__tests__|test\/|tests\/|e2e)/;

function isTestPath(template: ProjectTemplate, path: string): boolean {
  if (DEFAULT_TEST_RE.test(path)) return true;
  return (template.testFileRes ?? []).some((s) => {
    try {
      return new RegExp(s).test(path);
    } catch {
      return false;
    }
  });
}

/** Extract the exported identifier from an export declaration line, if present. */
function exportIdentifier(line: string): string | null {
  const named = line.match(/^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|const|let|var|class|abstract\s+class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/);
  if (named) return named[1];
  const list = line.match(/^\s*export\s*\{([^}]*)\}/);
  if (list) {
    const first = list[1].split(',').map((s) => s.trim()).find((s) => /^[A-Za-z_$][\w$]*$/.test(s));
    return first ?? null;
  }
  return null;
}

/** True when the same export name reappears in the file's added lines. */
function exportReAdded(file: any, name: string): boolean {
  return file.addedLines.some((l: { text: string }) =>
    new RegExp(`export\\s+(?:default\\s+)?(?:async\\s+)?(?:function|const|let|var|class|abstract\\s+class|interface|type|enum)\\s+${name}\\b`).test(l.text) ||
    new RegExp(`export\\s*\\{[^}]*\\b${name}\\b`).test(l.text)
  );
}

export async function runTemplateChecks(template: ProjectTemplate, diff: Diff, projectRoot: string): Promise<Finding[]> {
  const findings: Finding[] = [];

  // Collect tool checks to run once per template
  const toolChecks = template.checks.filter((c) => c.tool);
  if (toolChecks.length > 0) {
    const toolIds = toolChecks.map((c) => c.tool!);
    try {
      const toolFindings = await runToolChecks(toolIds, projectRoot);
      findings.push(...toolFindings);
    } catch {
      // Tool failures are non-fatal
    }
  }

  for (const c of template.checks) {
    // Skip tool checks - they're handled above
    if (c.tool) continue;
    const pathRe = c.pathRe ? new RegExp(c.pathRe) : null;
    const contentRe = c.contentRe ? new RegExp(c.contentRe) : null;
    const removedRe = c.removedRe ? new RegExp(c.removedRe) : null;
    const inScope = pathRe ? diff.files.filter((f) => !f.isDeleted && pathRe.test(f.path)) : diff.files.filter((f) => !f.isDeleted);
    // Content-bearing checks skip test files: fixtures intentionally contain violations.
    const codeScope = inScope.filter((f) => !isTestPath(template, f.path));
    if (c.absentRe) {
      const scopeFiles = c.newFilesOnly ? codeScope.filter((f) => f.isNew) : codeScope;
      if (scopeFiles.length === 0) continue;
      const absentRe = new RegExp(c.absentRe);
      const haystack =
        c.absentScope === 'diff'
          ? diff.files.flatMap((f) => f.addedLines)
          : codeScope.flatMap((f) => f.addedLines);
      // Diff-wide absence also matches file paths (e.g. an added CHANGELOG.md
      // satisfies "changelog entry" even though its lines never say CHANGELOG).
      const covered =
        haystack.some((l) => absentRe.test(l.text)) ||
        (c.absentScope === 'diff' && diff.files.some((f) => absentRe.test(f.path)));
      if (!covered) {
        findings.push({
          severity: c.severity,
          category: 'template',
          checkId: `${template.id}/${c.id}`,
          file: scopeFiles[0].path,
          message: `[${template.id}] ${c.message}`,
          suggestion: c.suggestion
        });
      }
      continue;
    }
    if (removedRe) {
      const removedScope = (pathRe
        ? diff.files.filter((f) => pathRe.test(f.path))
        : diff.files
      ).filter((f) => !isTestPath(template, f.path) && !isGenerated(f.path));
      for (const f of removedScope) {
        for (const l of f.removedLines) {
          if (removedRe.test(l.text)) {
            // A removed export that is re-added under the same name in the same
            // file (signature/value change) is not a breaking API removal.
            const name = exportIdentifier(l.text);
            if (name && exportReAdded(f, name)) continue;
            findings.push({
              severity: c.severity,
              category: 'template',
              checkId: `${template.id}/${c.id}`,
              file: f.path,
              message: `[${template.id}] ${c.message} (${f.path})`,
              suggestion: c.suggestion
            });
            break; // one finding per file per check
          }
        }
      }
      continue;
    }
    for (const f of codeScope) {
      if (!contentRe) {
        findings.push({
          severity: c.severity,
          category: 'template',
          checkId: `${template.id}/${c.id}`,
          file: f.path,
          message: `[${template.id}] ${c.message} (${f.path})`,
          suggestion: c.suggestion
        });
        continue;
      }
      for (const l of f.addedLines) {
        if (contentRe.test(l.text)) {
          findings.push({
            severity: c.severity,
            category: 'template',
            checkId: `${template.id}/${c.id}`,
            file: f.path,
            line: l.n,
            message: `[${template.id}] ${c.message} (${f.path}:${l.n})`,
            suggestion: c.suggestion
          });
          break; // one finding per file per check
        }
      }
    }
  }
  return findings.slice(0, 30);
}
