# DevGate Agentic Framework

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

A language-agnostic quality engineering framework for AI-assisted development. Drop it into any project — TypeScript, Python, Rust, Go, GDScript, or mixed stacks — and get test isolation, regression scanning, deploy gates, scheduled drift scans, CI workflows, a self-hosted runner standard, and guardrails out of the box.

## What This Is

DevGate is **not** a project template or a starter kit. It's a **quality gate** that sits between your AI agents and your production code. You clone it into an existing project (or add it as a submodule) and it enforces engineering standards without imposing architecture decisions.

**The problem it solves:** AI agents generate code fast, but velocity without guardrails produces regressions. DevGate catches the known failure patterns — SQL injection, unhandled promises, hardcoded credentials, unvalidated input, and 25+ more across languages — before they reach production. Scheduled drift scans catch everything else: dependency updates that aged, base-image/toolchain drift on your runners, and CI-config changes that never arrived as a PR.

## Quick Start

### Add to an existing project

```bash
# As a submodule (recommended — stays in sync with upstream)
git submodule add https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate

# Or clone directly
git clone https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate
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
# Pattern scan (checks all source file types in your project)
node .devgate/scripts/guardrails-scan.mjs

# Semantic scan (TypeScript/JavaScript AST — skips automatically if none found)
node .devgate/scripts/semantic-scan.mjs

# Regression check (file sizes, package audit, failure registry)
# --staged scopes to what you are about to commit. Do not use --all here: it
# scans every change since the last tag, not the commit you are making.
python3 .devgate/scripts/regression_check.py --staged --pre-commit

# On a clean checkout --staged sees NOTHING (it only scans uncommitted work).
# The gate says so loudly ("NOTHING SCANNED") instead of printing a clean pass.
# To audit already-committed content — e.g. a branch that was pushed without a
# local gate run — scan it explicitly:
python3 .devgate/scripts/regression_check.py --base origin/main   # diff origin/main...HEAD
# In CI, fail the job when a scope evaluated zero files:
python3 .devgate/scripts/regression_check.py --staged --fail-if-empty

# Run tests (auto-detects JS .test.js and Python test_*.py files)
node .devgate/scripts/run-tests.mjs

# Deploy (auto-detects npm/cargo/pip/go)
bash .devgate/scripts/deploy.sh 1.0.0
```

## How It Works

DevGate scripts **auto-detect** your project's:
- **Project root** — walks up from `.devgate/` to find `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `project.godot`, or `.git`
- **Source directories** — scans whatever directories exist (`src/`, `lib/`, `app/`, `scripts/`, `pkg/`, `cmd/`, etc.)
- **Package manager** — detects npm, cargo, pip, or go in deploy.sh
- **Test files** — finds `.test.js`, `.spec.js`, `test_*.py`, `_test.py` files anywhere in your project
- **Database engine** — schema-health-check.mjs defaults to `"none"` (skips) unless you configure it

DevGate does **not** impose:
- ❌ A specific directory structure (`src/` vs `lib/` vs `app/` — it scans whatever you have)
- ❌ A specific language (mix TS, Python, Rust, Go, GDScript — all scanned)
- ❌ A specific package manager (npm, cargo, pip, go — auto-detected)
- ❌ A specific database (SQLite, PostgreSQL, MySQL — adapter-based, or none)
- ❌ A specific test framework (`node --test`, `pytest`, `cargo test` — auto-detected)

## Supported Languages

| Language | Pattern Rules | Semantic Rules | File-Size Gates |
|----------|:---:|:---:|:---:|
| TypeScript/JavaScript | ✅ 6 rules | ✅ 2 rules | ✅ |
| Python | ✅ 4 rules | ✅ 2 rules | ✅ |
| Rust | ✅ 1 rule | ✅ 1 rule | ✅ |
| Go | ✅ 2 rules | ✅ 1 rule | ✅ |
| GDScript (Godot) | ✅ 5 rules | ✅ 2 rules | ✅ |
| Docker | ✅ 2 rules | — | — |
| Shell/Bash | ✅ 1 rule | — | — |
| Kotlin/Java | ✅ 1 rule | — | ✅ |
| Ruby | ✅ 3 rules | — | ✅ |
| PHP | ✅ 1 rule | — | ✅ |
| C/C++ | ✅ (file-size) | — | ✅ |
| Swift | ✅ (file-size) | — | ✅ |
| All languages | ✅ 3 rules | — | ✅ |

## Components

### Test Runner (`scripts/run-tests.mjs`)

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
  .devgate/.guardrails/prevention-rules/pattern-rules.json   <- shared baseline (upstream-owned)
  .devgate/.guardrails/failure-registry.jsonl                <- shared registry (upstream-owned)
  .guardrails/prevention-rules/pattern-rules.json            <- THIS project's delta only
  .guardrails/failure-registry.jsonl                         <- THIS project's bugs only
  .guardrailsignore                                          <- per-project scan scoping
```

Merge semantics (implemented once in `scripts/gate_overlay.py`, mirrored in
`guardrails-scan.mjs`):

* An overlay entry with a **new** id is appended — baseline rules keep firing.
* An overlay entry with the **same** id as a baseline entry **replaces** it, in
  place (retune severity, fix a false positive, override a message) — without
  ever forking the baseline into your repo.
* A missing overlay (or DevGate standalone) = baseline only, unchanged behaviour.
* An explicit `--rules` / `--registry` path or `PREVENTION_RULES_PATH` /
  `FAILURE_REGISTRY_PATH` / `GUARDRAILS_RULES` env collapses to that single
  source, no merge.

