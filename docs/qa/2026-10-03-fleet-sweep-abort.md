# Fleet sweep abort — root cause, fix, and open findings (2026-10-03)

**Scope:** why `Secret Fleet Sweep` was red nightly (SWEEP_RC=2), what was fixed,
what remains open. Per hard rule #1 this record states rule + path + line +
commit only — no secret values were printed or transcribed anywhere in this
investigation; clones containing secret history were deleted after use.

## Root cause (measured, reproduced locally)

The sweep died at `agent-guardrails-template-private`:

1. That repo ships its own `.gitleaks.toml`; two `regexes` allowlist entries
   (lines 30, 32) began with `*` — invalid regex ("no argument for repetition
   operator").
2. gitleaks 8.30.1 compiles allowlist regexes with `MustCompile` → **panics**
   on invalid input (exit ≠ 0/1).
3. `scripts/secret-scan.sh:166` maps any other exit to `scanner unusable →
   exit 2` (fail-closed: a scanner that did not run is not a clean repo).
4. `scripts/secret-scan-fleet.sh:217-227` treats exit 2 as fleet-fatal:
   `ABORTED=1`, and the remaining 124 of 134 declared repos were recorded
   "sweep aborted: the scanner is unusable" — never scanned. Coverage on
   those nights was ~5 repos, though the report still listed all 134.

## Fixes landed

- **Private repo config** — `agent-guardrails-template-private@5cd18a2`
  (pushed to its main): the two allowlist entries escaped to
  `\*\*\*REDACTED\*\*\*` — same literal match, valid regex, no panic.
  Verified: `gitleaks detect` on that repo now exits 1 with findings
  reported instead of crashing; `secret-scan.sh --all` on it returns
  exit 1 (findings), no longer exit 2 (unusable).
- **Drift Scan checkout depth** — `AIGGP-Agentic-Framework@809c414`:
  unrelated but red nightly since the same window; default `fetch-depth: 1`
  left no tags, `regression_check.py --all` fell back to EMPTY_TREE, the
  whole repo scanned as "added lines," and registry pattern FAIL-3619d624
  fired on `SOURCE_DIRS = []` (scripts/regression_check.py:100, added
  2026-08-08). `fetch-depth: 0` verified green (runs 37138924100 on the
  diagnostic branch, 37140249848 on main).

## Open findings (rule + path + line + commit — NOT yet triaged)

Surfaced by the 2026-10-03 sweep; all in sibling repos, none in DevGate:

| Repo | Rule | Path | Line | Commit | State |
|---|---|---|---|---|---|
| pi-ithacus-agent-framework | generic-api-key | docs/MASTER_PLAN.md | 96 | working tree | **live in tree** |
| pi-ithacus-agent-framework | generic-api-key | docs/MASTER_PLAN.md | 96 | 499597ee47e3 | same, in history |
| agent-guardrails-template | generic-api-key | docs/standards/PROJECT_CONTEXT_TEMPLATE.md | 230 | 79812fbf78df | history (file absent at HEAD) |
| agent-guardrails-template-private | generic-api-key | docs/standards/PROJECT_CONTEXT_TEMPLATE.md | (history) | 79812fbf78df | history; exposed once config stopped crashing the scanner |

The private repo's own finding was **masked** by the config crash: with the
broken allowlist regex the scanner died; with it fixed the scan completes and
reports 1 leak. "Clean" was never the truth there. Precedent for history-only
findings is the scrub-residue decision (2026-09-29): rotation of the affected
credentials is the real fix; re-chasing blobs is not.

## Design gap recorded, deliberately NOT fixed (owner choice 2026-10-03)

`scripts/secret-scan.sh` invokes gitleaks **without `--config`**, so each
scanned repo's own `.gitleaks.toml` is honored by the central fleet sweep.
Consequences measured above: one repo's malformed config aborts the fleet,
and — even when valid — a repo can **allowlist its own secrets away** from
central truth. Owner chose "fix the repo config first"; pinning a central
fleet config in `secret-scan.sh` (plus a negative-control fixture: a repo
with a malformed `.gitleaks.toml` must not abort the sweep) is the open
follow-up.

## Verification status

- agent-guardrails-template-private config fix: pushed, local repro green.
- Fleet-sweep re-run for true coverage: dispatched pending API rate-limit
  recovery (background retry); nightly schedule covers it regardless.
- Re-run must show: no "sweep aborted", per-repo states resolved, and the
  open findings above still present until triaged/rotated.
