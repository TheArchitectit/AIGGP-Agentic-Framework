# Tasks: art-creation-contract

Nothing here is marked complete from spec authoring. A checked box means the
work ran and its evidence is named below, not that the line was written.

**Traceability read at 2026-11-08, not assumed — and re-read after the rebase
onto `f5da682`, because the remote ratcheted underneath this change:** at this
head `195/199 requirements covered`, advisory 4 uncovered. Baseline without
this change (`f5da682`) is `184/187 covered`, advisory 3. Delta: +12
requirement IDs (187 -> 199), +11 covered (184 -> 195). 11 of the 12 carry
source markers at their enforcement sites across the three scanner files
(`scripts/art_checks.py`, `scripts/art_check_outcome.py`,
`scripts/art_creation_scan.py`). The one without a marker is `art-evolve-01`,
which is a process obligation on a human, not a code enforcement site —
recorded as deliberately uncovered rather than papered over. It is the +1 in
the advisory count (3 -> 4).

## S0 — Contract

- [x] 0.1 Freeze the ledger minimum-field set as spec-governed data
      (`art-ledger-01`). Landed as `LEDGER_MIN_FIELDS` in the scanner, 11
      fields; removing one is a change, not a config edit. Titles may add
      fields.
- [x] 0.2 Freeze the `stage` enum as derived from the title's declared pipeline
      stages. Landed in `check_stages`: the enum is built only from stages
      whose consumer exists, so a stage with no reader cannot enter it
      (`art-stage-01`). Fixture `accepted-not-terminal` pins the done-check
      against it.
- [x] 0.3 Fix the brief's required field list. Landed as the seven headings
      `check_brief` requires: readability, pillar, palette, shape language,
      footprint, material, camera. Every value stays with the title.

## S1 — Scanner

- [x] 1.1 The scanner reads a declared manifest. `NOT_APPLICABLE` is exit 3
      and prints "a zero-input run is not a green run". Fixture path exercised
      in the selftest. Laid out at the source soft limit (300), not squeezed
      toward the hard one:
      - `scripts/art_creation_scan.py` (143) — entry point: manifest lookup,
        `run_checks` orchestration, exit-code contract, `--selftest`.
      - `scripts/art_checks.py` (201) — declaration and inventory: brief,
        stages, ledger, rights.
      - `scripts/art_check_outcome.py` (131) — outcome: bytes, acceptance,
        draw, quantity.
      - `scripts/test_art_creation_scan.py` (158) — the fixture suite.
      Every source file is under the soft limit; the entry point still exposes
      `DIGEST_STAGES` / `run_checks` / `report` so the fixture import is
      unchanged.
- [x] 1.2 `art-brief-01` / `art-brief-02` — brief exists and is versioned, rows
      carry `brief_ref` naming that version, and a geometric rule is declared
      for every class present in the ledger.
- [x] 1.3 `art-stage-01` — consumer named and its path exists. Two fixtures:
      `stage-no-consumer`, `consumer-path-missing`.
- [x] 1.4 `art-ledger-01` — minimum fields per row, no duplicates, a digest per
      stage, artifacts outside the ledger named, published counts derived.
      Fixture `count-disagrees`.
- [x] 1.5 `art-bytes-01` — replication recorded, restore exercised, deletions
      carry a reason. Fixtures `no-replication`, `restore-never-run`.
- [x] 1.6 `art-accept-01` / `art-accept-02` — verdict names the declared rule
      for its class; `threshold` present and null means non-gating. Fixtures
      `verdict-no-rule`, `wrong-rule-for-class`, `meas-no-threshold`.
- [x] 1.7 `art-draw-01` — capture per target, `renderer: "dcc-preview"`
      rejected, `contains_game_geometry` required. Fixtures `no-capture`,
      `dcc-preview`, `clears-buffer-only` — the last is the observed class.
