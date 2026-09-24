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
- [ ] 3.3 Ledger the first real run's result, including the audit-branch false
  positive's disposition — **open: needs a hosted run after this push** (see 6.3)

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

- [ ] 5.1 `scripts/secret-scan-fleet.sh`: for each declared public repository,
  fetch, scan tree and history, report per-repo state
- [ ] 5.2 Install it beside the heartbeat in `runner-enroll.sh`, same
  EnvironmentFile discipline as the image cycle
- [ ] 5.3 Hub: accept and render per-repo scan state, unknown when absent
  (secret-scan-07), reusing the heartbeat path
- [ ] 5.4 Tests for unknown-vs-clean rendering and for an unfetchable repository
  being reported rather than omitted

## Sprint 6 — Evidence

- [x] 6.1 A planted canary in a scratch clone: the gate must fail, redact, and
  name the location; the report must not contain the value — three separate
  assertions in `tests/test_secret_scan.py` (the canary is absent from the gate's
  output; the written report carries no value; `--redact` appears on every
  scanner invocation)
- [ ] 6.2 Record the sweep's first run over the declared public repositories
- [ ] 6.3 **Record the first hosted run of the `secrets` job** (`gh run view`
  after this push), including whether it took the range path or the fall-back.
  Until that line is here, this change can claim a tested gate but not a
  verified one: everything above was measured locally, and a workflow that has
  never executed is a design, not evidence
