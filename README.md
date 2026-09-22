# DevGate Agentic Framework

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

A language-agnostic quality gate for AI-assisted development. Drop it into any project — TypeScript, Python, Rust, Go, GDScript, or a mixed stack — and get test isolation, regression scanning, deploy gates, scheduled drift scans, CI workflows, a self-hosted runner standard, and agent-behavior guardrails out of the box.

## Why this exists

AI agents write code fast, and velocity without guardrails ships regressions. DevGate sits between your agents and your production code. It catches the fast failure patterns — SQL injection, unhandled promises, hardcoded credentials, unvalidated input, 25+ more across languages — and the slow ones: dependency updates that aged, runner and base-image drift, CI-config changes that never arrived as a pull request.

DevGate is **not** a project template or starter kit. It imposes no architecture: no required directory layout, language, package manager, database, or test framework. It detects what you have and gates it.

## Quick start

```bash
# As a submodule (recommended — stays in sync with upstream)
git submodule add https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate

# Or clone directly
git clone https://github.com/TheArchitectit/DevGate-Agentic-Framework.git .devgate
```

Run the gates (every script auto-detects your project root and scans whatever source files exist, in whatever directories you keep them):

```bash
node .devgate/scripts/guardrails-scan.mjs        # pattern scan, all source types
node .devgate/scripts/semantic-scan.mjs           # AST scan (TS/JS; skips if none)
node .devgate/scripts/run-tests.mjs               # isolated per-file test runner
python3 .devgate/scripts/regression_check.py --staged --pre-commit   # regression + file size
bash .devgate/scripts/deploy.sh 1.0.0             # gated publish (auto-detects npm/cargo/pip/go)
```

Scopes worth knowing on the regression gate: `--staged` sees only uncommitted work — on a clean checkout it prints a loud `NOTHING SCANNED`, never a fake clean pass (add `--fail-if-empty` in CI to turn that into exit 2). To audit already-committed content, scan it explicitly with `--base origin/main` (diff `origin/main...HEAD`). `--all` scans every change since the last tag — that is a drift/release sweep, not a pull-request review; run it on a schedule, not per-PR.

## What's in the box

```
.devgate/
├── .guardrails/            # pattern/semantic rules, failure registry, pre-work checklist
├── scripts/                # the gates (scan, test, regression, deploy, schema, drift)
├── templates/
│   ├── github-workflows/   # drop-in CI workflows (guardrails, secrets, file size, smoke, drift)
│   ├── runner/             # self-hosted runner standard (ghcr.io image + Podman quadlet)
│   └── skills/             # agent-behavior skills (four-laws, scope-validator, three-strikes, ...)
├── AGENTS.md               # directions for AI agents working in projects that use DevGate
└── README.md
```

### The gates

| Gate | What it does |
|------|--------------|
| **Pattern scanner** (`guardrails-scan.mjs`) | Regex rules across 10+ languages; inline `// guardrails-allow PREVENT-029: reason` annotations supported |
| **Semantic scanner** (`semantic-scan.mjs`) | TypeScript-compiler AST checks (unhandled promises, missing useEffect deps). Fail-closed: if TS/JS files exist but the parser isn't installed, the gate FAILS with the install command — a gate that evaluated nothing must not read as "clean" |
| **Regression scanner** (`regression_check.py`) | Cross-references changed files against the append-only failure registry, enforces file-size limits, runs package audit, promotes soft violations to blocking for changed files. No vacuous green — zero changed files is a notice, never a pass |
| **Test runner** (`run-tests.mjs`) | Per-file process isolation, parallel pooling (up to 8 workers), serial lanes for shared-resource tests, flake adjudication (failed files re-run solo), hang-on-exit detection |
| **Deploy pipeline** (`deploy.sh`) | Gated publish for npm, cargo, pip, or go — build, test, lint, then publish |
| **Schema health** (`schema-health-check.mjs`) | Adapter-based schema validation (SQLite/PostgreSQL/MySQL); defaults to skip when no database is configured |
| **Findings → specs** (`findings_to_spec.py`) | Turns failure-registry entries and live scan violations into `openspec/specs/<capability>/spec.md` requirement skeletons, closing the loop: bug → requirement → `// spec:` trace → blocking traceability gate |

