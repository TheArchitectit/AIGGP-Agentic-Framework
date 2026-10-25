# 2026-10-25 — repository-supplied paths were not contained in the gates

Requirement: `security-boundaries` / `coh-sec-01` — *"Every path originating
from repository-supplied content … SHALL be validated for containment under
its declared root before any read. Traversal, absolute, escaping-symlink, and
NUL-bearing paths SHALL be rejected as invalid input (exit 30 class) without
reading the target, and the rejection reason SHALL name the offending path."*

This is a conformance record, not a schedule change: the requirement was
already published and enforced for the coherence service's own inputs
(`package.resolve`, `evaluators.*` selectors — `tests/test_hub_coherence_containment.py`).
It was **not** enforced anywhere the path entered from a config file, a
registry row, scanned output, or a sealed bundle. The prose was true of one
half of the tree, which is the shape of a published claim that is half false.

## What was measured on the tree before the fix

Every item below was read at `HEAD` and every one was exercised by a test in
`tests/test_gate_containment.py` / `tests/test_hub_coherence_containment.py`
before the code changed (the RED run is quoted under each).

| Site | Input (repository-supplied) | What it did with the path |
|---|---|---|
| `hub/coherence/store.py` `upload_bundle` | the sealed bundle's `evidence-manifest.json` objects | `bundle / rel` → `read_bytes()` → `store.put(...)` |
| `hub/coherence/context.py` `load_captured_facts` | a context's `captured_facts[].fact_id` | `<root>/facts/<id>` → `read_bytes()`; segment checks only, no symlink resolution |
| `scripts/check_manifest_join.py` `_expand`, `extract` | `.guardrails/manifest-joins.json` `declared`/`wired` `paths` | `root / rel` → `rglob` → `read_text()` (runs on every CI push, `ci.yml:218`) |
| `scripts/spec-fleet-classify.py` `check_provenance` | the templates lock's `vendored_path` | `root / vendored_path` → `read_bytes()` → SHA-256 |
| `scripts/regression_corpus.py` `stale_entries` | the failure registry's `affected_files` | `root / p` → `exists()` → `read_text()` for the pattern search |
| `scripts/findings_to_spec.py` `main` | `--capability`, or a finding's `category` (scanner output) | `root/openspec/specs/<cap>` → `mkdir` → **append** |
| `scripts/gate_common.py` `load_source_dirs` | `.guardrails/scope.json` `source_dirs`/`extra_source_dirs` | `os.walk` from `root / name` |

The most severe is the first: not a read-only leak but **exfiltration through
the durability path** — bytes named by an untrusted bundle are uploaded into
the evidence store, which is content-addressed, append-only, and replicated.
The RED run reproduced it, no special conditions:

```
AssertionError: Lists differ: [{'path': '../secret.txt', 'digest': 'sha256:98763a05…'}, …] != []
```

`../secret.txt` was read out of the fixture's host area and stored under its
digest. `findings_to_spec.py` is the second: the capability becomes a
directory the tool *creates and appends to*, so a category of
`../../escaped` writes outside the repository.

## The fix

- `gate_common.contained_path(root, rel)` — one primitive for gate code:
  absolute (`/`, `~`, drive) → embedded NUL → empty/dot/dotdot segment →
  resolve and confirm contained. It never touches the target, so a rejection
  cannot leak content, length, or existence. Missing files are not a
  containment error (the answer is "may this be read", not "does it exist"),
  so each caller keeps its own missing-file path.
- `hub/coherence/manifest.py:_check_safe` became **public `check_safe`** and
  gained the NUL rejection the requirement names. The three layers were
  already right; only its NUL gap and its privacy were wrong.
- Each site now refuses in its own vocabulary — the gate's exit 2, the
  classifier's `fault`, the registry audit's `escaping_paths`, the service's
  `ContextError`/`path-escapes-bundle` — always naming the path, never the
  target's content.
- Containment is applied **per expanded file** in `check_manifest_join`, not
  just to the declared root: a directory entry can hold a symlink out.

Deliberate duplication: the shipped service does not import `scripts/`
(`hub/coherence` must not depend on dev tooling), so two implementations
exist and both are pinned by tests. This is the one place the repo tolerates
the same rule twice; the alternative is a dependency from runtime code to
gate scripts.

## Evidence after the fix

- `tests/test_gate_containment.py` — 20 tests: the primitive (12), the four
  gate scripts (8), and three healthy controls so the fix cannot pass by
  refusing everything.
- `tests/test_hub_coherence_containment.py` — 3 new cases: a symlinked
  captured fact whose digest **matches** (only containment can refuse it), a
  NUL-bearing fact id, and an escaping bundle object that must never reach
  the store. Plus a contained control.
- `tests/test_gate_common.py` — 3 new cases: escaping and absolute walk
  roots refused, `.` accepted.
- `python3 -m pytest tests/ -q` → 1809 passed, 184 subtests.

## Not fixed here (and why)

- `scripts/negative_controls.py` and the other test-harness readers were not
  audited: they run only from a developer/CI checkout over paths the test
  itself wrote, and a wrong path there fails the test that wrote it. If this
  class is audited again, they belong in the sweep — they were not left out
  because they were shown safe.
- `hub/coherence/manifest.py:_gitlink_commit` follows a `.git` file's `gitdir:`
  pointer, which by design points outside the submodule (`../.git/modules/x`).
  It is the one reader where containment would break the legitimate layout, so
  it is left as-is rather than contained: the reads are `.git/HEAD` and
  `.git/packed-refs`, their content is used only if it matches a SHA or `ref:`
  form, and a hostile pointer therefore yields `submodule-unresolved` rather
  than host content. It should be revisited if that resolver ever parses
  anything freer than a commit id.
