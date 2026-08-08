# DevGate Agentic Framework

A language-agnostic quality engineering framework for AI-assisted development — test runner, regression scanner, deploy gates, CI workflows, and guardrails. Works with any language: TypeScript, Python, Rust, Go, GDScript, and more.

## What This Is

DevGate is the enforcement layer for AI agent development. It provides the tooling to validate, gate, and deploy code that was written by or with AI agents — ensuring the velocity of AI-generated code doesn't come at the cost of quality.

**DevGate is not another agent framework.** It's the quality gate that sits between your agents and your production code.

## Components

### Test Runner (`scripts/run-tests.mjs`)
- Node.js native test runner (`node --test`) with custom driver
- Per-file process isolation — each test file gets its own subprocess
- Parallel pooling (max 8 workers, configurable)
- Serial lanes for tests that can't share resources (port collision, CPU sensitivity)
- Flake adjudication — failed files re-run solo; flakes pass with flag
- Hang-on-exit detection — open handles don't block the pool
- Stale temp-dir sweeper

### Regression Scanner (`scripts/regression_check.py`)
- File-size limit enforcement (configurable per directory and language)
- npm audit gate (blocks on runtime HIGH/CRITICAL, warns on dev-only)
- Settings coverage check (every env var must have a dashboard entry)
- Soft-as-hard headroom gate — promotes soft violations to blocking, only for files changed since prior release tag
- Reads `.guardrails/failure-registry.jsonl` for known bug patterns

### Pattern Scanner (`scripts/guardrails-scan.mjs`)
- PREVENT-001: no JSON.parse without null check
- PREVENT-002: no SQL string concatenation
- PREVENT-003: no hardcoded credentials
- PREVENT-004: no direct .free() on Godot Nodes
- PREVENT-007: no bare except in Python
- PREVENT-009: no ignored error returns in Go
- PREVENT-013: no unwrap() in Rust production code
- Supports inline `// guardrails-allow PREVENT-xxx: <reason>` annotations
- Rules defined in `.guardrails/prevention-rules/pattern-rules.json` — add your own per language

### Semantic Scanner (`scripts/semantic-scan.mjs`)
- AST-based using TypeScript compiler API
- SEMANTIC-001: detects `.then()` chains without `.catch()` (unhandled promise rejection)
- Extensible rule format in `.guardrails/prevention-rules/semantic-rules.json`

### Schema Health Check (`scripts/schema-health-check.mjs`)
- Validates database schema integrity
- Checks for orphaned tables, missing indexes, constraint violations
- Configurable column registry

### Deploy Pipeline (`scripts/deploy.sh`)
Generic gated publish pipeline:
1. Clean git tree check
2. Native deps pre-flight
3. Full gate (build + test + lint + regression + guardrails)
4. Schema health validation
5. Build artifacts (if applicable)
6. Critical verify — bundle exists in pack output
7. UI smoke test (Playwright headless, if applicable)
8. Asset gate (required assets present, package size within budget)
9. Version bump
10. Commit + tag + push
11. Publish (npm, cargo, pip, or custom)
12. Post-publish verification

### CI Workflows (`.github/workflows/`)
| Workflow | Purpose |
|---|---|
| `ci.yml` | Full gate: build + test + lint + regression + schema health |
| `regression-guard.yml` | PR regression check + failure registry cross-reference + bot comment |
| `guardrails-lint.yml` | Scope boundaries, forbidden files, commit message format, AI attribution |
| `secret-validation.yml` | Gitleaks scan, .env file detection, hardcoded secret patterns |
| `documentation-check.yml` | 500-line doc limit, required sections, broken links, trailing whitespace |

### Pre-Commit Hook (`.claude/hooks/pre-commit.sh`)
Runs the full guardrails gate locally before commit.

### Failure Registry (`.guardrails/failure-registry.jsonl`)
Append-only JSONL log of historical bugs with:
- Affected files
- Root causes
- Prevention rules
- Status (active/resolved)

### Prevention Rules (`.guardrails/prevention-rules/`)
- `pattern-rules.json` — forbidden pattern definitions (multi-language)
- `pattern-rules.schema.json` — JSON schema for rule validation
- `semantic-rules.json` — AST-based semantic rules
- `extracted-rules.json` — extracted rule summaries

## Supported Languages

DevGate ships with prevention rules for:

| Language | Rules |
|----------|-------|
| TypeScript/JavaScript | JSON.parse, SQL injection, console.log, `any` type, unhandled promises |
| Python | bare except, mutable defaults, resource leaks, argument count |
| Rust | unwrap() in production, unreachable patterns |
| Go | ignored errors, goroutines without context, defer in loops |
| GDScript (Godot) | direct .free(), absolute paths, string get_node(), missing type hints, heavy ops in _process |
| Docker | latest tags, missing .dockerignore |
| Shell | command injection |
| Kotlin/Java | Thread.sleep |
| All | hardcoded credentials, TODO without ticket, debug mode, CORS wildcard, SSRF, weak hashes |

## Installation

### As a git submodule
```bash
git submodule add https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate
```

### As a direct clone
```bash
git clone https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate
```

### Copy specific tools
Each script is standalone. Copy only what you need:
```bash
# Just the test runner
curl -o scripts/run-tests.mjs https://raw.githubusercontent.com/TheArchitectit/DevGate-Agentic-Framework/main/scripts/run-tests.mjs

# Just the regression scanner
curl -o scripts/regression_check.py https://raw.githubusercontent.com/TheArchitectit/DevGate-Agentic-Framework/main/scripts/regression_check.py
```

## Usage

### Run the full test suite
```bash
node scripts/run-tests.mjs
```

### Run regression check
```bash
python3 scripts/regression_check.py --all
```

### Run guardrails scan
```bash
node scripts/guardrails-scan.mjs
```

### Run semantic scan
```bash
node scripts/semantic-scan.mjs
```

### Run the full gate (pre-commit)
```bash
bash .claude/hooks/pre-commit.sh
```

### Deploy
```bash
bash scripts/deploy.sh 1.0.0
```

## Configuration

### File Size Limits
Edit `scripts/regression_check.py` to adjust:
```python
SRC_SOFT = 300    # src/ soft limit (lines)
SRC_HARD = 500    # src/ hard limit
EXT_SOFT = 400    # extensions/ soft limit
EXT_HARD = 500    # extensions/ hard limit
TEST_HARD = 600   # test files hard limit
```

### Prevention Rules
Add custom patterns to `.guardrails/prevention-rules/pattern-rules.json`:
```json
{
  "rule_id": "PREVENT-CUSTOM-001",
  "name": "No eval() usage",
  "enabled": true,
  "pattern": "eval\\(",
  "message": "Do not use eval()",
  "severity": "error",
  "file_glob": ["*.js", "*.ts"]
}
```

### Failure Registry
Append new entries to `.guardrails/failure-registry.jsonl`:
```json
{
  "failure_id": "FAIL-001",
  "title": "Missing bundle in published package",
  "affected_files": ["dist/index.html"],
  "root_cause": "Build ran but output wasn't included in package",
  "prevention_rules": ["deploy.sh step 6 verifies bundle in pack --dry-run"],
  "status": "resolved",
  "date": "2026-07-15"
}
```

## License

MIT

## Author

TheArchitectit
