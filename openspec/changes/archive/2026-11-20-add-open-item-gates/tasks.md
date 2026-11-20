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

- [x] 4.1 Wire each gate where it can see its inputs. Placement is an owner
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
  - **DECIDED and IMPLEMENTED 2026-11-15.** The owner delegated the call
    ("you make the call for hooks or web hooks"); the call is both, with
    distinct jobs — git hooks are the fast local layer that blocks in the
    moment and is `--no-verify` bypassable **by design**; webhooks/CI is the
    authoritative record on a clean run and is not bypassable. Honesty rule,
    applied to every file touched: on a repository that accepts direct pushes
    to `main`, a push-time CI job **detects** a violation that has already
    landed — it is never called blocking, because it cannot block. Placement,
    exactly as decided:

    | Gate | Placement |
    |---|---|
    | `tree_clean_check.py` | local pre-commit hook |
    | `branch_drift_check.py` | local pre-push hook |
    | `open_item_aging_check.py` | local pre-commit hook **and** push-time CI (**detects**) |
    | `secret_rotation_check.py` | push-time CI (**detects**) **and** release preflight |
    | `surface_reach_check.py` | push-time CI (**detects**) |
    | `evidence_claim_check.py` | push-time CI (**detects**) **and** release preflight |

    Rationale, unchanged from the decision: `tree_clean` needs the working tree
    and `branch_drift` needs local ref tips, so neither can see its inputs in a
    CI checkout; the other four read files a checkout contains.

    Files: `scripts/hooks/pre-commit` (extended: tree_clean + open_item_aging
    ahead of the existing spec-state block), `scripts/hooks/pre-push` (new:
    branch_drift), `.github/workflows/open-item-gates.yml` (new: the four
    CI-able gates, every verdict recorded in one run), `scripts/release_preflight.sh`
    (extended: secret_rotation + evidence_claim before a release is tagged).
    The install one-liner is documented in both hooks and the README —
    `git config core.hooksPath scripts/hooks` — and is deliberately **not**
    auto-installed on clone. Every hook and preflight step fails closed on a
    missing gate script (hard error, never a silent pass), and nothing-scanned
    (exit 3) is not green anywhere in the wiring.

    Commit-moment semantics, stated because the raw gate verdicts alone would
    misdescribe the moment: `tree_clean` counts the staged set as dirt (it is
    `git status` output), and `branch_drift` counts the refs being pushed as
    drift (their tips are on no remote yet). The hooks run the gates
    **unmodified** and filter only the in-flight set from their verdicts — the
    staged commit (tc-01 exempts "a committed change") and the push's own refs
    — then fail closed on anything left. Demonstrated below on both sides.

  - **Measured 2026-11-15. Every gate run with a real command and a read exit
    code (`cmd > /tmp/x.log 2>&1; echo rc=$?`, exit code read, not a tail):**

    `tree_clean_check.py` — the two sides of the commit moment:

    ```
    $ python3 scripts/tree_clean_check.py --root . --max-depth 0   # this working tree
    repos scanned: 1 | with unclassified dirt: 1

      AIGGP-Agentic-Framework  real=12 generated=0 mode-only=0
        M   CHANGELOG.md
        M   README.md
        M   openspec/changes/add-open-item-gates/tasks.md
        M   scripts/hooks/pre-commit
        M   scripts/release_preflight.sh
        ??  .github/workflows/open-item-gates.yml
        ??  docs/evidence-claim-allowlist.txt
        ??  docs/open-items-ledger.md
        ??  docs/open-items-triage.jsonl
        ??  docs/secret-rotation.jsonl
        ... and 2 more

    FAIL: 1 repo(s) carry unclassified working-tree dirt. Commit the real work; add generated paths to .gitignore or --generated.
    rc=1
    ```
    (rc=1 is the honest state mid-change: the twelve named entries are exactly
    this change's own files — hooks, workflow, the three ledgers, the
    allowlist, the surfaces manifest, README, this tasks file — plus a
    CHANGELOG edit a concurrent session is writing. Nothing else is dirt.)
    Green side, on a clean clone of HEAD:

    ```
    $ git clone --quiet . /tmp/aiggp-clean-clone && python3 scripts/tree_clean_check.py --root /tmp/aiggp-clean-clone --max-depth 0
    repos scanned: 1 | with unclassified dirt: 0
    OK: no unclassified working-tree dirt
    rc=0
    ```

    `branch_drift_check.py` — real state of this clone:

    ```
    $ python3 scripts/branch_drift_check.py --root . --max-depth 0
    repos scanned: 1 | drift refs: 5 | unreachable remotes: 0

      AIGGP-Agentic-Framework  (5 ref(s) on no remote, 3 archived)
        chore/digest-followups                       88fef4584d0a  34 ahead
        devgate/secret-gate-adoption                 1b315f654b77  7 ahead
        docs/gitlab-sprint0-blocked                  af1cf2c4a20f  1 ahead
        fix/semantic-overlay-merge                   43532b6b2950  0 ahead
        spec-fleet-gate                              581ad56131b4  0 ahead

    FAIL: 5 ref(s) exist only on local disk. Push them, or tag archive/<name>-<date> to declare them deliberately parked.
    rc=1
    ```

    `open_item_aging_check.py` — decided inputs, green:

    ```
    $ python3 scripts/open_item_aging_check.py docs/open-items-ledger.md --triage docs/open-items-triage.jsonl
    open rows: 6 | aged >14d: 3 | triaged: 3 | expired deferrals: 0
    OK: every aged open item carries a live triage disposition
    rc=0
    ```

    `secret_rotation_check.py` — decided input, **RED** (the fixture
    disposition gap, recorded as OI-006; the honest rows cannot be green under
    real-secret rules and inventing `revoked: true` is refused):

    ```
    $ python3 scripts/secret_rotation_check.py docs/secret-rotation.jsonl
    entries: 5 | unrevoked: 2 | still committed: 3 | missing evidence: 0

    5 violation(s):
      gak-20261004-oap-envelope-fixtures: still in HEAD after 42d — the secret is live in the tree
      gak-20261005-oap-vectors: still in HEAD after 41d — the secret is live in the tree
      gak-20261004-harden-envelope-fixtures: still in HEAD after 42d — the secret is live in the tree
      gak-20261022-hub-operator-auth-fixtures: scrubbed from HEAD 24d ago but never revoked at the provider — scrubbing is not revocation (N34 pattern)
      gak-20261023-hub-build-toolchain-fixtures: scrubbed from HEAD 23d ago but never revoked at the provider — scrubbing is not revocation (N34 pattern)
    rc=1
    ```

    `surface_reach_check.py` — the ten forge-twin groups, green:

    ```
    $ python3 scripts/surface_reach_check.py docs/surfaces.json
    groups: 10 | surfaces checked: 20 | divergences: 0
      [OK] forge-bundle-size-check: 2 surface(s), mode=exists
      [OK] forge-drift-scan: 2 surface(s), mode=exists
      [OK] forge-file-size-check: 2 surface(s), mode=exists
      [OK] forge-guardrails-compliance: 2 surface(s), mode=exists
      [OK] forge-secret-validation: 2 surface(s), mode=exists
      [OK] forge-smoke-gate: 2 surface(s), mode=exists
      [OK] forge-spec-coherence: 2 surface(s), mode=exists
      [OK] forge-specs: 2 surface(s), mode=exists
      [OK] forge-storage-hygiene: 2 surface(s), mode=exists
      [OK] forge-text-integrity: 2 surface(s), mode=exists
    rc=0
    ```

    `evidence_claim_check.py` — declared allowlist, **RED** on exactly the one
    recorded item (290 raw findings scoped to 1; OI-005 owns it):

    ```
    $ python3 scripts/evidence_claim_check.py --root . --allow docs/evidence-claim-allowlist.txt
    files scanned: 1051 | unevidenced markers: 1 (bare=1)
      hub/alerts.py:67  [bare] marker with no evidence annotation
          raise NotImplementedError

    FAIL: mock/stub/deferred work must carry a followable reference. Use DEFERRED(owner=,reason=,review=), MOCK(src=,why=), or STUB(issue=,why=).
    rc=1
    ```

  - **The evidence-claim allowlist is declared and non-vacuous, 2026-11-15.**
    `docs/evidence-claim-allowlist.txt` names each exemption class with its
    reason (vendored trees, generated bytecode, benchmark fixture repos,
    detector docs and tooling that must quote marker syntax, prose ledgers that
    record findings by quoting them, and the named test fixture files). The
    290 raw findings (181 vendored `actions/stitcher-codereview/node_modules`,
    69 root `node_modules`, 17 tests, 8 scripts, 3 hub, 3 archived plans, 3
    spec prose, 3 docs/qa, 2 detector rules, 1 benchmark fixture) scope down to
    exactly the one real recorded item. Proven non-vacuous with a planted
    canary assembled at run time (no literal stored): a bare marker in
    `CANARY-evc-probe.py` (outside scope) is FLAGGED, the same marker under a
    vendored-tree path is EXEMPT, and both canaries are removed after the run:

    ```
    gate exit code: 1
    outside canary FLAGGED: True
    inside canary EXEMPT (not named): True
      gate said:   CANARY-evc-probe.py:1  [bare] marker with no evidence annotation
    canary files removed
    ```

  - **Hooks demonstrated on both sides of the moment, 2026-11-15.** Unstaged
    standing dirt blocks (the ten entries above are not yet the commit in
    flight); pushing `main` alone blocks on the five standing drift refs;
    pretending the push carries all five allows. Fail-closed proven by removing
    the gate script in a scratch clone (below).

    ```
    $ bash scripts/hooks/pre-commit            # dirty tree, nothing staged
    tree_clean: unclassified working-tree dirt beyond the commit in flight:
      M   CHANGELOG.md
      ... (this change's uncommitted entries) ...
    pre-commit: BLOCKED by tree_clean_check.py (local block; `git commit --no-verify`
    bypasses this hook and the push-time CI job DETECTS the state after it lands).
    rc=1

    $ printf 'refs/heads/main %s refs/heads/main %s\n' "$(git rev-parse main)" "$(git rev-parse main)" | bash scripts/hooks/pre-push origin <url>
    branch_drift: local ref(s) on no remote, not part of this push:
      chore/digest-followups                       88fef4584d0a  34 ahead
      devgate/secret-gate-adoption                 1b315f654b77  7 ahead
      docs/gitlab-sprint0-blocked                  af1cf2c4a20f  1 ahead
      fix/semantic-overlay-merge                   43532b6b2950  0 ahead
      spec-fleet-gate                              581ad56131b4  0 ahead
    pre-push: BLOCKED by branch_drift_check.py ...
    rc=1

    $ <same push lines, plus one line per drift ref: chore/digest-followups, devgate/secret-gate-adoption, docs/gitlab-sprint0-blocked, fix/semantic-overlay-merge, spec-fleet-gate> | bash scripts/hooks/pre-push origin <url>
    rc=0                                   # every drift ref is in this push

    $ cp scripts/hooks/pre-commit /tmp/aiggp-clean-clone/scripts/hooks/ && cd /tmp/aiggp-clean-clone && mv scripts/tree_clean_check.py /tmp/hold-tree-clean.py && bash scripts/hooks/pre-commit
    pre-commit: FAIL CLOSED — required gate script missing: scripts/tree_clean_check.py
    pre-commit: a missing gate is a hard error, never a silent pass.
    rc=1                                   # restored afterwards
    ```

  - The gate suite is untouched by this wiring and stays green:
    `python3 -m pytest tests/test_open_item_gates.py -q` → `30 passed`, rc=0.
