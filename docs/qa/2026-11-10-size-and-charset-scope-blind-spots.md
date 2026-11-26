# Size and charset gates scan less than they report (2026-11-10)

**Scope:** four scope blind spots in the DevGate gate suite, found while wiring
the gates into `sunset-earth` and holding them to a "a green check that names
what was actually checked" rule. Every citation is measured against
`AIGGP-Agentic-Framework@497854f`. These are not false positives -- they are
cases where a gate prints green while excluding tracked files from its own
view.

## Why this class matters

Three of the four build their file list from a hard-coded extension tuple or
from `git ls-files`, then read content from disk. Anything outside that view is
never examined and the gate still prints its success line. Under a rule that a
green check must name what was actually checked, a green that silently excludes
part of the tree is worse than a red: it converts "not scanned" into "looks
clean".

A downstream consequence is worth naming up front. `sunset-earth` consumes
`.devgate/` as a submodule pinned at `bf4cf33`, and `.devgate/AGENTS.md`
forbids editing files inside it. Where the framework's check could not be
extended from outside, that project had to write its own first-party gate
rather than weaken its standard. Fixing these upstream is what would let those
shims be deleted.

---

## Finding 1 - `regression_sizes.py` never sees `.mjs`, `.cjs` or `.css`

**Rule:** a size gate must scan every source file it claims to, or name which
it did not.

**Path:** `scripts/regression_sizes.py:44-46` (tuple), used at `:166` and `:210`.
**Commit:** `5f20fc7`.

`SOURCE_EXTENSIONS` is a literal tuple that ends at `.html`:

```
(".ts", ".tsx", ".py", ".rs", ".go", ".gd", ".java", ".kt",
 ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs",
 ".sh", ".zig", ".html")
```

`.mjs`, `.cjs` and `.css` are absent. The tuple is consulted both when sweeping
(`:166`) and when deciding scope (`:210`), so those files are not counted at
all -- not sized loosely, not sized.

At `497854f` that is **18 tracked files**, and they are not edge cases:

```
scripts/bundle-size-check.mjs
scripts/guardrails-scan.mjs
scripts/init.mjs
scripts/run-tests.mjs
scripts/schema-health-check.mjs
scripts/semantic-scan.mjs
scripts/lib/gate_common.mjs
scripts/lib/project-root.mjs
scripts/lib/test-runner-select.mjs
templates/hooks/opencode/session-start.mjs
tests/test_bundle_size_check.mjs
tests/test_gate_common.mjs
tests/test_guardrails_scan.mjs
tests/test_run_tests_runner.mjs
tests/test_scanner_root_anchor.mjs
tests/test_schema_health_config.mjs
tests/test_semantic_scan.mjs
.benchmarks/tasks/t04-path-traversal/repo/public/style.css
```

The framework's own gate entry points and seven of their tests have never been
sized. The gate still reports "All source files within soft/hard line limits".

**Minimal fix:** add `.mjs`, `.cjs`, `.css` to `SOURCE_EXTENSIONS`. If there is
a reason a language is deliberately excluded, the success line should say how
many files were skipped and why, rather than implying full coverage.

---

## Finding 2 - the test classifier misses `.test.mjs` / `.spec.mjs`

**Rule:** a file that is a test must be judged at the test limit, not the
source limit.

**Path:** `scripts/regression_sizes.py:78-89` (classifier), `:50`
(`TEST_PREFIX_EXTENSIONS`).
**Commit:** `5f20fc7`.

The test-classification tuple is:

```
(".test.ts", ".test.tsx", ".test.js", ".spec.ts",
 ".spec.js", "_test.py", "_test.go",
 ".test.rs", ".test.gd",
 "_test.zig")
```

`.test.mjs` and `.spec.mjs` are absent. `TEST_PREFIX_EXTENSIONS` covers the
`test_*` prefix convention for `(".py", ".sh", ".zig")` only.

Today this is masked by Finding 1, because `.mjs` is not in scope at all. It
stops being masked the moment Finding 1 is fixed: every `tests/test_*.mjs` and
`*.test.mjs` in this repo would then be sized as a source file. The two
findings must land together or the second becomes live.

Note the file already carries this class of history in its own comments --
`FAIL-8f9249ca` and `FAIL-f6228dda` are recorded for exactly this kind of
classifier gap, one language later each time. This is the same gap two
languages later.

**Minimal fix:** add `.test.mjs`, `.spec.mjs` to the endswith tuple and `.mjs`
to `TEST_PREFIX_EXTENSIONS`, in the same commit as Finding 1.

---

## Finding 3 - `HANDOFF` census is stale by 13 capability specs

**Rule:** a doc that states a count must be regenerated when the count moves,
or dated so a reader knows when it stopped being true.

**Path:** `HANDOFF-AIGGP-Agentic-Framework.md:14`.
**Commit:** `901f847`.

The line reads:

> Current census (2026-10-20): **31 capability specs** - 3 CLOSED, 0 PARTIAL,

`openspec/specs/` at `497854f` holds **44** `spec.md` files. The census is 13
specs behind and is presented as current, not as a historical snapshot.

This is the doc-truth class the repo has its own `doc-truth` capability spec
about. The date in parentheses is the only thing saving it from being a plain
false statement, and "Current census" contradicts that saving reading.

