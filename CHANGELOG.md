# Changelog

All notable changes to the DevGate Agentic Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-13

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

### Added

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

## [1.0.0] - 2026-09-11

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
