# Tasks: art-creation-contract

Nothing here is marked complete from spec authoring. A checked box means the
work ran and its evidence is named below, not that the line was written.

**Traceability read at 2026-11-08, not assumed — and re-read after the rebase
onto `f5da682`, because the remote ratcheted underneath this change:** at this
head `195/199 requirements covered`, advisory 4 uncovered. Baseline without
this change (`f5da682`) is `184/187 covered`, advisory 3. Delta: +12
requirement IDs (187 -> 199), +11 covered (184 -> 195). 11 of the 12 carry
source markers at their enforcement sites across two files
(`scripts/art_checks.py`, `scripts/art_check_outcome.py`); the entry point
(`scripts/art_creation_scan.py`) carries no marker (see 2.1). The one without
a marker is `art-evolve-01`, which is a process obligation on a human, not a
code enforcement site — recorded as deliberately uncovered rather than papered
over. It is the +1 in the advisory count (3 -> 4).

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
      in the selftest. The three scanner files are at or under the source soft
      limit (300); the fixture suite sits between the soft (300) and hard (600)
      test limits:
      - `scripts/art_creation_scan.py` (157) — entry point: manifest lookup,
        `run_checks` orchestration, exit-code contract, `--selftest`.
      - `scripts/art_checks.py` (280) — declaration and inventory: brief,
        stages, ledger, rights.
      - `scripts/art_check_outcome.py` (219) — outcome: bytes, acceptance,
        draw, quantity.
      - `scripts/test_art_creation_scan.py` (381) — the fixture suite.
      The entry point still exposes `DIGEST_STAGES` / `run_checks` / `report`
      so the fixture import is unchanged.
- [x] 1.2 `art-brief-01` / `art-brief-02` — brief exists and is versioned, rows
      carry `brief_ref` naming that version, and a geometric rule is declared
      for every class present in the ledger. A declared rule must be a
      non-blank string: `{"furniture": ""}` and `{"furniture": null}` are
      findings, not declarations. `brief_version` and `brief_ref` must also be
      non-blank; two whitespace values must not compare as a version. Fixtures
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
- [x] 3.3 Negative controls: 55 negatives among 60 cases (5 pass + 55 fail),
      plus 2 exit-contract checks outside `CASES` (a valid-JSON non-object
      manifest exits 2; a non-object ledger row exits 1 with a named
      `art-ledger-01` finding, never a traceback). Both exit-contract checks
      drive the real `main()` and assert its return code: `run_checks` alone
      shows the finding but cannot pin the process exit.
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
      `does not state:`). Selftest output: `60 cases, 2 exit-contract checks`,
      all ok.

      Three of the negatives pin the published-count type rule
      (`count-bool`, `count-float`, `count-string`) and each asserts the
      `is not an integer` message, not only the exit code — JSON `true` is an
      `int` subclass and `True == 1`, and `1.0 == 1` has the same shape, so a
      bare `true` or `1.0` in `published_counts` used to report a derived
      count that was never derived. With the message assertion, deleting the
      type guard fails all three rather than only the two whose value would
      also disagree with the derived count. The auditor's exact adversarial
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
      `art-evolve-01`). Seven cite `43a9bdb` (except the done check, `616f26f`)
      as the commit that made the class checkable; the eighth cites `0779267`,
      the commit that documents the path. `failure_registry_check.py` exits 0
      over 58 entries.
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
- [x] 5.2 Traceability read and recorded above.
- [ ] 5.3 Independent audit by an agent that did not write this change.
      **NOT_RUN** — not complete: the independent audit returned
      REQUEST-CHANGES, this response has not been re-audited, and the item is
      not reported as passed.
- [ ] 5.4 CHANGELOG entry at archive time, not before.
