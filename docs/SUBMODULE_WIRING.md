# Submodule wiring — the consumer contract

`DevGate` is wired into a consumer repository as a Git submodule at the fixed
path `.devgate/` (layout contract `root-anchor-01`): every gate resolves the
project root as the parent directory of `.devgate/`, never by walking up for a
marker file. The name is the contract — a submodule checked out at `devgate/`
or `vendor/devgate/` makes every gate scan the wrong tree, and no config fixes
a wrong path. This file is the operational contract for adding the submodule
and living with it; for the full onboarding narrative (overlay shapes, OpenSpec
package identity, CI ordering) see `docs/NEW_REPO_ONBOARDING.md`.

## Add or initialize

Fresh clone — fetch the submodule with the clone:

```bash
git clone --recurse-submodules <project-url> <dir>
```

Existing clone — register the submodule and initialize it:

```bash
git submodule add https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git .devgate
git submodule update --init --recursive
```

The case that actually bit a consumer: the `.gitmodules` entry was registered
but never initialized (for example, the entry was committed without
`git submodule update --init` ever running, or a later clone omitted
`--recurse-submodules`). Symptom: `.devgate/` exists but is empty, and every
gate fails or scans nothing. Fix — run the initializer from the project root:

```bash
git submodule update --init --recursive
```

Verify the submodule is initialized before running any gate:

```bash
git submodule status          # a NOT-yet-initialized entry prints "-<sha> .devgate"
                              # (leading minus); a checked-out pin prints "<sha> .devgate"
                              # with no marker, and "+<sha>" means the checkout differs
                              # from the recorded pin
ls .devgate/scripts           # the gates must be present, not an empty directory
```

## Scope: name every vendored/generated directory

There is **no dot-prefix exemption**. A hidden directory (`.agent-guardrails/`,
`.crew/`, `.claude/`, any consumer-vendored tree) is scanned as first-party
source unless its name is listed in `skip_dirs`. The walker
(`walk()` in `scripts/lib/gate_common.mjs`) descends every directory except:

- names present in the `skip_dirs` loaded from `.guardrails/scope.json` (spec
  `fw-scope-01`), and
- symlinked directories, which are never descended (cycle/escape guard).

Measured on a consumer game repo before this was understood: 162 pattern
violations and 107 warnings, all against upstream vendored code and none
against the consumer's own code, until a hidden vendored directory was named
in `skip_dirs`. That is why the baseline already carries `.claude`, `.crew`,
`.devgate`, `node_modules`, `vendor`, `build`, `dist`, `target`, and the rest —
and why every tree you vendor in-tree needs an entry of its own.

The overlay `.guardrails/scope.json` (project root) wins over the submodule
baseline; extend it there, never inside `.devgate/`. The shape:

```json
{
  "skip_dirs": ["node_modules", "vendor", ".agent-guardrails", "build-output"]
}
```

`source_dirs` is a separate, opt-in concern: it replaces the size-gate's
default walk-root candidate list entirely (falls back to `["."]` when nothing
matches), while `extra_source_dirs` only extends it. Adding to `skip_dirs`
and adding a source root are different operations — do not conflate them. For
the full scope contract see `docs/NEW_REPO_ONBOARDING.md` (`fw-scope-01`).

**Rule: after adding ANY submodule or vendored tree, add its directory name to
`skip_dirs` BEFORE the first gate run.** The failure this prevents is a first
gate run that reports hundreds of violations against code you did not write,
training the team to ignore red — the same failure class as a vacuous green.

## Secrets before first run

Add the `.gitignore` block **before** the first gate run — it must exist in the
tree before any gate executes, because the forbidden-file check in the
`guardrails-compliance` CI template (ci-match-01) blocks a tracked `.env` and
it should. A stray real `.env` committed before the patterns exist is exactly
the failure this prevents:

```gitignore
.env
.env.*
!.env.example
*.pem
*.key
```

`!.env.example` keeps the documented exception file committable while every
other `.env*` stays ignored. The forbidden-file check matches exact basenames,
not substrings, so `config/environment.yml` is not a false positive — only
real secret files fire. CI secrets themselves (deploy tokens, registry
credentials) live in the hosting platform's secret store, never in tracked
files.

## Living with the submodule

- **Never edit inside `.devgate/`.** The submodule is upstream-owned. Your
  delta lives in the project-root `.guardrails/` overlay; `gate_overlay.py`
  merges it over the bundled baseline by `rule_id` / `failure_id` and the
  overlay wins on collision. Editing the submodule forks the baseline and
  breaks the next upstream pull.
- **Never commit or push from inside `.devgate/`.** `git add .devgate` run
  from inside the submodule fails with `pathspec .devgate did not match any
  files` — run every parent-repo git command from the project root.
- **Pins track upstream `main`.** To advance, run `git submodule update
  --remote .devgate` (or checkout a specific ref) from the project root and
  commit the new pin. Advancing the pin is a reviewable commit in the consumer
  repo, which is how you can roll back.
- **Submodule URLs stay upstream-HTTPS.** CI checks out submodules anonymously
  over the URL recorded in `.gitmodules`; a local-path or fork URL that works
  on your machine fails the anonymous checkout. Never rewrite the recorded URL
  to a local path or a fork.
- **Don't repoint the path.** The submodule must stay at `.devgate/`; that is
  `root-anchor-01` (see `docs/NEW_REPO_ONBOARDING.md`).

## Gate sanity after wiring

Run the gates from the project root after wiring, and confirm each reports
**this** project's file paths before trusting any result:

```bash
node .devgate/scripts/guardrails-scan.mjs         # pattern scan, all source types
node .devgate/scripts/semantic-scan.mjs           # AST scan (TS/JS; skips if none)
node .devgate/scripts/run-tests.mjs               # isolated per-file test runner
python3 .devgate/scripts/regression_check.py --staged --pre-commit   # regression + file size
```

**Honesty rule: `NOTHING SCANNED` / `SKIPPED` is not a pass.** A gate that
evaluated zero inputs reports `NOTHING SCANNED` (gate-vacuous-01); on a clean
tree `regression_check.py --staged` prints exactly that rather than a fake
green. Add `--fail-if-empty` (or `--pre-commit`, which implies it) in CI so an
empty scope cannot green-light a commit. If a gate reports a sibling
repository's paths, it is not passing — it is scanning the wrong tree
(gate-root-01).

For prerequisites (pinned gitleaks, `typescript@5`, a pytest-capable python3)
and the tracked-tree gates that need an initial commit before they report
truthfully, see `docs/NEW_REPO_ONBOARDING.md` Step 2.

## Pairing with Agent Guardrails

Consumers commonly embed **both** systems. DevGate at `.devgate/` is the gate
submodule; Agent Guardrails (AGT, `agent-guardrails-template`) is wired in
separately for advisory agent behavior. They are distinct projects with
distinct purposes — DevGate gates code, AGT gates agent behavior — and the
AIGGP unification of the two is a proposal, not a shipped integration. Name
each vendored tree in `skip_dirs` regardless of which system owns it: a
vendored AGT checkout is scanned as first-party source until it is excluded,
which is precisely the failure above.

- AGT repo: <https://github.com/TheArchitectit/agent-guardrails-template>
- AGT how-to-apply: `docs/getting-started/how-to-apply.md` in that repo
