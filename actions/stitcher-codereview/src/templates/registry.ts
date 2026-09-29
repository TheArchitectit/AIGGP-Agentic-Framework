import type { ProjectTemplate } from './types.js';

export const GENERIC_TEMPLATE: ProjectTemplate = {
  id: 'generic',
  label: 'Generic',
  description: 'Language-agnostic fallback. No domain assumptions.',
  matchers: [],
  lens: '',
  checks: []
};

export const CLI_TEMPLATE: ProjectTemplate = {
  id: 'cli',
  label: 'CLI / harness',
  description: 'Command-line tools and test harnesses: exit codes, arg parsing, signals, stdio.',
  matchers: [
    { pkgField: 'bin', weight: 4 },
    { dep: 'commander', weight: 3 },
    { dep: 'yargs', weight: 3 },
    { dep: 'click', weight: 3 },
    { dep: 'clap', weight: 3 },
    { dep: 'System.CommandLine', weight: 3 },
    { file: 'src/cli.ts', weight: 2 },
    { file: 'src/cli.py', weight: 2 },
    { file: 'src/main.rs', weight: 1 }
  ],
  lens:
    'This is a CLI/harness project. Pay special attention: exit codes must be meaningful and documented (0 success, non-zero failure); ' +
    'arg/flag parsing must validate input and print usage on error; long-running commands must handle SIGINT/SIGTERM gracefully; ' +
    'never hang silently on stdin/TTY; machine-readable output (--json/--format) must be stable and parseable.',
  checks: [
    {
      id: 'exit-code',
      severity: 'medium',
      contentRe: 'process\\.exit\\((?!0\\)|1\\)|2\\))|sys\\.exit\\((?!0\\)|1\\)|2\\))|std::process::exit\\((?!0\\)|1\\)|2\\))',
      message: 'Non-standard exit code — document it or use 0/1/2.',
      suggestion: 'Keep 0 = success, 1 = expected failure, 2 = usage error; document any other code in --help.'
    },
    {
      id: 'signal-handling',
      severity: 'low',
      pathRe: '(cli|main|harness|runner)\\.(ts|tsx|js|jsx|mjs|cjs|py|rs|go|java|rb|sh|php|cs)$',
      absentRe: "SIGINT|SIGTERM|add_signal_handler|signal\\.signal|ctrlc|Ctrl-C",
      newFilesOnly: true,
      message: 'New CLI entry without signal handling (SIGINT/SIGTERM).',
      suggestion: 'Handle Ctrl-C gracefully: flush output, clean up temp state, exit 130/143 by convention.'
    },
    {
      id: 'raw-argv',
      severity: 'low',
      contentRe: 'process\\.argv\\.slice|sys\\.argv\\[1:\\]|env::args\\(\\)\\.skip',
      message: 'Raw argv parsing instead of a parser library.',
      suggestion: 'Use the project arg parser (commander/yargs/click/clap) for --help and validation.'
    }
  ],
  testFileRes: ['__snapshots__', 'e2e'],
  testHint: 'CLIs benefit from --help snapshot tests plus an e2e run of each touched subcommand.',
  // stdout/stderr are a CLI's interface — console output is not debug noise here.
  suppress: ['console-output']
};

export const WEB_SERVICE_TEMPLATE: ProjectTemplate = {
  id: 'web-service',
  label: 'Web service / API',
  description: 'Servers and APIs: auth, migrations, idempotency, backwards-compatible contracts.',
  matchers: [
    { file: 'Dockerfile', weight: 1 },
    { file: 'migrations', weight: 3 },
    { file: 'prisma/schema.prisma', weight: 3 },
    { dep: 'express', weight: 3 },
    { dep: 'fastify', weight: 3 },
    { dep: 'django', weight: 3 },
    { dep: 'flask', weight: 3 },
    { dep: 'fastapi', weight: 3 },
    { dep: 'axum', weight: 3 },
    { dep: 'spring-boot', weight: 3 },
    { dep: 'spring-web', weight: 3 }
  ],
  lens:
    'This is a web service/API project. Pay special attention: every endpoint change must consider authN/authZ; ' +
    'database changes need reversible migrations (expand-then-contract, never destructive in one step); ' +
    'request/response contract changes must stay backwards compatible or be versioned; ' +
    'mutations should be idempotent or carry idempotency keys; errors must map to correct status codes without leaking internals.',
  checks: [
    {
      id: 'migration-present',
      severity: 'medium',
      pathRe: '(models?/|schema|entities/|migrations/)',
      absentRe: 'migrat|ALTER TABLE|CREATE TABLE|up\\(\\)|change\\(\\)',
      message: 'Model/schema files changed but no migration in diff.',
      suggestion: 'Add a reversible migration (expand-then-contract for renames/drops).'
    },
    {
      id: 'auth-check',
      severity: 'medium',
      pathRe: '(routes?/|handlers?/|controllers?/|api/|views\\.py)',
      absentRe: 'auth|requireAuth|@login|permission|guard|middleware.*auth|depends.*auth|Authorize',
      message: 'Route/handler touched but no auth reference in diff.',
      suggestion: 'Confirm the endpoint is intentionally public or add authN/authZ.'
    },
    {
      id: 'status-codes',
      severity: 'low',
      contentRe: 'res\\.status\\(500\\)|raise HTTPException\\(500|StatusCode::INTERNAL_SERVER_ERROR',
      message: 'Hardcoded 500 — check the failure is truly unexpected.',
      suggestion: 'Map expected failures to 4xx; reserve 500 for bugs and log with a correlation id.'
    }
  ],
  testFileRes: ['supertest', '\\.http$', 'e2e'],
  testHint: 'Cover status codes and auth paths (happy path plus 401/403) for every touched endpoint.'
};

