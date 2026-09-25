# Tasks: add-secret-scanning

## Sprint 1 — Baseline and decision (this change)

- [x] 1.1 Measure the baseline rather than assume it (2026-09-24): working tree
  clean; full history across all refs (253 commits, 4.95 MB) holds exactly one
  hit — `generic-api-key` on the *prose* `RUNNER_TOKEN` in
  `docs/qa/2026-09-19-audit-delta.md:89` on `origin/audit`, reporting the
  scanner's own `REDACTED` marker as the value
- [x] 1.2 Decide the scope split (design D2): the push gate scans the pushed
  range; the history sweep is explicit and never silent
- [x] 1.3 Decide the disposition path (design D4): an entry covers a rule *and*
  a path, carries a reason, and goes stale visibly — never a disabled rule and
  never an excluded file class
- [x] 1.4 Pin the scanner by measurement (design D5): gitleaks `v8.30.1`,
  `linux_x64` tarball `sha256:551f6fc8…470eb`, matched against the vendor's
  `gitleaks_8.30.1_checksums.txt`
- [x] 1.5 Delta spec `specs/secret-scanning/spec.md` with `secret-scan-01` …
  `secret-scan-07`

## Sprint 2 — The gate script

- [x] 2.1 `scripts/secret-scan.sh`: scan the pushed range plus the working
  tree, redacted always, with the exit contract of secret-scan-01 (0 clean and
  scope-named, 1 finding, 2 scanner unusable, 3 bad invocation) and the
  fall-back-with-a-stated-scope behaviour for a base commit that does not exist
- [x] 2.2 Allowlist disposition: read `.guardrails/secret-allowlist.json`,
  require a reason per entry, fail uncovered findings, report stale entries
- [x] 2.3 Tests: a finding fails and is reported without the value; absent
  scanner fails closed; clean run exits 0 naming its scope; the range is the
  scope; missing base falls back and says so; an uncovered occurrence of an
  allowlisted rule still fails; a reasonless entry is refused; a stale entry is
  reported. Mutation-kill each guard by exactly one named test —
  `tests/test_secret_scan.py`, 18 tests
- [x] 2.4 `--all` sweep flag with its own scope reporting (secret-scan-04)
- [x] 2.5 Mutation battery, 2026-09-24: **20 mutations, 20 killed, 0 survivors**
  (`/tmp/mutate_secretscan.py`, one edit each, source restored). Guards that a
  text assertion would have let through — the `--redact` flag on every
  invocation, the pre-scan allowlist validation, the report actually being
  written, the value never being carried into the report — died on the
  behavioural assertions instead
- [x] 2.6 Reproduces the measured baseline exactly: `--all` reports
  `generic-api-key docs/qa/2026-09-19-audit-delta.md:89 (756c1d7bb4b3)`, exit 1
  uncovered, and exits 0 once dispositioned. The report was re-read after the
  run and contains no matched value (leak check: 0 occurrences of the canary
  and of the reported `Match` text)
- [x] 2.7 The pin was exercised for real, not only against the stub: the
  downloaded `gitleaks_8.30.1_linux_x64.tar.gz` matched the vendor's
  `gitleaks_8.30.1_checksums.txt` line, and the extracted binary was run on all
  three scopes. This is what settled the `--log-opts=VALUE` argv spelling that
  the recording stub cannot prove

## Sprint 3 — This repository's own push path

- [x] 3.1 A `secrets` job in `.github/workflows/ci.yml`, between `self-gates`
  and `specs`, on push and pull request: use a PATH scanner if the runner has
  one, otherwise fetch the pinned gitleaks release and verify it against the
  pinned checksum; run the gate over
  `github.event.pull_request.base.sha..head.sha`, else
  `github.event.before..after`, else `--all`; print the redacted report
- [ ] 3.1a **Deviation, recorded rather than glossed:** the task said "upload the
  redacted report". There is no `actions/upload-artifact` in the job. Every
  action in this repository is pinned by commit SHA, and there is no verified
  SHA for that action on hand; adding an unpinned one to a security job to move
  a JSON file that the log already carries is the wrong trade. The report is
  printed instead (`if: always()`), and log retention covers it. Revisit if and
  when the pin is verified
- [x] 3.2 A non-vacuity check on the job itself: `gitleaks version` must match
  the pin, and the step greps the gate's own `[secret-scan] scope:` line — a job
  that passes because the gate never ran is the exact failure this workflow
  exists to prevent
- [x] 3.3 First real run's result, ledgered (2026-09-24, run
  [36048653103](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36048653103),
  all seven jobs green). The runner carried **no** scanner, so the fetch path
  ran in production rather than only against a stub: `sha256sum -c` printed
  `gitleaks.tar.gz: OK` against the pin, and `gitleaks version` printed `8.30.1`.
  The gate then took the **range** path — `scope: commits in
  5d59989..fba5f9e, plus the working tree` — and reported 0 findings. The
  fall-back was not exercised, because that push had a real base; it stays
  covered by tests, and this ledger does not claim a production run of it.
  The allowlist entry printed `not matched in this scope (may be stale — run
  with --all to settle it)`, which is the designed narrow-scope wording: the
  false positive lives on `origin/audit`, outside a push range, and the reason
  is correctly withheld there because the claim is not definite

## Sprint 4 — The consumer template

- [x] 4.1 `templates/github-workflows/secret-validation.yml` rewritten to invoke
  the gate with the pinned-binary mechanism, dropping
  `gitleaks/gitleaks-action@v2` (secret-scan-05, secret-scan-06), keeping a
  self-hosted path that uses a pre-installed scanner, and naming in a header
  block what was removed and why so it is not re-added
