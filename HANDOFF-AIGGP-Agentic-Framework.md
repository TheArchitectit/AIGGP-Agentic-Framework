# HANDOFF — AIGGP-Agentic-Framework (DevGate upstream)

> **Project:** `AIGGP-Agentic-Framework`  ·  **Default branch:** `main`
> **Scope:** DevGate upstream: the framework the fleet consumes as .devgate/
> **This file:** `HANDOFF-AIGGP-Agentic-Framework.md` — a `HANDOFF-<project>` file. If the project name in this
> filename does not match the work you are doing, you have the wrong handoff.
> **Spec index:** [`openspec/INDEX.md`](openspec/INDEX.md)

> **Spec status lives in the index: [`openspec/INDEX.md`](openspec/INDEX.md).**
> Generated from each spec's own `Status:` line, its closure-table census, or a
> matching archived change. It is the single answer to "which specs are closed
> and which are not". Do not keep a second list here.
>
> Current census (2026-11-13): **44 capability specs** — 43 CLOSED, 1 DEFERRED,
> 0 PARTIAL, 0 OPEN, 0 UNKNOWN; **38 archived changes**; **5 open changes**
> (`add-art-creation-contract`, `add-gitlab-forge-support`, `add-open-item-gates`,
> `add-spec-state-ledger`, `aiggp-08-stitcher-proof-parity`).

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
| `openspec/specs/<capability>/spec.md` | 44 capability specs |
| `openspec/changes/<change>/` | 5 open changes |
| `openspec/changes/archive/` | 38 shipped changes |
| `scripts/` | gates (`check_*.py`, `guardrail*`) |
| `templates/github-workflows/` | consumer workflow templates incl. `text-integrity.yml` |
| `tests/` | gate self-tests; floors in `tests/expected-counts.json` |

## The thing to know about this repo's specs

**Every one of the 44 capability specs now carries closure evidence** — a
`Status:` line, a closure table, or a matched archived change. As of 2026-11-13
that is 43 CLOSED and 1 DEFERRED. The exception is deliberate:

- `base-specs-01` is **DEFERRED by owner decision**, not open work: the
  capability lives in the consuming game repo and stays deferred until that repo
  builds it. Do not close it by relabelling the line.

**Second structural gap (still live):** the 44 spec directory names and the 38
archived change names have **zero** overlap. They are separate taxonomies, so an
archived change cannot be used to close a spec by name. Fixing that means
aligning the two naming schemes, not adding more status lines.

## Gates

```bash
python3 -m pytest tests/ -q
node scripts/guardrails-scan.mjs
python3 scripts/check_charset.py --repo .
python3 scripts/check_corruption.py --repo .
python3 scripts/check_manifest_join.py --repo .
python3 tests/gen_floors.py
openspec validate --all          # 49 passed / 0 failed at 2026-11-13
```

Never weaken a gate, skip a check, or allowlist a finding to reach green.