- [x] 4.2 Adopt a triage ledger and a rotation ledger with content. The gates
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
  - **ADOPTED 2026-11-15 — all four missing inputs are now supplied, with real
    content.** Decided paths: `docs/open-items-ledger.md` (backlog),
    `docs/open-items-triage.jsonl` (dispositions), `docs/secret-rotation.jsonl`
    (rotation records).
    1. **Backlog:** six dated open rows seeded from the real open boxes of this
       program — four from `openspec/changes/add-gitlab-forge-support/tasks.md`
       and `add-art-creation-contract/tasks.md` (Sprint 0, the live parity
       half, GLF-10, and the archive-time CHANGELOG entry) with their true
       source dates (2026-10-11, 2026-10-11, 2026-10-11, 2026-11-08), plus two
       rows this rollout itself produced (the `hub/alerts.py:67` evidence-claim
       finding and the secret-rotation fixture-disposition gap, 2026-11-15).
       The MC-routed digest backlog (`docs/DIGEST-FOLLOWUPS.md`, NEXT-* ids,
       triaged in Mission Control) is deliberately not duplicated into this
       ledger: a row with two owners loses both. An empty ledger was refused as
       a measurement — six rows, three of them aged past the 14-day window.
    2. **Dispositions:** one JSONL object per row, keyed by id, covering every
       aged row (and the two fresh ones): all six are `deferred` with a future
       `review_by` and a written `reason` — each is honestly blocked on an
       owner decision or an external input, and a deferral that expires is the
       only deferral the gate accepts. Nothing is claimed `fixed`.
    3. **Real-vs-fixture classification:** `bash scripts/secret-scan.sh --repo .
       --report /tmp/aiggp-ss.json --all` → `rc=1`, `scanned 82 finding(s): 40
       allowlisted, 42 to fix`. All 42 uncovered hits were verified, not
       assumed: every one is TEST FIXTURE. Method — path class (`fixtures/`,
       `vectors/`, `tests/`), usage context (test-helper `secret=` default
       arguments and signed envelope/vector payloads), zero provider-prefix
       shapes (0 of 42 match `sk-`/`ghp_`/`AKIA`-style classes), and byte
       identity between the pre-archive fixture paths and their copies under
       `openspec/changes/archive/2026-10-13-*` where the scan already
       allowlists them. They are recorded as fixtures in five rotation rows
       (family + first-seen grouping, 2026-10-04 → 2026-10-23), with locations
       cited by path and line only — no secret value is stored or echoed. The
       two test-file groups are recorded `removed_from_head: true` (each hit
       span verified absent from HEAD on 2026-11-15, still reachable in
       history); the three fixture groups persist under their archive paths and
       are recorded `removed_from_head: false`.
    4. **Provider revocation records:** none exist and none are invented. No
       detection was real, so nothing was revoked at any provider and no
       revocation date or evidence id is claimed. For anything classified real
       the row would carry `revoked: false`, the real state, and the named
       actor — there were no such rows. Marking a fixture `revoked: true` to
       silence the gate is refused on purpose: it would claim a provider
       revocation that never happened (OI-006 records the decision this forces).
  - **Measured 2026-11-15 — the two ledger gates on the adopted inputs**
    (same `cmd > /tmp/x.log 2>&1; echo rc=$?` discipline; the full six-gate
    record is in 4.1):

    ```
    $ python3 scripts/open_item_aging_check.py docs/open-items-ledger.md --triage docs/open-items-triage.jsonl
    open rows: 6 | aged >14d: 3 | triaged: 3 | expired deferrals: 0
    OK: every aged open item carries a live triage disposition
    rc=0
    ```

    ```
    $ python3 scripts/secret_rotation_check.py docs/secret-rotation.jsonl
    entries: 5 | unrevoked: 2 | still committed: 3 | missing evidence: 0

    5 violation(s):
      gak-20261004-oap-envelope-fixtures: still in HEAD after 42d — the secret is live in the tree
      gak-20261005-oap-vectors: still in HEAD after 41d — the secret is live in the tree
      gak-20261004-harden-envelope-fixtures: still in HEAD after 42d — the secret is live in the tree
      gak-20261022-hub-operator-auth-fixtures: scrubbed from HEAD 24d ago but never revoked at the provider — scrubbing is not revocation (N34 pattern)
      gak-20261023-hub-build-toolchain-fixtures: scrubbed from HEAD 23d ago but never revoked at the provider — scrubbing is not revocation (N34 pattern)
    rc=1
    ```

    The aging gate is green over non-vacuous content (6 rows parsed, 3 aged,
    3 triaged — an empty ledger would have been exit 3). The rotation gate is
    **RED** and says so: sr-01..04 apply real-secret rules to every row, and
    the honestly classified fixture rows fail them. That red is the
    measurement, not a wiring fault — OI-006 tracks the decision (teach the
    gate an sr-05 fixture disposition, or keep this ledger for real secrets
    only and move fixture dispositions to `.guardrails/secret-allowlist.json`).
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