export const GAME_TEMPLATE: ProjectTemplate = {
  id: 'game-2d-3d',
  label: '2D/3D game',
  description: 'Games (Godot/Unity/Unreal/custom): frame budgets, assets, scenes, saves.',
  matchers: [
    { file: 'project.godot', weight: 5 },
    { file: 'Assets', weight: 4 },
    { file: 'ProjectSettings', weight: 4 },
    { file: 'Game.uproject', weight: 5 },
    { dep: 'godot', weight: 3 },
    { dep: 'bevy', weight: 3 },
    { dep: 'pygame', weight: 2 },
    { dep: 'arcade', weight: 2 }
  ],
  lens:
    'This is a 2D/3D game project. Pay special attention: per-frame code paths (update/process/physics) must avoid allocations, ' +
    'scene-tree searches, and synchronous I/O; assets should be compressed and sensibly sized (no multi-MB binaries without Git LFS); ' +
    'scene/prefab edits must be verified in-editor (watch for merge markers in YAML scenes); ' +
    'save formats must be versioned for backwards compatibility; input handling must cover remapping and gamepad/keyboard parity where applicable.',
  checks: [
    {
      id: 'binary-asset',
      severity: 'medium',
      pathRe: '\\.(psd|fbx|blend|max|wav|aiff|mp4|mov|avi|tga|exr)$',
      message: 'Large binary asset added — check size/compression and Git LFS tracking.',
      suggestion: 'Compress (e.g. .glb over .fbx/.blend, .ogg over .wav) and track via Git LFS if >1MB.'
    },
    {
      id: 'scene-edit',
      severity: 'low',
      pathRe: '\\.(unity|tscn|prefab|uasset|umap)$',
      message: 'Scene/prefab file changed — verify in-editor and check for merge markers.',
      suggestion: 'Open the scene in the editor; grep for <<<<<<< markers in YAML scenes.'
    },
    {
      id: 'frame-search',
      severity: 'medium',
      contentRe: 'FindObjectOfType|GameObject\\.Find|Resources\\.Load|get_node\\(.*%|Instantiate\\(',
      message: 'Runtime scene search/instantiation — hot-path and GC risk if per-frame.',
      suggestion: 'Cache references in _ready/Start/Awake; pool instantiated objects.'
    },
    {
      id: 'save-version',
      severity: 'low',
      pathRe: '(save|persist|serial)',
      absentRe: 'version|migrat|schema_version|SAVE_VERSION',
      message: 'Save/persistence code touched but no save-format versioning in diff.',
      suggestion: 'Version the save format so old saves fail gracefully instead of corrupting.'
    }
  ],
  testFileRes: ['EditMode', 'PlayMode', 'GUT', 'GdUnit'],
  testHint: 'Unity: cover EditMode and PlayMode tests; Godot: GUT/GdUnit suites for changed mechanics.'
};

export function builtinTemplates(): ProjectTemplate[] {
  return [GENERIC_TEMPLATE, CLI_TEMPLATE, WEB_SERVICE_TEMPLATE, GAME_TEMPLATE, LIBRARY_TEMPLATE];
}

export const LIBRARY_TEMPLATE: ProjectTemplate = {
  id: 'library',
  label: 'Library / package',
  description: 'Published packages: semver, public export surface, changelog, tree-shaking.',
  matchers: [
    { pkgField: 'exports', weight: 3 },
    { pkgField: 'main', weight: 2 },
    { pkgField: 'types', weight: 2 },
    { file: 'src/index.ts', weight: 2 },
    { file: 'src/index.js', weight: 2 },
    { file: 'src/lib.rs', weight: 2 },
    { file: 'tsup.config.ts', weight: 2 }
  ],
  lens:
    'This is a published library/package. Pay special attention: the public export surface is a semver contract — ' +
    'removed or renamed exports are breaking changes needing a major bump plus migration notes; ' +
    'new features need a changelog entry; avoid side effects at import time and bare side-effect imports ' +
    'so consumers keep tree-shaking; new dependencies become transitive costs — prefer peerDeps for frameworks.',
  checks: [
    {
      id: 'removed-export',
      severity: 'high',
      pathRe: '(^src/|^lib/|^packages/[^/]+/(src|lib)/)',
      removedRe: '^\\s*export\\s+(default\\s+)?(async\\s+function|function|const|let|var|class|abstract\\s+class|interface|type|enum)\\s+[A-Za-z_$]|^\\s*export\\s*\\{',
      message: 'Removed export — breaking API change.',
      suggestion: 'Restore it (deprecate first) or release a major version with migration notes.'
    },
    {
      id: 'changelog',
      severity: 'low',
      pathRe: '(^src/|^lib/|^packages/[^/]+/(src|lib)/)',
      absentRe: 'CHANGELOG|changeset',
      absentScope: 'diff',
      message: 'Library code changed but no changelog entry found in diff.',
      suggestion: 'Add a CHANGELOG entry or changeset fragment describing the user-visible change.'
    },
    {
      id: 'side-effect-import',
      severity: 'low',
      pathRe: '^src/',
      contentRe: "^\\s*import\\s+['\"]",
      message: 'Bare side-effect import in library code.',
      suggestion: 'Side-effect imports break tree-shaking; make the effect explicit or opt-in.'
    }
  ],
  testHint: 'Test the public export surface (package entry point), not internals.'
};
