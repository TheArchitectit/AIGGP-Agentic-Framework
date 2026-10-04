# DevGate — AI-assisted development quality gates

[![Sponsor](https://img.shields.io/badge/Sponsor-TheArchitectit-FF69B4?style=flat&logo=github-sponsors)](https://github.com/sponsors/TheArchitectit)

DevGate is a language-agnostic quality gate for AI-assisted development. It
ships test isolation, regression scanning, deploy gates, scheduled drift scans,
CI workflow templates, a self-hosted runner standard, agent-behavior skills,
and runner-fleet monitoring.

**AIGGP (Agent Intelligence Gate Loop Guardrails Platform) is a proposed
unification direction, not the product currently shipped by this repository.**
The distinction is intentional: the gates and evidence described below are
DevGate capabilities; the cross-product guardrails unification and OAP
integration remain proposals with separate prerequisites.

DevGate does not rearrange your code. It imposes no directory layout, language,
package manager, or test framework. It looks at what you have and gates it.

## What ships today

DevGate catches fast problems—SQL injection, unhandled promises, committed
credentials, unvalidated input, and other known patterns—and slow problems such
as dependency rot, base-image drift, and unnoticed CI changes.

The important behavior is evidence honesty:

- A scan that evaluated nothing reports `NOTHING SCANNED`; it does not print
  `clean`.
- A test run that discovers zero files does not exit 0.
- A gate that cannot run reports that it could not run.
- A green test command is not a claim that the tests are meaningful. Behavioral
  and contract evidence are stronger than presence checks.

DevGate ships bounded gate results, sealed/secret-redacted evidence, scoped
exceptions, and coherence-run records. These are DevGate artifacts and are not
an organization-wide security kernel, an OAP authorization, or a full
cross-product platform.

## Quick start

```bash
# As a submodule (recommended — stays in sync with upstream)
git submodule add https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git .devgate

# Or clone directly
git clone https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git .devgate
```

### What you get

```
.devgate/
├── .guardrails/
│   ├── failure-registry.jsonl          # Append-only bug history
│   ├── pre-work-check.md               # Mandatory pre-work checklist
│   ├── silent-success-allowlist.json   # Simulated-success markers
│   └── prevention-rules/               # Pattern, AST, and silent-success rules
├── scripts/                            # The gates (see Components below)
├── hub/                                # Runner monitor + spec coherence service
├── container/                          # Pinned evaluator image and profiles
├── templates/                          # CI, runner, monitor, and agent skills
├── openspec/                           # Capability specs and change packages
├── tests/                              # Behavioral test suite
├── docs/                               # Onboarding, release, audit, and runbooks
├── .github/workflows/                  # DevGate's own CI
├── AGENTS.md                           # Directions for AI agents
├── LICENSE                             # BSD 3-Clause
└── README.md                           # This file
```

`openspec/specs/` is the normative contract each gate implements. `scripts/`
holds the gates listed under [Components](#components), and `hub/` holds the
runner-monitor and coherence services.

### Run the gates

Scripts auto-detect the project root (the parent of `.devgate/`) and scan source
files regardless of language or directory structure.

```bash
node .devgate/scripts/guardrails-scan.mjs         # pattern scan, all source types
node .devgate/scripts/semantic-scan.mjs           # AST scan (TS/JS; skips if none)
node .devgate/scripts/run-tests.mjs               # isolated per-file test runner
python3 .devgate/scripts/regression_check.py --staged --pre-commit   # regression + file size
bash .devgate/scripts/deploy.sh 1.0.0             # gated publish (npm/cargo/pip/go)
```

`--staged` sees only uncommitted work. On a clean checkout it prints
`NOTHING SCANNED` rather than a fake pass; add `--fail-if-empty` in CI to make
that exit 2. `--all` is a scheduled drift sweep; use `--base origin/main` for a
pull-request-style range.

## Components

| Gate or service | What it does |
|---|---|
| `guardrails-scan.mjs` | Regex rules across ten-plus languages, with reason-required inline exceptions. |
| `semantic-scan.mjs` | TypeScript-compiler AST checks; fails closed when JS/TS exists but the parser is unavailable. |
| `regression_check.py` | Changed-file failure-registry checks, file-size limits, package audit, and blocking soft violations. |
| `run-tests.mjs` | Per-file process isolation, up to eight workers, serial lanes, flake adjudication, and hang-on-exit detection. |
| `deploy.sh` | Gated build, test, lint, and publish for npm, cargo, pip, or Go projects. |
| `schema-health-check.mjs` | Adapter-based SQLite, PostgreSQL, and MySQL schema validation; skips when unconfigured. |
| `findings_to_spec.py` | Converts registry entries and live findings into OpenSpec requirement skeletons. |
| `hub/` | Shipped runner-fleet monitoring and spec-coherence services. |

### Rules and test evidence

Rules are data, not code: pattern rules, silent-success rules, and an AST-rule
catalog are checked by `scripts/rules_check.py`. Two AST checks ship with
checkers (Promise `.catch` and React `useEffect` dependencies); catalog entries
without checkers are advisory and disabled.

Most pattern rules cover TypeScript/JSX/TSX/Svelte, Python, Go, Rust,
GDScript, Kotlin, Java, Ruby, PHP, YAML/CI configuration, Dockerfiles, and
shell. Agent-behavior rules live in skills because a file scanner cannot enforce
them.

The isolated runner discovers `.test.js` / `.spec.js` files for `node --test`
and `test_*.py` / `*_test.py` files for `pytest`.

```bash
DEVGATE_TEST_TIMEOUT=120000    # per-file hard cap in ms
DEVGATE_TEST_POOL=8            # parallel worker count
DEVGATE_TEST_HANG_MS=10000     # silence threshold before force-kill
```

Grade evidence accurately:

- **Behavioral:** calls the real code path and asserts the outcome.
- **Contract:** parses or validates the real produced artifact.
- **Presence:** checks a substring or file exists; this detects deletion, not
  breakage, and must not be reported as strong testing.

### Regression scanner

`scripts/regression_check.py` cross-references changed files with the append-only
failure registry, enforces source/test size limits, audits packages, and supports
`--base REF` and `--all`. A zero-file scope prints `NOTHING SCANNED`; it never
uses an empty scope as evidence of a clean result.

### Pattern and semantic scanners

`guardrails-scan.mjs` walks detected source files and supports
`guardrails-allow RULE-ID: <reason>` and file-scope
`//! guardrails-allow-file RULE-ID: <reason>` annotations. Reasons are required.

`semantic-scan.mjs` implements `SEMANTIC-001` (Promise `.then()` chains without
`.catch()`). If TypeScript/JavaScript exists and the parser is unavailable, it
fails with the install command. A project that knowingly cannot provide the
parser may set `DEVGATE_SEMANTIC_REQUIRED=0`; that is reported as `SKIPPED`, not
green.

### Deploy pipeline

| If found | Commands used |
|---|---|
| `package.json` | `npm run build`, `npm test`, `npm run lint`, `npm publish` |
| `Cargo.toml` | `cargo build --release`, `cargo test`, `cargo clippy`, `cargo publish` |
| `pyproject.toml` / `setup.py` | `pytest`, `twine upload` |
| `go.mod` | `go build`, `go test` |
| `project.godot` | Skips build; run Godot headless tests manually. |
| None of the above | Skips build/test; tag is pushed and publishing remains manual. |

### Schema health

Create `<project>/.guardrails/schema-health.json`; never edit files inside
`.devgate/`:

```json
{
  "adapter": "postgres",
  "expected_columns": [
    ["users", "id", "TEXT NOT NULL PRIMARY KEY"],
    ["users", "email", "TEXT NOT NULL UNIQUE"]
  ]
}
```

A half-configured gate fails loudly. `--db <path>` or `DEVGATE_DB_PATH` supplies
the connection string.

### Failure registry and findings-to-spec loop

`.guardrails/failure-registry.jsonl` records affected files, root cause,
prevention rule, and status. When a file changes, the regression scanner checks
it against active failures.

```bash
python3 .devgate/scripts/findings_to_spec.py --list        # dry run
python3 .devgate/scripts/findings_to_spec.py               # group by category
node .devgate/scripts/guardrails-scan.mjs 2>&1 \
  | python3 .devgate/scripts/findings_to_spec.py --stdin   # fold live findings in
```

`spec_traceability.py` discovers requirements in both
`openspec/specs/<capability>/spec.md` and active change-package specs. The loop
is: `log_failure.py` records a bug → `findings_to_spec.py` turns it into a
requirement → a `// spec: <id>` marker ties the fix back to that requirement.

## Runner fleet monitoring (`hub/`)

The stdlib-only hub watches a self-hosted runner fleet from one machine. Spokes
enroll with one-time tokens and heartbeat with per-runner revocable tokens;
only salted hashes are stored at rest. The hub polls the GitHub API for runner
online state, queue-drain age, watched-branch check conclusions, and drift-scan
recency, combining those with heartbeats as independent evidence channels.

Alerts are deduplicated by `(repo, check-class, runner)`: one GitHub issue per
key, recurrence as a comment, and every event appended to an append-only JSONL
log. `scripts/hub-watchdog.sh` fails its systemd unit when the hub dies—the hub
cannot report its own death. The service binds loopback by default; read
[docs/runner-monitor-monitor-hub.md](docs/runner-monitor-monitor-hub.md) for
TLS, firewall, and exposure notes.

The runner standard in `templates/runner/` installs the official
`ghcr.io/actions/actions-runner` image on your hardware as a Podman quadlet.
`runner-enroll.sh`, `runner-heartbeat.sh`, and `runner-image-cycle.sh` manage
enrollment, health reporting, and pinned evaluator-image convergence.

## Spec coherence service (`hub/coherence/` + `container/`)

The coherence service evaluates whether a repository meets its OpenSpec
specifications. An OpenSpec package, policy bundle, and signed evaluation
context produce a canonical result with the frozen exit-code matrix (0 PASS,
10 ADVISORY, 20 FAIL, 30–40 ERROR classes) plus sealed, secret-redacted
evidence. `python -m hub.coherence --request` runs the evaluator; `--launch-config`
runs it inside a digest-pinned, read-only, non-root, network-none Podman
container whose isolation is derived host-side.

The service and its decision/evidence stack are shipped DevGate components.
Adoption-ladder and fleet-integration work remains in progress; do not read the
service as an organization-security kernel or as OAP authority. See the
published [OpenSpec specs](openspec/specs/) for the normative contract and the
[archived design record](openspec/changes/archive/2026-10-01-devgate-spec-coherence-service/)
for the delivery history.

`scripts/coherence-local` runs the gate from a checkout through the same builder
and driver invocations used by the CI template. `--build-only` emits the request
and launch without a container; `--dry-run` prints the commands. The template's
command is replayed and byte-compared so local and CI paths are checked rather
than merely asserted to match.

## Configuration and project overlays

All source file types are checked. The defaults in `scripts/regression_check.py`
are:

```python
SRC_SOFT = 300    # warning
SRC_HARD = 500    # blocks commit
TEST_HARD = 600   # test-file hard limit
```

A consuming project adds its own rules in a project-root `.guardrails/` overlay;
it never edits or copies the bundled baseline:

```
<project>/
├── .devgate/.guardrails/       # shared baseline; upstream-owned
├── .guardrails/                # this project's delta only
└── .guardrailsignore            # per-project scan scoping
```

Overlay rules merge by rule ID. Agent-behavior rules belong in skills, including
the Git safety, secrets, scope, and halt-condition rules listed in
`templates/skills/`.

## CI, runner templates, and agent skills

Seven workflow templates ship in `templates/github-workflows/`: guardrails
compliance, secret validation, file size, smoke gate, scheduled drift scan,
spec coherence, and specs validation. Each has a `SETUP` header and
`CUSTOMIZE` placeholders. `detect-host-ci.py` reads the host repository's
`runs-on:` labels instead of assuming `ubuntu-latest`.

DevGate runs its secret-scanning template on itself and reports findings by rule,
path, line, and commit—never by value. See
[.github/workflows/ci.yml](.github/workflows/ci.yml) for the reference CI and
its full test, scanner, traceability, and container-image jobs.

Five skills ship in `templates/skills/`: four-laws, scope-validator,
halt-conditions, production-first, and commit-validator. Agent directions are
in [AGENTS.md](AGENTS.md); template usage is in
[templates/README.md](templates/README.md).

## Verification records

The following references are records of checks at their cited hosted revision;
they are not claims that every proposed integration is deployed.

| Claim | Checked by | State |
|---|---|---|
| Specs validate under the strict delta grammar | `specs` job → `openspec validate --all --strict` | **GREEN** |
| Strict validation refuses malformed material | `specs` job → `scripts/specs-validate-negative-control.sh` | **GREEN** |
| The per-file runner discovers this repository's tests | `tests` job → discovered count ≥ 1 | **GREEN** |
| Scanners resolve the project root without escaping to an ancestor | `tests` job → `tests/test_scanner_root_anchor.mjs` | **GREEN** |
| A pushed commit cannot carry a credential into `main` | `secrets` job → `scripts/secret-scan.sh` | **GREEN** — [run 36048653103](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36048653103) |
| The evaluator image builds reproducibly with frozen schemas | `container-image` job → `podman build` and schema load | **GREEN** |
| The recorded identity is fetchable by consumers | `container-image` job → anonymous pull by recorded digest | **GREEN** — [run 36055148205](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/36055148205) |

## Proposed integrations and roadmap

### AIGGP unification — proposed, not shipped

AIGGP names a future direction: bring a separate agent-guardrails system into
DevGate so the projects can be evaluated together. The unification plan and
other open packages live in the private staging repository
[`TheArchitectit/repo-brainstorming`](https://github.com/TheArchitectit/repo-brainstorming)
under `devgate-open-changes/`. The stated plan is a non-squashed subtree merge
under `modules/guardrails/`, with the predecessor archived only after continuity
is proven.

The imported draft packages remain frozen for provenance in
[openspec/aiggp-source/](openspec/aiggp-source/). No AIGGP draft package is
implemented, and no DevGate gate or traceability ID wires those drafts into
shipped behavior. `guardrails-control-plane` is an integration design that
composes pinned components; it is not a shipped full platform.

The retired drafts `aiggp-00` (kernel truth model: signed envelopes, org CA,
append-only ledger, and waivers) and `aiggp-09` (runner enrollment/fleet
identity) described capabilities no product implements. DevGate's shipped
evidence bundles, HMAC attestation, scoped exceptions, and coherence-run ledger
are not those proposed organization-security-kernel capabilities. See the
[retirement record](openspec/changes/AIGGP-RETIREMENT-2026-10-02.md) and
[disposition record](openspec/changes/AIGGP-DISPOSITION-2026-10-03.md).

### OAP evidence integration — proposed and observe-only

The OAP evidence consumer is a proposed change, not a deployed OAP integration
or effect-authority path. The current hardening package states that its
remediation is specification-only: no OAP grant, identity issuer, effect engine,
new network service, or production enablement is shipped. A valid DevGate
receipt would be evidence; OAP would independently own action authorization.

Mandatory enablement remains blocked until the real producer → serialized
artifact → parser → cryptographic verifier → independent trust store → receiver
path is proven with malicious cases and approved by independent security and OAP
owners for one exact operation. Observe-only fixtures or a unit-level signature
pass are not OAP integration.

## License

BSD 3-Clause

## Author

TheArchitectit

---

## ☕ Support This Project

If this project helps you, consider [sponsoring on GitHub](https://github.com/sponsors/TheArchitectit). Every donation goes straight back into the work — GPU hardware and cloud compute for AI development, API credits for the agents that build and test these projects, and keeping everything free and open source. As a solo architect shipping on nights and weekends, even a small monthly sponsor makes a real difference.

Help keep this project going — use a referral link below and both of us get credits!

| Service | Your Bonus | Details | Referral Code |
| --------- | ----------- | ----------- | ----------- |
| [**Neuralwatt**](https://portal.neuralwatt.com/auth/register?ref=NW-ROGER-ET3Y) | $5 in credits | Refer a friend — when they use $25 in compute, you both earn $5 in credits | `NW-ROGER-ET3Y` |
| [**Synthetic**](https://synthetic.new/?referral=UAWqkKQQLFkzMkY) | $10 in credits | Subscribe → both get $10 credit | `UAWqkKQQLFkzMkY` |
| [**Ozore**](https://ozore.com/?ref=cwe4kdx0) | 50% off first month | AI-ready cloud — code **lundrog50** | `lundrog50` |

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-TheArchitectit-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/TheArchitectit)
