# Changelog

All notable changes to the DevGate Agentic Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

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
