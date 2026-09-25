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
  errors folded into (1–3); (12) two claims in the unit remain unclaimed by any
  test **and by any mutation**, which the audit is right about:
  `--report %t/devgate-secretscan-$SLUG.json` and `TimeoutStartSec=3600`.
  Nothing reads that report until 5.3 builds the hub side, so there is nothing
  to pin yet — and the timeout is a real hazard worth naming, because a
  whole-fleet clone can exceed an hour and a timeout kill is a sweep that
  reports nothing. Recorded here as a 5.3 input rather than pinned with a test
  that would assert the number back at itself; (13) closed — the check it named
  was already correct; (14) fixed, and its fix is the quote strip in (4).
- [ ] 5.3 Hub: accept and render per-repo scan state, unknown when absent
  (secret-scan-07), reusing the heartbeat path — NOT YET. Note for whoever
  builds it: the sweep's report is a file, and the heartbeat is a POST body, so
  the state has to travel the way the image state does — a field on the
  heartbeat, one per declared repository, with absence rendered as unknown
  rather than as clean (the `UNREPORTED` sentinel in `hub/registry.py` is the
  precedent, and `null` is a positive report there, not an absence).

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