**Minimal fix:** regenerate the census, or change the lead-in to "Census as of
2026-10-20 (since superseded)" and add the live count. The table is already
described as generated from each spec's own `Status:` line -- if there is a
generator, the census line should come from the same run.

---

## Finding 4 - `check_charset.py` builds its file list with `git ls-files`

**Rule:** a gate whose view is taken at run time must not report green about
files outside that view.

**Path:** `scripts/check_charset.py:238` (list source), `:296` and `:422`
(content source).
**Commit:** `b01d5e1`.

The file list comes from `git ls-files -z` (`:238`), but each file's content is
read from disk (`(root / rel).read_bytes()` at `:296`). Two failure modes, one
root cause -- the gate's view of the tree is taken at run time, not at commit
time:

1. **Untracked files are invisible.** A newly written file is not in
   `git ls-files` until it is staged, so the gate prints `OK` while the file
   may be illegal.
2. **Writes made after the run are unchecked.** A tracked file's new content
   *is* scanned from disk -- but only when the gate runs after the write. Gate
   first, write second, and the new text is never checked.

This produced a real false green downstream on 2026-11-10. An `openspec/project.md`
was written with U+2248 and U+00B1 typed as glyphs. `npm run gates` was run
twice before commit and printed `PASS check-charset` both times because the
file was untracked. The tree went red the moment it was committed, and a
subagent had to land an out-of-scope fix. A second instance was caught by
pre-verification before it happened: a plan task ran the gates at one step and
wrote its evidence log at the next, so pasted evidence text would never have
been charset-checked.

**Minimal fix:** include untracked text files in the scan (`git ls-files -z
--others --exclude-standard` alongside the tracked list), and state in the
success line how many files were scanned and from which view. Fail closed if
the file list cannot be built.

---

## Cross-cutting suggestion

Findings 1, 2 and 4 share one shape: **the gate's notion of "the tree" is
narrower than the tree, and the success line does not say so.** Whatever the
fix for each, the summary line should report what was in scope. A gate that
scanned 411 of 947 tracked files should say that, and a reader can then tell
"clean" from "not looked at".

## Findings — triaged and fixed (2026-11-13, v1.3.30)

All four reproduced on `main` on 2026-11-13 before any edit; none were
environment artifacts. Fixed in the order below, each with a test that fails
without the fix.

- Finding 1 - size scope: `scripts/regression_sizes.py:44-46`, `5f20fc7`.
  **FIXED.** `.mjs`, `.cjs` and `.css` joined `SOURCE_EXTENSIONS`. Largest
  newly-scoped file is `scripts/semantic-scan.mjs` at 454 lines — under
  `SRC_HARD`. Tests: `test_oversize_es_module_is_flagged_at_src_hard`,
  `test_oversize_stylesheet_is_flagged_at_src_hard`.
- Finding 2 - test classification: `scripts/regression_sizes.py:78-89`, `5f20fc7`.
  **FIXED in the same change**, as the finding requires: `.test.mjs` and
  `.spec.mjs` joined the endswith tuple and `.mjs` joined
  `TEST_PREFIX_EXTENSIONS`. This was not cosmetic — three `tests/*.mjs` files
  are over 500 lines and would have been judged at `SRC_HARD` the moment
  Finding 1 landed. Tests:
  `test_an_es_module_test_file_is_judged_at_the_test_limit`,
  `test_a_dot_test_es_module_is_judged_at_the_test_limit`.
- Finding 3 - stale census: `HANDOFF-AIGGP-Agentic-Framework.md:14`, `901f847`.
  **FIXED.** The census and the two following sections now state the live
  numbers (44 specs / 43 CLOSED / 1 DEFERRED, 38 archived, 5 open) dated
  2026-11-13, and the spec/archive name overlap is re-measured at zero.
- Finding 4 - charset file list: `scripts/check_charset.py:238`, `b01d5e1`.
  **FIXED.** The scan now takes `git ls-files --cached --others
  --exclude-standard`, so untracked-but-not-ignored files are read before they
  are committed; the success line reports "N tracked + M untracked"; the
  zero-file failure names the scope it examined. Baseline generation stays
  deliberately tracked-only, so `--write-baseline` can never grandfather debt
  in a file that has not been committed. Tests:
  `test_untracked_file_is_scanned`,
  `test_success_line_reports_tracked_and_untracked_scope`,
  `test_zero_text_files_fails`.

**What is still open** is the second half of Finding 4, which is a property of
any pre-commit gate and not a defect: a write made *after* the last gate run is
unchecked until the next run. The gates are ordered before commit for that
reason; no gate can read a file that does not exist yet.

## Checks actually run

Read `scripts/regression_sizes.py` (tuple at `:44-46`, classifier at `:78-89`,
prefix set at `:50`, both use sites at `:166` and `:210`); read
`scripts/check_charset.py` (`:238`, `:296`, `:422`); `git ls-files | wc -l`
(947 tracked) and the in-scope subset for the `SOURCE_EXTENSIONS` tuple (411);
`git ls-files | grep -E '\.(mjs|cjs|css)$'` (18 files, listed above);
`find openspec/specs -name spec.md | wc -l` (44) against the HANDOFF census
claim of 31; `git log -1 --format` per cited file for the commit hashes. No
file in this repository was modified by the investigation.
