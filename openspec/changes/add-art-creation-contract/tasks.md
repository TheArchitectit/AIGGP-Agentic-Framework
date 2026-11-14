# Tasks: art-creation-contract

Nothing here is marked complete from spec authoring. A checked box means the
work ran and its evidence is named below, not that the line was written.

**Traceability measured, not assumed — and measured twice, because a figure
carried forward is the same class of claim as any other.** The change's own
delta was read on 2026-11-08 at `43a9bdb`: `195/199 requirements covered`,
advisory 4. Baseline without this change (`f5da682`) is `184/187 covered`,
advisory 3 — delta +12 requirement IDs (187 -> 199), +11 covered (184 -> 195).
Those figures reproduce against those two commits and their own
`spec_traceability.py`; they are not the tree's totals today. At `cb2644c` the
corpus reads `235/241 covered`, advisory 6 — the corpus grew by 42 ids over
those figures (199 -> 241), 40 of them covered, and the additional *uncovered*
ids are `game-matrix-01..03` (already uncovered in the `f5da682` baseline),
`spec-state-08` and `spec-state-09`. The art outcome is unchanged: 11 of the
12 ids carry source markers at
their enforcement sites across `scripts/art_checks.py` and
`scripts/art_check_outcome.py`; the entry point
(`scripts/art_creation_scan.py`) carries no marker (see 2.1); and
`art-evolve-01` — a process obligation on a human, not a code enforcement site
— is recorded as deliberately uncovered rather than papered over. Ratchet floor
at that head: 228. Re-measure and rebind the number before archive.

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
      and prints "a zero-input run is not a green run". The rule is pinned
      through `main()`, not only through `report()`: the `not-applicable`
      exit-contract check runs the CLI against an empty root and asserts exit
      3 plus both lines, and `manifest-missing-explicit` asserts that a named
      but absent `--config` is exit 2 rather than a clean skip. The three
      scanner files are at or under the source soft
      limit (300); the fixture suite sits between the soft (300) and hard (600)
      test limits:
      - `scripts/art_creation_scan.py` (157) — entry point: manifest lookup,
        `run_checks` orchestration, exit-code contract, `--selftest`.
      - `scripts/art_checks.py` (280) — declaration and inventory: brief,
        stages, ledger, rights.
      - `scripts/art_check_outcome.py` (219) — outcome: bytes, acceptance,
        draw, quantity.
      - `scripts/test_art_creation_scan.py` (426) — the fixture suite.
      The entry point still exposes `DIGEST_STAGES` / `run_checks` / `report`
      so the fixture import is unchanged.
- [x] 1.2 `art-brief-01` / `art-brief-02` — brief exists and is versioned, rows
      carry `brief_ref` naming that version, and a geometric rule is declared
      for every class present in the ledger. A declared rule must be a
      non-blank string: `{"furniture": ""}` and `{"furniture": null}` are
      findings, not declarations. `brief_version` is stripped and must be
      non-blank, so two whitespace values cannot agree on nothing. `brief_ref`
      has a presence check (`if not ref`), not a strip: a whitespace ref is
      caught as a version mismatch instead — it fails closed either way, but
      the requirement text promises a non-blank ref and the code enforces a
      present one. Fixtures
      `no-shape-rule`, `shape-rule-blank`, `shape-rule-null`,
      `brief-version-whitespace`.
- [x] 1.3 `art-stage-01` — every stage declares input, output, consumer and
      determinism, and the consumer is an existing file (a directory is not
      code). Negatives: `stage-no-consumer`, `consumer-path-missing`,
      `consumer-is-directory`, `stage-no-input`, `stage-no-output`,
      `stage-no-determinism`; `stage-complete` and the `pass` case carry all
      four and stay green.
- [x] 1.4 `art-ledger-01` — minimum fields per row, no duplicates, a digest per
      stage, artifacts outside the ledger named, published counts derived.
      Completeness is not presence: a row must carry a non-blank `prompt`, an
      integer `seed` (not null, not a bool) and a non-blank `class`, and a
      non-object row is a named finding rather than a traceback. Fixtures
      `count-disagrees`, `blank-prompt`, `null-seed`, `seed-string`,
      `blank-class`, `class-whitespace`; row shape is pinned by the
      `ledger-row-not-object` exit-contract check, which asserts the CLI exits
      1 with the named finding.