## 5. Two corrections on top of the rollout, 2026-11-15 (measured, not asserted)

### 5.1 `secret_rotation_check.py` learns a true-negative disposition

The five rotation rows are **not secrets**. Re-measured by field-name audit of
the cited files: the credential-shaped values sit in fields named
`signing_public_key_hex`, `public_key`, `key_id`. A scan of the same documents
for private-or-secret-shaped field names (`private|secret|password|passwd|
credential|token|api.?key`) returns **ZERO hits**. A public key is published by
design and a key id is an identifier; neither has a provider secret to revoke.
The scanner matched the substring "key" in a field name, not a credential.

The gate had no way to say that. Modelling every detection as a secret is
itself a false model: it demands a provider revocation for something that has
none, and it pressures an author into writing `revoked: true` for a thing that
was never revoked — which is worse than a red gate. So `not_a_secret: true`
plus a mandatory non-empty `determination` is now a first-class disposition.
It is **counted and printed on every run** (`| not-a-secret (reviewed): N`), so
a reviewed non-secret is visible, never silently absorbed.

**The gate is not weakened, and that is proved rather than asserted.**
Negative controls, each with a read exit code:

| Control | rc | Result |
|---|---|---|
| real scrubbed-not-revoked secret | **1** | `scrubbed from HEAD 45d ago but never revoked (N34 pattern)` |
| real still-committed secret | **1** | `still in HEAD after 45d` |
| `not_a_secret: true` with **no** determination | **1** | `an unevidenced non-secret is indistinguishable from hiding one` |
| the five reviewed rows | **0** | `not-a-secret (reviewed): 5` |

