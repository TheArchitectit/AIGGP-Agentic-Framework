---
id: commit-validator
name: Commit Validator
description: Validates git commits follow conventional-commit and AI-attribution standards
version: 1.0.0
tags: [safety, workflow]
applies_to: [claude, cursor, opencode, openclaw, windsurf, copilot]
author: TheArchitectit
tools: [Bash, Read, Grep]
globs: "**/*"
alwaysApply: false
---

# Commit Validator

Validate all git commits against conventional-commit and AI-attribution standards.

## Validation Rules

### 1. AI Attribution (REQUIRED)

Every commit message MUST include AI attribution: `Co-Authored-By: <AI Name> <noreply@anthropic.com>`

### 2. Single Focus Rule

- One commit = One logical change
- No unrelated changes in the same commit

### 3. No Secrets in Diff

Scan for API keys, tokens, passwords, private keys, .env contents, DB connection strings. Block immediately if found.

### 4. Pre-Commit Requirements

- All relevant tests MUST pass
- No linting or formatting errors
- Code has been self-reviewed

## Commit Message Format

```
<type>: <description>

[optional body]

Co-Authored-By: <AI Name> <noreply@anthropic.com>
```

Types: feat, fix, docs, style, refactor, test, chore

## Validation Failure Actions

If validation fails:
1. Block the commit
2. Explain the violation
3. Provide specific fix instructions
4. Require user confirmation before proceeding

## Task

Validate the current git state against the commit standards above. Check staged changes, commit messages, and diffs for violations. If issues are found, explain the violations and provide specific fix instructions. Require user confirmation before allowing the commit to proceed.

## References

- `skills/scope-validator/SKILL.md` — Scope rules for staged changes
- `docs/AGENT_GUARDRAILS.md` — Core safety protocols
