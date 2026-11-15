# stitcher-codereview

Spec-aware code review CLI (TypeScript). Verifies a git diff **against an OpenSpec change** — not just generic bugs.

## How OpenSpec is incorporated
- **Input:** `openspec/changes/<name>/` — `proposal.md`, `specs/<cap>/spec.md` deltas (`ADDED/MODIFIED/REMOVED Requirements` + `WHEN/THEN` scenarios), `design.md`, `tasks.md`; baseline `openspec/specs/` for context.
- **Core check:** every requirement is scored for diff evidence (keyword overlap + capability→filepath match). Missing → `blocker`; partial → `high`; `REMOVED` still present → `high`.
- **Drift check (reverse):** every changed source file maps to a capability (baseline `openspec/specs/` + delta specs, path-token and keyword overlap). Files in a known capability with no covering requirement → `medium` (`drift-uncovered`); files in no known capability → `low` (`drift-uncategorized`); no baseline at all → one `info` pointing at `openspec/specs/` instead of per-file noise.
- **Companion checks:** `tasks.md` traceability, correctness, security, tests presence, style/`AGENTS.md`.

## Usage
```bash
npm install && npm run build
node dist/cli.js --change spec-review-cli --base main --format markdown
node dist/cli.js --change my-change --base origin/main --format json --fail-on high
node dist/cli.js --change my-change --only spec-compliance,tests --format markdown
```

## Project-type templates
The reviewer adapts to what kind of project it is. A template is a prompt **lens** (extra paragraph in the LLM rescore) plus a **heuristic pack** (domain checks over the diff).
```bash
node dist/cli.js --change my-change --template auto        # detect (default)
node dist/cli.js --change my-change --template game-2d-3d  # force
node dist/cli.js --list-templates                          # show registry
```
- Built-ins: `generic` (fallback) · `cli` (exit codes, signals, argv) · `web-service` (migrations, auth, status codes) · `game-2d-3d` (binary assets, scene edits, frame hot-paths, save versioning) · `library` (removed exports = breaking, changelog, side-effect imports).
- Detection is score-based (`project.godot`, `Assets/`+`ProjectSettings/`, `package.json#bin`, `package.json#exports`, `Dockerfile`+migrations, key deps) and always reported: `**Template:** CLI (cli) — auto: package.json#bin matched (+4)`. Ambiguous → `generic`, never a hard guess; `--template` overrides.
- Custom templates live in `openspec/review-templates/<id>.md` (`# Label`, `## Match` with `file:|dep:|pkgField:`, `## Lens`, `## Checks` with `severity | path|line|removed|absent | pattern | message [| suggestion [| scope [| scoped|diff]]]`, `## Tests` with `pattern:`/`hint:` lines — escape literal pipes as `\|`). Custom ids override built-ins. `--only` accepts `template` to scope the pack.
- Templates also teach the tests checker their layout (`EditMode`/`PlayMode`, `supertest`, `e2e`, …): archetype test files count as tests, and the no-tests suggestion carries an archetype hint.

## Blended LLM rescore (optional)
Heuristic scores are explainable but dumb; an LLM judges semantics. Blend them per requirement: `weight * llm + (1 - weight) * heuristic`, re-thresholded with the same cutoffs. `REMOVED` requirements stay heuristic-only.
```bash
node dist/cli.js --change my-change --llm auto --llm-weight 0.6
node dist/cli.js --change my-change --llm require --llm-provider anthropic --llm-model claude-haiku-4-5
```
- `off` (default): heuristics only, fully offline. `auto`: LLM enriches, fails open to heuristics. `require`: LLM failure is a `blocker`.
- Providers: OpenAI-compatible (`OPENAI_API_KEY`, or any `--llm-base-url` like Ollama — no key needed for local) and Anthropic (`ANTHROPIC_API_KEY`). Env fallback: `STITCHER_CODEREVIEW_LLM*`.
- Overrides are logged as `info` findings (`"X" missing → covered: <rationale>`); blend inputs land in the JSON report (`heuristicScore/llmScore/blendedScore`).

## GitHub Action
```yaml
- uses: drwhofan2k18-pixel/stitcher-codereview@v1
  with:
    base: ${{ github.base_ref }}
    llm: auto
    llm-api-key: ${{ secrets.STITCHER_CODEREVIEW_API_KEY }}
```
Posts the report as a PR comment, exposes `verdict` / `report-path` outputs, and fails the step per `fail-on`. Needs `pull-requests: write`. See `action.yml` + `.github/workflows/stitcher-codereview.yml` (change defaults to the head branch name).