- [x] 1.5 `art-bytes-01` — replication recorded, restore exercised, deletions
      carry a reason. A non-boolean `present`, a whitespace-only
      `restore_exercised_at` and a whitespace-only `deletion_reason` are not
      records. Fixtures `no-replication`, `restore-never-run`,
      `replication-present-string`, `restore-whitespace`,
      `deletion-reason-whitespace`.
- [x] 1.6 `art-accept-01` / `art-accept-02` — verdict names the declared rule
      for its class; a measurement must exist (not `{}` or `null`) and carry
      meaning (`name` + `value`), with `threshold` present and null meaning
      non-gating. A missing or blank declared rule cannot skip the compare: an
      accept verdict is never checked against nothing. Class lookup strips, the
      same meaning of "class" as `check_brief`. Fixtures `verdict-no-rule`,
      `wrong-rule-for-class`, `meas-no-threshold`, `meas-empty`, `meas-null`,
      `meas-threshold-only`, `shape-rule-blank`, `shape-rule-null`,
      `class-padded-wrong-rule`, `class-padded-right-rule`.
- [x] 1.7 `art-draw-01` — capture per target, `renderer: "dcc-preview"`
      rejected, `contains_game_geometry` must be declared `true` (not a truthy
      string or `1`), and `frame_sha256` must be a non-blank digest. Fixtures
      `no-capture`, `dcc-preview`, `clears-buffer-only` — the last is the
      observed class — plus `geometry-string`, `geometry-int`,
      `capture-sha-whitespace`.
- [x] 1.8 `art-rights-01` — blank or whitespace-only is invalid, not just the
      empty string. Fixtures `blank-rights`, `blank-rights-ws`.
- [x] 1.9 `art-qty-01` — shortfall (`max(0, floor - counted)`) and fidelity
      failure are computed and reported independently, one message each. A
      declared floor that is not met fails even with every verdict green; a
      red verdict fails even with the floor met. A non-integer `library_floor`
      (bool included) and a negative one are each their own finding. Both
      messages print the floor (`floor=none` when none is declared). Fixtures
      `floor-shortfall-only`, `floor-fidelity-only`, `floor-shortfall-and-fidelity`,
      `floor-met-all-accept`, `floor-bool`, `floor-string`, `floor-negative`,
      `fidelity-only-no-floor`.
- [x] 1.10 Exit codes 0/1/2/3 as documented in the module docstring.

## S2 — Marker coverage

- [x] 2.1 `# spec:` markers sit at the enforcement sites and name the 11
      requirement IDs the scanner enforces. A marker now lives immediately
      above the function that enforces it, so deleting the check deletes the
      marker with it:
      - `art_checks.py` — `art-brief-01, art-brief-02` on `check_brief`;
        `art-stage-01` on `check_stages`; `art-ledger-01` on `check_ledger`;
        `art-rights-01` on `check_rights`
      - `art_check_outcome.py` — `art-bytes-01` on `check_bytes`;
        `art-accept-01, art-accept-02, art-done-01` on `check_acceptance`;
        `art-draw-01` on `check_draw`; `art-qty-01` on `check_quantity`
      - `art_creation_scan.py` — no marker. `report` owns the zero-input /
        NOT_APPLICABLE exit rule and never inspects targets, captures,
        renderer or geometry; the module-level marker at the top of this file
        (line 2 at `HEAD`, naming both `art-done-01` and `art-draw-01`, above
        the docstring, not on an enforcement site) kept traceability green
        when the real check was deleted. `art-done-01` does not appear here
        either: its enforcement site is `check_acceptance`.
      Every marker sits on the function that enforces it: the sweep found one
      offender (that module-level marker in the entry point) and deleted it.
      Proof on a `/tmp` copy with the `check_draw` marker removed:
      `art-draw-01: UNCOVERED`; on the real tree it stays covered by
      `check_draw` alone.
      Union of the marker sites is exactly the 11.
