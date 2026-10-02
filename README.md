# AIGGP — Agent Intelligence Gate Loop Guardrails Platform

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

This repository is DevGate, a quality gate for AI-assisted development, and it
is the host of AIGGP — the **Agent Intelligence Gate Loop Guardrails
Platform**: the settled path is the agent guardrails system merging INTO this
repo (the plan is in the [AIGGP section](#aiggp--agent-intelligence-gate-loop-guardrails-platform)
below). The heading carries the destination now, the way a rename is announced
before the paperwork; what ships from this repository today is still DevGate.

Drop it into a project — TypeScript, Python, Rust, Go, GDScript, or a mix — and
you get test isolation, regression scanning, deploy gates, scheduled drift scans,
CI workflow templates, a self-hosted runner standard, and agent-behavior
guardrails.

DevGate is not a template or a starter kit, and it won't rearrange your code. It
imposes no directory layout, language, package manager, or test framework. It
looks at what you have and gates it.

## Why this exists

Agents write code faster than anyone reviews it, and speed without a gate ships
regressions. DevGate sits between your agents and your production code and
catches two kinds of problems: the fast ones (SQL injection, unhandled promises,
committed credentials, unvalidated input, and about thirty more patterns) and the
slow ones — dependency rot, base-image drift, CI config that changed and nobody
noticed.

The part that matters more than the pattern list is that the gates refuse to lie.
A scan that evaluated nothing does not print "clean". A test run that discovered
zero files does not exit 0. A gate that can't run reports that it couldn't. If
you only take one idea from this project, take that one.

## Quick start

```bash
# As a submodule (recommended — stays in sync with upstream)
git submodule add https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git .devgate

# Or clone directly
git clone https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git .devgate
```

### What you get

```
.devgate/
├── .guardrails/
│   ├── failure-registry.jsonl          # Append-only bug history
│   ├── pre-work-check.md               # Mandatory pre-work checklist
│   ├── silent-success-allowlist.json   # Simulated-success markers (per-project; baseline ships empty)
│   └── prevention-rules/
│       ├── pattern-rules.json          # Regex-based rules (32 rules, 10+ languages)
│       ├── pattern-rules.schema.json   # JSON schema for custom rules
│       ├── semantic-rules.json         # AST-rule catalog (advisory path; scanner implements SEMANTIC-001)
│       └── silent-success-rules.json   # Simulated-success detector families (ship disabled)
├── scripts/                            # The gates (see "Components" below)
├── hub/                                # Runner-monitor hub + spec-coherence service (Python, stdlib-only)
├── container/                          # Pinned evaluator image + execution-profile registry
├── templates/                          # CI workflows, runner standard, runner-monitor, agent skills
├── openspec/                           # Capability specs + change packages (the source of truth)
├── tests/                              # Behavioral test suite (pytest + node fixture harnesses)
├── docs/                               # Onboarding, release gate, audit process, runbooks, QA records
├── .github/workflows/                  # The framework's own CI (runs the gates on itself)
├── AGENTS.md                           # Directions for AI agents
├── LICENSE                             # BSD 3-Clause
└── README.md                           # This file
```

See the tree in full — this README names the highlights; `scripts/` holds the
gates listed under [Components](#components), `hub/` holds the two services
below, and `openspec/specs/` is the normative contract each gate implements.

### Run the gates

All scripts auto-detect your project root (the parent of `.devgate/`) and scan whatever source files exist there — regardless of language or directory structure.

```bash
node .devgate/scripts/guardrails-scan.mjs         # pattern scan, all source types
node .devgate/scripts/semantic-scan.mjs           # AST scan (TS/JS; skips if none)
node .devgate/scripts/run-tests.mjs               # isolated per-file test runner
python3 .devgate/scripts/regression_check.py --staged --pre-commit   # regression + file size
bash .devgate/scripts/deploy.sh 1.0.0             # gated publish (npm/cargo/pip/go)
```

Two things about the regression gate worth knowing up front. `--staged` sees only
uncommitted work, so on a clean checkout it prints `NOTHING SCANNED` rather than a
fake pass (add `--fail-if-empty` in CI to make that exit 2). And `--all` scans
everything since the last tag — that's a drift sweep for a schedule, not a
per-pull-request review; use `--base origin/main` for that.

## The gates

| Gate | What it does |
|------|--------------|
| `guardrails-scan.mjs` | Regex rules across ten-plus languages. Annotate a deliberate exception inline with `// guardrails-allow PREVENT-029: reason`. |
| `semantic-scan.mjs` | TypeScript-compiler AST checks (unhandled promises, missing `useEffect` deps). Fails closed: if TS/JS files exist and the parser isn't installed, the gate fails and prints the install command instead of reporting a clean scan. |
| `regression_check.py` | Cross-references changed files against the append-only failure registry, enforces file-size limits, runs a package audit, and promotes soft violations to blocking for files you actually changed. |
| `run-tests.mjs` | Per-file process isolation, up to 8 parallel workers, serial lanes for shared-resource tests, flake adjudication (failing files re-run alone), and hang-on-exit detection. |
| `deploy.sh` | Gated publish: build, test, lint, then publish — for npm, cargo, pip, or go. |
| `schema-health-check.mjs` | Adapter-based schema validation (SQLite, PostgreSQL, MySQL), skipping cleanly when no database is configured. |
| `findings_to_spec.py` | Turns failure-registry entries and live violations into `openspec/specs/<capability>/spec.md` requirement skeletons, so a bug becomes a requirement with a `// spec:` trace back to it. |

### Things we learned the hard way

A suite of presence checks ("does this string appear in the file") detects
deletion, not breakage — don't cite it as "tested". And building a fixture by
hand-writing the literal proves nothing about the code that saves it; build the
fixture by calling the real function.

## Rules, and how to add yours

The rules are data, not code: 37 pattern rules, 9 silent-success rules, and 10
AST (semantic) checks — 2 enabled with shipped checkers (Promise `.catch`,
React `useEffect` dependencies) and 8 disabled pending their checkers.
`scripts/rules_check.py` keeps that honest: an enabled rule with no registered
checker fails CI (rule-truth-01). Most pattern
rules are scoped to several extensions at once, so the useful statement is
coverage rather than a per-language count: TypeScript / JSX / TSX / Svelte,
Python, Go, Rust, GDScript (`.gd`, `.tscn`, `.tres`), Kotlin, Java, Ruby, PHP,
YAML and CI config, Dockerfiles, and shell.

Isolated per-file test runner. Auto-detects test file types:
- `.test.js` / `.spec.js` → `node --test`
- `test_*.py` / `*_test.py` → `pytest`

Features:
- **Per-file process isolation** — each test file gets its own subprocess
- **Parallel pooling** — up to 8 workers (configurable via `DEVGATE_TEST_POOL`)
- **Serial lanes** — tests that share resources run one-at-a-time
- **Flake adjudication** — failed files re-run solo
- **Hang-on-exit detection** — open handles don't block the pool

Env overrides:
```bash
DEVGATE_TEST_TIMEOUT=120000    # per-file hard cap in ms
DEVGATE_TEST_POOL=8            # parallel worker count
DEVGATE_TEST_HANG_MS=10000     # silence threshold before force-kill
```

#### Evidence quality: what a green run actually proves

run-tests executes whatever test files exist; it cannot judge whether those
tests prove anything. When you write or review a suite, grade each test:

- **Behavioral (strong):** calls the real code path and asserts on the outcome
  (a swap function rejects an invalid move; `saveGame()` output round-trips
  through `loadSave()`).
- **Contract (useful):** parses/validates the real artifact (the shipped HTML's
  script blocks parse; the save schema a real save produces has the required
  fields).
- **Presence (weak):** substring or file-existence checks (`assert "function"
  in source`). These detect deletion, not breakage.

Rules of thumb:
- A suite that is ONLY presence checks is weak evidence — say so in the
  handoff; never cite it as "tested".
- Round-tripping a hand-written literal (e.g. `JSON.parse(JSON.stringify({
  wave: 1 }))`) proves nothing about the code that actually saves. Build the
  fixture by CALLING the real function, or drop the test.
- Expose seams for behavioral tests where the runtime allows it (e.g. a
  `window.__hooks` object) instead of testing copies of the logic.

### Regression Scanner (`scripts/regression_check.py`)

Scans changed files against the failure registry and pattern rules.
- **File-size enforcement** — soft/hard limits, auto-detects source directories
- **Package audit** — auto-detects your package manager (npm audit, or skips if not npm)
- **Soft-as-hard headroom gate** — promotes soft violations to blocking for changed files only
- **Failure registry** — cross-references changed files against known bug history
- **No vacuous green** — a scope with zero changed files prints a NOTHING
  SCANNED notice (never the clean-pass line); `--fail-if-empty` turns it into
  exit 2 for CI
- **`--base REF`** — scans committed content as `diff REF...HEAD`, so pushed
  branches can be audited after the fact (staged-only scanning cannot)
- **`--all` on small repos** — with no tags and 20 or fewer commits it scans
  from the repository root (empty-tree base) instead of crashing on `HEAD~20`;
  an undiffable base still fails loud rather than passing vacuously

### Pattern Scanner (`scripts/guardrails-scan.mjs`)

Regex-based scanner. Walks your project's source files (auto-detected) and checks them against enabled rules. Scans `.ts`, `.py`, `.rs`, `.go`, `.gd`, `.java`, `.kt`, `.rb`, `.php`, `.js`, `.c`, `.cpp`, `.cs`, `.swift`.

Supports inline annotations:
```typescript
// guardrails-allow PREVENT-029: This file is the API boundary — network calls are intentional
fetch("https://api.example.com/data");
```

The annotation form is `guardrails-allow RULE-ID: <reason>` — **reason text is
required** in every scanner (the shared `line_has_allow` / `lineHasAllow`
matcher). A bare `guardrails-allow PREVENT-029:` with no justification is not
an exemption; the rule still fires. File-scope `//! guardrails-allow-file
RULE-ID: <reason>` (guardrails-scan only) holds the same reason-required
contract.

### Semantic Scanner (`scripts/semantic-scan.mjs`)

AST-based scanner using the TypeScript compiler API. If your project has no TypeScript/JavaScript files, it exits 0 with "no matching files found."

- `SEMANTIC-001`: Promise `.then()` chains without `.catch()`

That is the only AST rule the scanner implements. The other rules declared in
`.guardrails/prevention-rules/semantic-rules.json` are a catalog, not
enforcement — they feed `regression_check.py`'s advisory path only; do not
rely on them as scanner coverage.

The parser (`typescript@5`) is loaded lazily. When TS/JS files exist but the
parser is unavailable, the gate FAILS with the install command — a gate that
evaluated nothing must not read as "clean". Projects that knowingly cannot
provide the parser may set `DEVGATE_SEMANTIC_REQUIRED=0`: the gate then exits
0 with an explicit `SKIPPED` line, so the gate list says "skipped", not
"green".

### Deploy Pipeline (`scripts/deploy.sh`)

Generic gated publish pipeline. Auto-detects your project's package manager:

| If found | Commands used |
|----------|---------------|
| `package.json` | `npm run build`, `npm test`, `npm run lint`, `npm publish` |
| `Cargo.toml` | `cargo build --release`, `cargo test`, `cargo clippy`, `cargo publish` |
| `pyproject.toml` / `setup.py` | `pytest`, `twine upload` |
| `go.mod` | `go build`, `go test` |
| `project.godot` | Skips build (run Godot headless tests manually) |
| None of the above | Skips build/test; tag pushed, publish manually |

### Schema Health (`scripts/schema-health-check.mjs`)

Database-agnostic schema validation. Engine adapter templates ship for SQLite, PostgreSQL, and MySQL; the gate defaults to unconfigured (skips gracefully) so it never breaks if you don't use a database or use a different engine.

To enable, create `<project>/.guardrails/schema-health.json` — never edit files inside `.devgate/`:

```json
{
  "adapter": "postgres",
  "expected_columns": [
    ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
    ["users", "email", "TEXT NOT NULL UNIQUE"]
  ]
}
```

A half-configured gate (adapter without columns, or columns without an
adapter) fails loudly instead of asserting nothing; a config naming an adapter
whose engine code is not enabled in the script also fails with instructions.
`--db <path>` (or `DEVGATE_DB_PATH`) supplies the connection string.

### Failure Registry (`.guardrails/failure-registry.jsonl`)

Append-only JSONL log of historical bugs. Each entry records:
- Affected files
- Root cause
- Prevention rule
- Status (active/resolved)

When a file is changed, the regression scanner checks it against active failures — preventing reintroduction of known bugs.

### Findings → Specs (`scripts/findings_to_spec.py`)

Gates produce findings; findings should produce requirements, not just
warnings. This scaffolder converts both sources — every merged failure-registry
entry, optionally plus live `guardrails-scan.mjs` violations piped in — into
`openspec/specs/<capability>/spec.md` skeletons in the format
`scripts/spec_traceability.py` gates:

```bash
python3 .devgate/scripts/findings_to_spec.py --list        # dry run
python3 .devgate/scripts/findings_to_spec.py               # group by category
node .devgate/scripts/guardrails-scan.mjs 2>&1 \
  | python3 .devgate/scripts/findings_to_spec.py --stdin   # fold live findings in
```

`spec_traceability.py` discovers requirements in both standard OpenSpec
layouts — `openspec/specs/<capability>/spec.md` and
`openspec/changes/<change>/specs/**/*.md` (archived changes excluded) — keyed
on `<!-- id: name -->` markers. Spec files without id markers get an explicit
"0 requirement IDs in the supported format" diagnostic (exit 2), never a
misleading "no specs found".

The loop closes: `log_failure.py` records a bug → `findings_to_spec.py` turns
it into a spec requirement → the fix carries `// spec: <id>` →
`spec_traceability.py` fails (in blocking mode) when a requirement loses its
enforcing code. Re-runs are idempotent: existing spec files are only ever
APPENDED to, findings are recognized by their provenance line, hand edits
survive.

## Runner Monitor Hub (`hub/`)

A stdlib-only Python service that watches your self-hosted runner fleet from
one machine. Spokes enroll with one-time tokens and heartbeat with per-runner
revocable tokens (constant-time compared; only salted hashes are stored at
rest). The hub polls the GitHub API per registered repo for runner online
state, queue-drain age, check-run conclusions on watched branches, and
drift-scan recency, combining that with spoke heartbeats as **independent**
evidence channels. Alerts are deduplicated by `(repo, check-class, runner)`:
one GitHub issue per key, recurrence as a comment, every event appended to an
append-only JSONL log. A spoke-side watchdog (`scripts/hub-watchdog.sh`)
fails its own systemd unit when the hub dies — the hub cannot report its own
death. Binds loopback by default; see
[docs/runner-monitor-monitor-hub.md](docs/runner-monitor-monitor-hub.md) for
deployment, TLS, and firewall notes before exposing it.

## Spec Coherence Service (`hub/coherence/` + `container/`)

The gate suite catches known-bad patterns; the coherence service evaluates
whether a repository actually MEETS its OpenSpec specifications. You build an
OpenSpec package (assertions + normative inventory, digest-pinned), a policy
bundle (required assertions, severity floors, baseline ratchet, expiring
exceptions), and a signed evaluation context (time, stage, and captured
external facts come only from the context — never the host clock or
network). `python -m hub.coherence --request` then produces a canonical
result with a frozen exit-code matrix (0 PASS / 10 ADVISORY / 20 FAIL /
30-40 ERROR classes) plus sealed, secret-redacted evidence. `--launch-config`
runs the same evaluation inside a digest-pinned, read-only, non-root,
network-none Podman container whose isolation is derived host-side — the
container never self-certifies. Deterministic by construction: the same
inputs produce byte-identical results. See
`openspec/changes/devgate-spec-coherence-service/` for the 60+ requirement
contract.

## Configuration

### File Size Limits

All source file types are checked. Edit `scripts/regression_check.py`:

```python
SRC_SOFT = 300    # soft limit (lines) — warning
SRC_HARD = 500    # hard limit (lines) — blocks commit
TEST_HARD = 600   # test files hard limit
```

Limits apply to all files matching source extensions (`.ts`, `.py`, `.rs`, `.go`, `.gd`, `.java`, `.kt`, `.rb`, `.php`, `.js`, `.c`, `.cpp`, `.cs`, `.swift`) in any source directory that exists in your project.

### Custom Prevention Rules — the overlay contract

A project using DevGate as a `.devgate/` submodule adds its **own** rules in a
project-root `.guardrails/` overlay — it never edits or copies the bundled
baseline. The gates MERGE the two by rule/failure id:

```
<project>/
  .devgate/.guardrails/...   # shared baseline (upstream-owned, never edited)
  .guardrails/...            # THIS project's delta only
  .guardrailsignore          # per-project scan scoping
```

The gates merge overlay and baseline by rule id: new ids append, same-id entries
replace in place, so you can retune a severity or kill a false positive without
touching the baseline. `semantic-scan.mjs` is the exception — its checks are
hardcoded AST logic, not data. Passing an explicit `--rules`/`--registry` path
collapses everything to that single source.

Agent-behavior rules live in skills, not in prevention-rules JSON that no file
scanner can enforce (rule-behavior-01). The ten rules that shipped in
`.guardrails/prevention-rules/extracted-rules.json` moved into the skill
templates — one owner each:

| Former rule | Now covered by |
|---|---|
| PREVENT-GIT-001 … 006 — no force push, no hard reset, no git-config edits, no amend without permission, no skipping hooks, no rebase on shared branches | `templates/skills/commit-validator` — Git Safety Rules |
| PREVENT-SYS-001 — no dangerous `rm -rf` | `templates/skills/four-laws` — Law 2, Stay in Scope |
| PREVENT-SEC-001 — no secrets in code or diffs | `templates/skills/commit-validator` — No Secrets in Diff |
| PREVENT-SEC-002 — no production database in test code | `templates/skills/four-laws` — Law 4, Halt When Uncertain |
| PREVENT-SCOPE-001 — pre-work failure-registry check before modifying files | `templates/skills/scope-validator` — Pre-work check |

## What's in the repository

```
.devgate/                      (this repo, when used as a submodule)
├── scripts/                   the gates and the fleet tooling
├── hub/                       runner-monitor hub (stdlib HTTP service + registry)
├── container/                 the coherence evaluator image and its recorded identity
├── templates/
│   ├── github-workflows/      seven drop-in CI workflows
│   ├── runner/                self-hosted runner standard (Podman quadlet)
│   ├── runner-monitor/        the hub's own container
│   └── skills/                six agent-behavior skills
├── openspec/                  change packages and published specs
├── docs/                      runbooks, threat model, onboarding, QA records
├── tests/                     the suite that gates this repository
├── AGENTS.md                  directions for agents working in DevGate projects
└── README.md
```

## CI, runners, and agent skills

Seven workflow templates ship in `templates/github-workflows/`: guardrails
compliance, secret validation, file size, smoke gate, scheduled drift scan, the
spec-coherence gate, and the specs-validation gate (`specs.yml`). Each carries a
`SETUP` header and `CUSTOMIZE`
placeholders. DevGate is host-repo aware — `detect-host-ci.py` reads your repo's
own `runs-on:` labels so the templates bind to the infrastructure you declared
instead of assuming `ubuntu-latest`.

DevGate runs the secret-scanning template's gate on itself: a `secrets` job in
this repository's CI calls the same `scripts/secret-scan.sh` that the template
hands to consumers, over the pushed range. Findings are reported by rule, path,
line, and commit — never by value, because a scanner that prints the match into
logs has published the secret a second time. Full history is clean as of
2026-09-24; the one hit it held was a documentation false positive, dispositioned
by rule *and* path in `.guardrails/secret-allowlist.json` rather than by
disabling the rule or excluding the file.

DevGate runs its own gates on itself: see [.github/workflows/ci.yml](.github/workflows/ci.yml)
for the reference implementation (full test suite with deterministic collection,
pattern + semantic + regression + silent-success scans against the framework's
own tree, registry hygiene, spec traceability counts, and a container-image
job that proves the evaluator image carries its frozen schemas). Their CI is
the honest baseline for yours — copy the shape, not just the commands.


The runner standard (`templates/runner/`) puts the official
`ghcr.io/actions/actions-runner` image onto your own hardware as a Podman
quadlet, one container per project, registration token from a `.env` that is
never committed. Three ticks keep a fleet honest: `runner-enroll.sh` installs the
units, `runner-heartbeat.sh` reports host health to the hub, and
`runner-image-cycle.sh` converges the pinned evaluator image into the podman
store the job actually reads (the gate never pulls at job time, so those bytes
have to be there beforehand).

The hub (`hub/`, container template in `templates/runner-monitor/`) is a
stdlib-only HTTP service on `/enroll`, `/heartbeat`, and `/health`. It combines
GitHub API polling with the heartbeats and raises deduplicated alerts as GitHub
issues — one open issue per `(repo, check-class, runner)`, with recurrence added
as a comment. Its registry lives on the hub volume and is never committed; only
the schema and a redacted example ship here.

Five skills ship in `templates/skills/` — four-laws (safety), scope-validator,
halt-conditions, production-first, and commit-validator — each a single
`SKILL.md` that drops into any agent runtime using that convention. Agent
directions live in [AGENTS.md](AGENTS.md); template usage is in
[templates/README.md](templates/README.md).

## The spec coherence service

This repository dogfoods its own idea. `hub/coherence/` is a service — stdlib
only, dual-runnable, evaluators isolated in a container — that answers one
question with a signed, replayable record: did this change set actually satisfy
the specs it claims to satisfy?

The pieces a human cares about:

- **Signed evaluation contexts.** A control-plane stand-in issues a context
  binding the policy, stage, baseline, and evaluation time. The run path verifies
  digests and countersignatures before believing anything.
- **A five-stage adoption ladder** — inventory → advisory → ratchet →
  enforced-core → enforced-full — so a repository earns enforcement instead of
  being handed a wall of red.
- **Anti-rollback.** A context binds the exact policy bundle (digest plus an
  epoch floor). An older-but-validly-signed bundle is rejected unless the control
  plane recorded a grandfather window, and the attempt is machine-readable in
  fleet reporting.
- **A stable exit-code contract:** PASS 0, ADVISORY 10, FAIL 20, invalid input
  30, policy refusal 31, execution error 32, seal failure 33 — plus deterministic
  replay of any historical decision.
- **`scripts/coherence-local`** runs the gate from your checkout through the same
  builder and driver invocations the CI template uses, resolving identity from
  the same registry the pin checks. `--build-only` emits the request and launch
  without a container; `--dry-run` prints the commands. A test replays the
  template's own command and byte-compares the output, so "local == CI" is
  enforced rather than asserted.

Status: Sprint 6 of 8 is in progress (adoption ladder and fleet integration);
Sprints 0–5 delivered the decision contract, the container/evaluator boundary,
and the attestation and evidence stack. The spec, task ledger, and design record
are in [openspec/changes/devgate-spec-coherence-service/](openspec/changes/devgate-spec-coherence-service/).

## What is verified, and where

Every state below was read off a real hosted run of `main`. Nothing in this table
is inferred from reading the configuration.

| Claim | Checked by | State |
| --- | --- | --- |
| Every spec validates under the strict delta grammar | `specs` job → `openspec validate --all --strict` | **GREEN** |
| Strict validation actually refuses malformed material | `specs` job → `scripts/specs-validate-negative-control.sh` | **GREEN** |
| The per-file runner discovers this repo's own tests | `tests` job → discovered count ≥ 1 | **GREEN** |
| Scanners resolve the project root without escaping to an ancestor | `tests` job → `tests/test_scanner_root_anchor.mjs` | **GREEN** |
| A pushed commit cannot carry a credential into `main` | `secrets` job → `scripts/secret-scan.sh` over the pushed range | **GREEN.** Run [36048653103](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36048653103) — the runner had no scanner, so the fetch path ran for real: `sha256sum` printed `gitleaks.tar.gz: OK` against the pin, `gitleaks version` printed `8.30.1`, and the gate reported `scope: commits in 5d59989..fba5f9e, plus the working tree` with 0 findings. |
| The evaluator image builds reproducibly, carrying its frozen schemas | `container-image` job → `podman build` plus an in-image schema load | **GREEN.** Two consecutive runs on `main` built the identical digest and printed `schemas OK in image`. The build is content-addressed over `hub/` and the coherence schemas. |
| The recorded identity is bytes a consumer can actually fetch | `container-image` job → anonymous `podman pull image@recorded`, then a schema load inside the fetched bytes | **GREEN.** Run [36055148205](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36055148205) pulls `ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence@sha256:fc7074e70752…` with `REGISTRY_AUTH_FILE=/nonexistent` — a consumer's runner has no credentials either — and loads the schemas from those bytes (`schemas OK in the fetched image`). The pull is the whole check: it verifies the manifest it fetched against the requested digest, so a success means the registry holds bytes addressed by the record. |

That identity row spent a day green while the pin was unpullable, and the reason
is worth one sentence: it compared a locally built image's digest against the
record — two values off the same build-time axis, neither of which is a digest
the registry serves. They matched on hosted CI, so the check passed while
`podman pull` of that exact record failed with `manifest unknown` for every
consumer. Pushing re-encodes the manifest; only a pull establishes the pullable
identity, so the gate now pulls.

Then the pull gained a second comparison — the fetched ref's `podman image
inspect`, against the record — and that one is local-storage too. On
2026-09-24 it failed a *correct* pin: the pull landed, the fetched bytes were
the pinned image's, and the check still went red because the store reported
`6032c209…` for bytes the registry addresses as `fc7074e7…`. The same read was
in the publish job's `served digest` line, where it printed a digest no
consumer could fetch (`manifest unknown`, anonymously, for the value it had
just advertised). Both now take their answer from the registry, and a test
runs each step against a podman that refuses to echo back the digest it was
handed — the failure is reproduced rather than described.

The item total isn't quoted on purpose: `--all` counts discovered items, so any
fixed number goes stale the moment a package is added. And the negative control
failed on its first clean-runner execution — the CLI couldn't be resolved from
its temp directory, because the probe used a bare `npx openspec` that a globally
installed CLI had been masking on the author's machine. It failed closed on a
real defect, which is the entire point of having it.

## AIGGP — Agent Intelligence Gate Loop Guardrails Platform

AIGGP is a portmanteau naming one goal: **pull the agent guardrails system
into DevGate** — one platform for AI-coding guardrails. This repository
already carries that name. The unification plan is written down in
[openspec/changes/aiggp-10-repository-unification-migration/](openspec/changes/aiggp-10-repository-unification-migration/)
— the agent guardrails system (`agent-guardrails-template` / `guardrail-mcp`
lineage) enters this repo by a non-squashed subtree merge under
`modules/guardrails/`, existing history stays reachable, and the standalone
predecessor is archived with a durable pointer once continuity is proven. The
current integration mechanism is `guardrails-control-plane`, which composes
DevGate and the guardrail engines as pinned submodules.

AIGGP spec packages were imported in September 2026 and live under
[openspec/changes/aiggp-01…10](openspec/changes/), with the sources as received
kept for provenance in [openspec/aiggp-source/](openspec/aiggp-source/). Be clear
about what that is: a specification, not shipped code. Nothing in those packages
is implemented, and no gate or traceability ID is wired to them.

**Two packages were retired on 2026-10-02** — `aiggp-00` (kernel truth model:
signed envelopes, org CA, append-only ledger, waivers) and `aiggp-09` (runner
enrollment / fleet identity). They specified kernel-level hardening that no
product implements, and DevGate already ships the working equivalent
(evidence bundles, HMAC attestation, scoped exceptions, the coherence run
ledger in `hub/coherence/`). The kept packages are re-anchored to that shipped
machinery. Decision record and measurements:
[AIGGP-RETIREMENT-2026-10-02.md](openspec/changes/AIGGP-RETIREMENT-2026-10-02.md).

## License

BSD 3-Clause

## Author

TheArchitectit

---

## ☕ Support This Project

If this project helps you, consider [sponsoring on GitHub](https://github.com/sponsors/TheArchitectit). Every donation goes straight back into the work — GPU hardware and cloud compute for AI development, API credits for the agents that build and test these projects, and keeping everything free and open source. As a solo architect shipping on nights and weekends, even a small monthly sponsor makes a real difference.

Help keep this project going — use a referral link below and both of us get credits!

| Service | Your Bonus | Details | Referral Code |
| --------- | ----------- | --------- | --------------- |
| [**Neuralwatt**](https://portal.neuralwatt.com/auth/register?ref=NW-ROGER-ET3Y) | $10 in credits | Spend $10+ → you get $10, we get $20 | `NW-ROGER-ET3Y` |
| [**Synthetic**](https://synthetic.new/?referral=UAWqkKQQLFkzMkY) | $10 in credits | Subscribe → both get $10 credit | `UAWqkKQQLFkzMkY` |
| [**Ozore**](https://ozore.com/?ref=cwe4kdx0) | 50% off first month | AI-ready cloud — code **lundrog50** | `lundrog50` |

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-TheArchitectit-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/TheArchitectit)
