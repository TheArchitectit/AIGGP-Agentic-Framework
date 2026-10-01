# R9 provenance capture — real-repo pilot facts

**Status:** CAPTURED 2026-09-28. Owner approval for read-only inspection of the
two private pilot repos was granted before capture (see `acceptance.md`).
**Scope:** read-only inspection. No file in either pilot repository was written,
and no branch, gate, or protection was changed. Both remain PRIVATE.

This record exists because R9 (`review.md:93-95`) found the pilot narrative was
*motivation, not verified evidence*: "Do not manufacture game lineage, owners,
ages, or finding identities. Record pilot commit SHA, source report digest,
capture time, and source locations before calling a fixture derived from
verified facts."

Per ADR-019, a fixture may only be relabeled non-synthetic when **all four**
record fields are present. What this capture establishes — and what it does
not — is stated per-subject below.

## Subject 1 — LobsterWars (the 13-violation baseline)

**This subject's record is COMPLETE.** All four ADR-019 fields are captured.

| Field | Value |
|---|---|
| Source repository | `TheArchitectit/LobsterWars` (private) |
| Source commit SHA | `f5b48a30a7113217742f0754ffe1cc6357ac9416` (branch `master`) |
| Commit subject | `fix(ci): add npm ci for semantic scan, make pattern scan advisory` |
| Commit date | 2026-09-17T04:56:26Z |
| Capture time | 2026-09-28T09:45:37Z (run `createdAt`) |
| Source location | GitHub Actions run `36405534067`, job "Full-tree drift scan", step "Run gate suite", workflow `drift-scan.yml`, event `schedule` |
| Run URL | https://github.com/TheArchitectit/LobsterWars/actions/runs/36405534067 |
| Report digest | `sha256:8c19f2f1a2482f6852c562939b00e1fb81e8aa25c886601a1e8a300c9dba558f` |

**Digest derivation** (so it is reproducible, not asserted): the 13 violation
records are reconstructed from the run log **in the order the gate emitted
them** — the order matters and is therefore pinned here, since sorting changes
the hash — canonicalized as `severity\trule\tlocation\tmessage` per line, joined
with `\n`, and SHA-256'd. The 16 advisory warnings are excluded: the baseline
the ratchet demo operates on is the violation set, and mixing severities would
make the digest change when only an advisory moved.

The table below is listed in that emitted order for exactly this reason. To
recompute: `gh run view 36405534067 --repo TheArchitectit/LobsterWars
--log-failed`, keep lines matching `[GUARDRAILS][error|critical]`, and hash the
four canonical fields in the order they appear.

**The count of 13 is confirmed as a real count, not a narrative.** The gate
itself printed `GUARDRAILS: 13 violation(s) found.`; independent reconstruction
from the log yields exactly 13, splitting 12 × `PREVENT-011` (error, "Usage of
'any' type defeats TypeScript's type safety") + 1 × `PREVENT-029` (critical,
"Core modules should not make network calls at runtime"). The 16 `PREVENT-012`
warnings are separate and non-blocking.

The 13, by location — this is the named-debt baseline the Stage 2 ratchet demo
(criterion 8) and the real-fixture half (criterion 10) need. **Criterion 8 has
since consumed this shape**: `scripts/ratchet_demo.py` (2026-09-28) drives the
real service at stage 2 over it and demonstrates both ladder obligations
(in-window ADVISORY, aged-out BLOCK, new location BLOCK). Note the shape is
what it consumes — the run is synthetic, so nothing in this record is
discharged by it, and the table below remains the provenance for a real run
when a spoke executes one.

| # | Severity | Rule | Location |
|---|---|---|---|
| 1 | error | PREVENT-011 | `server/GameRoom.ts:93` |
| 2 | error | PREVENT-011 | `server/GameRoom.ts:108` |
| 3 | error | PREVENT-011 | `server/index.ts:75` |
| 4 | error | PREVENT-011 | `src/audio/AudioManager.ts:64` |
| 5 | error | PREVENT-011 | `src/game/scenes/BootScene.ts:914` |
| 6 | error | PREVENT-011 | `src/game/scenes/BootScene.ts:915` |
| 7 | error | PREVENT-011 | `src/game/systems/ProjectileSystem.ts:283` |
| 8 | error | PREVENT-011 | `src/game/systems/UISystem.ts:65` |
| 9 | error | PREVENT-011 | `src/game/systems/UISystem.ts:66` |
| 10 | critical | PREVENT-029 | `src/network/NetworkManager.ts:40` |
| 11 | error | PREVENT-011 | `src/systems/ReplayRecorder.ts:24` |
| 12 | error | PREVENT-011 | `src/systems/ReplayTypes.ts:17` |
| 13 | error | PREVENT-011 | `src/systems/TheaterSystem.ts:27` |

**Stability check.** Ten consecutive scheduled runs (2026-09-18 → 2026-09-27)
all failed on this same SHA and reported the same total, so the baseline is
stable across days rather than a one-off snapshot. The run captured here
(2026-09-28) is the most recent.

## Subject 2 — gamerepo01 (the lineage-mismatch narrative)

**This subject's record is INCOMPLETE, and the capture found why: there is no
declared product identity to mismatch.**

| Field | Value |
|---|---|
| Source repository | `TheArchitectit/gamerepo01` (private) |
| Source commit SHA | `886b0bcfc5f9cd8c5aec445eb103e66aff16f236` (branch `main`) |
| Commit subject | `docs(specs): pre-execution audit of spec packet + 300-rule change` |
| Commit date | 2026-09-16T21:19:10Z |
| Repository created | 2025-12-02T12:45:09Z |
| Capture time | 2026-09-28 |
| Source location | repository metadata + root tree listing via the GitHub contents API |
| Report digest | **not applicable — see below** |

The submitted narrative describes a *lineage mismatch*: a product whose declared
identity disagrees with its historical lineage. Capturing the subject shows the
premise does not hold in the form the narrative assumes: **`gamerepo01` carries
no `.guardrails/` directory at all**, so it declares no product identity for a
lineage to mismatch against. (Probed `.guardrails/`, `.guardrails/scope.json`,
`.guardrails/product.json`, `.guardrails/identity.json` — all 404.)

This is consistent with the owner's Q9 decision (2026-09-26): the fixture starts
synthetic because the *declared* identity is normative while historical lineage
is merely informative. It also means criterion 10's real-fixture half for this
subject is blocked on the subject, not on the harness: a real-repo
lineage-mismatch fixture needs a repo that has declared an identity, and this
one has not. **No gamerepo01-derived fixture may be relabeled non-synthetic.**

There is also no report digest to record for this subject, because no gate
report making the lineage claim was produced — the narrative was supplied
context. Recording a digest for a report that does not exist would be the
precise failure R9 names.

## What this capture changes

- **LobsterWars:** the 13-violation baseline may now be labeled a captured
  production baseline rather than a synthetic model. Criteria 8 and 10 have
  their real subject available.
- **gamerepo01:** the fixture stays synthetic. The reason is now measured (no
  declared identity exists) rather than a default.
- **Criteria 9's fleet half** is unaffected by this record — it needs a hosted
  coherence run on an enrolled spoke, which is a separate act.

## What this capture explicitly did NOT do

- Did not write to either pilot repository.
- Did not change any gate, branch protection, or fleet enforcement.
- Did not infer owners, ages, or finding identities beyond what the run log and
  the repository metadata state.
- Did not treat the gamerepo01 narrative as verified fact; it was contradicted
  by the repository's actual contents, which is itself the finding.
