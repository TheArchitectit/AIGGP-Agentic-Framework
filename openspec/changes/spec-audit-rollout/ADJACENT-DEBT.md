# Adjacent debt filed by spec-audit-rollout (SA-DEBT)

Items found while doing this package that belong to someone else's change.
Filed here so they are tracked and not silently fixed inside a package whose
spec does not own them (design.md assumption 5).

## SA-DEBT-1 — the gate template's validate step is not pinned at its call site

- **Where:** `AIGGP-Agentic-Framework/templates/github-workflows/specs.yml`
  — the "openspec validate (strict, hard gate)" step runs
  `npx openspec validate --all --strict`.
- **What the comment claims:** "PINNED ON PURPOSE: an unpinned CLI moves the
  gate under the tree whenever upstream publishes."
- **What is actually true:** the pin exists only in a *separate* step
  (`npm install --no-save --no-audit --no-fund "@fission-ai/openspec@1.13.0"`).
  The call site itself names no version, and `npx` without `--no-install`
  will fetch the latest published CLI from the registry whenever the local
  `node_modules/.bin/openspec` is missing — a pruned cache, a reordered or
  renamed install step, a consumer whose install wrote to another cwd. In
  that state the gate silently becomes the version upstream shipped that
  morning, which is exactly the failure mode the comment says it prevents.
- **Why it is not fixed here:** the template is shared by every consumer
  repo; changing how its gate resolves its validator is its own reviewed
  change with its own rollout (and should come with a negative control that
  proves the pinned path is the one taken).
- **Suggested shape:** invoke `node_modules/.bin/openspec validate …`
  explicitly (or `npx --no-install openspec …`), so a missing install fails
  the step instead of resolving something else from the network; add a test
  that the step's command mentions no bare `npx openspec`.
- **Status:** open. Found 2026-10-23 while landing the spec-fleet sweep,
  which for its own job installs the CLI and hands it to the classifier by
  absolute path (`SPEC_AUDIT_OPENSPEC_BIN`) rather than relying on `npx`.