The three "still in HEAD" rows also had **stale paths** — they cited
pre-archive locations that no longer exist. Corrected to the real
`openspec/changes/archive/2026-10-13-*` paths.

### 5.2 `evidence_claim_check.py` stops flagging abstract methods

`hub/alerts.py:67` is `raise NotImplementedError` as the body of an
`@abc.abstractmethod`. That is not deferred work: it is unreachable (the ABC
machinery refuses to instantiate the class) and it is the canonical Python body
for a method that must be overridden. Flagging it does not surface a gap — it
pressures the author to delete the guard, after which an unimplemented abstract
method silently returns `None`, which is strictly worse.

Fixed by walking back from the raise through the enclosing function body to its
`def` line, then through the decorator stack above it. **A naive lookback window
is not enough and was proved wrong before the fix landed:** a 5-line window
exempted a raise in `h()` because `@abc.abstractmethod` sat on the *previous*
function `g()`. Two rounds of negative control were needed:

| Control | rc | Meaning |
|---|---|---|
| bare raise, no decorator | **1** | still a finding |
| `@abc.abstractmethod` on a **different** def | **1** | must NOT exempt (this caught the window bug) |
| `@abc.abstractmethod` on the **same** def | **0** | correctly exempt |
| plain `# TODO:` | **1** | still a finding |
| real repo scan | **0** | `1051 files, 0 unevidenced markers` |

Both changes are precision fixes to false models, not exemptions. Nothing was
added to an allowlist and no gate was made easier for a real violation.
