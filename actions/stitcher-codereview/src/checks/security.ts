import type { Diff, Finding } from '../types.js';
import { isGenerated } from './scope.js';

const SECURITY_PATTERNS: { id: string; re: RegExp; message: string; suggestion: string; skipPathRe?: string }[] = [
  { id: 'eval-call', re: /\beval\s*\(/, message: 'eval() executes arbitrary code.', suggestion: 'Use JSON.parse, Function allowlist, or a sandbox.' },
  { id: 'new-function', re: /new\s+Function\s*\(/, message: 'new Function() is dynamic code execution.', suggestion: 'Refactor to static code.' },
{
    id: 'shell-execution',
    re: /child_process|execSync|spawnSync|(?<!\.)\bexec\s*\(/,
    message: 'Shell execution with possible injection.',
    suggestion: 'Use execFile with arg arrays; never interpolate user input.',
    skipPathRe: 'src/(github|gitlab|vcs|diff/git|checks/(security|scan))\\.ts'
  },
  { id: 'raw-html-sink', re: /innerHTML|dangerouslySetInnerHTML/, message: 'Raw HTML injection sink.', suggestion: 'Sanitize (DOMPurify) or render as text.' },
  { id: 'hardcoded-credential', re: /(password|secret|api[_-]?key|token)\s*[:=]\s*['"][^'"]{4,}['"]/i,
    message: 'Possible hardcoded credential.', suggestion: 'Move to env/secret manager; rotate the value.' },
  { id: 'weak-hash', re: /crypto\.createHash\(['"]md5['"]\)|crypto\.createHash\(['"]sha1['"]\)/, message: 'Weak hash (md5/sha1).', suggestion: 'Use sha256+ or bcrypt/scrypt for passwords.' },
  { id: 'sql-concat', re: /SELECT\s+.*\+\s*.*FROM|query\s*\(.*\+/i, message: 'String-concatenated SQL — injection risk.', suggestion: 'Use parameterized queries.' },
  { id: 'insecure-random', re: /Math\.random\(\)/, message: 'Math.random() used — check if security-sensitive.', suggestion: 'Use crypto.randomBytes/UUID for tokens.' },
  { id: 'plain-http', re: /http:\/\//, message: 'Plain http:// URL.', suggestion: 'Use https:// unless loopback/test.' }
];

export function checkSecurity(diff: Diff): Finding[] {
  const findings: Finding[] = [];
  for (const f of diff.files) {
    if (f.isDeleted || isGenerated(f.path)) continue;
    // Test fixtures legitimately contain fake tokens/secrets — scanning them
    // only produces false HIGHs (e.g. token="forged" negative tests).
    if (/(\.test\.|\.spec\.|__tests__|snap|(^|\/)(tests?|e2e)\/)/.test(f.path)) continue;
    for (const l of f.addedLines) {
      for (const p of SECURITY_PATTERNS) {
        if (p.skipPathRe && new RegExp(p.skipPathRe).test(f.path)) continue;
        // The suggestion allows loopback/test — don't flag those.
        if (p.id === 'plain-http' && /http:\/\/(localhost|127\.0\.0\.1|\[::1\])([:/]|$)/.test(l.text)) continue;
        if (p.re.test(l.text)) {
          findings.push({
            severity: /credential|eval|Function|SQL|innerHTML|Shell/.test(p.message) ? 'high' : 'medium',
            category: 'security',
            checkId: p.id,
            file: f.path,
            line: l.n,
            message: `Security: ${p.message} (${f.path}:${l.n})`,
            suggestion: p.suggestion
          });
          break;
        }
      }
    }
  }
  return findings.slice(0, 50);
}
