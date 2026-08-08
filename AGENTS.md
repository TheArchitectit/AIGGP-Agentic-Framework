# DevGate — Agent Instructions

> **You are working in a project that uses DevGate as a quality gate.**
> DevGate is NOT the project you're building — it's a tool cloned in to enforce engineering standards.

## What DevGate Is

DevGate is a language-agnostic quality engineering framework. It provides:
- Pattern-based guardrails (SQL injection, unhandled promises, hardcoded creds, etc.)
- File-size enforcement (soft/hard limits per directory)
- Test isolation (per-file subprocess, parallel pooling, flake adjudication)
- Regression scanning (failure registry cross-reference)
- Deploy gating (clean tree → build → test → lint → scan → publish)

## What DevGate Is NOT

- ❌ It is NOT your project's codebase
- ❌ It is NOT a starter kit or project template
- ❌ It is NOT an agent framework or AI model
- ❌ It does NOT impose architecture decisions on your project

## How It'sstructured

```
your-project/               ← YOUR project code lives here
├── src/                    ← Your source files
├── tests/                  ← Your test files
├── package.json            ← Your package manifest
└── .devgate/               ← DevGate lives here (don't rename)
    ├── .guardrails/
    │   ├── failure-registry.jsonl
    │   ├── pre-work-check.md
    │   └── prevention-rules/
    ├── scripts/
    │   ├── deploy.sh
    │   ├── guardrails-scan.mjs
    │   ├── regression_check.py
    │   ├── run-tests.mjs
    │   ├── schema-health-check.mjs
    │   └── semantic-scan.mjs
    ├── AGENTS.md           ← This file
    ├── LICENSE             ← BSD 3-Clause
    └── README.md
```

## Before You Write Code

1. **Read `.devgate/.guardrails/pre-work-check.md`** — mandatory pre-work checklist
2. **Check the failure registry** — see if your files have known bug patterns:
   ```bash
   grep -f <(echo "your_file.ts") .devgate/.guardrails/failure-registry.jsonl
   ```
3. **Understand the rules** — scan `.devgate/.guardrails/prevention-rules/pattern-rules.json` for the 29 prevention rules across 10+ languages

## Before You Commit

Run these gates (all must pass):

```bash
# Pattern scan (all source file types)
node .devgate/scripts/guardrails-scan.mjs

# Semantic scan (TypeScript AST)
node .devgate/scripts/semantic-scan.mjs

# Regression check (file sizes, npm audit, failure registry)
python3 .devgate/scripts/regression_check.py --staged --pre-commit

# Schema health (if using SQLite)
node .devgate/scripts/schema-health-check.mjs
```

Or run the pre-commit hook directly:
```bash
bash .devgate/.claude/hooks/pre-commit.sh
```

## When You Fix a Bug

1. **Fix the bug**
2. **Append to the failure registry** — add a JSONL entry to `.devgate/.guardrails/failure-registry.jsonl`:
   ```json
   {"failure_id":"FAIL-YYYYMMDD01","timestamp":"2026-08-08T12:00:00Z","category":"runtime","severity":"high","error_message":"Description","root_cause":"Why it happened","affected_files":["src/file.ts"],"fix_commit":"abc1234","prevention_rule":"What prevents recurrence","status":"resolved"}
   ```
3. **Never edit existing registry entries** — append only
4. **Consider adding a new prevention rule** to `pattern-rules.json` if the bug pattern is generic

## Inline Rule Suppression

Use `// guardrails-allow RULE-ID: <reason>` to suppress a rule on a specific line:

```python
# guardrails-allow PREVENT-007: This bare except is intentional for the crash handler
except:
    handle_crash()
```

```typescript
// guardrails-allow PREVENT-029: This is the API boundary — network calls are intentional
fetch("https://api.example.com/data");
```

The reason text is required. Audited exceptions should be deliberate.

## Adding Custom Rules

Add to `.devgate/.guardrails/prevention-rules/pattern-rules.json`:

```json
{
  "rule_id": "PREVENT-CUSTOM-001",
  "name": "No eval() usage",
  "enabled": true,
  "pattern": "eval\\(",
  "forbidden_context": null,
  "message": "Do not use eval()",
  "severity": "error",
  "file_glob": ["*.js", "*.ts"],
  "suggestion": "Use Function() or a proper parser"
}
```

Rule IDs must match `^PREVENT(-[A-Z]+)?-\\d+$`.

## File-Size Limits

| Directory | Soft (warning) | Hard (blocks) |
|-----------|:---:|:---:|
| `src/` | 300 lines | 500 lines |
| `extensions/` | 400 lines | 500 lines |
| Test files | — | 600 lines |
| Python scripts | — | 600 lines |

When a file hits the soft limit, split it. Don't squeeze toward the hard limit.

## Deploy

```bash
bash .devgate/scripts/deploy.sh 1.0.0
```

The deploy pipeline auto-detects your package manager (npm, cargo, pip) and runs the full gate before publishing. Nothing publishes if any step fails.

## Key Principles

- **DevGate is a tool, not the project** — your code lives in the parent directory
- **Don't modify DevGate scripts** unless adding rules to `pattern-rules.json`
- **The failure registry is append-only** — never edit or delete entries
- **Rules apply to all matching files** — use inline annotations for deliberate exceptions
- **The pre-commit gate is mandatory** — never use `--no-verify` to skip it