- [x] 2.2 Traceability **read**, twice. At `43a9bdb` (this change's own
      measurement, 2026-11-08): `195/199 covered`, advisory 4 uncovered
      (baseline `f5da682`, without this change: `184/187`, advisory 3) —
      delta +12 requirement IDs, +11 covered. Re-read at `cb2644c`:
      `235/241 covered`, advisory 6; the uncovered ids there are
      `game-matrix-01..03`, `art-evolve-01`, `spec-state-08` and
      `spec-state-09`, and only `art-evolve-01` belongs to this change.
      Each figure is bound to the commit it was read at, not carried forward:
      the remote ratchets traceability underneath this change, and a stale
      figure here would be the same class of claim as the 411-line one.

## S3 — Fixture

- [ ] 3.1 Point the scanner at a live title exhibiting the `proposal.md`
      failure classes and record its actual output. **NOT_RUN** — the fixture
      title is outside this repository and wiring it is the follow-on work
      named in the proposal's Impact section. Not reported as passed.
- [x] 3.2 Synthetic pass fixture: the selftest's `pass` case runs the real
      `run_checks` against a temp tree with a real brief, a real consumer file
      and a real ledger, and must report zero findings.
- [x] 3.3 Negative controls: 55 negatives among 60 cases (5 pass + 55 fail),
      plus 4 exit-contract checks outside `CASES`: a valid-JSON non-object
      manifest exits 2; a non-object ledger row exits 1 with a named
      `art-ledger-01` finding, never a traceback; a root with no manifest
      exits 3 through `main()` with both zero-input lines; an explicitly
      named but absent `--config` exits 2, not 3. All four drive the real
      `main()` and assert its return code: `run_checks` alone shows the
      finding but cannot pin the process exit. The last two were added after
      the independent audit found the zero-input rule was pinned only through
      `report()`; each was proven able to fail on a `/tmp` copy (`return 3`
      -> `return 0` reds `not-applicable`; removing the `if args.config`
      branch reds `manifest-missing-explicit` with exit 3).
      Each case asserts the EXACT set of requirement IDs it trips - which may
      contain more than one id, and is supposed to. `stage-empty` trips both
      `art-ledger-01` (blank stage) and `art-done-01` (never reaching terminal
      stage), which is the fail-closed behaviour the done check was fixed to
      have; "exactly one requirement per case" would have been a bug. The
      set-equality assertion is what makes that checkable: a mutated expected
      set fails even when the exit code matches. Where two branches trip the
      same requirement, the ID set cannot see one branch removed, so the
      `art-qty-01` and `art-stage-01` negatives also pin the exact finding
      count and message substrings (`shortfall=`, `fidelity-fail=`,
      `does not state:`). Selftest output: `60 cases, 4 exit-contract checks`,
      all ok.

      Three of the negatives pin the published-count type rule
      (`count-bool`, `count-float`, `count-string`) and each asserts the
      `is not an integer` message, not only the exit code — JSON `true` is an
      `int` subclass and `True == 1`, and `1.0 == 1` has the same shape, so a
      bare `true` or `1.0` in `published_counts` used to report a derived
      count that was never derived. With the message assertion, deleting the
      type guard fails all three fixtures; without it, `count-string` would
      pass (its value still mismatches, so exit 1 and the id set match),
      while `count-bool` and `count-float` would still fail on the exit code
      because the scanner exits 0 where the fixture expects 1. The pair was
      named backwards here once; the audit caught it. The auditor's exact
      adversarial
      case (`{"published_counts": {"library": true}}` against a 1-row ledger)
      is re-run through the real CLI as well as the fixture suite: it returns
      exit 1 with `art-ledger-01: published count 'library' is not an integer`.
      The honest `{"library": 1}` against the same ledger still returns exit 0.

## S4 — Registry wiring

