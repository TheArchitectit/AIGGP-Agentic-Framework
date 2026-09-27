import type { Diff, Finding } from '../types.js';
import { isGenerated } from './scope.js';

type Pattern = {
  id: string;
  re: RegExp;
  message: string;
  suggestion: string;
  severity: Finding['severity'];
  skipPathRe?: string;
};

const CORRECTNESS_PATTERNS: Pattern[] = [
  { id: 'todo-marker', re: /\bTODO\b|\bFIXME\b|\bHACK\b/, message: 'Leftover TODO/FIXME marker added.', suggestion: 'Resolve or file an issue; do not merge placeholders.', severity: 'low' },
  { id: 'console-output', re: /console\.(log|debug|info)\s*\(/, message: 'console.* debug output added.', suggestion: 'Remove or switch to the project logger.', severity: 'medium' },
  { id: 'empty-catch', re: /catch\s*\([^)]*\)\s*\{\s*\}/, message: 'Empty catch block — errors are swallowed.', suggestion: 'Log/handle the error or rethrow.', severity: 'high' },
  // Built dynamically: a literal here would match its own definition line.
  { id: 'loose-equality', re: new RegExp('[^=!]' + '==' + '[^=]'),
    message: 'Loose equality (==) — possible coercion bug.',
    suggestion: 'Use === unless coercion is intentional.', severity: 'medium',
    skipPathRe: '\\.ya?ml$' },
  { id: 'awaited-promise-all', re: /await\s+[^;]*\bPromise\.all\(\s*\[/, message: 'await Promise.all — serializes unnecessarily?', suggestion: 'Drop the outer await if concurrency was intended.', severity: 'low' },
  { id: 'any-type', re: /\bany\b\s*[;,)=]/, message: '`any` type weakens the spec contract.',
    suggestion: 'Use a concrete type matching the spec.', severity: 'medium',
    skipPathRe: '(\\.test\\.|\\.spec\\.|__tests__|/(tests?|e2e)/)' },
  { id: 'settimeout-zero', re: /setTimeout\s*\(.*,\s*0\s*\)/, message: 'setTimeout(...,0) — ordering hack.', suggestion: 'Use queueMicrotask or make ordering explicit.', severity: 'low' }
];

/** Strip string literals so patterns match code shape, not prose in quotes. */
function stripStrings(line: string): string {
  return line.replace(/'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`/g, "''");
}

export function checkCorrectness(diff: Diff): Finding[] {
  const findings: Finding[] = [];
  for (const f of diff.files) {
    if (f.isDeleted || isGenerated(f.path)) continue;
    for (const l of f.addedLines) {
      // Comment-only lines are prose, not code (kills == in comments etc.).
      // Exception: such markers live in comments by definition.
      const isComment = /^\s*(\/\/|#|\*|<!--)/.test(l.text);
      const code = stripStrings(l.text);
      for (const p of CORRECTNESS_PATTERNS) {
        if (isComment && p.id !== 'todo-marker') continue;
        if (p.skipPathRe && new RegExp(p.skipPathRe).test(f.path)) continue;
        if (p.re.test(code)) {
          findings.push({
            severity: p.severity,
            category: 'correctness',
            checkId: p.id,
            file: f.path,
            line: l.n,
            message: `${p.message} (${f.path}:${l.n})`,
            suggestion: p.suggestion
          });
          break;
        }
      }
    }
  }
  return findings.slice(0, 50);
}
