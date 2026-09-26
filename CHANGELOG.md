# Changelog

All notable changes to the DevGate Agentic Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed (pre-existing)

- **Mutation harness:** the hermetic env scrubbed `HOME` (git identity
  isolation), which relocates Python's user base — on a `pip --user` host the
  nested `python -m pytest` died with `No module named pytest` (exit 1) and
  `run_entry` read that as a failing test, so **every mutant reported
  "killed"** (4 verdict tests red; CI passed only because hosted pip installs
  system-wide). `PYTHONUSERBASE` now survives the scrub, and a nested run
  that cannot start raises `HarnessFailure` — reported as `HARNESS FAILURE`,
  never as a verdict.
- **Hub:** `/enroll` duplicate-name check moved inside the locked section
  (the pre-check outside it let two concurrent enrolls with different valid
  tokens both append — TOCTOU); request bodies capped at 64 KiB with a 413
  before any read (unauthenticated `Content-Length` was an allocation lever);
  the monitor now reads a locked deep copy of the registry instead of racing
  in-place heartbeat writes; queue-stall alerts key on the runs API's real
  `id` field (was `run_id`, so every stall deduped to one `"?"` issue);
  `Retry-After` parsing can no longer raise out of the poll loop; `repo`
  validation tightened to `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z` in server and
  schema; a failed recurrence comment drops the issue dedupe entry instead of
  burning the cooldown.
- **`runner-enroll.sh`:** revoke payload built with `json.dumps` like enroll
  (string interpolation let a runner name smuggle JSON fields); `--interval`
  validated as whole seconds before it reaches unit heredocs/arithmetic; the
  installation window maps raw failures to the documented exit code 3 (`ERR`
  trap under `set -E`) instead of leaking child codes as usage errors.
- **`guardrails-scan.mjs`:** the test-scope inversion branch was an empty
  `if` — production lines were silenced by their own forbidden-context words
  (`password = "sample_key"` vs PREVENT-003). Suppression now applies only
  when the file is a test file or the line carries the test vocabulary
  itself; fixture 4b pins it.
- **`regression_check.py --base`:** the flag advertised scanning committed
  content but never fed the base-diff files into the known-bug and
  pattern checks — on a clean pushed tree they evaluated nothing while the
  gate printed a clean pass. `get_changed_files`/`get_diff_content` now take
  `base` (11 files scanned where 0 before, proven against `HEAD~5`).
- **`silent-success-scan.sh`:** project root by layout rule like every other
  gate (the nearest-`.git` walk could select an outer repo and scan
  siblings).
- **`secret-scan-fleet.sh`:** declared URLs starting with `-` are rejected
  before `git clone` (option injection through the declaration file).
- **CI:** the specs job's `| tail` pipelines run under `set -o pipefail` —
  a traceability regression used to be masked by tail's exit 0; the
  framework's own template had the fix, its CI did not.

### Changed

- **Rule coverage is honest now** (rule-truth-01/rule-behavior-01, design
  D1/D2/D7 from the archived `2026-09-13-rule-enforcement-gaps` change):
  `extracted-rules.json` deleted — its ten agent-behavior rules live in the
  skill templates (commit-validator gains the six git-safety laws, four-laws
  the `rm -rf` and production-in-test prohibitions, scope-validator the
  pre-work failure-registry check), with a README mapping table. Eight
  semantic rules flipped to `enabled:false` / `status:"not-implemented"`,
  and README counts corrected (37 pattern rules, seven workflow templates,
  six skills).
- **Templates:** `spec-coherence` bootstraps the pinned runtime *before*
  verifying it (the gate could never pass on a fresh checkout) and takes
  dispatch inputs via `env:` (shell-injection); `smoke-gate` fails on its
  own failure sentinel (the old branch shape let every sentinel hit pass);
  `guardrails-compliance` forbidden-files matches basenames as globs
  (`.env` as an ERE failed `config/environment.yml`, which ci-match-01
  explicitly protects) and its header/summary now say which checks are
  advisory; template `drift-scan` fetches full history and installs
  typescript@5 before the semantic arm; `file-size-check` fails on
  *exceeding* the limit, not meeting it.

### Added

- **Rules hygiene gate** (`scripts/rules_check.py`, wired into CI): an
  enabled rule with no registered checker, a rules file that fails its
  schema, or an enabled rule missing message/severity now fails the build —
  asked of the scanner itself via `semantic-scan.mjs --list-checkers`.
- **SEMANTIC-005** (React `useEffect` missing dependencies) is actually
  implemented in `semantic-scan.mjs` — no-deps arrays and omitted free
  identifiers are reported (warning severity, `guardrails-allow
  SEMANTIC-005` escape), closing the header's long-standing claim.
- **CHECKSUMS.sha256** regenerated from the current tree (79 entries,
  `verify` green; at audit time 9 digests were stale and 8 shipped files had
  never been listed).

