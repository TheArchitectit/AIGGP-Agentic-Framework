# DevGate — Agent Instructions

> **You are working in a project that uses DevGate as a quality gate.**
> DevGate is NOT the project you're building — it's a tool cloned in to enforce engineering standards.

## What DevGate Is

DevGate is a language-agnostic quality engineering framework. It provides:
- Pattern-based guardrails (SQL injection, unhandled promises, hardcoded creds, etc.)
- File-size enforcement (soft/hard limits, auto-detects source directories)
- Test isolation (per-file subprocess, parallel pooling, flake adjudication)
- Regression scanning (failure registry cross-reference)
- Deploy gating (clean tree → build → test → lint → scan → publish)
- Schema validation (adapter-based — SQLite, PostgreSQL, MySQL, or none)

## What DevGate Is NOT

- ❌ It is NOT your project's codebase
- ❌ It is NOT a starter kit or project template
- ❌ It is NOT an agent framework or AI model
- ❌ It does NOT impose architecture, language, database, or directory structure decisions
- ❌ It does NOT assume you use npm, SQLite, TypeScript, or any specific technology

## How It's Structured

```
your-project/               ← YOUR project code lives here (any structure, any language)
├── your source files...    ← Whatever directories your project uses
├── your config files...    ← package.json, Cargo.toml, pyproject.toml, go.mod, etc.
└── .devgate/               ← DevGate lives here (don't rename)
    ├── .guardrails/
    │   ├── failure-registry.jsonl
    │   ├── pre-work-check.md
    │   ├── silent-success-allowlist.json
    │   └── prevention-rules/
    ├── docs/
    │   ├── RELEASE_GATE.md         ← Release stages and why each exists
    │   └── WRITE_AUDIT_REVIEW.md   ← The four-gate agent process
    ├── scripts/
    │   ├── deploy.sh
    │   ├── guardrails-scan.mjs
    │   ├── log_failure.py          ← Append a failure-registry entry
    │   ├── regression_check.py
    │   ├── run-tests.mjs
    │   ├── schema-health-check.mjs
    │   ├── semantic-scan.mjs
    │   └── silent-success-scan.sh  ← Simulated-success detector
    ├── AGENTS.md           ← This file
    ├── LICENSE             ← BSD 3-Clause
    └── README.md
```

## Auto-Detection

DevGate scripts auto-detect your project's technology stack. You do NOT need to configure:
- **Project root** — found by walking up to find `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `project.godot`, or `.git`
- **Source directories** — scans whatever exists (`src/`, `lib/`, `app/`, `scripts/`, `pkg/`, `cmd/`, `game/`, or project root)
- **Package manager** — npm, cargo, pip, or go detected automatically in `deploy.sh`
- **Test files** — `.test.js`, `.spec.js`, `test_*.py`, `_test.py` found anywhere in your project
- **Database engine** — schema-health-check defaults to `"none"` (skips) unless you configure it

## Before You Write Code

1. **Read `.devgate/.guardrails/pre-work-check.md`** — mandatory pre-work checklist
2. **Check the failure registry** — see if your files have known bug patterns:
   ```bash
   grep -f <(echo "your_file.py") .devgate/.guardrails/failure-registry.jsonl
   ```
3. **Understand the rules** — scan `.devgate/.guardrails/prevention-rules/pattern-rules.json` for the 29 prevention rules across 10+ languages

## Before You Commit

Run these gates (all must pass):

```bash
# Pattern scan (auto-detects your source files, any language)
node .devgate/scripts/guardrails-scan.mjs

# Semantic scan (TypeScript/JavaScript AST — skips if none found)
node .devgate/scripts/semantic-scan.mjs

# Regression check (file sizes, package audit, failure-registry patterns)
python3 .devgate/scripts/regression_check.py --staged --pre-commit

# Silent-success scan (skips when no detector families are enabled)
bash .devgate/scripts/silent-success-scan.sh