- [x] 4.2 Tests: the template calls the gate; no marketplace scanning action; no
  floating `@vN`; the template and `ci.yml` name the same version and checksum
  (drift guard) — `tests/test_secret_validation_template.py`, 15 tests
- [x] 4.3 Mutation battery, 2026-09-24: **10 mutations, 10 killed, 0 survivors.**
  The first draft of this suite had 4 survivors, all one disease — the
  assertions tested prose, and an `if false;` mutation leaves the asserted
  string exactly where it was. The fix was to execute the step bodies against
  stubbed tools, which is now how the load-bearing assertions work: the fetch
  that must not happen, the checksum that must reject wrong bytes before
  installation, the gate that must be present, the scope line that must appear
- [x] 4.4 That rewrite exposed a test that measured the host: the checksum
  assertion passed on this machine because `/usr/bin/gitleaks` exists here, so
  the step took the "already installed" branch and never fetched. The scanner
  steps now run against a sandbox PATH containing only what the step needs

## Sprint 5 — The fleet sweep

- [x] 5.1 `scripts/secret-scan-fleet.sh`: for each declared public repository,
  fetch, scan tree and history, report per-repo state. The declaration is a
  file of URLs (blank lines and `#` comments skipped), which is what makes the
  fetch path real in tests: they declare `file://` remotes and the sweep clones
  them, rather than a stubbed git agreeing with the script about what fetching
  means. Per-repo state is one of clean / findings / unfetchable / unscannable,
  each with the reason when it is not a verdict; the sweep asks the gate for
  `--all` (every ref plus the working tree), so the credential that was
  committed and then deleted is in scope — that case is why the sweep exists
  separately from the push gate. Exit codes: 0 all clean, 1 an uncovered
  finding, 2 the scanner is unusable, 3 bad invocation, 4 at least one
  repository could not be scanned. Precedence is 3 > 2 > 1 > 4 because a bad
  invocation means nothing ran, a scanner fault means no verdict is
  trustworthy, and a live leak outranks an unknown. Two refusals are load
  bearing and each is pinned by a test: an empty or absent declaration exits 3
  (zero repositories scanned is not a clean fleet — the run-tests.mjs rule), and
  a scanner that crashed aborts with 2 rather than letting the repositories
  already scanned stand as verdicts. **Recorded reason**: the line is taken from
  the *end* of the gate's log and the *start* of git's, and both are measured.
  The gate echoes its scope before it runs the scanner, so a run that dies on
  the scanner has the scope line first and the fault last; git puts its
  diagnosis first and follows it with advice ("Please make sure you have the
  correct access rights / and the repository exists"). Reading the first line
  for both recorded "scope: full history (all refs), plus the working tree" as
  the reason a repository could not be scanned — a line that reads like a
  successful scan. A test pins each direction and a mutation (F8) pins the
  branch where the choice is observable; an rc=3 refusal happens before the gate
  prints anything, so head and tail agree there and neither is pinned.
  **Audit fixes before shipping**: `cleanup()` used a bare `[ ... ] && rm` — as
  an AND-list a false test returns non-zero, and `set -e` is still in force
  inside an EXIT trap, so the cleanup for a caller-supplied `--work` aborted the
  trap; it is an `if` now. And `record()` echoed its state argument, which
  nothing read once the caller started printing its own lines — the function
  writes the record and nothing else.
- [x] 5.4 Tests for unknown-vs-clean rendering and for an unfetchable repository
  being reported rather than omitted: 15 tests in `tests/test_secret_scan_fleet.py`
  against real `file://` git origins and a stubbed gitleaks on PATH.
  `test_an_unfetchable_repository_is_reported_not_omitted` is the requirement's
  own scenario (`secret-scan-07`), and `test_every_declared_repository_appears_
  exactly_once` is the invariant underneath it — the failure mode being a
  shorter, greener list. The stub reports a finding when the *fetched* repository
  contains a committed marker file, so "this repository has a credential" is a
  property of the repository rather than of the order the sweep ran in.
  `tests/mutation_battery_secret_scan_fleet.py`: 8 mutations killed, 1 negative
  control survived (a summary line reworded, saying the same thing). Each
  mutation leaves the script valid, which is the point — `bash -n` cannot see
  any of them and an exit code is not a value a test can read out of the text.
  The battery is registered in ci.yml's batteries step, which
  `test_every_battery_runs_in_the_suite` reads back.
- [x] 5.2 Installed beside the heartbeat in `runner-enroll.sh`, same
  EnvironmentFile discipline as the image cycle (2026-09-24). What it does:
  copies BOTH scripts into `~/.config/containers` — `secret-scan-fleet.sh` and
  the `secret-scan.sh` it resolves as `$(dirname $0)/secret-scan.sh`, because a
  sweep copied without the gate beside it dies at that precondition on every
  tick, which is a host that looks enrolled and sweeps nothing — then emits
  `devgate-secretscan-$SLUG.{service,timer}` reading the runner's existing
  EnvironmentFile (D3.1, no new file), and enables the timer only when
  provisioned, exactly as `enable_image_cycle` does. **The ExecStart's
  declaration is `"\$SECRET_SCAN_DECLARED"` — escaped so the unquoted heredoc
  leaves it for systemd rather than expanding it in enroll's shell (where it is
  unset, so the unit would go out as `--declared` with no argument and exit 3
  on every tick while enrollment reported success — incident #1's shape, one
  heredoc over), and quoted so systemd passes its expansion through as one
  word.** Enabled by `SECRET_SCAN_DECLARED` naming an existing, NON-EMPTY file:
  the sweep exits 3 on an empty declaration by design, so enabling early buys a
  unit that fails every tick, which on a dashboard is indistinguishable from a
  sweep that ran and found nothing. Interval is its own (86400s) for the
  cycle's reason taken further — a tick clones every declared repository in
  full. Revoke removes both new units and stops/disables the timer, since the
  `--declared` path lives in the env file it deletes. `--help` and the header
  now name the sweep, its unit and its provisioning key, and the header's
  account of which file emits which unit body was corrected — the watchdog and
  the sweep are emitted in `scripts/lib/runner-units.sh`, where their
  enablement rule lives. **Two findings from the battery, both real:** (a) the
  first draft had an `-z` branch and a `-s` branch, and the battery's F3
  mutated the first with the suite staying green — `[ -s "" ]` is already
  false, so the second branch caught every case and the first was a message
  selector, not a guard. The branches are now one condition, mutated two ways
  and killed by two different named tests. (b) The negative control's anchor
  went stale when that message was rewritten; the control was re-pointed at the
  operator-guidance line, deliberately NOT at the `NOT enabled` substring,
  because a test does read that one — it is an operator's only signal that the
  sweep they think is running is not. **The bug this slice actually shipped,
  and how it was caught:** the gate was first installed as
  `devgate-secret-scan.sh`, matching every other helper's name, while the sweep
  resolves it as `$(dirname $0)/secret-scan.sh`. The test written for it
  compared the two installed files' presence, parent directory and *bytes* —
  all three held — so it was green while the installed sweep died with "the
  gate script is not beside this one" on every tick. It was caught by running
  the installed helper end to end (helper → gate → scanner, over a real
  `file://` repository with a stubbed scanner) rather than by reading the
  generated files, which is now
  `test_the_installed_sweep_can_actually_run` and battery mutation F9. 14 tests
  in `tests/test_runner_enroll_sweep.py`; `tests/mutation_battery_runner_sweep.py`
  is 9 mutations killed (including F9, which renames the gate back) + 1 control
  survived, and is registered in ci.yml's batteries step. Size note for whoever
  adds the next unit: `runner-enroll.sh` is at 496/500 after this, which is why
  the sweep's units were emitted in the library rather than in it.
  **Anomaly, reported rather than tidied away:** one battery run left three
  mutations applied to disk (F5 and the N1 control in the library, F9 in
  enroll) and reported verdicts that were therefore derived from an
  already-mutated tree — two of them naming the wrong killer test, which is the
  tell. The harness restores in a `finally` and a targeted probe of three
  entries restored correctly in isolation, so the mechanism is not understood;
  the cause was not found and is NOT explained here. The two files were
  restored by hand, and the battery was re-run wrapped in before/after sha256
  hashes of both artifacts: 9/9 killed, 1/1 control survived, both files
  byte-identical afterwards. The verdicts above are from that hashed run. A
  battery that can leave a mutant on disk is an evaluator-integrity hazard of
  the kind this repository keeps meeting — the next run's anchors would go
  stale and its verdicts would be read off a tree that is not the one under
  test — so it is recorded here as a task rather than as a footnote