## [1.3.0] - 2026-09-23

### Highlights

First release with **hosted CI on every push** (the framework's own gates
execute on GitHub runners: test suite, self-gates, specs strict validation,
evaluator-integrity attacks, container-image build + GHCR publish). The
spec-coherence evaluator image is now **published**
(`ghcr.io/thearchitectit/devgate-agentic-framework/devgate-coherence`),
digest-pinned in `container/execution-profiles.json`, and consumers get a
byte-equivalence-verified local invocation (`scripts/coherence-local`).

The fw-* readiness program adds a permanent evaluator-integrity CI job:
mutation testing with a self-check, ten negative controls through the real
CLI, a both-direction-validated benchmark corpus, fleet and determinism
drills, an allowlist-growth monitor, and test-count floors.

### Fixed

- **Runner enrollment:** the heartbeat unit no longer uses an inline `bash -c`
  ExecStart. systemd expands `$` in `ExecStart` against the unit's own
  environment, so the variables the body defined for itself (`DISK_OK`,
  `PODMAN_OK`) arrived empty, the POST went out as malformed JSON, the hub
  rejected it, and the unit exited 22 on *every tick* while enrollment still
  reported success. `ExecStart` now points at a copied
  `scripts/runner-heartbeat.sh`.
- **Runner enrollment:** units and the token env file are named per runner
  (`devgate-hb-<name>`, `devgate-watchdog-<name>`,
  `devgate-heartbeat-<name>.env`), so enrolling a second runner on one host no
  longer overwrites the first runner's token. Two names that sanitize to the
  same unit name are refused rather than merged. Legacy fixed-name units are
  retired for the runner being re-enrolled, and left alone when they belong to
  another.

### Fixed (pre-existing)

- **Gates:** tracked-artifact checks (COMMITTED-ENV/COMMITTED-GENERATED) now
  honor `.guardrailsignore` like the walk-based checks. One carve-out: a bare
  `.env` can never be ignored — that check is the framework's leak tripwire.
  Hygiene variants (.env.testing, .env-redacted) stay ignorable.
- **Gates:** file-size gate exempts generated files — a source file whose
  first 1KB contains a "Code generated" marker is skipped from line counting
  (build artifacts, not hand-maintained code). Validated on rad-gateway:
  3 generated files left the report, hand-written oversize files unchanged.
- **Gates:** `regression_check.py` no longer crashes on repositories with
  non-UTF-8 bytes in git diff output (`UnicodeDecodeError` before any summary
  was printed). `run_git_command` now decodes with `errors="replace"`, so the
  file-size gate runs to completion and reports real counts on such trees.

### Added

- **Runner monitor hub** (`hub/`) — a stdlib-only Python service that watches
  the self-hosted runner fleet from one machine. Endpoints `/enroll`,
  `/heartbeat`, `/revoke`, `/health`; one-time enrollment tokens and
  per-runner revocable heartbeat tokens (constant-time compared); an atomic
  `runners.json` registry on a hub volume that is never committed. Polls the
  GitHub API per registered repo for runner online state, queue-drain age, the
  latest check-run conclusion per watched branch, and scheduled drift-scan
  recency, combining that with spoke heartbeats as **independent** evidence
  channels. Alerts are deduplicated by `(repo, check-class, runner)`: one
  GitHub issue per key, recurrence as a comment, every event appended to an
  append-only JSONL log. Ships `scripts/runner-enroll.sh` (enroll / `--revoke`
  / systemd user timer), a Containerfile + Podman quadlet template under
  `templates/runner-monitor/`, a spoke-side hub watchdog, and the
  deployment runbook `docs/runner-monitor-monitor-hub.md`. The hub is
  monitor-only by default and binds loopback unless deliberately widened; see
  the runbook's TLS and firewall notes before exposing it.
- `spec_traceability.py`: a marker line may now carry several requirement IDs
  (`// spec: a-01, b-02, c-03`). The pattern previously captured only the first
  ID, so a multi-ID marker silently covered one requirement and reported the
  rest as uncovered.
- **Spoke-side hub watchdog** (`scripts/hub-watchdog.sh` + a
  `devgate-hub-watchdog.timer` installed by `runner-enroll.sh`) — the inverted
  dead-man switch (`mon-deadman-01`). The hub cannot report its own death and a
  GitHub-scheduled workflow cannot report its own absence, so each spoke polls
  the hub's `/health` on a timer and fails its own systemd unit when the hub is
  unreachable or its poll loop has gone stale. Local-only by design: no token
  on the spoke, no GitHub issue. `/health` now also reports
  `polling_enabled` / `poll_interval_sec` so a watchdog can tell "no PAT,
  polling off by design" (`last_poll_at` null, warn) from a wedged poll loop
  (`last_poll_at` stale, fail) rather than reading an unconfigured hub as a dead
  one. `monitor.py` now actually records `last_poll_at` each cycle (it was
  declared but never written).
