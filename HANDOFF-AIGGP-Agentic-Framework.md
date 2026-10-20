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
> Current census (2026-10-20): **31 capability specs** — 3 CLOSED, 0 PARTIAL,
> 1 OPEN, 27 UNKNOWN; **25 archived changes**; **2 open changes**
> (`add-gitlab-forge-support`, `add-runner-toolchain-requests`).

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
| `openspec/specs/<capability>/spec.md` | 31 capability specs |
| `openspec/changes/<change>/` | 2 open changes |
| `openspec/changes/archive/` | 25 shipped changes |
| `scripts/` | gates (`check_*.py`, `guardrail*`) |
| `templates/github-workflows/` | consumer workflow templates incl. `text-integrity.yml` |
| `tests/` | gate self-tests; floors in `tests/expected-counts.json` |

## The thing to know about this repo's specs

**27 of 31 capability specs carry no closure evidence at all** — no `Status:`
line and no closure table. That is a documentation gap, not a signal the work is
unfinished. Only four state a status:

- `doc-truth` — Closed (2 of 2, 2026-10-14)
- `per-screen-tracking` — Closed (2 of 2, 2026-10-19)
- `zig-opengl-engine` — Implemented (4 of 4, 2026-10-14)
- `add-runner-to-fleet` — matched to its archived change

**Second structural gap:** the 31 spec directory names and the 25 archived
change names barely overlap (exactly one match). They are separate taxonomies,
so an archived change cannot generally be used to close a spec by name. Fixing
that means aligning the two naming schemes, not adding more status lines.

## Gates

```bash
python3 -m pytest tests/ -q
node scripts/guardrails-scan.mjs
python3 scripts/check_charset.py --repo .
python3 scripts/check_corruption.py --repo .
python3 scripts/check_manifest_join.py --repo .
python3 tests/gen_floors.py
openspec validate --all          # 33 passed / 0 failed at 2026-10-20
```

Never weaken a gate, skip a check, or allowlist a finding to reach green.