- [x] 5.2a The hardening pass 5.2 needed, and the hosted red it shipped — one
  commit-pair after 5.2, because "push → confirm hosted green before claiming
  closure" was the ritual step 5.2 had not finished. Run
  [36090931527](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36090931527)
  was **red in three jobs**, from two causes, and the second is the one worth
  recording. (a) `tests/mutation_battery_runner_sweep.py` went in without the
  exec bit — this host has `core.fileMode=false`, so the mode never reached the
  index; it failed both the exec-bit step and
  `test_fw_guards::TestExecBitCheck::test_real_tree_passes`, one missing
  `git update-index --chmod=+x`. (b) The fw-* lane reported **32/34 killed with
  survivors F1 and E5** — and both were *anchor misses this slice had caused*:
  E5 anchored on the revoke list's last line, which split in two when the
  sweep's units joined it, and F1 on the fixture's scrub line, which this
  slice's `SECRET_SCAN_` edit had rewritten. Neither mutation had ever been
  applied. The harness detected this (`ANCHOR … appears 0 times`) and then
  filed it under **`survivors (a guard no named test depends on)`** — the wrong
  diagnosis, sending the reader to write a test for a question nobody asked.
  **Three fixes in the harness, each pinned by a test that fails without it:**
  stale anchors get their own heading (a survivor and a stale anchor have the
  same exit code, so the distinction can only live in the report); an exclusive
  `flock` keyed by the resolved root refuses a second battery on the same tree
  rather than interleaving; and the artifacts' sha256 is taken **before** the
  battery starts and verified after, because per-entry restore verified against
  a captured "original" cannot see a tree that a concurrent run already
  mutated — each entry restores faithfully to the other's mutant and every
  per-entry check passes. That third check is the mechanism behind 5.2's
  recorded anomaly, reproduced by the fresh-eyes audit and now prevented rather
  than documented. Twelve tests for the harness (18 in the file); the new
  guards were probed by mutation, and the first version of the drift check was
  **inert** — the pure functions were tested and nothing called them, caught by
  probing and fixed by injecting the failure into `main`. **The fresh-eyes
  audit's findings, all dispositioned:** (1, 2, 3) the escaping narrative in
  three places was measured *wrong* — it claimed an unescaped
  `$SECRET_SCAN_DECLARED` "expands to the empty string … while enrollment
  reports success". Measured four ways against the real enroll: ambient unset
  gives `rc=1, SECRET_SCAN_DECLARED: unbound variable` — enroll aborts under
  `set -u` and installs nothing, which is loud; ambient **set** gives `rc=0`
  and the *ambient path frozen into the unit*, where no later edit of the runner's
  env file reaches it. So the escape defends against the freeze, not the crash,
  and the silent case had no test — it does now
  (`test_an_ambient_declaration_is_not_baked_into_the_unit`), while the
  fixture's `SECRET_SCAN_` scrub was **deleted as inert**: nothing on the enroll
  path reads the ambient variable, so no test could distinguish it, and it
  removed the only way to exercise the hazard. Both batteries' F1 now run with
  an ambient value set, which is why F1 is credited to the test that asserts the
  token survives instead of to whichever enrolling test hit the crash first.
  (4) enroll's reader is not systemd's: a declaration written
  `SECRET_SCAN_DECLARED="/tmp/a b/declared.txt"` — a line systemd unquotes and
  runs — was read *with its quotes on*, found no such file, and left a
  provisioned sweep disabled; the strip is one `case`, and the boundary (one
  layer of quotes, not an EnvironmentFile parser) is stated beside it. (5) the
  empty-declaration and missing-file tests drove one branch, so the second
  asserted nothing the first did not; they are one test now. (6) the
  commented-out test was the only one that survived deleting the feature — it
  has its siblings' non-vacuity assert. (8) the battery's header omitted F9 and
  claimed "no assertion here reads a message", false for the suite it names;
  both corrected, and F9's note now says the harness credits the presence
  assertion rather than the end-to-end run. (9) the suite was absent from
  `tests/expected-counts.json`, so all of it could have been deleted with CI
  green — `gen_floors.py --update`, which also picked up six other suites that
  had gone unfloored (total floor 727 → 861). **The gap 5.2's own comment
  documented, closed:** a declaration that exists and is non-empty but names no
  repository used to enable the timer that then exits 3 every tick — the exact
  noise the gate exists to prevent. The check is now the sweep's OWN rule
  (`strip at the first #, drop whitespace, skip if empty`) as one grep, and the
  obvious shorter form a review proposed — `'^[^#[:space:]]'` — is **itself
  divergent, measured**: it refuses an *indented* url, which the sweep reads and
  scans, so enroll would report a provisioned sweep as not enabled. Both
  directions of that agreement are asserted, in one test that asks both readers
  about the same file. Guards added for the bare-path ExecStart (F10 —
  incident #1's shape, pinned for the heartbeat and the cycle but until now only
  *asserted* here, with no mutation able to falsify it) and for the quote strip
  (F11). Final: **17 tests** in `tests/test_runner_enroll_sweep.py`, **12
  mutations + 1 control** in the battery, each mutation killed by a named test
  and the artifacts byte-identical after; `docs/contract-inventory.md`
  regenerated (it had drifted to omitting nine suites) and reworded so a stale
  count reads as staleness rather than as a regression. The audit's remaining
  findings, dispositioned rather than silently dropped: (7) three of the
  suite's assertions read a log substring (`"NOT enabled"`) — deliberate, since
  that line is an operator's only signal that the sweep they believe is running
  is not, and the battery's negative control is what keeps those distinguishable
  from the assertions that read behaviour; (10, 11) both were the narrative
  errors folded into (1–3); (12) two claims in the unit were unclaimed by any
  test **and by any mutation**, which the audit was right about:
  `--report %t/devgate-secretscan-$SLUG.json` and `TimeoutStartSec=3600`.
  **Half of this is now closed and half is not, and they are split apart on
  purpose.** The report path stopped being unclaimed the moment 5.3a gave it a
  second reader: it is computed once in `scripts/lib/runner-units.sh`, carried
  by the unit's `--report` and by the env file, and four mutations (S1, S2,
  S13, S20) plus the joint sweep→heartbeat test now fail if the two carriers
  disagree about the file. The timeout is unchanged and still unclaimed —
  a whole-fleet clone can exceed an hour and a timeout kill is a sweep that
  reports nothing, so it is recorded as a residual of 5.3a rather than pinned
  with a test that would assert the number back at itself; (13) closed — the
  check it named was already correct; (14) fixed, and its fix is the quote
  strip in (4).
