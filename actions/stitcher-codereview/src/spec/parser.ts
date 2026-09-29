import type { Requirement, TaskItem } from '../types.js';

/**
 * Parse OpenSpec delta spec.md.
 * Expected shape (spec-driven schema):
 *   ## ADDED|MODIFIED|REMOVED Requirements
 *   ### Requirement: <name>
 *   <requirement text>
 *   #### Scenario: <name>
 *   - **WHEN** ... / - **THEN** ...
 */
export function parseDeltaSpec(raw: string, capability: string, sourceFile: string): Requirement[] {
  const out: Requirement[] = [];
  const sectionRe = /^##\s+(ADDED|MODIFIED|REMOVED)\s+Requirements/m;
  if (!sectionRe.test(raw)) {
    // No explicit operation header: treat whole file as ADDED with best-effort split.
    return parseRequirementsBlock(raw, 'ADDED', capability, sourceFile);
  }
  // Split by operation sections
  const parts = raw.split(/^##\s+(ADDED|MODIFIED|REMOVED)\s+Requirements\s*$/m);
  // parts[0] = preamble, then alternating [op, body, op, body...]
  for (let i = 1; i < parts.length; i += 2) {
    const op = parts[i].trim().toUpperCase() as Requirement['operation'];
    const body = parts[i + 1] ?? '';
    out.push(...parseRequirementsBlock(body, op, capability, sourceFile));
  }
  return out;
}

function parseRequirementsBlock(
  body: string,
  op: Requirement['operation'],
  capability: string,
  sourceFile: string
): Requirement[] {
  const reqs: Requirement[] = [];
  const chunks = body.split(/^###\s+Requirement:\s*/m);
  for (let i = 1; i < chunks.length; i++) {
    const chunk = chunks[i];
    const nl = chunk.indexOf('\n');
    const id = (nl === -1 ? chunk : chunk.slice(0, nl)).trim() || `unnamed-${i}`;
    const rest = nl === -1 ? '' : chunk.slice(nl + 1);
    // Split scenarios
    const scenChunks = rest.split(/^####\s+Scenario:\s*/m);
    const text = (scenChunks[0] ?? '').trim().slice(0, 2000);
    const scenarios = [];
    for (let s = 1; s < scenChunks.length; s++) {
      const sc = scenChunks[s];
      const snl = sc.indexOf('\n');
      const name = (snl === -1 ? sc : sc.slice(0, snl)).trim();
      const sbody = snl === -1 ? '' : sc.slice(snl + 1);
      const whenThen = sbody
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => /when|then/i.test(l))
        .slice(0, 12);
      scenarios.push({ name: name || `scenario-${s}`, whenThen });
    }
    reqs.push({ id, capability, operation: op, text, scenarios, sourceFile });
  }
  return reqs;
}

/** Parse tasks.md checklist: "- [ ] 1.1 text" grouped under "## 1. Group" */
export function parseTasks(raw: string): TaskItem[] {
  const items: TaskItem[] = [];
  let group = 'ungrouped';
  for (const line of raw.split('\n')) {
    const g = line.match(/^##\s+(.+)/);
    if (g) {
      group = g[1].trim();
      continue;
    }
    const m = line.match(/-\s+\[( |x|X)\]\s+(\d+(?:\.\d+)*)?\s*(.*)/);
    if (m) {
      items.push({
        id: (m[2] ?? `${items.length + 1}`).trim(),
        group,
        text: (m[3] ?? '').trim().slice(0, 500),
        done: m[1].toLowerCase() === 'x'
      });
    }
  }
  return items;
}

/** Tokenize text into lowercase keyword set (for evidence matching). */
export function keywords(text: string): Set<string> {
  const stop = new Set(
    'the,a,an,and,or,of,to,in,on,for,with,when,then,user,system,shall,must,should,will,be,is,are,by,as,at,it,its,that,this,from'.split(',')
  );
  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9_\-/ ]/g, ' ')
    .split(/[\s/_\-]+/)
    .filter((w) => w.length > 2 && !stop.has(w));
  return new Set(words);
}
