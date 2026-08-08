# Pre-Work Regression Check

**MANDATORY:** Read this document before starting ANY work on this codebase.

---

## Quick Checklist

Before editing any file, verify:

- [ ] **I have read the relevant documentation**
- [ ] **I know which files I will modify**
- [ ] **I have checked the Failure Registry** for known bugs in those files
- [ ] **I understand what bugs have been fixed** in this area before
- [ ] **I will not reintroduce known patterns** that caused previous bugs

---

## Active Failures Relevant to Current Work

**Instructions:** Before starting, run:
```bash
python scripts/regression_check.py --all
```

This will show you any potential regressions in your current changes. If you're starting fresh, check the registry for files in your scope:

```bash
grep -l "your_file.py" .guardrails/failure-registry.jsonl
```

---

## Known Bug Patterns by Category

### Build Failures
- Missing dependencies in imports
- Incorrect build configuration
- Circular dependencies

### Runtime Failures
- Null/undefined access without checks
- Unhandled promise rejections
- Resource leaks (files, connections)

### Test Failures
- Flaky tests without proper setup/teardown
- Tests depending on external state
- Race conditions in async tests

### Type Failures
- Missing type annotations
- Incorrect generic usage
- Type coercion issues

### Config Failures
- Missing environment variables
- Invalid configuration values
- Hardcoded values that should be configurable

---

## Prevention Rules in Effect

DevGate ships with language-agnostic prevention rules. The following patterns are automatically checked:

| Rule ID | Language | Pattern | Severity |
|---------|----------|---------|----------|
| PREVENT-001 | TS/JS | JSON.parse without null check | error |
| PREVENT-002 | Multi | SQL string concatenation | critical |
| PREVENT-003 | All | Hardcoded credentials | critical |
| PREVENT-004 | GDScript | Direct .free() on Node | error |
| PREVENT-007 | Python | Bare except clause | error |
| PREVENT-008 | Python | Mutable default arguments | error |
| PREVENT-009 | Go | Ignored error return | error |
| PREVENT-011 | TS/JS | `any` type usage | error |
| PREVENT-013 | Rust | unwrap() in production | warning |
| PREVENT-014 | Docker | :latest tag | error |
| PREVENT-022 | Multi | Debug mode in production | error |
| PREVENT-023 | Multi | CORS wildcard | error |
| PREVENT-029 | TS/JS | Network calls in core | critical |

**Run the regression check to see all active rules:**
```bash
python scripts/regression_check.py --verbose
```

---

## Required Verification Steps

### Before Starting Work

1. **Identify scope**: List all files you plan to modify
2. **Check registry**: Search for those files in failure-registry.jsonl
3. **Review patterns**: Understand what caused previous bugs
4. **Plan defensively**: Design your changes to avoid known issues

### During Development

1. **Run regression check frequently**:
   ```bash
   python scripts/regression_check.py --unstaged
   ```

2. **Test edge cases** that caused previous bugs

3. **Add regression tests** for any bug fixes you make

### Before Committing

1. **Final regression check**:
   ```bash
   python scripts/regression_check.py --staged
   ```

2. **Review your diff** for any patterns that match known bugs

3. **Verify no previous fixes were undone**

---

## When You Find a New Bug

**YOU MUST:**

1. **Fix the bug first**
2. **Log it in the registry** (append to `.guardrails/failure-registry.jsonl`)
3. **Add a regression test**
4. **Update prevention rules** if applicable

---

## Remember

> **The goal is not to slow you down—it's to prevent the same bugs from being fixed over and over again.**

---

**Last Updated:** Auto-generated from failure-registry.jsonl
**Registry Path:** `.guardrails/failure-registry.jsonl`
**Check Command:** `python scripts/regression_check.py`