- [x] 5.3 Hub: accept and render per-repo scan state, unknown when absent
  (secret-scan-07), reusing the heartbeat path — **5.3a AND 5.3b BOTH DONE.**
  5.3a is the producer and the transport: the sweep's report reaches the
  heartbeat, the heartbeat ships it, the hub stores it presence-aware. 5.3b
  (below, at the end of this sprint) is the rendering. That the split was worth
  recording rather than hiding: between the two, the state was stored and
  NOTHING RENDERED IT — a real intermediate state, and exactly the kind of
  half-built thing that gets mistaken for done.

  **The path, which is where the work actually was.** The distinguishing
  decision: TWO processes now read one file on two different timers, and they
  decide the path independently unless something stops them. The sweep names it
  by `$SLUG` (sanitized) and the heartbeat knows `$RUNNER_NAME`, so for any
  runner whose name needs sanitizing — `prod/web 1` → `prod-web-1` — a
  heartbeat deriving the path would look for a filename the sweep never writes,
  and that host would read unknown forever while scanning perfectly. This is
  the two-readers-one-fact divergence this repository has already been bitten
  by twice, so the value is computed ONCE (`runtime_dir()` and the assignment
  that uses it, both in `scripts/lib/runner-units.sh`) and
  handed to both carriers: the unit's `--report` and the env file. It costs a
  small loss of authority — systemd's `%t` was the specifier that resolved
  this, and enroll now reimplements it — and that is stated in the code rather
  than left as an inconsistency, because the heartbeat is a bash script with no
  specifiers and could not have read `%t` at all. What keeps the two carriers
  honest is a test (`test_the_sweep_unit_reports_to_the_path_the_heartbeat_reads`)
  rather than the hope that one assignment was written twice the same way.
  **A mutation found this test was weaker than it read:** the first version
  asserted the path was merely "under tmp_path", which $HOME also is, and the
  mutation that moved the report to `~/.cache` walked through it — the two
  carriers still agreed with each other, which is a different question from
  which directory. The assertion is the exact path now.

  **The reader's three cases**, each of which collapses into a fleet reading
  clean while blind, so each is its own mutation (S4/S5/S6):
  `SECRET_SCAN_REPORT` unset or the file missing → `scan_state: null`, a
  POSITIVE report of absent (which is what lets the hub clear a stale verdict
  to unknown); the file will not parse → `{"repos": [], "unreadable": ...}`,
  NEVER an empty fleet — an empty `repos` list is the sentence a dashboard
  renders as clean, produced from a file nobody could read; and a repository
  the sweep could not fetch keeps its reason rather than being dropped.

  **A live race, closed.** The report was written with `open(path, "w")`, which
  leaves it zero-length and half-written for the length of the write. Harmless
  while nothing else read it; a reader on a one-minute tick landing in that
  window is a real case now that the heartbeat does. The write is a sibling
  plus `os.replace`, and the test measures the INODE change — `open(w)` keeps
  the file it truncates, `os.replace` necessarily yields a new inode. Stated as
  necessary for atomicity and not proof of it; the reader's half is the
  `unreadable` case above.

  **What the heartbeat ships, decided rather than inherited:** the per-repo
  STATE, not the finding locations. The report file keeps rule/path/line/commit
  so an operator on the host can act; the heartbeat carrying them would put the
  file paths of unremediated findings on the wire on every tick and grow the
  body with every finding in the fleet. Pinned by a test so it cannot quietly
  reverse.

  **Hub side**, the image precedent exactly: `scan_state` joins the
  presence-aware `UNREPORTED` read at the registry and at the JSON boundary
  (S8/S9 — conflating "says null" with "says nothing" either keeps a superseded
  sweep or wipes a real one), the field is declared in the schema (the drift
  invariant picks it up automatically), and `scan_state_unknown()` is the
  predicate 5.3b will render on — keyed on the state being USABLE, so an
  unreadable report is unknown and not a verdict (S10).

  New: `tests/test_runner_scan_report.py` (13 tests) and
  `tests/mutation_battery_scan_report.py` (**18 mutations + 4 controls, all 18
  killed** by a named test in one of four suites — the change crosses runner and
  hub, so its guards are tested where they live). The battery is registered in
  the CI batteries step, which `test_every_battery_runs_in_the_suite` checks
  against the directory. Floors 863 → 884 (64 suites, 983 tests), contract
  inventory regenerated.

  **An adversarial read of the finished slice, and what it changed.** A
  fresh-eyes audit was run over the whole change once it was green, and most of
  what it returned was not style — it was guards I had written believing they
  were guards. Dispositioned in full, because the pattern matters more than the
  individual lines:

  * **`scan_state_unknown()` was type-unsafe, and that is a live defect, not
    tidiness.** It read `state.get("unreadable")` on whatever a spoke posted.
    Nothing validates that field on the way in — `test_every_field_the_registry
    _writes_is_declared_in_the_schema` asserts exactly that nothing does — so a
    buggy or hostile host holding a valid heartbeat token can put `"clean"` or
    `[1, 2]` there, and `.get` on a string raises `AttributeError` inside the
    function 5.3b's fleet view renders through. Worse, `{}` — a dict, so no
    raise — read as a USABLE verdict: a fleet with no repositories in it, which
    is the sentence a dashboard shows as clean. The predicate now asks
    `isinstance` first, requires `repos` to be a list one level down, and every
    shape that is not the declared one reads as unknown. That is the
    requirement read strictly: a repository with no recorded scan state is
    unknown, never healthy, and "recorded" means recorded in the declared
    shape (S14, S15, plus `test_a_scan_state_of_the_wrong_shape_reads_as_unknown
    _and_does_not_raise`).
  * **Two lines removed rather than kept with a comment praising them.** The
    heartbeat's `if not path: return None` was behaviourally redundant (an
    unset variable arrives as the empty string, and `open("")` raises
    `FileNotFoundError` on its own), and `os.path.abspath(report_path)` in the
    sweep was inert. The second is worth recording because the audit *claimed*
    a mutation would kill it — an unresolved relative `--report` leaving
    `dirname` empty so `mkstemp` fails — and when the mutation was written it
    **SURVIVED**. Measured directly instead of argued: `mkstemp(dir="")`
    resolves against the process directory and succeeds, and `os.replace` works
    either way, so the line changed no behaviour on any input and the guard it
    claimed to remove did not exist. It is gone, with the measurement written
    where the mutation would have been (S18's slot in the battery) and the
    behaviour pinned for both spellings instead. **Measurement beat the
    audit's reasoning, and the reasoning was plausible** — which is the case
    for writing the mutation rather than taking the finding on faith.
  * **Three untested guards in code I had just written**, each given a test and
    a mutation: the reader's `isinstance(repos, list)` (S16), `runtime_dir()`'s
    XDG fallback — the variable is absent over a non-login ssh session, which
    is where hosts get provisioned (S17) — and the write's failure-path cleanup
    of its temporary (S19).
  * **The seam, which no single suite could see before this round.** Every
    other test of the transport checks one half: the sweep's tests inspect a
    report they wrote, the heartbeat's inspect one they wrote themselves. So
    the sweep could name a repository under a key the heartbeat never reads and
    BOTH suites stay green while every host in the fleet reads unreadable for a
    field that is right there under a different name — the two-readers failure
    again, one layer down. `test_the_report_the_heartbeat_reads_is_the_one_the
    _sweep_actually_wrote` runs a real sweep over real git origins into the path
    enrollment computed and has the real heartbeat read it back; S20 is the
    mutation that only it can kill.
  * **A harness gap, closed per-suite rather than fixed.** A kill in
    `tests/mutation_harness.py` is "the named test exited non-zero", and it does
    not first check that the test passes UNMUTATED — so a test that later
    starts failing for a reason of its own would be credited as the killer of
    whatever mutation names it. The harness is not mine to rewrite mid-slice;
    what is here instead is a negative control per suite (N1–N4, rewording a
    comment in the heartbeat, the sweep, the registry and the server). If the
    guards were reading prose, or a named test were failing for the wrong
    reason, a control stops surviving and says so. Queued as a task against the
    harness itself, which is where the real fix belongs.
  * **Prose that lied, corrected.** A docstring claimed the 500-line hard limit
    forced the test-file split; the real limit for a `test_*.py` is 600 and the
    split was for room — and it cited another file that repeated the claim, so
    both were wrong together. The escaping counterfactual ("if the unit
    escaped `$SCAN_REPORT` the two carriers would disagree about the name") was
    replaced with the measured mechanism, which is worse and different: an
    escaped reference is not an env-file key, so systemd expands it to the
    EMPTY STRING, the sweep runs `--report ""`, and takes that as "no report
    requested" — **a silent total no-op, not a name mismatch.** And a comment
    describing the extracted globals block overstated what declaring them buys
    (it does not silence-proof anything; `set -u` aborts loudly) — it now says
    what the block is actually for, and `SLUG_OWNER`/`SLUG_ATTRIBUTABLE` are
    declared nowhere at all, because the three sites that read them call
    `slug_owner()` on the line before and a declaration would be a line that
    never runs.
  * **Four new guardrail warnings, all the same false positive.** The scanner's
    PREVENT-024 ("triple-underscored package name may be AI-hallucinated") fires
    on `from hub.registry import scan_state_unknown`, because a function name
    with three snake_case segments looks like a PyPI package. Nine across the
    tree now, four of them from this change's import lines, all warning-level
    and non-blocking; recorded so that a future reader does not read the count
    as adoption of an undeclared dependency.

  **Residuals, recorded rather than implied away.** (i) The report lives in the
  runtime directory (`%t`'s location, unchanged from 5.2), which is
  per-session, so a reboot leaves the fleet reading unknown until the next
  sweep — up to a day. That IS what the requirement asks for (absence renders
  unknown, never healthy) and it is why the assertion pins the directory
  explicitly, but a state directory that survives a reboot is a defensible
  alternative and the choice is now visible instead of accidental. (ii)
  `install_helper` never refreshes an existing helper: a host enrolled before
  this change keeps its old heartbeat script, which does not ship `scan_state`
  at all — and because "says nothing" is deliberately read as "no news", that
  host keeps whatever verdict it last reported rather than going unknown. The
  presence-aware rule is right; the upgrade path is the gap. (iii) A sweep that
  exceeds `TimeoutStartSec=3600` is killed, and the last successful report stays
  on disk — a stale verdict with nothing marking it stale. Not pinned, because
  the honest fix is a timestamp the reader checks and that is 5.3b's business.
  (iv) A `SIGKILL` between `mkstemp` and `os.replace` leaves a
  `.devgate-secretscan-*.json.tmp` in the runtime directory; the `BaseException`
  path covers signals a handler can see, not the one that cannot be caught.

  **Hosted evidence, and a red that was the gate being right.** Pushed as
  6bbe79f + fc821eb (run 36109634621). The regression step — the one that sizes
  every changed file and scans their added lines — **passed**: the 5.3a content
  was evaluated on the runner, not only locally. Specs, the secret scan, the
  image build and the attack suite were green. Two jobs were red and there was
  one cause: `tests/mutation_battery_scan_report.py` was committed at 100644
  with a shebang, so `check_exec_bits` failed, which surfaced as a green suite
  with one red test (`test_fw_guards.py::TestExecBitCheck::test_real_tree_passes`)
  in the pytest job and a red step 11 in the gates job. Fixed in 090e948.

  It passed locally, and how it stopped passing is the part worth keeping:
  `core.fileMode` is false in this clone, so an exec bit travels through `git
  update-index --chmod=+x` and not through the working tree — and splitting the
  paired commits began with `git reset -q`, after which `git add` re-derived the
  mode from the bit git has been told to ignore. Every local gate had run over
  the staged tree BEFORE that reset. Both gates were honest about the tree they
  were shown; only one of them was shown the tree that shipped.

  090e948 was then red for a second reason (run 36111059327) and **the second
  red was correct**: the regression step reported "NOTHING SCANNED — the selected
  scope contains 0 changed files", because a commit that changes only a file
  mode adds no line to any diff, and that step's scope is built from added lines
  and `+++` headers. Measured, not assumed: `git diff --name-status fc821eb
  090e948` lists one modified file and the diff body is a `diff --git` header
  plus `old mode`/`new mode` — no `+++`, no hunk, nothing to size and nothing to
  pattern-match.

  A fix was written and then **withdrawn**, which is the part worth recording.
  It taught `get_changed_files` to collect a file from its `diff --git` header
  when the record has no `+++` line, so a mode-only push would count as a
  changed file and the step would go green. The change is literally correct for
  that function's contract — a mode change does touch the file — and it would
  have been a false green: the size check reads `touched`, which is built from
  added lines, and the pattern scan reads `get_diff_content`, so the file would
  have been counted while nothing about it was evaluated. It converts "this run
  evaluated no inputs, and is not evidence of a clean tree" into "1 file
  changed, ✓ no potential regressions" — a green certifying nothing, which is
  the exact class of failure this repository has spent four slices learning to
  refuse. Reverted with the tests. **A mode-only push has no content to gate, and
  the honest response is a push that carries content**, which is what this
  commit is.

  **Hosted green, and this is the closure evidence:** run 36113714716 for
  4bf4721 — test suite, secret scan, the attack suite, specs, the evaluator
  image build and the DevGate gates job all success, publish skipped as it is on
  every push. Three pushes, two reds, and the last one red for the right reason
  before this one went green: 36109634621 (the 5.3a content, red on the exec
  bit), 36111059327 (the exec-bit fix, red because a mode-only push has nothing
  for the gate to evaluate), 4bf4721 (this record).

  Residual, queued rather than fixed: the gate's message is accurate but does
  not say WHICH empty case it is, so an operator who has just set an exec bit
  reads "the selected scope contains 0 changed files" and has to rediscover the
  reasoning above. A diagnosis line for a scope whose diff exists but holds only
  mode/rename records would be safe — it explains the red without dissolving it
  — and it is deliberately not bundled here, because a message change made in
  the same breath as a withdrawal is not the moment to touch that file again.

- [x] 5.3b **The rendering half — 5.3 is now complete.** `hub/scan_view.py`
  (`scan_alerts(runner) -> [(check_class, detail)]`, a pure function of one
  registry dict) plus ten lines of dispatch in `hub/monitor.py` (`_check_scan_state`,
  section 3.6, one alert per runner). 12 tests in `tests/test_hub_scan_view.py`,
  one seam test in `tests/test_hub_monitor.py`, and 16 mutations + 2 controls in
  `tests/mutation_battery_scan_view.py` — **16/16 killed, 2/2 controls behaved.**

  **Why a module and not the monitor.** `hub/monitor.py` was at 433 of the 500-line
  hard limit and the sentences are ~90; more to the point, deciding what a verdict
  should SAY needs none of a timer, a GitHub client or a registry, and keeping it a
  pure function of one dict is the only reason each non-clean case can be pinned
  without a fixture. The monitor's own share is deliberately small — a loop and a
  `_raise_alert` — because `_check_scan_state` must not form a second opinion about
  whether a state is usable. It calls `registry.scan_state_unknown`, the same
  predicate the heartbeat contract and every future dashboard key on: a renderer
  with its own "is this usable" judgement would be the two-readers-one-fact
  divergence this repository has now been bitten by three times, in the slice
  written to avoid it.

  **Silence is a whitelist on `clean`, never a blacklist on the states this file
  knows.** `state` is host-supplied and stored unvalidated (the predicate's
  docstring spells out what a spoke can post), so a sweep that grows a fifth state
  — or a compromised spoke reporting nonsense — arrives as a word the renderer has
  never seen. A blacklist reads the first unrecognised word as a pass: the
  requirement's exact failure wearing a new spelling, which is what V3 pins.

  **The two buckets the predicate collapses are told apart here without disagreeing
  with it.** "could not be read" (the state's own `unreadable`, or a `repos` that is
  not a list) and "has not reported" are both unknown, both alert, and they name
  different fixes — provision the host, or fix what it reported. Same split as the
  image check's unknown-vs-cannot-serve, and the same requirement that the SENTENCE
  differ rather than a trailing parenthetical.

  **What the mutations found on their first run, which is why they exist.** V7
  ("a broken-shape report is rendered as a host that has not reported") SURVIVED:
  the test asserted `"repos" in detail`, and the fallback sentence's own word
  "re**pos**itories" satisfies it. The assertion was checking a substring instead
  of the fact, and the mutant rendered a report-nobody-can-read as a host that had
  said nothing at all — the exact confusion this slice is about, in the test written
  to prevent it. Fixed by asserting the quoted field and the explicit ABSENCE of the
  never-reported clause; V7 is now killed by
  `test_an_unreadable_report_with_no_reason_still_says_what_is_wrong`, and the
  shape of that miss is recorded in the test itself so the next reader does not
  re-weaken it.

  **Two guards were added only because the battery asked for them.** `_name_of`'s
  fallback and the non-dict-entry branch had no test — an inert guard by this
  repository's standard — so
  `test_a_report_whose_entries_are_not_records_renders_unknown_without_dying` was
  written (V10 kills it by removing the `isinstance`): `repos` is a list of
  ANYTHING a spoke posted, and the predicate guarantees the list, not its contents.
  A renderer that reached in with `.get()` would take the dashboard down on hostile
  input, which is worse than the unknown it was trying to report; one that skipped
  the entry would shorten the list, which is how a fleet reads clean while blind.

  **The exec bit, caught before the push this time.** The three new files were
  staged 100644 with shebangs and `check_exec_bits.py` failed — but against the
  INDEX, before any commit, and the fix was the tree's own convention rather than a
  special case: `hub/*.py` and `tests/test_*.py` carry no shebang at 100644, only
  `tests/mutation_battery_*.py` are 100755. Two shebangs removed, one
  `git update-index --chmod=+x`, re-verified with `git ls-files -s`. This is the
  5.3a failure caught a step earlier — see the memory note on the third occurrence;
  the gate that fired is the one built for it, and it fired where it should.

  **…and the same exec bit was wrong again in the commit, by a NEW mechanism.**
  The gate passed, the index said 100755 — and `git ls-tree HEAD` said 100644,
  because `git commit -- <pathspec>` (the partial commit this ritual uses to
  split code from docs) rebuilds its commit from the WORKING TREE for the named
  paths and re-derives the mode there, discarding the staged bit. The worktree
  file was still 0644: `core.fileMode=false` means `git update-index --chmod=+x`
  fixes the index and nothing else, so the two were free to disagree and did.
  The gate reads the INDEX and the hosted gate reads the COMMIT, so this would
  have shipped red for a reason no local run could show — the third distinct
  spelling of one trap in three slices (`git reset` before, the pathspec
  partial commit now). Fixed by `chmod +x` in the worktree TOO — so the worktree
  agrees with the index and a partial commit cannot lie — then `git commit
  --amend --no-edit` with NO pathspec, which commits the index as it stands, and
  re-verified with `git ls-tree HEAD` rather than with the index that had just
  been declared correct.

  **A fresh-eyes audit found three real defects in this diff, all now fixed and
  mutation-pinned — the round that earned its keep.** (F1, the severe one) The
  scan check was dispatched at the END of `_poll_repo`, so it was silenced by a
  failure that is not an HTTP status: `hub/github_client.py` catches `HTTPError`
  but not `URLError`, so a refused connection or a DNS failure raises out of
  `_check_runner_status`, is caught by `poll_cycle`'s per-repo handler, and aborts
  every check after it. Measured with a closed port and nothing monkeypatched:
  `URLError: [Errno 111] Connection refused`, then `sink.alerts == []` — no leak
  alert, for every cycle of the outage. The docstring claimed a rate limit cannot
  silence this check, which was true and beside the point. Fixed by moving both
  registry-only checks (3.5 and 3.6, which share the claim) ahead of every call
  that can raise; the seam test was rebuilt around a closed port rather than a
  403, which is the strictly harder case and would have passed either way.
  (F3) The findings test asserted `"3" in detail or "2" in detail`, so the
  `uncovered` count the docstring insists on could be dropped without the test
  noticing — an assertion that cannot fail for the fact it claims to pin; now one
  substring carrying both counts, and V11 kills it. (F4) `why = reason or "no
  reason recorded"` was reached by no test at all — the reason-dropping mutation
  V5 replaces the whole expression, so the right operand was unprotected and
  deletable in silence; the null-reason case is now pinned and V12 kills it.
  Three findings were dispositions rather than defects: (F2) a report carrying
  BOTH a leak and a truthy `unreadable` renders the leak as unknown, because the
  predicate short-circuits — kept deliberately, since re-deriving a leak from a
  report the shared predicate has just declared unusable is the second opinion
  this module refuses to hold; the shipped heartbeat cannot emit both. (F5, F6)
  one `check_class` covers three different causes and names the evidence rather
  than the fault; that is inherited alert design plus residual (iii) below, and no
  change is made here.

  **Residual, recorded rather than implied (i):** staleness. Nothing here checks
  that a usable report is RECENT — a sweep that ran a month ago renders clean
  forever. The predicate's docstring records it as a residual and this rendering
  inherits it; bounded staleness needs the sweep's cadence, which is the same
  question `img-cycle-03` left open and is not answered here.
  **(ii)** `scanned_at` is shipped and not rendered. The alert says a repository is
  unknown; it does not say since when. That is the input a staleness check would
  need and it is deliberately carried unread rather than dropped.
  **(iii)** `check_class` is free-form (`hub/alerts.py` dedupes on
  `(repo, check_class, runner)` and validates nothing), so `runner_scan_unknown` and
  `runner_scan_findings` are a convention rather than a contract; a typo in either
  would silently split a dedupe key. Pinned by the tests, not by the type system.
  **(iv)** "The fleet view" here means the alerts the monitor raises, which is how
  `img-cycle-03`'s equivalent requirement is already satisfied; there is no
  dashboard endpoint that renders scan state. `secret-scan-07` shows `covered`
  under `spec_traceability.py --report` (the advisory run is 70/123, and
  `secret-scan-01..06` remain uncovered because their markers are shell-side).
  **(v)** The harness still does not check the unmutated baseline (task 23), so this
  battery's verdicts rest on its two negative controls the way its siblings' do.
  **(vi)** One check raising still aborts the remaining checks for that repo —
  fixed for the registry-only pair by ordering (F1 above), not by isolating each
  check. After the reorder the checks that can still be aborted all need the
  network and would fail anyway, so this is recorded rather than re-shaped: a
  poll-loop-wide per-check guard is a change to every check's failure semantics,
  not to this slice's. **(vii)** The unreadable branch interpolates the
  host-supplied `reason` into a GitHub issue body, so a spoke with a valid
  heartbeat token can inject markdown or mentions. Inherited deliberately, on the
  same stated policy as `image_reason` — render what the host reported, never
  match on it — and the alert body is written once and never rewritten
  (`hub/alerts.py` dedupes on the title and only comments afterwards).

## Sprint 6 — Evidence

- [x] 6.1 A planted canary in a scratch clone: the gate must fail, redact, and
  name the location; the report must not contain the value — three separate
  assertions in `tests/test_secret_scan.py` (the canary is absent from the gate's
  output; the written report carries no value; `--redact` appears on every
  scanner invocation)
- [ ] 6.2 Record the sweep's first run over the declared public repositories
- [x] 6.3 First hosted run of the `secrets` job recorded: run 36048653103, job
  success in 5s, range path, fetch-and-verify path exercised for real, 0
  findings (detail in 3.3). Two failures stand behind this green and are worth
  keeping in the record: the first push of this change went red because the
  template suite imported PyYAML and the hosted lane installs only pytest, so
  collection aborted all 823 tests — a test-only dependency that takes the whole
  suite down when it is missing. The second was caught before it left the
  machine: the checksum assertion had been passing because the *authoring host*
  has gitleaks installed, so the step took the already-installed branch and never
  fetched. Both are now executed against a sandbox PATH, and the hosted run above
  is the first evidence that the fetch path works somewhere real