## Serve mode (async webhooks)
For long-running repos (game engines, monorepos) where a CI step would be too slow, run a persistent server that reviews on webhook and posts inline:
```bash
node dist/cli.js --serve --serve-port 3000 --serve-host 0.0.0.0 \
  --serve-secret "$(openssl rand -hex 32)" --llm auto
```
- **Endpoints:** `POST /webhook` reviews a GitHub/GitLab PR or MR event; `GET /health` returns `{"ok":true,"root":...}` for load balancers.
- **Delivery:** the server fetches the PR/MR head into a local tracking ref (no checkout), diffs against the base, runs the full engine, and posts **inline review comments** via `gh`/`glab` (needs `GITHUB_TOKEN` / `GITLAB_TOKEN`). The remote name is auto-detected (default `origin`).
- **Serialized per repo:** concurrent webhooks for the same repo queue up (keyed mutex), so reviews of one PR never interleave.
- **Hardened:** 1 MB request-body limit (`413`), 30 s request timeout (`408`), signature verification (`X-Hub-Signature-256`, `401` on mismatch), non-review actions acked and ignored, and graceful shutdown on `SIGINT`/`SIGTERM`.
- **Safety:** without `--serve-secret` signatures are **not** verified — a warning is logged; set a secret in production. The config policy from `openspec/review.yaml` applies to every webhook review.

## SARIF + inline annotations
```bash
node dist/cli.js --change my-change --format sarif > review.sarif
node dist/cli.js --change my-change --format markdown --sarif-out review.sarif
```
- SARIF 2.1.0: one rule per distinct check (`stitcher-codereview/<category>/<check-id>`, e.g. `stitcher-codereview/security/eval-call`), severity→level (blocker/high error, medium warning, low/info note), file:line→inline locations, verdict/change/template in run properties.
- `--sarif-out` writes a sidecar from the same run, so LLM rescoring never pays twice.
- The Action uploads automatically (`sarif: 'true'`, file `stitcher-codereview.sarif`, category `stitcher-codereview`) — findings render inline in the diff. Needs `security-events: write` **and code scanning enabled** (private repos need GHAS); upload is best-effort and never fails the job — the review verdict is authoritative. Set `sarif: 'false'` to skip.

Exit code `1` when findings meet `--fail-on` (default `high`), so it gates CI.

Exit codes: `0` = PASS (or `--fail-on never`); `1` = findings at/above `--fail-on`; `2` = usage/config error (bad flags, missing change, empty git state).

## Diagnostics
- `node dist/cli.js --change my-change --timing --format json` adds per-category wall-clock `stats.durationsMs` to the report (heuristic categories + LLM rescore/gap); omitted by default so output stays byte-deterministic across runs.
- Every JSON report carries `verification` — a repo fingerprint (HEAD + touched-file hash) and `executable:false`, so a consumer can tell the heuristic result is evidence-based, never over-claimed.
- In CI, `--sarif-out` and `--no-user-config` make runs reproducible; `docs/PERF.md` publishes measured latency vs diff size.

## Repo config (`openspec/review.yaml`)
```yaml
fail-on: high
template: auto
only: all # or [spec-compliance, tests]
llm: { mode: off, provider: '', model: '', base-url: '', weight: 0.5, max-concurrency: 3, max-retries: 2 }
sarif-file: '' # set to write a SARIF sidecar on every run
disable: [line-too-long] # check ids to drop
severities: { scenario-unmatched: low } # check id -> level
max-line-length: 140 # style threshold for added code lines
covered-at: 0.3 # spec-coverage score >= this = covered
partial-at: 0.12 # score >= this = partial
max-findings: 200 # total findings cap (per-check caps still apply first)
baselines: [] # extra baseline specs: local paths or GitHub tree URLs
ignore: [] # path globs never scanned
include: [] # when set, only these path globs are scanned
post: none # none | github | gitlab | vcs (auto-detect)
scan: off # off | repository (whole-tree drift scan)
```
Precedence: explicit flags > env (`STITCHER_CODEREVIEW_LLM_*`) > config file > defaults. `--config <path>` overrides auto-resolve (explicit missing path errors); disable/severities apply to all categories before sort/verdict so every format agrees. Invalid values fail fast; unknown keys warn.