Two honest notes about test evidence: a suite of only presence checks ("does the string appear in the file") detects deletion, not breakage — never cite it as "tested." And round-tripping a hand-written literal proves nothing about the code that actually saves; build the fixture by calling the real function.

### Supported languages

| Language | Pattern rules | Semantic rules | File-size gates |
|----------|:---:|:---:|:---:|
| TypeScript/JavaScript | 6 | 2 | yes |
| Python | 4 | 2 | yes |
| Rust | 1 | 1 | yes |
| Go | 2 | 1 | yes |
| GDScript (Godot) | 5 | 2 | yes |
| Docker / Shell | 3 | — | — |
| Kotlin, Java, Ruby, PHP, C/C++, Swift | 7 | — | yes |
| All languages (git/system/security) | 3 | — | yes |

## Customizing

**File-size limits** live in `scripts/regression_check.py` (soft 300 / hard 500 source lines, hard 600 test lines).

**Your own rules go in an overlay, never a fork.** A project using DevGate as a submodule adds rules in a project-root `.guardrails/` overlay; the gates merge it with the bundled baseline by rule id — new ids append, same-id entries replace in place (retune severity, fix a false positive) without ever forking the baseline:

```
<project>/
  .devgate/.guardrails/...   # shared baseline (upstream-owned, never edited)
  .guardrails/...            # THIS project's delta only
  .guardrailsignore          # per-project scan scoping
```

`semantic-scan.mjs` is exempt (its checks are hardcoded AST logic, not data). An explicit `--rules`/`--registry` path collapses to that single source with no merge.

## CI, runners, and agent skills

Five drop-in workflow templates live in `templates/github-workflows/` (guardrails compliance, secret validation, file size, smoke gate, scheduled drift scan) — each has a `SETUP` header and `CUSTOMIZE` placeholders. The runner standard (`templates/runner/`) puts the official `ghcr.io/actions/actions-runner` image on your own hardware as a Podman quadlet, one container per project, registration token via a never-committed `.env`. DevGate is host-repo aware: `detect-host-ci.py` reads your repo's own `runs-on:` labels so workflow templates bind to your declared infrastructure, not a hardcoded `ubuntu-latest`.

Six agent-behavior skill templates ship in `templates/skills/` — four-laws (safety), scope-validator, halt-conditions, three-strikes, commit-validator, production-first — each a single `SKILL.md` that drops into any agent runtime supporting the convention. Full agent directions: [AGENTS.md](AGENTS.md). Template usage guide: [templates/README.md](templates/README.md).

## The Spec Coherence Service — DevGate gates itself

This repository dogfoods its own idea: `hub/coherence/` is a Python service (stdlib-only, dual-runnable, container-isolated evaluators) that answers one question with a signed, replayable record — *did this change set actually satisfy the specs it claims to satisfy?*

The pieces that matter to a human:

- **Signed evaluation contexts** — a control-plane stand-in issues a context binding the policy, stage, baseline, and evaluation time; the run path verifies digests and countersignatures before believing anything.
- **A five-stage adoption ladder** — inventory → advisory → ratchet → enforced-core → enforced-full — monotonically narrowing which known debt stays advisory as a repository earns enforcement.
- **Anti-rollback** — a context binds the exact central policy bundle (digest + epoch floor); an older-but-signed bundle is rejected unless the control plane recorded a grandfather window for it, and the attempt is machine-parsable in fleet reporting.
- **A stable exit-code contract** — PASS 0, ADVISORY 10, FAIL 20, invalid input 30, policy refusal 31, execution error 32, seal failure 33 — plus deterministic replay of any historical decision.
- **`scripts/coherence-local`** — run the gate from your checkout through the *same* builder + driver invocations the CI template runs, with identity resolved from the same registry the pin checks. `--build-only` emits the request/launch without a container; `--dry-run` prints the commands. A test replays the template's own command and byte-compares the output, so "local == CI" is enforced, not asserted.

Status: mid **Sprint 6 of 8** (adoption ladder and fleet integration). Sprints 0–5 delivered the decision contract, container/evaluator boundary, and the attestation/evidence stack. The full spec, task ledger, and design record live in [openspec/changes/devgate-spec-coherence-service/](openspec/changes/devgate-spec-coherence-service/).

