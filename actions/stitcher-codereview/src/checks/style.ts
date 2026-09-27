import type { Diff, Finding } from '../types.js';
import { isGenerated } from './scope.js';

export function checkStyle(diff: Diff, conventions: string, maxLineLength?: number): Finding[] {
  const findings: Finding[] = [];
  // Explicit config wins; otherwise sniff conventions for a stated limit.
  const maxLen = maxLineLength ?? (/max.*line|line.*length|120|100|80/i.test(conventions) ? 120 : 140);
  for (const f of diff.files) {
    if (f.isDeleted || isGenerated(f.path)) continue;
    // Prose wraps by renderer, not by column — length applies to code only.
    const isProse = /\.(md|mdx|txt|rst)$/.test(f.path);
    for (const l of f.addedLines) {
      if (!isProse && l.text.length > maxLen) {
        findings.push({
          severity: 'low',
          category: 'style',
          checkId: 'line-too-long',
          file: f.path,
          line: l.n,
          message: `Line exceeds ${maxLen} chars (${l.text.length}) at ${f.path}:${l.n}.`,
          suggestion: 'Wrap the line per project style.'
        });
      }
      if (/\s+$/.test(l.text)) {
        findings.push({
          severity: 'low',
          category: 'style',
          checkId: 'trailing-whitespace',
          file: f.path,
          line: l.n,
          message: `Trailing whitespace at ${f.path}:${l.n}.`,
          suggestion: 'Trim it.'
        });
      }
    }
  }
  return findings.slice(0, 30);
}
