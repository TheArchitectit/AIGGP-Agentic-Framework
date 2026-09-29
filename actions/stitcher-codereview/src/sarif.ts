import { readFileSync } from 'node:fs';
import type { Finding, ReviewResult, Severity } from './types.js';
import { checkMeta } from './checks/catalog.js';

function toolVersion(): string {
  try {
    // src/../package.json in dev, dist/../package.json after build
    const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as { version?: string };
    return pkg.version ?? '0.0.0';
  } catch {
    return '0.0.0';
  }
}

const LEVEL: Record<Severity, 'error' | 'warning' | 'note'> = {
  blocker: 'error',
  high: 'error',
  medium: 'warning',
  low: 'note',
  info: 'note'
};

function findingText(f: Finding): string {
  const req = f.requirementId ? `[req: ${f.requirementId}] ` : '';
  const loc = f.file ? ` (${f.file}${f.line ? ':' + f.line : ''})` : '';
  const tip = f.suggestion ? `\nSuggestion: ${f.suggestion}` : '';
  return `${req}${f.message}${loc}${tip}`;
}

/** One SARIF rule per distinct check: `stitcher-codereview/<category>/<checkId>`. */
export function ruleIdFor(f: Pick<Finding, 'category' | 'checkId'>): string {
  return `stitcher-codereview/${f.category}/${f.checkId}`;
}

/** Serialize a review as SARIF 2.1.0 (one rule per distinct check). */
export function toSarif(r: ReviewResult): string {
  const order: string[] = [];
  const byRule = new Map<string, Finding[]>();
  for (const f of r.findings) {
    const id = ruleIdFor(f);
    if (!byRule.has(id)) {
      byRule.set(id, []);
      order.push(id);
    }
    byRule.get(id)!.push(f);
  }
  const rank = { error: 0, warning: 1, note: 2 } as const;
  const rules = order.map((id) => {
    const fs = byRule.get(id)!;
    const first = fs[0];
    const meta = checkMeta(first.checkId, first.category);
    const top = fs.map((f) => LEVEL[f.severity]).sort((a, b) => rank[a] - rank[b])[0];
    return {
      id,
      name: meta.title,
      shortDescription: { text: meta.title },
      fullDescription: { text: meta.description },
      defaultConfiguration: { level: top }
    };
  });
  const ruleIndex = new Map(order.map((id, i) => [id, i]));
  const sarif = {
    $schema: 'https://json.schemastore.org/sarif-2.1.0.json',
    version: '2.1.0',
    runs: [
      {
        tool: {
          driver: {
            name: 'stitcher-codereview',
            version: toolVersion(),
            informationUri: 'https://github.com/drwhofan2k18-pixel/stitcher-codereview',
            fullDescription: {
              text: `Spec-aware code review of OpenSpec change "${r.change}" (template: ${r.template.id}). Verdict: ${r.verdict}.`
            },
            rules
          }
        },
        properties: {
          verdict: r.verdict,
          change: r.change,
          template: r.template.id,
          requirementsCovered: `${r.stats.requirementsCovered}/${r.stats.requirementsTotal}`
        },
        results: r.findings.map((f) => {
          const result: Record<string, unknown> = {
            ruleId: ruleIdFor(f),
            ruleIndex: ruleIndex.get(ruleIdFor(f)),
            level: LEVEL[f.severity],
            message: { text: findingText(f) },
            properties: {
              severity: f.severity,
              category: f.category,
              ...(f.requirementId ? { requirementId: f.requirementId } : {}),
              ...(f.suggestion ? { suggestion: f.suggestion } : {})
            }
          };
          if (f.file) {
            result.locations = [
              {
                physicalLocation: {
                  // URIs must be encoded (spaces etc.); plain repo paths pass through unchanged.
                  artifactLocation: { uri: encodeURI(f.file) },
                  ...(f.line ? { region: { startLine: f.line } } : {})
                }
              }
            ];
          }
          return result;
        })
      }
    ]
  };
  return JSON.stringify(sarif, null, 2);
}