# Schema health (skips if no database configured)
node .devgate/scripts/schema-health-check.mjs
```

## The Four Gates (Write → Audit → Review → Commit)

DevGate's scanners catch *known* failure patterns. They cannot tell whether the work does what was asked, whether a test asserts anything, or whether an agent reported success it never achieved. So work moves through four gates:

| Gate | Actor | Definition of done |
|------|-------|--------------------|
| 1. Write | Writer agent | Only in-scope files changed; self-checked |
| 2. Audit | **Independent** agent | Evidence gathered first-hand; explicit verdict |
| 3. Review | Lead | Findings reconciled; gates re-run |
| 4. Commit & Push | Lead | Clean diff, documented message, pushed |

**The separation rule:** the agent that *writes* must not be the only agent that *validates*. The audit is performed by a **different agent in a different session**, and it sees the produced artifact — not the writer's reasoning. The lead reviews after the audit and is the **only** role that commits and pushes.

Never report a check as passed when it failed, was skipped, or was never run. Use `NOT_RUN` with the blocker stated — a gate falsely reported green is worse than one that was never run, because it removes the reason to look.

See **[docs/WRITE_AUDIT_REVIEW.md](docs/WRITE_AUDIT_REVIEW.md)** for the full process, the auditor checklist, and the acceptance-report contract. Release-specific gates are in **[docs/RELEASE_GATE.md](docs/RELEASE_GATE.md)**.

## When You Fix a Bug

1. **Fix the bug**
2. **Append to the failure registry** — use the helper (it validates the enums and generates the ID):
   ```bash
   python3 .devgate/scripts/log_failure.py \
     --error-message "what broke" --category runtime --severity high \
     --root-cause "why it happened" --affected-files path/to/file \
     --regression-pattern 'the_signature_that_must_not_return' \
     --prevention-rule "what prevents recurrence"
   ```
   The `regression_pattern` is the important field: `regression_check.py` compiles it and fails the build if that pattern reappears in newly **added** code. Scope it with `--file-glob` when the pattern would otherwise match docs or helpers. Or append the JSONL entry by hand:
   ```json
   {"failure_id":"FAIL-YYYYMMDD01","timestamp":"2026-08-08T12:00:00Z","category":"runtime","severity":"high","error_message":"Description","root_cause":"Why it happened","affected_files":["path/to/your/file"],"fix_commit":"abc1234","prevention_rule":"What prevents recurrence","status":"resolved"}
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

Applies to ALL source file types (`.ts`, `.py`, `.rs`, `.go`, `.gd`, `.java`, `.kt`, `.rb`, `.php`, `.js`, `.c`, `.cpp`, `.cs`, `.swift`) in whatever source directories your project uses.

| Category | Soft (warning) | Hard (blocks) |
|----------|:---:|:---:|
| Source files | 300 lines | 500 lines |
| Test files | — | 600 lines |

When a file hits the soft limit, split it. Don't squeeze toward the hard limit.

## Database Configuration (Optional)

If your project uses a database, edit `scripts/schema-health-check.mjs`:

```javascript
const DB_ADAPTER = "postgres"; // "sqlite" | "postgres" | "mysql" | "none"
const EXPECTED_COLUMNS = [
    ["your_table", "your_column", "expected_type"],
];
```

Uncomment the adapter block for your database engine. If you don't use a database, leave `DB_ADAPTER = "none"` — the script skips gracefully.

**DevGate will NOT change your database engine or suggest one.** It only validates schema integrity for whatever engine you've chosen.

## Deploy

```bash
bash .devgate/scripts/deploy.sh 1.0.0
```

The deploy pipeline auto-detects your package manager and runs the appropriate build/test/publish commands. Nothing publishes if any step fails.

| If your project has | Deploy uses |
|---------------------|-------------|
| `package.json` | `npm publish` |
| `Cargo.toml` | `cargo publish` |
| `pyproject.toml` / `setup.py` | `twine upload` |
| `go.mod` | Tag pushed (Go has no central registry) |
| `project.godot` | Tag pushed (manual export) |
| None of the above | Tag pushed, publish manually |

## Key Principles

- **DevGate is a tool, not the project** — your code lives in the parent directory
- **Don't modify DevGate scripts** unless adding rules to `pattern-rules.json`
- **The failure registry is append-only** — never edit or delete entries
- **Rules apply to all matching files** — use inline annotations for deliberate exceptions
- **The pre-commit gate is mandatory** — never use `--no-verify` to skip it
- **DevGate auto-detects your stack** — don't override unless you have a specific need
