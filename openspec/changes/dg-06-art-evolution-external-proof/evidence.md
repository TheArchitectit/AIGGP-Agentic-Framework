# DG-06 art evolution evidence

Snapshot: detached AIGGP worktree at `1070d3ed917c77773019d2c880d1c911769a2d6f`, 2026-11-25.

## Executable local checks and human obligations

| Area | Executable behavior and evidence | Human or external boundary |
| --- | --- | --- |
| Record a failure | [`scripts/log_failure.py`](../../../scripts/log_failure.py) appends a JSONL record to the project registry by default (`registry_path`, lines 75-81; entry construction, 84-103). The art guide directs the operator to use it and says the registry is append-only (`docs/ART-CONTRACT-EXTENSION.md`, lines 13-45). | A human must establish that an art failure actually reached a person, describe the class, and choose the prevention requirement. The generic writer does not collect consumer owner, target, or evidence URL fields. |
| Validate the registry | [`scripts/failure_registry_check.py`](../../../scripts/failure_registry_check.py), lines 62-68 and 221 onward, checks the generic required fields/status plus commit and path validity. | Its schema has no owner or consumer-evidence fields and cannot prove that a human observed/reviewed a class or that a title shipped it. |
| Enforce the art contract locally | [`scripts/art_creation_scan.py`](../../../scripts/art_creation_scan.py), lines 64-100 and 113 onward, orchestrates manifest-backed local checks and returns exit 3 (`NOT_APPLICABLE`) when a title declares no art pipeline. Declaration checks are in [`scripts/art_checks.py`](../../../scripts/art_checks.py), lines 53, 114, 161, and 270; outcome checks are in [`scripts/art_check_outcome.py`](../../../scripts/art_check_outcome.py), lines 19, 48, 120, and 167. | These checks validate a supplied title manifest and local declarations. They do not enforce the human process that grows the registry-driven contract, and a local fixture is not evidence from an external consumer. |
| Fidelity and build acceptance | `check_acceptance` has a required human verdict field; `check_draw` requires declared target-render evidence. The existing fixture suite exercises the local checks. | A manifest field or fixture is not owner attestation, a real renderer capture, or proof that a consumer's shipped target passed. |
| Evolve the contract | [`docs/ART-CONTRACT-EXTENSION.md`](../../../docs/ART-CONTRACT-EXTENSION.md), lines 47-85, tells a human to map the class to an existing requirement or draft a delta, add a code marker only above a real enforcing function, and leave a human-only obligation uncovered. | There is no executable enforcement site for `art-evolve-01`; `rg` over `scripts/` found no `art-evolve-01` source marker. The requirement is intentionally uncovered. |

The AIGGP repository has no root `art-creation.json`. Running
`python3 scripts/art_creation_scan.py --root /workspace` against this AIGGP
checkout printed `NOT_APPLICABLE` and exited 3. That is the expected zero-input
result; it is not a game-title or shipped-build result.

## Real registry event and local test evidence

The repository does contain an actual process-class record:
`.guardrails/failure-registry.jsonl:60`, `FAIL-d91fd88e`, records that the art
brief and checks were written after the failures they describe. Its prevention
rule names `art-evolve-01`, states that the obligation is on a human, and leaves
the requirement deliberately uncovered by code. Its `fix_commit`
`0779267e46ff6c6a62a63ca3c9ff998909b5f3cf` resolves in this worktree. That
commit adds `docs/ART-CONTRACT-EXTENSION.md` and the registry entries; it does
not add a runtime check for the human process.

The archived art-contract task record, `openspec/changes/archive/2026-11-20-add-art-creation-contract/tasks.md:266-288`, lists eight recorded art failure classes with prevention mappings. It identifies `FAIL-d91fd88e` as the human-process class and records the local art negative-control and registry validation commands. This supports the registry mapping and local gate history; it does not prove external-title behavior or provide a direct test of a human decision.

Read-only local verification on this worktree:

- `python3 scripts/test_art_creation_scan.py` — **PASS**, 60 fixtures plus 4 exit-contract checks. These fixtures exercise local art checks, not `art-evolve-01` or a consuming game.
- `python3 -m pytest -q tests/test_failure_registry_check.py tests/test_log_failure.py` — **PASS**, 25 tests. These test generic writer/validator behavior.
- `FAILURE_REGISTRY_PATH=.guardrails/failure-registry.jsonl python3 scripts/failure_registry_check.py` — **PASS**, exit 0, when the worktree's shared Git metadata was mounted so commit checks could resolve. An initial container invocation without the linked worktree metadata could not resolve two commits; the corrected local-metadata run passed.
- `python3 scripts/art_creation_scan.py --root /workspace` — **NOT_APPLICABLE**, exit 3, because this framework repository has no art pipeline manifest.
- Repository pre-work `python3 scripts/regression_check.py --all` — **NOT_RUN / incomplete**. It was stopped after more than six minutes with `git diff` still active against the Windows-mounted tree; no result is claimed.

## External consumer proof disposition

**Applicable requirement:** `art-evolve-01`, specifically a disposition whose
claim depends on a consuming title outside AIGGP.

**Status: NOT_RUN.** This checkout and its supplied task context identify no
consuming title/repository or responsible individual, and contain no
owner-supplied consumer commit, shipped target, or build/test result to review.
No consumer identity is inferred. The owner is **NOT IDENTIFIED**. The required
owner role is the **art/game owner for the actual consuming title**, to be
identified by an AIGGP maintainer after the consumer is named. Required proof
from that owner is the consumer-repository revision plus its shipped-target
build/test evidence and a direct reference connecting that result to the art
failure class and `art-evolve-01` disposition. Until those artifacts and the
owner are supplied, external behavior remains unverified.

The 2026-11-25 current audit routes `art-evolve-01` to “Art workflow and
consumer owners” and records no source marker (`openspec/audits/2026-11-25-aiggp-current-audit.md:117,198`). Its prior evidence review likewise says no external game-consumer proof was verified (`openspec/audits/2026-11-25-aiggp-open-closed-coded.md:423`). This record does not convert local docs or fixtures into external proof.
