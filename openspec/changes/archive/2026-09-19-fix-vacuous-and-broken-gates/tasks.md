# Tasks: fix-vacuous-and-broken-gates

## 1. Root anchoring parity (C2/C3)

- [x] 1.1 Port the `guardrails-scan.mjs` `.devgate`-basename + marker contract
       into `scripts/semantic-scan.mjs` `findProjectRoot()`; a standalone
       checkout resolves to itself, never the parent.
- [x] 1.2 Same port into `scripts/run-tests.mjs` `findProjectRoot()`.
- [x] 1.3 Add walk() guards in both scanners: unreadable directories are
       reported and skipped (not EACCES crash), symlink cycles cannot recurse.
- [x] 1.4 Fixture test: standalone layout in a markerless temp parent —
       semantic-scan scans exactly the repo tree; run-tests discovers the
       repo's own test files (non-zero), never siblings.

## 2. Test runner correctness (C4, discovery)

- [x] 2.1 Fix the Rust arm to `cargo test --test <stem>`; assert a fixture
       integration file whose function names omit the stem still executes its
       tests (fails when the functions fail).
- [x] 2.2 Extend `isTestFile` to `test_*.mjs`/`test_*.js`/`*.spec.ts` and
       discovery to the documented "anywhere" set (`pkg/`, `scripts/`, root),
       or narrow the docs — one truth.
- [x] 2.3 Wire `tests/test_guardrails_scan.mjs` into the default run (rename
       or matcher); it must execute under `node scripts/run-tests.mjs`.
- [x] 2.4 Decide the `iso` mkdtemp dir: use it (per-file TMPDIR/CWD isolation
       as advertised) or delete it; do not ship dead isolation scaffolding.

## 3. npm audit classification (C6)

- [x] 3.1 `regression_audit.py`: classify runtime via `isDirect`/`fixAvailable`
       plus `name in runtime_deps`; `effects` alone must not downgrade.
- [x] 3.2 Fail loud, never silent green: npm missing, timeout, empty stdout, or
       unparseable JSON is a warning-headed exit, not `(0, 0, [])`.
- [x] 3.3 Regression test with a fixture audit document carrying a direct
       HIGH runtime vuln (`effects: []`, `isDirect: true`).

## 4. Deploy pipeline truth (C7, H7)

- [x] 4.1 `regression_check.py`: anchor project-root detection on the
       *consumer* tree when invoked as `.devgate/scripts/...` (script-location
       anchoring like guardrails-scan), keeping CWD override for direct runs;
       kill the module-level `PROJECT_ROOT` import-time evaluation so callers
       can pass a root explicitly.
- [x] 4.2 `deploy.sh`: detect standalone vs submodule layout (as
       `detect-host-ci.py:63` already does) and run every gate against the
       project root; both gates must evaluate the same tree.
- [x] 4.3 Fix the twine upload to explicit precedence with visible stderr and
       version-scoped artifacts (`dist/<pkg>-<new_version>*`), never a bare
       `dist/*` re-upload.
- [x] 4.4 Clean-tree gate: include untracked files in the dirty check.
- [x] 5-gate honesty: schema/lint/clippy either block or print an explicit
       `SKIPPED/WARN` contract line; document which in RELEASE_GATE.md.

## 5. Marker grammar and registry targeting (H6, H8)

- [x] 5.1 `spec_traceability.py`: accept `#`-prefixed markers for
       `.py`/`.rb`/`.sh`/`.toml` alongside `//`; one documented grammar table.
- [x] 5.2 `findings_to_spec.py`: emit per-language marker advice.
- [x] 5.3 `log_failure.py`: default target is the project overlay
       (project-root `.guardrails/failure-registry.jsonl`), with explicit
       `--baseline` to write upstream; `--registry` CLI flag parity.
- [x] 5.4 `failure_registry_check.py`: an explicit path that does not exist is
       exit 1 (all labels), reusing `gate_overlay` merge instead of the
       inlined reimplementation.
- [x] 5.5 Tests: `# spec:` marker discovered in Python; log_failure default
       lands in overlay; typo'd explicit registry path fails the hygiene gate.

## 6. scene_inventory (C1)

- [x] 6.1 Remove the `ET.parse` dead-end; make the regex parser primary and
       fix node-path vs bare-name comparison (`from` path's last segment).
- [x] 6.2 Add a self-test with a real minimal `.tscn` (valid scene passes,
       orphaned signal fails) or delete `scene_inventory.py`,
       `scripts/game-framework-README.md`, and their spec references — decide
       per the roadmap's game-tooling disposition.
- [x] 6.3 No vacuous green: zero scenes found prints NOTHING SCANNED and
       honors `--fail-if-empty`.

## 7. Closure

- [x] 7.1 Append failure-registry entries for each incident-class fix that
       lacks one (registry first, fixes reference it).
- [x] 7.2 Full gate self-scan green; `docs/qa/` delta note recording the
       closure of C1-C7/H6-H8 or their tracked disposition.