- `.github/workflows/hub-health-probe.yml` — the former
  `devgate-monitor-deadman.yml`, converted from a scheduled "dead-man switch"
  that only ever printed an `echo` line (its header claimed it would open a
  GitHub issue if the schedule stopped firing; nothing in GitHub Actions or in
  the file did so) into an honest `workflow_dispatch` hub probe. It shares the
  watchdog's verdict logic so a manual probe and the spoke check cannot
  disagree. No `schedule:`, since a workflow cannot report its own absence.

### Fixed

- `regression_check.py --all` no longer crashes on repositories with no tags
  and 20 or fewer commits (`RuntimeError: could not diff HEAD~20...HEAD`); it
  falls back to the empty-tree base and scans the whole reachable tree.
- `spec_traceability.py` now discovers the standard OpenSpec change-package
  layout (`openspec/changes/<change>/specs/**/*.md`, archived changes
  excluded) in addition to `openspec/specs/<capability>/spec.md`, and
  distinguishes "no spec files found" from "spec files found but 0
  requirement IDs in the <!-- id: --> format" instead of reporting both as
  "no specs found under openspec/specs/".

### Added (gates)

- `regression_check.py`: a scope that scanned zero files now prints an
  explicit NOTHING SCANNED notice instead of the clean-pass line
  (no-vacuous-green); new `--fail-if-empty` (exit 2 on zero-input runs, for
  CI) and `--base REF` (scan committed content as `diff REF...HEAD`) flags;
  `--json` output gains `files_scanned` and `vacuous`.
- `semantic-scan.mjs`: missing TypeScript parser error now states the gate
  evaluated nothing, and `DEVGATE_SEMANTIC_REQUIRED=0` opts into an explicit
  SKIPPED exit-0 for projects that cannot provide the parser.
- README/AGENTS.md: "Evidence quality" guidance — presence/substring-only
  tests are weak evidence, and hand-written-literal round-trips prove nothing
  about the real save/load path.

## [1.2.0] - 2026-09-04

### Added

- Self-hosted runner standard under `templates/runner/`: the official
  `ghcr.io/actions/actions-runner` image deployed as a Podman quadlet, with
  secret drop-ins, durable registration, and no hosted-runner fallback.
- Scheduled drift-scan workflow templates plus `scripts/detect-host-ci.py`,
  which reads a host repo's own workflows and reports the `runs-on:` labels and
  `schedule:` crons already declared there (secrets redacted).
- The spec traceability gate (`scripts/spec_traceability.py`): every OpenSpec
  requirement ID needs a `// spec: <id>` marker in a source file, advisory by
  default and blocking per capability.
- Reusable gate patterns ported from the game project (scene inventory,
  file-size check, guardrails compliance, secret validation, smoke gate) under
  `templates/`.
- Go rules for rune digits, listen-on-all-interfaces, and unclosed file
  handles; newly surfaced rule warnings.
- GitHub Sponsors (`FUNDING.yml`, README section, badge).

### Changed

- Gates now **block** a deploy on failure rather than warning (regression,
  guardrails, build, test), with an incident-proven failure-registry
  enforcement loop.
- `exclude_glob` support and `**` globstar parity in the gate configuration
  contract, plus a registry hygiene gate.
- The game framework is absorbed directly instead of being carried as a
  submodule.

### Fixed

- `regression-check` honors a rule's `file_glob`; `info` findings are advisory.
- `run-tests.mjs` parser repaired — a crashed test file now fails the gate
  instead of passing silently. Rust test-file support added.
- The `.devgate` tree is excluded from the marker scan.

## [1.1.0] - 2026-08-08

### Changed

- All scripts are now fully generic: they auto-detect the project root,
  language, and package manager instead of assuming a fixed layout. Rewrote
  `regression_check.py`, `run-tests.mjs`, `semantic-scan.mjs`,
  `guardrails-scan.mjs`, `schema-health-check.mjs`, and `deploy.sh` against the
  detected project rather than a hardcoded tree, and updated AGENTS.md and the
  README to match.

## [1.0.0] - 2026-08-08

### Added

- First tagged release, cut as part of the guardrails control-plane
  architecture so consumers can pin DevGate as a versioned submodule instead of
  vendoring drifting copies.
- Static/CI quality gates: pattern and semantic scans, regression check, test
  isolation, deploy gate, and drift scans, with GitHub workflow templates and a
  runner under `templates/`.
- Policy skill templates under `templates/skills/` (Four Laws, halt conditions,
  production-first, scope validator, three strikes, commit validator). The
  canonical versions of these rules now live in
  [guardrail-policy-packs](https://github.com/TheArchitectit/guardrail-policy-packs)
  (`core/` pack v1.0.0); the copies here remain for compatibility until
  consumers migrate to pinned packs.
