# Tasks: Six Open-Item Gates, One per Deficiency Family

Status is per-task below, not a blanket label. Every gate in this package is
implemented and runnable; **none is wired into CI**, because placement is an
owner decision (see the closing section).

## 1. Specification

- [x] 1.1 `branch-drift` delta with four requirements (`bd-01..04`).
- [x] 1.2 `evidence-claims` delta with six requirements (`evc-01..06`).
- [x] 1.3 `open-item-aging` delta with four requirements (`oia-01..04`).
- [x] 1.4 `secret-rotation` delta with four requirements (`sr-01..04`).
- [x] 1.5 `surface-reach` delta with four requirements (`srch-01..04`).
- [x] 1.6 `tree-clean` delta with four requirements (`tc-01..04`).
  Validated with the CI pin (`@fission-ai/openspec@1.14.3`,
  `validate --all --strict`); the negative control still refuses the planted
  malformed item.

## 2. Implementation — one script per family

- [x] 2.1 `scripts/branch_drift_check.py` — compares every local ref tip
  against advertised remote refs; an archived commit is a recorded decision,
  not drift.
- [x] 2.2 `scripts/evidence_claim_check.py` — parses `DEFERRED`, `MOCK`, and
  `STUB` markers in tracked source; exemptions come from a declared file
  (`--allow`), never from inference.
- [x] 2.3 `scripts/open_item_aging_check.py` — reads an append-only backlog and
  triage ledger; an aged item with no live disposition fails, named
  individually.
- [x] 2.4 `scripts/secret_rotation_check.py` — reads a rotation ledger; a
  detection removed from `HEAD` without a revocation (date + evidence) past the
  window fails.
- [x] 2.5 `scripts/surface_reach_check.py` — reads a surfaces manifest; every
  declared surface must exist and hold identical content.
- [x] 2.6 `scripts/tree_clean_check.py` — classifies working-tree entries into
  committed change, declared generated churn, file-mode-only churn, or real
  dirt; only the last fails by default.
- [x] 2.7 Every script keeps the shared nothing-scanned contract (exit `3`,
  never a bare green) and the frozen exit codes `0/1/2/3`; each takes explicit
  input paths and writes no state.
- [x] 2.8 Each script carries `// spec:` markers for its own family, and every
  file is executable in the index (shebang implies `100755`).
- [x] 2.9 Each gate was demonstrated failing on a fixture before the commit, and
  passing on a clean fixture.
  - **Re-runnable since 2026-11-13.** The tick described an authoring session,
    not anything in the tree: no fixture, test or invocation existed, so the
    claim could not be checked by anyone after the fact — the same class this
    package exists to gate. `tests/test_open_item_gates.py` now drives all six
    gates as subprocesses against synthetic fixtures (29 tests): each gate's
    failing fixture must exit `1` **and name the offending input** (so a gate
    that fails for the wrong reason cannot pass as detection), its clean
    fixture must exit `0` (so it is not always-red), and its empty input must
    exit `3` (the shared nothing-scanned contract). Non-vacuity measured per
    gate by mutation: forcing each script's verdict return to `EXIT_OK` turns
    that gate's tests red (`branch_drift` 1 failed, `evidence_claim` 3,
    `open_item_aging` 3, `secret_rotation` 3, `surface_reach` 2,
    `tree_clean` 1), and restoring them returns 29/29.
  - The fixtures found one real contract defect: `--json` on `branch_drift`,
    `evidence_claim` and `tree_clean` printed the human `OK:` line after the
    JSON document, so `json.loads(stdout)` failed on the **clean** path only —
    the worst place for machine output to break. `--json` now emits the
    document and nothing else on every path (`open_item_aging` has no `--json`
    mode, so it is unchanged).

## 3. Traceability

- [x] 3.1 `scripts/spec_traceability.py --ratchet` reports 228/241 covered; the
  floor is raised to 228 so removing a marker later is a failure.
- [x] 3.2 The nine `spec-state-*` IDs proposed by `add-spec-state-ledger` remain
  advisory (specification-only package, no enforcing code yet).

## 4. Open — not done by this change

- [ ] 4.1 Wire each gate where it can see its inputs. Placement is an owner
  decision: a push-time CI job **detects** a violation that already landed, and
  must not be described as blocking on a repository that accepts direct pushes
  to `main` (the same honesty rule as `spec-state-09`).
  - **Measured 2026-11-15. No gate is wired anywhere.**
    `grep -rnE 'open_item_aging_check|secret_rotation_check|branch_drift_check|tree_clean_check|surface_reach_check|evidence_claim_check' .github/ scripts/hooks/`
    exits 1 with zero matches. The only execution today is
    `tests/test_open_item_gates.py` under `pytest` in the `tests` job
    (`.github/workflows/ci.yml`, "Run the shipped gates against its own tree"),
    and it runs each gate against synthetic fixtures, not this repository's
    own inputs. `scripts/hooks/pre-commit` runs `scripts/spec_state_gate.py`
    only, is installed per clone (`git config core.hooksPath scripts/hooks`),
    and is bypassable with `--no-verify`.
  - **Measured placement constraints.** `actions/checkout` leaves CI in a
    detached checkout with no local branches, so `branch_drift_check.py`
    (local ref tips vs advertised remotes) and `tree_clean_check.py`
    (working-tree classification) cannot see their inputs in CI; they can only
    run on a developer machine. `open_item_aging_check.py`,
    `secret_rotation_check.py`, `surface_reach_check.py` and
    `evidence_claim_check.py` read files a checkout contains, so they are
    CI-able in principle.
  - **Owner question, exactly:** for each of the six gates, choose one
    placement among (a) local pre-commit/pre-push hook (blocks locally,
    bypassable with `--no-verify`), (b) push-time CI job (detects after the
    commit has landed on `main`; does not block), (c) release preflight
    (`scripts/release_preflight.sh`, blocks a release not a push), (d)
    scheduled advisory run. `branch_drift` and `tree_clean` can only be (a) or
    a developer-machine advisory. The owner must also name the input paths for
    the two ledger gates (4.2).