## Pre-commit
The repo ships `.pre-commit-hooks.yaml` (hook id `stitcher-codereview`) and the
parity harness `scripts/stitcher-local.mjs`. The hook runs the same CLI and the
same checks as CI against the working tree, so local and CI verdicts agree for
the same change.
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/TheArchitectit/AIGGP-Agentic-Framework
    rev: <tag>
    hooks:
      - id: stitcher-codereview
        args: [--change, my-change, --base, origin/main, --fail-on, high]
```
The hook is `language: system`, so put the CLI on PATH once from a checkout
(`npm ci && npm run build && npm link` in this directory).

Parity is checked, not assumed: the harness runs the review twice - once on the
working tree, once in a clean `git worktree` at HEAD - and compares the
normalized verdict, findings and requirement coverage. Any divergence is
classified as a defect and exits 1:
```bash
node scripts/stitcher-local.mjs --run --root . --change my-change --base origin/main
# or compare two saved reports:
node scripts/stitcher-local.mjs --local local.json --ci ci.json --out parity.json
```

## Reverse drift gate
`--drift-only` evaluates a range with no change package: every changed behavior
file whose capability gained no spec update in the same range is a finding (the
severity is declared with `--drift-severity`, default `medium`). The repo-level
entry point is `scripts/stitcher-drift.mjs`, so CI and pre-commit run the same
code path:
```bash
node scripts/stitcher-drift.mjs --base origin/main --fail-on medium
```

## Task traceability (both directions)
Given `--root` and `--base`, the tasks check also maps commits to tasks: a
commit that changes behavior files and names no task is `trace-orphan-commit`
(with file evidence); a task marked done that no commit implements is
`trace-orphan-task`. An unresolvable range reports `trace-commits-unavailable`
instead of a clean mapping it did not compute.

## External-tool adapters (identity preserved)
Adapter-ingested findings carry the source tool's name, version (or content
digest), the digest of the input it scanned and the digest of the raw output.
Their check ids stay source-attributed (`guardrails-scan/PREVENT-003`,
`secret-scan-declared/declared-repo`); they are never renamed to AIGGP checks.
The first two targets are `guardrails-scan.mjs` and
`secret-scan-declared.sh` (Q12.2).

## Evidence-linked comments and agent verdicts
Every finding and requirement verdict carries a `coh-ev-<digest>` evidence
reference; SARIF results expose it in `properties.evidenceRef`, and review
comments append it. A comment without an evidence link is refused before any
forge API call (`--evidence-base-url` renders it as a link).
`--verdict` is the coding-agent-loop endpoint: it prints a `promote`/`halt`
record keyed to `--subject-digest`; a loop presenting its own prior output
(`--loop-outputs`) re-enters as an unverified subject and halts.
```bash
node dist/cli.js --change my-change --base main --verdict \
  --subject-digest "$(git rev-parse HEAD)" --producer claude-code-loop
```

## Agent skill
Coding agents should review their own changes before declaring done:
```bash
# one-time: copy the skill into your project
cp -r <this-repo>/skills/stitcher-codereview <your-project>/skills/
# after implementing openspec/changes/<name>
npx stitcher-codereview --change <name> --base main --fail-on high
```
`skills/stitcher-codereview/SKILL.md` holds trigger conditions, verdict reading, and the fix-code-or-narrow-spec loop. Works with Claude Code, Cursor, OpenCode, and Copilot (Agent Skills format).

## Design
See `openspec/changes/spec-review-cli/` (proposal, specs, design, tasks) — the tool dogfoods OpenSpec. Pipeline: `loader → git diff → parser → checks/* → engine (+ llm/) → reporter`, with `action.yml` wrapping the CLI for CI.

## Development
```bash
npm install
npm run build   # tsc — type-check + emit to dist/
npm test        # vitest run — full suite in parallel
```
- Test runner config lives in `vitest.config.ts` (30 s timeouts, ≤8 parallel workers) so the suite is stable on slow hosts.
- `tests/external-tools.live.test.ts` runs **live semgrep / trivy / osv-scanner** if installed (`which`) and skips otherwise — it exercises scanners that also power the `external-tools` check.
- No changes are committed until you ask; the standard loop is `npm run build && npm test` before a commit.

## Roadmap
See [upstream `docs/ROADMAP.md`](https://github.com/drwhofan2k18-pixel/stitcher-codereview/blob/main/docs/ROADMAP.md) — competitive landscape (2026) + phased feature plan: inline PR comments, incremental review, config flexibility, drift-scan mode, evidence trace, LLM tier, multi-VCS, distribution. (The roadmap is not vendored — this directory carries only the files the composite action needs — so the link points at upstream rather than at a path that does not exist here.)
