# HANDOFF — AIGGP-Agentic-Framework (DevGate upstream)

> **Project:** `AIGGP-Agentic-Framework`  ·  **Default branch:** `main`
> **Scope:** DevGate upstream: the framework the fleet consumes as .devgate/
> **This file:** `HANDOFF-AIGGP-Agentic-Framework.md` — a `HANDOFF-<project>` file. If the project name in this
> filename does not match the work you are doing, you have the wrong handoff.
> **Spec index:** [`openspec/INDEX.md`](openspec/INDEX.md)

> Start with the [generated spec index](openspec/INDEX.md) for the current
> capability and package states. See the
> [future readiness audit](docs/AIGGP-FUTURE-READINESS.md) for dependencies,
> owners, and what this repository can support in a consumer deployment.
>
> **Continuing in the lab?** The [November 27 lab handoff](openspec/changes/qualify-consumer-delivery-evidence/lab-handoff.md)
> records the checkout commands, hosted consumer test plan, approval-verification gap and outstanding bank tasks.

For the separate DG-02 review, resume at **DG02-U-145**. The first 144 rows have individually recorded dispositions. All 182 baseline rows remain UNPROVEN. [Batch index and evidence](openspec/changes/dg-02-evidence-ledger-reconciliation/README.md).

## Identity

| Field | Value |
|---|---|
| Remote | `git@github.com:TheArchitectit/AIGGP-Agentic-Framework.git` |
| Default branch | `main` |
| Note | `DevGate-Agentic-Framework` is the **same repo** (old name); the submodule URL `DevGate-Agentic-Framework.git` resolves here |

## What this repo is

The upstream DevGate framework — the source the fleet consumes as `.devgate/`.
Gates, templates, runner standard, runner-monitor hub, and the coherence
evaluation service all originate here.

## Where things live

| Path | Purpose |
|---|---|
| `openspec/INDEX.md` | **generated** spec census — start here |
| `openspec/specs/<capability>/spec.md` | Published capability specs |
| `openspec/changes/<change>/` | Active change packages and their tasks |
| `openspec/changes/archive/` | Archived packages and dated disposition evidence |
| `scripts/` | gates (`check_*.py`, `guardrail*`) |
| `templates/github-workflows/` | consumer workflow templates incl. `text-integrity.yml` |
| `tests/` | gate self-tests; floors in `tests/expected-counts.json` |

## Reading OpenSpec status

Use the generated index and state ledger at the revision under review. An
archived package describes its disposition. Where ledger proof is required,
a capability remains `UNPROVEN` until the proving evidence is accepted.
Active change deltas describe proposed behavior. Use the referenced acceptance
records before presenting that behavior as available to consumers.

## Gates

```bash
python3 -m pytest tests/ -q
node scripts/guardrails-scan.mjs
python3 scripts/check_charset.py --repo .
python3 scripts/check_corruption.py --repo .
python3 scripts/check_manifest_join.py --repo .
python3 tests/gen_floors.py
openspec validate --all --strict
```

Never weaken a gate, skip a check, or allowlist a finding to reach green.
