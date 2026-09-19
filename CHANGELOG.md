# Changelog

All notable changes to the DevGate Agentic Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Test-suite hardening** (`harden-test-suite`) — the coherence golden
  vectors are load-bearing: `compute_golden.py` imports the real canon module
  (verified byte-identical) and `test_hub_coherence_golden.py` asserts the
  frozen vectors plus the profile-rejection contract; a collection-floor
  meta-test fails when discovered test files shrink (the F12 class);
  chmod-based exit-33 tests skip under root; regression-check fixtures moved
  out of the repo tree.
- **Runner monitor hub** (`hub/coherence/` + `container/`) — turns an
  OpenSpec package + policy + signed evaluation context into a canonical,
  deterministic accept/reject decision with sealed evidence and a frozen
  exit-code matrix (0 PASS / 10 ADVISORY / 20 FAIL / 30-40 ERROR classes).
  Domain-separated canonical digests, digest-verified packages/contexts/
  policy, an overlay that can strengthen but never weaken central policy, a
  fingerprinted baseline ratchet with expiring exceptions, four built-in
  evaluators, atomic artifact emission with a temp-dir fallback, and a
  reference launcher + containerized driver enforcing digest-pinned,
  read-only, non-root, network-none Podman execution with an
  execution-profile identity registry. 13 frozen JSON schemas ship with the
  service (`hub/coherence/schemas/`); 60+ `coh-*` requirements live under
  `openspec/changes/devgate-spec-coherence-service/` (S1-S4 of 8 sprints
  delivered; S5 signing, S6 fleet integration, S7 3D slice, S8 release
  remain). ~4k lines of stdlib-only Python with behavioral conformance,
  exit-code, ladder, launcher, and container test suites.

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


### Changed

- **Spec platform migration (`migrate-specs-to-openspec-conventions`).**
  `openspec validate --all --strict` passes 26/26 and the CLI now sees every
  capability's requirements (previously 15/15 specs failed and all read as 0
  requirements — two tools, two truths). All 17 main specs carry Purpose +
  Requirements + RFC-2119 SHALL/MUST; the three game specs were rewritten to
  describe the tooling that actually ships here (the phase matrix is marked
  planned, owned by the consuming game repo); two stale complete changes were
  archived (`fleet-add-01` published); the lost `mon-local-01` local-only
  posture requirement is restored; `ai01-runner-monitor-impl` gained its
  missing proposal and correct archive pointers; AGENTS.md documents the
  OpenSpec conventions and archive ceremony; CI enforces strict validation as
  a hard gate. Also: `extracted-rules.json` deleted (required absent by
  `rule-coverage-truth`, schema-violating, loaded by nothing);
  `game_regression.py` gained the standard `--fail-if-empty` /
  NOTHING SCANNED contract and honors `DEVGATE_PROJECT_ROOT`.


### Fixed

- **2026-09-19 audit remediation part 2 (`harden-security-boundaries`).**
  Trust-boundary and operational hardening; itemized record in
  `docs/qa/2026-09-19-audit-delta.md`.
  - **Coherence containment (F3/F4):** package inventory paths and assertion
    file selectors are validated for containment before any read — traversal,
    absolute paths, and symlink escapes are invalid input/UNRESOLVED, never
    host-file reads. Manifest size and digest now come from one streaming read
    (F11).
  - **Hub runtime (F2/F5-F10):** SIGTERM shuts the idle hub down promptly
    (serve-loop timeout; the old `handle_request()` blocked until the next
    request); enrollment uniqueness is decided atomically under the registry
    lock; JSON bodies are capped (`HUB_MAX_BODY_BYTES`, 413 before read);
    monitor alerts key on the real run `id`; the `default` watched-branch
    sentinel resolves via the API instead of 404'ing silently; Retry-After is
    read from the HTTP header; the poll thread snapshots the registry under
    the lock; killed podman clients reap their containers via `--cidfile`.
  - **Token hygiene (mon-sec-02):** heartbeat verifiers are salted-hashed at
    rest (legacy plaintext registries upgrade on load; revocation clears the
    verifier); `runner-enroll.sh` builds JSON with `json.dumps`, never prints
    the issued token (it goes straight to the 0600 env file), time-bounds
    every curl, and validates identity fields before unit generation.
  - **Template supply chain (ci-sec-01):** every shipped action is pinned to a
    40-hex commit SHA (including `gitleaks-action`, which receives
    `GITHUB_TOKEN`), container images are digest-pinned with the rotation
    procedure documented inline, and the runner-monitor image gains a
    `/health` HEALTHCHECK.
  - **Quadlet secrets:** one canonical mechanism — the quadlets declare
    `EnvironmentFile=` (raw env file) and all three runner/hub docs match it;
    the old instructions wrote a bare env file into a `.container.d/` drop-in,
    which is quadlet INI and never parsed.
  - **detect-host-ci.py:** lookaround-based redaction (`RUNNER_TOKEN=` caught,
    `blacksmith-2x` no longer mangled), bounded asset walk that skips
    unreadable files, `*.yaml` workflows discovered, `FROM --platform=`
    parsed.
  - New tests: `test_hub_coherence_containment.py`,
    `test_hub_hardening.py`, `test_detect_host_ci.py`,
    `test_template_supply_chain.py`, `test_runner_enroll.sh`; monitor tests
    for the sentinel resolution and queue-id keys.