### What is verified, and where

Every row below names the mechanism that proves it, and every state below was
read off an actual hosted run of `main` — not asserted. An external audit
(2026-09-20) found this README claiming more than the tree delivered; a later
revision then over-corrected into an *unverified* "the runner has no podman, so
these rows do not run" — which was false the same way: assumed, not measured.
A hosted run builds the image on every push to main. Evidence is cited under
the table.

| Claim | Checked by | State |
| --- | --- | --- |
| Every spec validates under the strict delta grammar | `specs` job → `openspec validate --all --strict` | **GREEN** |
| Strict validation actually refuses malformed material | `specs` job → `scripts/specs-validate-negative-control.sh` | **GREEN**, and see the note under the table — this row was red on its first hosted run and is the reason the note exists. |
| The per-file runner discovers this repo's own tests | `tests` job → runner discovery count ≥ 1 | **GREEN** |
| Scanner project-root anchoring (no ancestor escape) | `tests` job → `tests/test_scanner_root_anchor.mjs` | **GREEN** |
| Evaluator image builds, reproducibly, carrying its frozen schemas | `container-image` job → `podman build` + in-image schema load | **GREEN on hosted CI.** `ubuntu-latest` ships podman. Two consecutive main runs built the identical digest and printed `schemas OK in image` inside the container. The build is content-addressed over `hub/` + the coherence schemas, so identical inputs give an identical digest. |
| Evaluator image matches its pinned identity registry | `container-image` job → digest comparison | **OPEN — runs and reports a mismatch.** The built digest and the value recorded in `container/execution-profiles.json` differ. The comparison executes on every push but `::notice`s rather than failing, because retiring the mismatch means publishing the rebuilt image (S4, registry-credential-gated). Reproducibility is no longer the open question; the **published** identity is — consumers pull by digest, and no full-container request/response smoke has run against the pinned image. |

The last row is deliberately not green. What the table used to get wrong, in
both directions, is worth keeping: it first implied the container path was
proven, then claimed it was never exercised, and *both* were guesses. It now
says the build runs and is reproducible on hosted CI, and reserves "not
verified" for the two things actually unverified — the published digest and the
full-container smoke. The item total is not quoted on purpose either: `--all`
counts discovered items, so any fixed number goes stale the moment a package is
added.

**The negative control's first hosted run failed, and that is the whole point of
having it.** The control (`scripts/specs-validate-negative-control.sh`) invokes
the validator and refuses to pass unless the rejection *names the fixture's
designed defect*. On its first execution on a clean runner it exited nonzero —
the CLI could not be resolved from inside the probe's temp directory, because
the control used a bare `npx openspec` that a globally-installed CLI had masked
on the author's machine. It failed closed, exactly as designed, on the author's
own over-claim — the same defect class the audit was written to catch, caught by
the audit's own instrument. The control now resolves the same pinned CLI
binary the hard gate above it does. Hosted provenance in general was a blind
spot: ci.yml triggers on `push: branches: [main]`, the remediation branch was
never pushed to main, and no PR was opened (own repo), so every "green" on that
branch was local-only until the merge ran it for real.

## Roadmap: the AIGGP packages (imported for evaluation — no merge commitment)

In September 2026 we imported eleven AIGGP ("Agent Intelligence Gate Loop Guardrails Platform") spec packages under [openspec/changes/aiggp-00…10](openspec/changes/) — a proposal to give DevGate, Agent Guardrails, and Mission Control one shared truth model: one verdict algebra, one evidence envelope, one policy-bundle format, one append-only ledger.

They are **imported, not adopted**. Nothing in them is implemented, and nothing has been reconciled with the coherence service that already ships (notably AIGGP-02, which overlaps the adoption ladder). **There is no commitment to merge DevGate into Agent Guardrails.** That decision is parked until the coherence service's open-spec work is further along and a feasibility pass proves the unification is worth doing — if the openspec work finishes first, the feasibility call happens after it. The source documents as received are kept for provenance in [openspec/aiggp-source/](openspec/aiggp-source/).

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