- [ ] 4.2 Adopt a triage ledger and a rotation ledger with content. The gates
  read these files; creating them is a process decision, and an empty ledger is
  a pass, not evidence.
  - **Measured 2026-11-15 — neither ledger can be adopted from repository data
    without a process decision, so both stay open with the missing input
    named.**
  - Triage ledger: the gate needs a backlog of dated open rows plus one
    disposition per aged row (`fixed`, `deferred` with `review_by` + `reason`,
    or `not-actionable`). This repository has no live dated backlog:
    `git grep -nE '^\s*-\s*\[[ ~!]\].*20[0-9]{2}-[0-9]{2}-[0-9]{2}' -- '*.md'`
    returns three rows, all historical lines inside archived change packages
    (`openspec/changes/archive/2026-10-01-devgate-spec-coherence-service/tasks.md`
    and `2026-10-13-harden-oap-evidence-verification/tasks.md`), not a ledger
    the gate should age. The canonical append-only ledger the gate was written
    against (`ai-news/nextday-actions.md`) lives outside this repository. A
    named but absent backlog is exit 2
    (`python3 scripts/open_item_aging_check.py /tmp/no-such-backlog.md` ->
    `rc=2`, `FATAL: backlog not found`), not a pass, and there is nothing real
    to point it at.
  - Rotation ledger: `bash scripts/secret-scan.sh --repo . --report
    /tmp/aiggp-ss.json --all` exits 1: `scanned 82 finding(s): 40 allowlisted,
    42 to fix` (21 allowlist entries). The 42 uncovered hits are
    credential-shaped fixtures in `openspec/changes/add-oap-evidence-consumer/vectors/`
    and `tests/` (rule `generic-api-key`, plus one `github-pat` under
    `fleet-manager/tests/`). Writing them into `secret-rotation.jsonl` forces
    two decisions this change cannot make: whether each hit is a real
    credential or a test fixture, and — for a real one — whether it was revoked
    at the provider, with a revocation date and evidence id. The gate treats an
    empty ledger as exit 0 (`OK: empty rotation ledger — no detections recorded
    yet`, measured), which is a pass, not evidence, so an empty file ticks
    nothing.
  - **Missing inputs, named:** (1) the backlog path the operator adopts;
    (2) a disposition per aged row; (3) a real-vs-fixture classification per
    secret detection; (4) provider revocation records (date + evidence id) for
    anything classified real.
- [x] 4.3 Unit tests under `tests/` for each gate. Today the evidence is the
  authoring-time demonstration named in the commit; a suite that pins the
  passing and failing fixtures would make that evidence re-runnable.
  - Done 2026-11-13: `tests/test_open_item_gates.py`, 29 tests across the six
    gates (failing fixture, clean fixture, empty input per gate). The suite
    pins behavior through the real CLI, not by importing internals, so an exit
    code or message change is visible. `tests/expected-counts.json` was
    regenerated with `gen_floors.py --update` (new floor `test_open_item_gates:
    26`, `total_floor` 1752 → 1798); the other floors that rose in the same
    regeneration (`check_charset` 14→16, `hub_coherence_traceability` 7→9,
    `hub_enroll_heartbeat` 13→16, `regression_sizes` 14→18,
    `spec_traceability` 18→19) are tests already on `main` that the stale file
    had not yet counted — no floor was lowered.
  - **Revised 2026-11-13 (v1.3.33): 30 tests, and the suite found a second
    defect.** Running the suite in full-suite order (not standalone) failed
    `test_divergent_surfaces_fail_and_the_odd_one_is_named` intermittently:
    `surface_reach_check.py` chose its "odd one out" with
    `max(counts, key=counts.get)` over `set(hashes.values())`, so on a 1-1 tie
    the answer followed hash randomisation and named `ui-a.tsx` on one run and
    `ui-b.tsx` on the next. The reference is now the most common hash with
    ties broken by the hash value, and reported paths are sorted, so identical
    input produces identical output. The fixtures split the two cases: a
    two-agreeing-one-drifts group (unambiguous majority) and a 1-1 tie that
    asserts byte-identical output across two runs. Per-gate mutation counts
    re-measured: `branch_drift` 1, `evidence_claim` 3, `open_item_aging` 3,
    `secret_rotation` 3, `surface_reach` 3, `tree_clean` 1.
