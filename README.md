# DevGate Agentic Framework

A language-agnostic quality engineering framework for AI-assisted development. Drop it into any project — TypeScript, Python, Rust, Go, GDScript, or mixed stacks — and get test isolation, regression scanning, deploy gates, CI workflows, and guardrails out of the box.

## What This Is

DevGate is **not** a project template or a starter kit. It's a **quality gate** that sits between your AI agents and your production code. You clone it into an existing project (or add it as a submodule) and it enforces engineering standards without imposing architecture decisions.

**The problem it solves:** AI agents generate code fast, but velocity without guardrails produces regressions. DevGate catches the known failure patterns — SQL injection, unhandled promises, Godot `.free()` crashes, Rust `unwrap()` panics, hardcoded credentials, and 25+ more — before they reach production.

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
│   ├── deploy.sh                       # Gated publish pipeline
│   ├── guardrails-scan.mjs             # Pattern scanner (all languages)
│   ├── regression_check.py             # Regression + file-size + npm audit
│   ├── run-tests.mjs                   # Isolated per-file test runner
│   ├── schema-health-check.mjs         # DB schema validation
│   └── semantic-scan.mjs               # AST-based TS scanner
├── LICENSE                             # BSD 3-Clause
└── README.md                           # This file
```

### Run the gates

```bash
# Run all guardrails scans
node .devgate/scripts/guardrails-scan.mjs

# Run semantic (AST) scan on TypeScript files
node .devgate/scripts/semantic-scan.mjs

# Run regression check (file sizes, npm audit, failure registry)
python3 .devgate/scripts/regression_check.py --all

# Run the full test suite with isolation
node .devgate/scripts/run-tests.mjs

# Pre-commit gate (runs everything)
bash .devgate/.claude/hooks/pre-commit.sh

# Deploy (gated publish)
bash .devgate/scripts/deploy.sh 1.0.0
```

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
| All languages | ✅ 3 rules | — | ✅ |

### Rule highlights

| Rule | Languages | What it catches |
|------|-----------|-----------------|
| PREVENT-001 | TS/JS | `JSON.parse()` without null check |
| PREVENT-002 | Multi | SQL injection via string concatenation |
| PREVENT-003 | All | Hardcoded credentials |
| PREVENT-004 | GDScript | Direct `.free()` on Node (crash risk) |
| PREVENT-007 | Python | Bare `except:` catches SystemExit |
| PREVENT-008 | Python | Mutable default arguments |
| PREVENT-009 | Go | Ignored error returns |
| PREVENT-011 | TS/JS | `any` type usage |
| PREVENT-013 | Rust | `unwrap()` in non-test code |
| PREVENT-014 | Docker | `:latest` tag in production |
| PREVENT-022 | Multi | Debug mode enabled in production |
| PREVENT-023 | Multi | CORS wildcard |
| PREVENT-024 | Multi | AI-hallucinated package imports |
| PREVENT-025 | Multi | Weak hash for passwords (MD5/SHA1) |
| PREVENT-026 | Multi | SSRF via unvalidated URL |
| PREVENT-029 | TS/JS | Network calls in core modules |

## Components

### Test Runner (`scripts/run-tests.mjs`)

Isolated per-file test runner using Node's native `node --test`.

- **Per-file process isolation** — each test file gets its own subprocess
- **Parallel pooling** — up to 8 workers (configurable via `DEVGATE_TEST_POOL`)
- **Serial lanes** — tests that share resources (ports, CPU budgets) run one-at-a-time
- **Flake adjudication** — failed files re-run solo; flakes pass with flag
- **Hang-on-exit detection** — open handles don't block the pool
- **Stale temp-dir sweeper** — cleans up test artifacts older than 60 minutes

Env overrides:
```bash
DEVGATE_TEST_TIMEOUT=120000    # per-file hard cap in ms
DEVGATE_TEST_POOL=8            # parallel worker count
DEVGATE_TEST_HANG_MS=10000     # silence threshold before force-kill
```

### Regression Scanner (`scripts/regression_check.py`)

Scans changed files against the failure registry and pattern rules.

- **File-size enforcement** — soft/hard limits per directory and language
- **npm audit gate** — blocks on runtime HIGH/CRITICAL vulnerabilities
- **Soft-as-hard headroom gate** — promotes soft violations to blocking for changed files only
- **Failure registry** — cross-references changed files against known bug history

### Pattern Scanner (`scripts/guardrails-scan.mjs`)

Regex-based scanner that checks all source files (`.ts`, `.py`, `.rs`, `.go`, `.gd`, `.java`, `.kt`, `.rb`, `.php`) against enabled rules. Supports inline annotations:

```typescript
// guardrails-allow PREVENT-029: This file is the API boundary — network calls are intentional
fetch("https://api.example.com/data");
```

### Semantic Scanner (`scripts/semantic-scan.mjs`)

AST-based scanner using the TypeScript compiler API. Catches structural issues that regex can't:

- `SEMANTIC-001`: Promise `.then()` chains without `.catch()`
- `SEMANTIC-005`: React `useEffect` with missing dependencies
- `SEMANTIC-007`: Rust unreachable match arms
- `SEMANTIC-008`: Godot signal connected to non-existent method

### Deploy Pipeline (`scripts/deploy.sh`)

Generic gated publish pipeline. Auto-detects your package manager:

1. Clean git tree check
2. Full gate (build + test + lint + regression + guardrails)
3. Schema health validation
4. Build artifacts (if applicable)
5. Critical verify — bundle exists in pack output
6. UI smoke test (if Playwright configured)
7. Version bump
8. Commit + tag + push (before publish — push failure aborts)
9. Publish (npm / cargo / pip / custom)
10. GitHub release with auto-generated notes

### Failure Registry (`.guardrails/failure-registry.jsonl`)

Append-only JSONL log of historical bugs. Each entry records:

- Affected files
- Root cause
- Prevention rule
- Status (active/resolved)

When a file is changed, the regression scanner checks it against active failures — preventing reintroduction of known bugs.

## Configuration

### File Size Limits

Edit `scripts/regression_check.py`:

```python
SRC_SOFT = 300    # src/ soft limit (lines) — warning
SRC_HARD = 500    # src/ hard limit (lines) — blocks commit
EXT_SOFT = 400    # extensions/ soft limit
EXT_HARD = 500    # extensions/ hard limit
TEST_HARD = 600   # test files hard limit
PY_HARD = 600     # Python files hard limit
```

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

### Schema Health

Edit `scripts/schema-health-check.mjs` and add your tables to `EXPECTED_COLUMNS`:

```javascript
const EXPECTED_COLUMNS = [
    ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
    ["users", "email", "TEXT NOT NULL UNIQUE"],
    ["users", "created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"],
];
```

## CI Integration

Add to your `.github/workflows/ci.yml`:

```yaml
- name: Guardrails scan
  run: node .devgate/scripts/guardrails-scan.mjs