- [x] 4.1 Append the eight observed failure classes to the failure registry
      with prevention rules citing the requirement that would have prevented
      each (`art-evolve-01`). Logged through `scripts/log_failure.py`, one
      entry per class, each `prevention_rule` naming its covering requirement:
      `FAIL-0e705936` (no shared language → `art-brief-01, art-brief-02`),
      `FAIL-920d00bd` (unversioned bytes → `art-bytes-01`), `FAIL-64935b0d`
      (stage with no reader → `art-stage-01`), `FAIL-2ba50210` (done meant
      "file written" → `art-done-01`), `FAIL-49fe7808` (target draws nothing →
      `art-draw-01`), `FAIL-3830b455` (quantity for quality → `art-qty-01`),
      `FAIL-bb25c017` (score on the wrong question → `art-accept-01,
      art-accept-02`) and `FAIL-d91fd88e` (method written after the mess →
      `art-evolve-01`). Six cite `43a9bdb` as the commit that made the class
      checkable, the done check cites `616f26f`, and the eighth — the process
      obligation — cites `0779267`, the commit that documents the path it
      names. `failure_registry_check.py` exits 0 over 58 entries.
- [x] 4.2 Document the extension path. Landed as
      `docs/ART-CONTRACT-EXTENSION.md`: log with `scripts/log_failure.py`,
      decide coverage by the requirement ids, extend the delta when nothing
      covers the class, put the marker on the enforcing function (never above
      a module docstring), add the negative control first, then run
      `test_art_creation_scan.py`, `failure_registry_check.py`,
      `spec_traceability.py --ratchet`, `openspec validate --all --strict` and
      the size/regression gate.

## S5 — End gate

- [x] 5.1 `openspec validate --all --strict`, re-measured 2026-11-08 at
      `43a9bdb`: `Totals: 47 passed, 0 failed (47 items)`, exit 0. Baseline
      at `f5da682`, extracted with `git archive` into a scratch tree:
      `Totals: 46 passed, 0 failed (46 items)`, exit 0. This change
      validates: `✓ change/add-art-creation-contract`. An earlier revision of
      this row quoted `32 passed, 13 failed (45 items)` against a
      `31 passed, 13 failed (44 items)` baseline; those figures predate
      `a596263` ("archive 13 complete change packages, publish 44 specs"),
      which is an ancestor of `f5da682`, so the 13-failure era was over
      before the stated base. Absolute counts are re-measured per head from
      here on rather than carried forward.
- [x] 5.2 Traceability read and recorded above: `195/199` at `43a9bdb`,
      `235/241` at `cb2644c`; ratchet floor 184 at `43a9bdb` and 228 at
      `cb2644c`, `--ratchet` exit 0 at both.
- [x] 5.3 Independent audit by an agent that did not write this change. The
      earlier audit returned REQUEST-CHANGES; this is the re-audit. Run
      2026-11-14 by a fresh agent that was given the change and no
      authorship, read-only over the tree (every mutation it tried was made in
      a `/tmp` copy). Verdict: **APPROVE**, with six nits — the fixture
      suite's line count, the traceability figures, the published-count pair
      (named backwards), the "seven cite `43a9bdb`" wording, the `brief_ref`
      over-claim, and the zero-input rule, which it found pinned only through
      `report()`. All six are fixed above; the sixth by adding two real
      `main()` exit-contract checks and proving both able to fail. Verdict on
      that delta, re-checked: **APPROVE**, with three wording nits, also
      fixed. What it verified itself, not from this file: exactly 8 `# spec:`
      marker lines carrying 11 ids, each immediately above the `def` that
      enforces it and none above a docstring; `scripts/art_creation_scan.py`
      carries no marker; deleting the `check_draw` marker on a copy turns
      `art-draw-01` UNCOVERED (234/241); all eight registry ids exist with
      status `resolved`, prevention rules that resolve to delta ids, and
      `fix_commit`s that `git cat-file -t` reports as commits and
      `git merge-base --is-ancestor` confirms are ancestors of HEAD; the
      adversarial CLI case returns exit 1 with "is not an integer" for a
      boolean published count and exit 0 for the honest `1`; and each named
      tree's own traceability tool reproduces its figure (`43a9bdb`
      195/199, `f5da682` 184/187, `616f26f`, `0779267` and `3fcb661`
      235/241). It did not run the size gate, the regression gate or CI;
      those were run here, from `ci.yml`'s own commands, by exit code.
      Out of its reach, and still open: 3.1's live title.
- [ ] 5.4 CHANGELOG entry at archive time, not before.
