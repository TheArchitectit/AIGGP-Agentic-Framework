# DevGate Agentic Framework

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

A language-agnostic quality engineering framework for AI-assisted development. Drop it into any project — TypeScript, Python, Rust, Go, GDScript, or mixed stacks — and get test isolation, regression scanning, deploy gates, scheduled drift scans, CI workflows, a self-hosted runner standard, and guardrails out of the box.

## What This Is

DevGate is **not** a project template or a starter kit. It's a **quality gate** that sits between your AI agents and your production code. You clone it into an existing project (or add it as a submodule) and it enforces engineering standards without imposing architecture decisions.

**The problem it solves:** AI agents generate code fast, but velocity without guardrails produces regressions. DevGate catches the known failure patterns — SQL injection, unhandled promises, Godot `.free()` crashes, Rust `unwrap()` panics, hardcoded credentials, and 25+ more — before they reach production. Scheduled drift scans catch everything else: dependency updates that aged, base-image/toolchain drift on your runners, and CI-config changes that never arrived as a PR.

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
│   └── prevention-rules/
│       ├── pattern-rules.json          # Regex-based rules (29 rules, 10+ languages)
│       ├── pattern-rules.schema.json   # JSON schema for custom rules
│       ├── semantic-rules.json         # AST-based rules
│       └── extracted-rules.json        # Git/system/security rules
├── scripts/
│   ├── deploy.sh                       # Gated publish pipeline (auto-detects package manager)
│   ├── guardrails-scan.mjs             # Pattern scanner (all languages)
│   ├── regression_check.py             # Regression + file-size + package audit
│   ├── run-tests.mjs                   # Isolated per-file test runner (JS + Python)
│   ├── schema-health-check.mjs         # Database schema validation (adapter-based)
│   ├── semantic-scan.mjs               # AST-based TS/JS scanner
│   └── detect-host-ci.py               # Host-repo CI/runner detector (secrets-redacted)
├── templates/
│   ├── README.md                       # Template index and usage guide
│   ├── github-workflows/               # Drop-in CI workflow templates
│   │   ├── guardrails-compliance.yml   # Process gates (scope, forbidden files, commits, AI attribution)
│   │   ├── secret-validation.yml       # Gitleaks + .env + credential + hardcoded-secret scan
│   │   ├── file-size-check.yml         # CI-enforced source-file line-count limit
│   │   ├── smoke-gate.yml              # Headless run + completion-sentinel validation
│   │   └── drift-scan.yml              # Scheduled full-tree sweep, host-aware runner targeting
│   ├── runner/                         # Self-hosted runner standard (ghcr.io + Podman/Docker)
│   │   ├── README.md                   # The standard: official image, quadlet, secrets hygiene
│   │   └── self-hosted-runner.container # Podman quadlet template (ghcr.io/actions/actions-runner)
│   └── skills/                         # Agent-behavior skill templates
│       ├── four-laws/                  # The Four Laws of Agent Safety (mandatory)
│       ├── scope-validator/            # Stay-in-scope enforcement
│       ├── halt-conditions/            # When to stop and ask the user
│       ├── three-strikes/              # Halt after 3 failed attempts
│       ├── commit-validator/           # Conventional commit + AI-attribution rules
│       └── production-first/           # Production code before tests/infrastructure
├── AGENTS.md                           # Directions for AI agents
├── LICENSE                             # BSD 3-Clause
└── README.md                           # This file
```

### Run the gates

All scripts auto-detect your project root (the parent of `.devgate/`) and scan whatever source files exist there — regardless of language or directory structure.

```bash
# Pattern scan (checks all source file types in your project)
node .devgate/scripts/guardrails-scan.mjs

# Semantic scan (TypeScript/JavaScript AST — skips automatically if none found)
node .devgate/scripts/semantic-scan.mjs

# Regression check (file sizes, package audit, failure registry)
python3 .devgate/scripts/regression_check.py --all --pre-commit

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

### Regression Scanner (`scripts/regression_check.py`)

Scans changed files against the failure registry and pattern rules.
- **File-size enforcement** — soft/hard limits, auto-detects source directories
- **Package audit** — auto-detects your package manager (npm audit, or skips if not npm)
- **Soft-as-hard headroom gate** — promotes soft violations to blocking for changed files only
- **Failure registry** — cross-references changed files against known bug history

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
- `SEMANTIC-005`: React `useEffect` with missing dependencies

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

Database-agnostic schema validation. Ships with adapter templates for SQLite, PostgreSQL, and MySQL, but defaults to `"none"` (skips gracefully) so it never breaks if you don't use a database or use a different engine.

To enable, edit `scripts/schema-health-check.mjs`:
```javascript
const DB_ADAPTER = "postgres"; // "sqlite" | "postgres" | "mysql" | "none"
const EXPECTED_COLUMNS = [
    ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
    ["users", "email", "TEXT NOT NULL UNIQUE"],
];
```

Uncomment the adapter block for your database engine. The script auto-skips if `DB_ADAPTER` is `"none"` or `EXPECTED_COLUMNS` is empty.

### Failure Registry (`.guardrails/failure-registry.jsonl`)

Append-only JSONL log of historical bugs. Each entry records:
- Affected files
- Root cause
- Prevention rule
- Status (active/resolved)

When a file is changed, the regression scanner checks it against active failures — preventing reintroduction of known bugs.

## Configuration

### File Size Limits

All source file types are checked. Edit `scripts/regression_check.py`:

```python
SRC_SOFT = 300    # soft limit (lines) — warning
SRC_HARD = 500    # hard limit (lines) — blocks commit
TEST_HARD = 600   # test files hard limit
```

Limits apply to all files matching source extensions (`.ts`, `.py`, `.rs`, `.go`, `.gd`, `.java`, `.kt`, `.rb`, `.php`, `.js`, `.c`, `.cpp`, `.cs`, `.swift`) in any source directory that exists in your project.

### Custom Prevention Rules

Add to `.guardrails/prevention-rules/pattern-rules.json`:

```json
{
  "rule_id": "PREVENT-CUSTOM-001",
  "name": "No eval() usage",
  "enabled": true,
  "pattern": "eval\\(",
  "forbidden_context": null,
  "message": "Do not use eval()",
  "severity": "error",
  "file_glob": ["*.js", "*.ts"]
}
```

Rule IDs must match `^PREVENT(-[A-Z]+)?-\\d+$`.

## CI Integration

Add to your `.github/workflows/ci.yml`:

```yaml
- name: Guardrails scan
  run: node .devgate/scripts/guardrails-scan.mjs

- name: Semantic scan (skips if no TS/JS)
  run: node .devgate/scripts/semantic-scan.mjs

- name: Regression check
  run: python3 .devgate/scripts/regression_check.py --all --pre-commit

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