- name: Semantic scan
  run: node .devgate/scripts/semantic-scan.mjs

- name: Regression check
  run: python3 .devgate/scripts/regression_check.py --all --pre-commit

- name: Schema health
  run: node .devgate/scripts/schema-health-check.mjs
```

## Agent Setup Guide

When an AI agent clones this framework into your project, it should:

1. **Read this README and `.guardrails/pre-work-check.md` first** — understand the rules before writing code
2. **NOT rename the `.devgate/` directory** — scripts reference paths relative to the framework root
3. **Run `python3 scripts/regression_check.py --all` before any commit** — this is the gate
4. **Add new failure entries to `failure-registry.jsonl`** when fixing bugs — append-only, never edit existing entries
5. **Add custom rules to `pattern-rules.json`** — don't modify the schema file
6. **Use inline `// guardrails-allow RULE-ID: <reason>` annotations** for deliberate exceptions — never disable rules globally
7. **Recognize this is a tool, not the project** — DevGate enforces quality; your project's code lives alongside it, not inside it

### For AI Agents (AGENTS.md snippet)

If you're an AI agent working in a project that uses DevGate, add this to your project's `AGENTS.md`:

```markdown
## DevGate Framework

This project uses DevGate for quality gates. The framework lives in `.devgate/`.

Before committing:
1. Run `python3 .devgate/scripts/regression_check.py --staged --pre-commit`
2. Run `node .devgate/scripts/guardrails-scan.mjs`
3. Check `.devgate/.guardrails/failure-registry.jsonl` for known bugs in your files

DevGate is NOT this project — it's a quality tool cloned in. Don't modify DevGate's
scripts unless adding a new rule to `pattern-rules.json`. Your project's code lives
in the parent directory, not inside `.devgate/`.
```

## License

BSD 3-Clause

## Author

TheArchitectit
