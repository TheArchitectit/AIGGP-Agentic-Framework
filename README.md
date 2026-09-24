# AIGGP — Agent Intelligence Gate Loop Guardrails Platform

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

This repository is DevGate, a quality gate for AI-assisted development, on a
settled path to merge into AIGGP — the **Agent Intelligence Gate Loop Guardrails
Platform** (the plan is in the [AIGGP section](#aiggp--agent-intelligence-gate-loop-guardrails-platform)
below). The heading carries the destination now, the way a rename is announced
before the paperwork; what ships from this repository today is still DevGate.

Drop it into a project — TypeScript, Python, Rust, Go, GDScript, or a mix — and
you get test isolation, regression scanning, deploy gates, scheduled drift scans,
CI workflow templates, a self-hosted runner standard, and agent-behavior
guardrails.

DevGate is not a template or a starter kit, and it won't rearrange your code. It
imposes no directory layout, language, package manager, or test framework. It
looks at what you have and gates it.

## Why this exists

Agents write code faster than anyone reviews it, and speed without a gate ships
regressions. DevGate sits between your agents and your production code and
catches two kinds of problems: the fast ones (SQL injection, unhandled promises,
committed credentials, unvalidated input, and about thirty more patterns) and the
slow ones — dependency rot, base-image drift, CI config that changed and nobody
noticed.

The part that matters more than the pattern list is that the gates refuse to lie.
A scan that evaluated nothing does not print "clean". A test run that discovered
zero files does not exit 0. A gate that can't run reports that it couldn't. If
you only take one idea from this project, take that one.

## Quick start

```bash
# As a submodule (recommended — stays in sync with upstream)
git submodule add https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate

# Or clone directly
git clone https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate
```

Every script finds your project root and scans whatever source files exist,
wherever you keep them:

```bash
node .devgate/scripts/guardrails-scan.mjs         # pattern scan, all source types
node .devgate/scripts/semantic-scan.mjs           # AST scan (TS/JS; skips if none)
node .devgate/scripts/run-tests.mjs               # isolated per-file test runner
python3 .devgate/scripts/regression_check.py --staged --pre-commit   # regression + file size
bash .devgate/scripts/deploy.sh 1.0.0             # gated publish (npm/cargo/pip/go)
```

Two things about the regression gate worth knowing up front. `--staged` sees only
uncommitted work, so on a clean checkout it prints `NOTHING SCANNED` rather than a
fake pass (add `--fail-if-empty` in CI to make that exit 2). And `--all` scans
everything since the last tag — that's a drift sweep for a schedule, not a
per-pull-request review; use `--base origin/main` for that.

## The gates

| Gate | What it does |
|------|--------------|
| `guardrails-scan.mjs` | Regex rules across ten-plus languages. Annotate a deliberate exception inline with `// guardrails-allow PREVENT-029: reason`. |
| `semantic-scan.mjs` | TypeScript-compiler AST checks (unhandled promises, missing `useEffect` deps). Fails closed: if TS/JS files exist and the parser isn't installed, the gate fails and prints the install command instead of reporting a clean scan. |
| `regression_check.py` | Cross-references changed files against the append-only failure registry, enforces file-size limits, runs a package audit, and promotes soft violations to blocking for files you actually changed. |
| `run-tests.mjs` | Per-file process isolation, up to 8 parallel workers, serial lanes for shared-resource tests, flake adjudication (failing files re-run alone), and hang-on-exit detection. |
| `deploy.sh` | Gated publish: build, test, lint, then publish — for npm, cargo, pip, or go. |
| `schema-health-check.mjs` | Adapter-based schema validation (SQLite, PostgreSQL, MySQL), skipping cleanly when no database is configured. |
| `findings_to_spec.py` | Turns failure-registry entries and live violations into `openspec/specs/<capability>/spec.md` requirement skeletons, so a bug becomes a requirement with a `// spec:` trace back to it. |

### Things we learned the hard way

A suite of presence checks ("does this string appear in the file") detects
deletion, not breakage — don't cite it as "tested". And building a fixture by
hand-writing the literal proves nothing about the code that saves it; build the
fixture by calling the real function.

## Rules, and how to add yours

The rules are data, not code: 32 pattern rules, 10 AST (semantic) checks, 9
silent-success rules, and 10 rules extracted from past failures. Most pattern
rules are scoped to several extensions at once, so the useful statement is
coverage rather than a per-language count: TypeScript / JSX / TSX / Svelte,
Python, Go, Rust, GDScript (`.gd`, `.tscn`, `.tres`), Kotlin, Java, Ruby, PHP,
YAML and CI config, Dockerfiles, and shell.

Add your own rules in an overlay, never by forking:

```
<project>/
  .devgate/.guardrails/...   # shared baseline (upstream-owned, never edited)
  .guardrails/...            # THIS project's delta only
  .guardrailsignore          # per-project scan scoping
```

The gates merge overlay and baseline by rule id: new ids append, same-id entries
replace in place, so you can retune a severity or kill a false positive without
touching the baseline. `semantic-scan.mjs` is the exception — its checks are
hardcoded AST logic, not data. Passing an explicit `--rules`/`--registry` path
collapses everything to that single source.

## What's in the repository

```
.devgate/                      (this repo, when used as a submodule)
├── scripts/                   the gates and the fleet tooling
├── hub/                       runner-monitor hub (stdlib HTTP service + registry)
├── container/                 the coherence evaluator image and its recorded identity
├── templates/
│   ├── github-workflows/      six drop-in CI workflows
│   ├── runner/                self-hosted runner standard (Podman quadlet)
│   ├── runner-monitor/        the hub's own container
│   └── skills/                five agent-behavior skills
├── openspec/                  change packages and published specs
├── docs/                      runbooks, threat model, onboarding, QA records
├── tests/                     the suite that gates this repository
├── AGENTS.md                  directions for agents working in DevGate projects
└── README.md
```

## CI, runners, and agent skills

Six workflow templates ship in `templates/github-workflows/`: guardrails
compliance, secret validation, file size, smoke gate, scheduled drift scan, and
the spec-coherence gate. Each carries a `SETUP` header and `CUSTOMIZE`
placeholders. DevGate is host-repo aware — `detect-host-ci.py` reads your repo's
own `runs-on:` labels so the templates bind to the infrastructure you declared
instead of assuming `ubuntu-latest`.

DevGate runs the secret-scanning template's gate on itself: a `secrets` job in
this repository's CI calls the same `scripts/secret-scan.sh` that the template
hands to consumers, over the pushed range. Findings are reported by rule, path,
line, and commit — never by value, because a scanner that prints the match into
logs has published the secret a second time. Full history is clean as of
2026-09-24; the one hit it held was a documentation false positive, dispositioned
by rule *and* path in `.guardrails/secret-allowlist.json` rather than by
disabling the rule or excluding the file.

The runner standard (`templates/runner/`) puts the official
`ghcr.io/actions/actions-runner` image onto your own hardware as a Podman
quadlet, one container per project, registration token from a `.env` that is
never committed. Three ticks keep a fleet honest: `runner-enroll.sh` installs the
units, `runner-heartbeat.sh` reports host health to the hub, and
`runner-image-cycle.sh` converges the pinned evaluator image into the podman
store the job actually reads (the gate never pulls at job time, so those bytes
have to be there beforehand).

The hub (`hub/`, container template in `templates/runner-monitor/`) is a
stdlib-only HTTP service on `/enroll`, `/heartbeat`, and `/health`. It combines
GitHub API polling with the heartbeats and raises deduplicated alerts as GitHub
issues — one open issue per `(repo, check-class, runner)`, with recurrence added
as a comment. Its registry lives on the hub volume and is never committed; only
the schema and a redacted example ship here.

Five skills ship in `templates/skills/` — four-laws (safety), scope-validator,
halt-conditions, production-first, and commit-validator — each a single
`SKILL.md` that drops into any agent runtime using that convention. Agent
directions live in [AGENTS.md](AGENTS.md); template usage is in
[templates/README.md](templates/README.md).

## The spec coherence service

This repository dogfoods its own idea. `hub/coherence/` is a service — stdlib
only, dual-runnable, evaluators isolated in a container — that answers one
question with a signed, replayable record: did this change set actually satisfy
the specs it claims to satisfy?

The pieces a human cares about:

- **Signed evaluation contexts.** A control-plane stand-in issues a context
  binding the policy, stage, baseline, and evaluation time. The run path verifies
  digests and countersignatures before believing anything.
- **A five-stage adoption ladder** — inventory → advisory → ratchet →
  enforced-core → enforced-full — so a repository earns enforcement instead of
  being handed a wall of red.
- **Anti-rollback.** A context binds the exact policy bundle (digest plus an
  epoch floor). An older-but-validly-signed bundle is rejected unless the control
  plane recorded a grandfather window, and the attempt is machine-readable in
  fleet reporting.
- **A stable exit-code contract:** PASS 0, ADVISORY 10, FAIL 20, invalid input
  30, policy refusal 31, execution error 32, seal failure 33 — plus deterministic
  replay of any historical decision.
- **`scripts/coherence-local`** runs the gate from your checkout through the same
  builder and driver invocations the CI template uses, resolving identity from
  the same registry the pin checks. `--build-only` emits the request and launch
  without a container; `--dry-run` prints the commands. A test replays the
  template's own command and byte-compares the output, so "local == CI" is
  enforced rather than asserted.

Status: Sprint 6 of 8 is in progress (adoption ladder and fleet integration);
Sprints 0–5 delivered the decision contract, the container/evaluator boundary,
and the attestation and evidence stack. The spec, task ledger, and design record
are in [openspec/changes/devgate-spec-coherence-service/](openspec/changes/devgate-spec-coherence-service/).

## What is verified, and where

Every state below was read off a real hosted run of `main`. Nothing in this table
is inferred from reading the configuration.

| Claim | Checked by | State |
| --- | --- | --- |
| Every spec validates under the strict delta grammar | `specs` job → `openspec validate --all --strict` | **GREEN** |
| Strict validation actually refuses malformed material | `specs` job → `scripts/specs-validate-negative-control.sh` | **GREEN** |
| The per-file runner discovers this repo's own tests | `tests` job → discovered count ≥ 1 | **GREEN** |
| Scanners resolve the project root without escaping to an ancestor | `tests` job → `tests/test_scanner_root_anchor.mjs` | **GREEN** |
| A pushed commit cannot carry a credential into `main` | `secrets` job → `scripts/secret-scan.sh` over the pushed range | **GREEN.** Run [36048653103](https://github.com/TheArchitectit/DevGate-Agentic-Framework/actions/runs/36048653103) — the runner had no scanner, so the fetch path ran for real: `sha256sum` printed `gitleaks.tar.gz: OK` against the pin, `gitleaks version` printed `8.30.1`, and the gate reported `scope: commits in 5d59989..fba5f9e, plus the working tree` with 0 findings. |
| The evaluator image builds reproducibly, carrying its frozen schemas | `container-image` job → `podman build` plus an in-image schema load | **GREEN.** Two consecutive runs on `main` built the identical digest and printed `schemas OK in image`. The build is content-addressed over `hub/` and the coherence schemas. |
| The recorded identity is bytes a consumer can actually fetch | `container-image` job → anonymous `podman pull image@recorded`, then a schema load inside the fetched bytes | **GREEN.** Run [36022160394](https://github.com/TheArchitectit/DevGate-Agentic-Framework/actions/runs/36022160394) pulls `ghcr.io/…/devgate-coherence@sha256:f470110c…` with `REGISTRY_AUTH_FILE=/nonexistent` — a consumer's runner has no credentials either — compares the fetched manifest digest against `container/execution-profiles.json`, and loads the schemas from the fetched bytes. |

That identity row spent a day green while the pin was unpullable, and the reason
is worth one sentence: it compared a locally built image's digest against the
record — two values off the same build-time axis, neither of which is a digest
the registry serves. They matched on hosted CI, so the check passed while
`podman pull` of that exact record failed with `manifest unknown` for every
consumer. Pushing re-encodes the manifest; only a pull establishes the pullable
identity, so the gate now pulls.

The item total isn't quoted on purpose: `--all` counts discovered items, so any
fixed number goes stale the moment a package is added. And the negative control
failed on its first clean-runner execution — the CLI couldn't be resolved from
its temp directory, because the probe used a bare `npx openspec` that a globally
installed CLI had been masking on the author's machine. It failed closed on a
real defect, which is the entire point of having it.

## AIGGP — Agent Intelligence Gate Loop Guardrails Platform

DevGate is on a path to merge into the guardrail platform. The unified product is
AIGGP: **Agent Intelligence Gate Loop Guardrails Platform**. The plan is written
down in [openspec/changes/aiggp-10-repository-unification-migration/](openspec/changes/aiggp-10-repository-unification-migration/)
— DevGate is imported into the Agent Guardrails repository by a non-squashed
subtree merge, both products sit behind explicit module boundaries, existing
history stays reachable from documented refs in the unified repository, and the
standalone repositories are archived with durable pointers once continuity is
proven.

Eleven AIGGP spec packages were imported in September 2026 and live under
[openspec/changes/aiggp-00…10](openspec/changes/), with the sources as received
kept for provenance in [openspec/aiggp-source/](openspec/aiggp-source/). Be clear
about what that is: a specification, not shipped code. Nothing in those packages
is implemented, no gate or traceability ID is wired to them, and AIGGP-02's
overlap with the adoption ladder that does ship is an open reconciliation item.
The sequencing is deliberate — the coherence-service specs land first, and the
feasibility pass on the unification comes after that.

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
