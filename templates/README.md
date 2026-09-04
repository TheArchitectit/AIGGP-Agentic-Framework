# DevGate Reusable Templates

This directory contains reusable CI workflow templates and agent-behavior skill templates that project owners can copy into their own repositories. Every project that pulls DevGate gets the complete set.

## Directory Structure

```
templates/
├── README.md                        # This file
├── github-workflows/                # Copy-into-.github/workflows templates
│   ├── guardrails-compliance.yml    # Process gates (scope, forbidden files, commits, AI attribution)
│   ├── secret-validation.yml        # Gitleaks + .env + credential + hardcoded-secret scan
│   ├── file-size-check.yml          # CI-enforced source-file line-count limit
│   └── smoke-gate.yml               # Headless run + completion-sentinel validation
└── skills/                          # Agent-behavior skill templates
    ├── four-laws/                   # The Four Laws of Agent Safety (mandatory)
    ├── scope-validator/             # Stay-in-scope enforcement
    ├── halt-conditions/             # When to stop and ask the user
    ├── three-strikes/               # Halt after 3 failed attempts
    ├── commit-validator/            # Conventional commit + AI-attribution rules
    └── production-first/            # Production code before tests/infrastructure
```

## How to Use

### GitHub Workflow Templates

Each file in `github-workflows/` is a drop-in workflow. To use one:

1. Copy the file to your repo at `.github/workflows/<filename>.yml`
2. Open the file and read the `SETUP` header comments
3. Replace any `CUSTOMIZE` placeholders with values for your project
4. Commit and push — the workflow runs on your next PR

The templates are deliberately generic: no game-specific paths, no hard-coded binary names. They work for any project — game engine, web app, CLI tool, data pipeline.

### Skill Templates

Each directory in `skills/` contains a `SKILL.md` following the [agent skill convention](https://github.com/anthropics/knowledge-work-plugins). To use one:

1. Copy the entire skill directory to your project's skills location
2. Place it where your agent runtime discovers skills (e.g. `~/.claude/skills/`, `.claude/skills/`, or your platform's equivalent)
3. The skill's frontmatter (`applies_to`, `tools`, `globs`) is already generic — no edits required for basic use

All six skills are **language-agnostic and project-agnostic**. They contain no references to specific file paths, engines, or frameworks. If you need a project-specific variant, copy the file and adapt — but the base versions are the canonical starting point.

## Customization Notes

Every workflow template has `CUSTOMIZE` markers in header comments showing what to change. The most common edits are:
- **Branch names** in `on:` blocks (default: `main, develop`)
- **Forbidden file patterns** in guardrails-compliance.yml
- **Source directories and file patterns** in file-size-check.yml
- **Launch command and sentinel strings** in smoke-gate.yml

If a customization is project-specific and would be useful to other projects, consider upstreaming it back to this directory.

## Versioning

These templates are versioned alongside DevGate. Breaking changes are documented in the project changelog. The `version` field in each SKILL.md follows semver.