- [x] 1.8 `art-rights-01` — blank is invalid. Fixture `blank-rights`.
- [x] 1.9 `art-qty-01` — floor cannot be green while fidelity is red; the two
      quantities printed separately.
- [x] 1.10 Exit codes 0/1/2/3 as documented in the module docstring.

## S2 — Marker coverage

- [x] 2.1 `# spec:` markers sit at the enforcement sites and name the 11
      requirement IDs the scanner enforces:
      - `art_checks.py` — `art-brief-01, art-brief-02, art-stage-01,
        art-ledger-01, art-rights-01`
      - `art_check_outcome.py` — `art-bytes-01, art-accept-01, art-accept-02,
        art-done-01, art-draw-01, art-qty-01`
      - `art_creation_scan.py` — `art-done-01, art-draw-01` (the exit-code and
        NOT_APPLICABLE rule)
      Union of the three sets is exactly the 11.
- [x] 2.2 Traceability **read** at this head: `195/199 covered`, advisory 4
      uncovered (baseline at `f5da682`, without this change: `184/187`,
      advisory 3). Delta: +12 requirement IDs, +11 covered. `art-evolve-01`
      deliberately uncovered — see the note above. The absolute numbers are
      re-read after the rebase, not carried forward: the remote ratcheted
      traceability underneath this change and a stale figure here would have
      been the same class of claim as the 411-line one.

## S3 — Fixture

- [ ] 3.1 Point the scanner at a live title exhibiting the `proposal.md`
      failure classes and record its actual output. **NOT_RUN** — the fixture
      title is outside this repository and wiring it is the follow-on work
      named in the proposal's Impact section. Not reported as passed.
- [x] 3.2 Synthetic pass fixture: the selftest's `pass` case runs the real
      `run_checks` against a temp tree with a real brief, a real consumer file
      and a real ledger, and must report zero findings.
- [x] 3.3 Negative controls: 24 negatives among 25 cases (1 pass + 24 fail).
      Each case asserts the EXACT set of requirement IDs it trips - which may
      contain more than one id, and is supposed to. `stage-empty` trips both
      `art-ledger-01` (blank stage) and `art-done-01` (never reaching terminal
      stage), which is the fail-closed behaviour the done check was fixed to
      have; "exactly one requirement per case" would have been a bug. The
      set-equality assertion is what makes that checkable: a mutated expected
      set fails even when the exit code matches. Selftest output: `25 cases`,
      all ok.

      Three of the negatives pin the published-count type rule
      (`count-bool`, `count-float`, `count-string`) — JSON `true` is an `int`
      subclass and `True == 1`, and `1.0 == 1` has the same shape, so a bare
      `true` or `1.0` in `published_counts` used to report a derived count that
      was never derived. The auditor's exact adversarial case
      (`{"published_counts": {"library": true}}` against a 1-row ledger) is
      re-run through the real CLI as well as the fixture suite: it returns
      exit 1 with `art-ledger-01: published count 'library' is not an integer`.
      The honest `{"library": 1}` against the same ledger still returns exit 0.

## S4 — Registry wiring

- [ ] 4.1 Append the eight observed failure classes to the failure registry
      with prevention rules citing the requirement that would have prevented
      each (`art-evolve-01`). **NOT_RUN.**
- [ ] 4.2 Document the extension path. **NOT_RUN** — lands with 4.1.

## S5 — End gate

- [x] 5.1 `openspec validate --all --strict` at this head: `32 passed, 13
      failed (45 items)`. The 13 failures are the 13 pre-existing failing
      changes and specs (9 `change/` + 4 `spec/`), not open work this change
      introduced - baseline before this change: `31 passed, 13 failed (44
      items)`. This change validates: `✓ change/add-art-creation-contract`.
- [x] 5.2 Traceability read and recorded above.
- [ ] 5.3 Independent audit by an agent that did not write this change.
- [ ] 5.4 CHANGELOG entry at archive time, not before.