Overlay rule file shape — list only your delta, it does NOT need upstream's rules:

```json
{
  "version": "1.0.0",
  "rules": [
    {
      "rule_id": "PREVENT-SI-001",
      "name": "Non-cryptographic checksum for saves",
      "enabled": true,
      "pattern": "fn.*checksum.*\\(.*\\).*u64",
      "forbidden_context": "(sha|hmac|argon)",
      "message": "Save checksum is not cryptographic — use HMAC-SHA256",
      "severity": "warning",
      "file_glob": ["*.rs"],
      "suggestion": "Use hmac::Hmac<sha2::Sha256> for save integrity"
    }
  ]
}
```

Rule IDs must match `^PREVENT(-[A-Z]+)?-\\d+$` (per-project prefixes like
`-SI-`, `-SOH-` are the convention for scoping). Note `semantic-scan.mjs` is
exempt: its checks are hardcoded AST logic, not data — a project
`semantic-rules.json` is merged for `regression_check.py`'s advisory path but
does not drive that scanner.

## CI Integration

DevGate runs its own gates on itself: see [.github/workflows/ci.yml](.github/workflows/ci.yml)
for the reference implementation (full test suite with deterministic collection,
pattern + semantic + regression + silent-success scans against the framework's
own tree, registry hygiene, spec traceability counts, and a container-image
job that proves the evaluator image carries its frozen schemas). Their CI is
the honest baseline for yours — copy the shape, not just the commands.

Add to your `.github/workflows/ci.yml`:

```yaml
- name: Guardrails scan
  run: node .devgate/scripts/guardrails-scan.mjs

- name: Semantic scan (skips if no TS/JS)
  run: node .devgate/scripts/semantic-scan.mjs

- name: Regression check (drift window)
  # --all scans every change since the last tag (or HEAD~20). That is a
  # drift/release sweep, NOT a review of this pull request: on a repository
  # with legacy oversize files it reports pre-existing debt as blocking, the
  # gate goes permanently red, and reviewers stop reading it. Schedule it
  # (see templates/github-workflows/drift-scan.yml) and keep it off the
  # pull-request path.
  run: python3 .devgate/scripts/regression_check.py --all --pre-commit

# NOTE: DevGate has no flag to scope the regression scan to an arbitrary base
# ref (for example origin/main...HEAD), which is what a pull-request gate
# needs. --staged/--unstaged see nothing in a plain CI checkout, and --all
# widens to the tag window, so there is currently no per-PR scope. For
# file-size enforcement on pull requests use
# templates/github-workflows/file-size-check.yml; for the full governance
# sweep, run the regression gate on a schedule.

- name: Schema health (skips if no database configured)
  run: node .devgate/scripts/schema-health-check.mjs
```

## Reusable Templates

DevGate ships with a complete set of drop-in templates for every project that pulls it in. These are **separate from the framework scripts** — they are project-side assets that the consuming repo copies in. Located in `templates/`:

### CI Workflow Templates (`templates/github-workflows/`)

| Template | What it does |
|----------|--------------|
| `guardrails-compliance.yml` | Process gates: change-scope boundaries, forbidden files, conventional-commit format, AI attribution, GitHub Step Summary table |
| `secret-validation.yml` | Gitleaks scan, .env-file check, credential-file patterns, hardcoded-secret patterns |
| `file-size-check.yml` | CI-enforced line-count limit on source files (parameterized: SIZE_LIMIT, SOURCE_DIRS, FILE_PATTERN) |
| `smoke-gate.yml` | Headless run + completion-sentinel validation — fails closed if the app crashes, hangs, or produces no output |
| `drift-scan.yml` | Scheduled full-tree gate sweep; resolves the host's own runner label via `detect-host-ci.py` instead of hardcoding `ubuntu-latest` |

Each template has a `SETUP` header comment and clearly-marked `CUSTOMIZE` placeholders. See [templates/README.md](templates/README.md) for usage.

### Self-Hosted Runner Standard (`templates/runner/`)

DevGate's standard for producing CI evidence on your own hardware: the **official
`ghcr.io/actions/actions-runner` image** (GitHub-maintained, MIT) deployed as a
Podman quadlet or Docker container — one container per project, distinct labels,
registration token via a drop-in `.env` (never committed). See
[templates/runner/README.md](templates/runner/README.md) for the standard and
[templates/runner/self-hosted-runner.container](templates/runner/self-hosted-runner.container)
for the copy-in quadlet.

DevGate is **host-repo aware**: `scripts/detect-host-ci.py` reads the host
repo's own `runs-on:` labels and `schedule:` crons from
`.github/workflows/*.yml` (secrets-redacted) so workflows bind to the host's
declared infrastructure rather than a hardcoded hosted runner.

### Agent Skill Templates (`templates/skills/`)

Six language-agnostic, project-agnostic skills that any AI agent can load:

- **four-laws** — mandatory safety laws (read-before-edit, stay-in-scope, verify-before-commit, halt-when-uncertain)
- **scope-validator** — enforces "only touch authorized files" with dependency analysis
- **halt-conditions** — checklist of when to STOP and ask the user
- **three-strikes** — halt after 3 failed attempts on a single task
- **commit-validator** — conventional-commit format + AI attribution enforcement
- **production-first** — production code before tests or infrastructure

Each skill is a single `SKILL.md` with frontmatter, ready to drop into any agent runtime that supports the skill convention.

## Agent Directions

See [AGENTS.md](AGENTS.md) for comprehensive directions that AI agents should read when working in a project that uses DevGate.

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