- **2026-09-19 audit remediation (`fix-vacuous-and-broken-gates`,
  `fix-coherence-container-contract`).** Full-repo review findings F1 and the
  still-open C-series/H-series from `docs/qa/2026-09-13-full-qa.md` are closed;
  each fix is locked by a test that fails on the old behavior. See
  `docs/qa/2026-09-19-audit-delta.md` for the itemized record.
  - **Container contract (F1, critical):** the pinned evaluator image could
    not load its frozen schemas (`SCHEMA_DIR` resolved through a change-package
    path the image never carried) — every in-container request died exit 30
    with a misleading reason, and the only real-container test asserted that
    same exit for an invalid request. Schemas moved to `hub/coherence/schemas/`
    with package-relative resolution; smoke evidence now includes an
    in-image schema load and a valid-request PASS case; rejection reasons must
    name the invalid input.
  - **Scanner root anchoring (C2/C3):** `semantic-scan.mjs` and
    `run-tests.mjs` no longer escape to the parent of a standalone clone
    (EACCES crash / stranger trees / "0 tests across 0 files" exit 0 while the
    repo's own tests sat unrun). All scanners now share the layout contract;
    `tests/test_scanner_root_anchor.mjs` locks it.
  - **Test runner:** Rust files run via `cargo test --test <stem>` (the old
    positional filter matched function names, so integration files ran zero
    tests and passed); discovery covers `test_*.mjs` and the whole project
    tree — `tests/test_guardrails_scan.mjs` now executes under the runner.
  - **npm audit (C6):** a HIGH/CRITICAL vuln in a DIRECT runtime dependency
    is blocking again (npm's `effects` is empty for direct deps; classification
    now uses `isDirect` + dependency name + effect chains). Tooling failures
    (npm missing, timeout, empty/unparseable output) surface as warnings with
    a named reason instead of reading as "no vulnerabilities".
  - **Deploy (C7/H7):** `deploy.sh` detects standalone vs submodule layout and
    gates the PROJECT tree (regression_check/failure_registry_check/
    scene_inventory/log_failure anchored by layout contract, with
    `DEVGATE_PROJECT_ROOT` override); the twine upload no longer double-publishes
    (`(A||B)&&C` precedence bug aborted the pipeline after a successful
    immutable publish) and uploads only the just-released version's artifacts;
    the clean-tree gate includes untracked files; schema health blocks when a
    database is configured instead of silently warning.
  - **Markers (H6):** spec traceability accepts `# spec: <id>` alongside
    `// spec: <id>`, mirrored in the coherence evaluator's grammar;
    `findings_to_spec.py` emits per-language advice.
  - **Registry targeting (H8):** `log_failure.py` defaults to the project
    overlay (the bundled baseline needs `--baseline`); an explicitly named
    registry path that does not exist fails the hygiene gate instead of
    passing vacuously.
  - **scene_inventory (C1):** no more `xml.etree` dead-end (every valid
    `.tscn` reported "parse error"); connections match by node-path segment;
    empty scope prints NOTHING SCANNED and `--fail-if-empty` exits 2.
  - **Test collection:** `tests/__init__.py` + `conftest.py` — a foreign
    `tests` package on the machine silently dropped the five conformance files
    from collection; discovered live during this audit.
  - **Test-infra:** `tests/test_regression_audit.py`,
    `tests/test_log_failure.py`, `tests/test_failure_registry_check.py`,
    `tests/test_scene_inventory.py` added; PREVENT-024 false positives on
    local module imports annotated with audited same-line exceptions.
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


- `regression_check.py --all` no longer crashes on repositories with no tags
  and 20 or fewer commits (`RuntimeError: could not diff HEAD~20...HEAD`); it
  falls back to the empty-tree base and scans the whole reachable tree.
- `spec_traceability.py` now discovers the standard OpenSpec change-package
  layout (`openspec/changes/<change>/specs/**/*.md`, archived changes
  excluded) in addition to `openspec/specs/<capability>/spec.md`, and
  distinguishes "no spec files found" from "spec files found but 0
  requirement IDs in the <!-- id: --> format" instead of reporting both as
  "no specs found under openspec/specs/".

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
