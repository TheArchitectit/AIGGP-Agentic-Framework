/**
 * Human-readable metadata per check id. SARIF rules are derived from these;
 * unknown ids (e.g. custom template checks) fall back to a humanized title.
 */
export const CHECK_META: Record<string, { title: string; description: string }> = {
  // spec-compliance
  'empty-diff': {
    title: 'Empty diff',
    description: 'No files changed for the given base; verify --base and that changes are committed or staged.'
  },
  'no-delta-specs': {
    title: 'No delta specs',
    description: 'The change has no specs/*/spec.md deltas, so spec compliance cannot be verified.'
  },
  'requirement-missing': {
    title: 'Requirement not implemented',
    description: 'An ADDED/MODIFIED requirement has no evidence in the diff.'
  },
  'requirement-partial': {
    title: 'Requirement partially implemented',
    description: 'An ADDED/MODIFIED requirement has only weak diff evidence; some scenarios may be missing.'
  },
  'removed-still-present': {
    title: 'Removed behavior still present',
    description: 'A REMOVED requirement still matches code in the diff.'
  },
  'drift-uncovered': {
    title: 'Capability touched without a spec',
    description: 'A changed file maps to a known capability with no covering requirement in this change.'
  },
  'drift-uncategorized': {
    title: 'Change outside known capabilities',
    description: 'A changed file maps to no baseline or delta capability.'
  },
  'drift-no-baseline': {
    title: 'No baseline specs',
    description: 'openspec/specs/ is absent, so capability drift mapping is unavailable.'
  },
  // tasks
  'no-tasks-file': {
    title: 'No tasks file',
    description: 'No tasks.md checklist found; task traceability unavailable.'
  },
  'task-done-no-evidence': {
    title: 'Task marked done without evidence',
    description: 'A tasks.md item is checked but has little diff evidence.'
  },
  'task-undone-with-evidence': {
    title: 'Task implemented but unchecked',
    description: 'A tasks.md item looks implemented but is still unchecked.'
  },
  'task-progress': {
    title: 'Task progress',
    description: 'Checked vs total tasks.md items.'
  },
  // correctness
  'todo-marker': { title: 'Leftover TODO marker', description: 'TODO/FIXME/HACK added; resolve or file an issue.' },
  'console-output': { title: 'Console debug output', description: 'console.* added; use the project logger.' },
  'empty-catch': { title: 'Empty catch block', description: 'Errors are swallowed; log, handle, or rethrow.' },
  'loose-equality': { title: 'Loose equality', description: '== invites coercion bugs; prefer ===.' },
  'awaited-promise-all': { title: 'Awaited Promise.all array', description: 'Outer await may serialize intended concurrency.' },
  'any-type': { title: '`any` type', description: 'Weakens the spec contract; use a concrete type.' },
  'settimeout-zero': { title: 'setTimeout(...,0)', description: 'Ordering hack; prefer queueMicrotask or explicit ordering.' },
  // security
  'eval-call': { title: 'eval()', description: 'Executes arbitrary code.' },
  'new-function': { title: 'new Function()', description: 'Dynamic code execution.' },
  'shell-execution': { title: 'Shell execution', description: 'Possible command injection; use arg arrays.' },
  'raw-html-sink': { title: 'Raw HTML sink', description: 'innerHTML-class injection sink; sanitize first.' },
  'hardcoded-credential': { title: 'Hardcoded credential', description: 'Secret in source; use env/secret manager and rotate.' },
  'weak-hash': { title: 'Weak hash', description: 'md5/sha1; use sha256+ or bcrypt/scrypt.' },
  'sql-concat': { title: 'Concatenated SQL', description: 'Injection risk; use parameterized queries.' },
  'insecure-random': { title: 'Math.random()', description: 'Unsafe for tokens; use crypto randomness.' },
  'plain-http': { title: 'Plain http:// URL', description: 'Use https unless loopback/test.' },
  // tests
  'no-tests-touched': {
    title: 'No tests touched',
    description: 'Source changed for a spec requirement but no test file was modified.'
  },
  'scenario-unmatched': {
    title: 'Scenario without matching test',
    description: 'A spec scenario has no obviously matching test file.'
  },
  // style
  'line-too-long': { title: 'Line too long', description: 'Added line exceeds the project limit.' },
  'trailing-whitespace': { title: 'Trailing whitespace', description: 'Added line ends with whitespace.' },
  // engine (LLM blend)
  'llm-rescore-moved': {
    title: 'LLM rescore moved coverage',
    description: 'The blended LLM score changed a requirement status vs the heuristic.'
  },
  'llm-unavailable-fallback': {
    title: 'LLM unavailable, heuristic used',
    description: 'Fail-open fallback when the provider cannot rescore.'
  },
  'llm-required-unavailable': {
    title: 'Required LLM unavailable',
    description: 'Fail-closed blocker when --llm require cannot reach its provider.'
  },
  // template: cli
  'cli/exit-code': { title: 'Non-standard exit code', description: 'CLI exit code outside 0/1; document it.' },
  'cli/signal-handling': { title: 'No signal handling', description: 'CLI entry without SIGINT/SIGTERM handling.' },
  'cli/raw-argv': { title: 'Raw argv parsing', description: 'Use the project arg parser for --help and validation.' },
  // template: web-service
  'web-service/migration-present': { title: 'Schema change without migration', description: 'Model/schema touched but no migration in diff.' },
  'web-service/auth-check': { title: 'Route without visible auth', description: 'Route/handler touched but no auth reference in diff.' },
  'web-service/status-codes': { title: 'Hardcoded 500', description: 'Map expected failures to 4xx; reserve 500 for bugs.' },
  // template: game-2d-3d
  'game-2d-3d/binary-asset': { title: 'Large binary asset', description: 'Check size/compression and Git LFS tracking.' },
  'game-2d-3d/scene-edit': { title: 'Scene/prefab edited', description: 'Verify in-editor; check YAML scenes for merge markers.' },
  'game-2d-3d/frame-search': { title: 'Runtime scene search', description: 'Find/Instantiate in hot paths; cache and pool.' },
  'game-2d-3d/save-version': { title: 'Unversioned save format', description: 'Version saves so old data fails gracefully.' },
  // template: library
  'library/removed-export': { title: 'Removed export', description: 'Breaking API change; needs a major version.' },
  'library/changelog': { title: 'Missing changelog entry', description: 'Library code changed without a changelog fragment.' },
  'library/side-effect-import': { title: 'Side-effect import', description: 'Bare imports break tree-shaking.' }
};

export function checkMeta(checkId: string, category: string): { title: string; description: string } {
  const known = CHECK_META[checkId];
  if (known) return known;
  const human = checkId
    .split('/')
    .pop()!
    .replace(/[-_]+/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase());
  return { title: `[${category}] ${human}`, description: `Finding from the ${category} checker (${checkId}).` };
}
