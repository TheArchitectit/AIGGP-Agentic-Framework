# AIGGP draft retirement — kernel-hardening packages (2026-10-02)

> **Disposition update 2026-10-03:** the surviving packages listed below as
> "kept" (aiggp-01/02/03/04/05/06/08/10) are no longer in this tree — all
> open spec packages moved to `TheArchitectit/repo-brainstorming`
> (`devgate-open-changes/`), owner directive. Full accounting:
> `AIGGP-DISPOSITION-2026-10-03.md`. This record below stays as written for
> the 2026-10-02 retirement itself.

**Status: decision record.** Owner decisions from the 2026-10-01/02 architect
review, with the measurements that support them.

## What was decided

1. **The AIGGP name stays.** AIGGP is a portmanteau — the goal was always to
   pull the *agent guardrails* system into *DevGate*, one platform. The repo
   name (`TheArchitectit/AIGGP-Agentic-Framework`) and README title are correct;
   what was wrong is the drafts' description of the relationship.
2. **Retired: `aiggp-00-kernel-truth-model` and
   `aiggp-09-runner-monitoring-enrollment`.** These are the kernel-level
   hardening proposals — signed evidence envelopes, org CA, append-only ledger,
   waiver algebra, conformance kit (00); runner enrollment, fleet identity,
   CA-trust, heartbeats (09). Owner rule for the cut: *"anything that is AI
   guardrails is good, like the prompt injection etc."* Neither package is an
   AI guardrail; both are security-platform infrastructure.
3. **Kept: aiggp-01 … aiggp-06, aiggp-08** (audit hardening, fleet spec
   coherence, prompt-injection defense, semantic content filtering, runtime
   sandbox isolation, indirect-injection provenance, stitcher / proof
   parity) — all AI-guardrail or gate-correctness packages.
   **aiggp-07 (GitLab forge) was kept by this rule but then split out**
   (owner, 2026-10-02: *"split that into a different spec"*): salvaged as
   the DevGate-native change package
   `openspec/changes/add-gitlab-forge-support/` (GLF- IDs, written against
   the shipped templates/scripts/hub surface), and the draft directory
   retired. Its two owner decisions (Q11.1 per-instance ownership, Q11.2
   self-hosted axes) carry into the new package's `design.md` locked
   decisions 6–7 unchanged in substance; the verbatim ANSWERED records stay
   in `openspec/aiggp-source/aiggp-07-…-b68fd3cf.txt`.
4. **Rewritten: aiggp-10 direction.** The guardrails system is pulled INTO
   DevGate (the repo already carries the AIGGP name). ADR-001's "Agent
   Guardrails repository is the host" is superseded — see
   `aiggp-10-repository-unification-migration/alignment-review.md`.

## Why the retirement is evidence-backed, not preference

Measured 2026-10-01/02 (three-way review: drafts / guardrails platform repos /
DevGate tree):

- **Neither real system knows the kernel exists.** GitHub code search across
  `guardrail-mcp`, `guardrails-control-plane`, `guardrail-policy-packs`,
  `agent-guardrails-template`, `missioncontrol`: **0 references** to evidence
  envelope, append-only ledger, verdict algebra, or conformance kit. The
  drafts' premise — "DevGate, Agent Guardrails, and Mission Control converge
  under one kernel" — describes a convergence no product has started.
- **DevGate already ships the useful half, differently.** Sealed evidence
  bundles (`hub/coherence/evidence.py`, validated by `scripts/evidence-validate.py`),
  HMAC attestation (`hub/coherence/attest.py` — deliberately symmetric; no PKI,
  no CA), scoped exceptions with expiry (`hub/coherence/adoption.py`),
  anti-rollback policy digests (`hub/coherence/issue.py`, `coh-pol-*`). The
  kernel package would replace shipped, mutation-proved machinery with
  unimplemented ceremony.
- **The drafts never referenced the shipped surface they claimed to extend.**
  Across all 11 packages: 0 references to `hub/coherence`, 0 to
  `regression_check`, 0 to mutation batteries, 0 to `expected-counts.json`.
  They were authored 2026-09-19 as flattened LLM drafts (import commit
  `ec0c9e1`) against an imagined platform, then this session's walk-through
  (Q1–Q14) answered their open questions as if they were real.
- **Provenance is preserved.** The as-received sources remain frozen in
  `openspec/aiggp-source/aiggp-00-…-2af511f3.txt` and
  `openspec/aiggp-source/aiggp-09-…-af1e5d62.txt`. Nothing is lost; the
  packages are retired, not erased.

## Consequences for the kept packages (dangling-reference bridge)

The kept packages cite "the AIGGP-00 envelope" ~42 times. Those citations are
re-anchored, package by package, to **DevGate's shipped evidence format**:

- "AIGGP-00 envelope" → "DevGate sealed evidence bundle
  (`hub/coherence/evidence.py`; validated by `scripts/evidence-validate.py`)"
- "signed with kernel keys / CA" → "attested with DevGate's HMAC attestation
  (`hub/coherence/attest.py`; signer identity from
  `DEVGATE_SIGNER_IDENTITY`/`DEVGATE_SIGNER_KEY_ID`)"
- "lands in the append-only ledger" → "recorded in the run ledger produced by
  the coherence service" (per-run ledger is what ships; an append-only
  cross-run ledger is NOT claimed)
- "waiver" → "scoped exception (`hub/coherence/adoption.py`: specific
  assertion_id + subject_ref, expiry evaluated against context time)"
- aiggp-05's citations of aiggp-09 enrollment → DevGate's shipped runner
  enrollment (`scripts/runner-enroll.sh`, `hub/schema/runners.schema.json`)
- aiggp-07's "aiggp-00 CA-optional enrollment model" → DevGate runner
  enrollment as shipped; the CA-optional principle survives as a stated
  assumption (SA-9) without the kernel package.

## Stated assumptions added by this retirement

- **SA-9 (replaces the kernel's trust model):** trust for evidence is
  DevGate's shipped HMAC attestation. Asymmetric signing, CAs, and enrollment
  certificates are out of scope until a concrete AI-guardrail requirement
  demands them. CA-optional remains the standing owner principle if that day
  comes ("ca's should be client choosen as optional also" — 2026-10-01).
- **SA-10 (replaces the ledger requirement):** the unit of durable truth is
  the sealed evidence bundle plus the coherence run ledger. An append-only
  cross-run ledger is not required by any kept package.
- **SA-11 (aiggp-10 direction):** repository unification means the agent
  guardrails system moving INTO the DevGate/AIGGP repo — the reverse of
  ADR-001 as drafted. `guardrails-control-plane`'s submodule composition is
  the current integration mechanism and stays valid until AIGGP-10 executes.

## What was NOT retired and why it survived this review

- aiggp-01: gate-correctness (no vacuous gates, nonzero test floors) — the
  audit it describes was executed against this repo; its requirements match
  shipped CI behavior.
- aiggp-02: overlaps the shipped coherence service but as a *spec of record*
  for the fleet ladder; reconciliation note kept in-package.
- aiggp-03/06: prompt-injection defense and provenance — core AI guardrails;
  map to `agent-guardrails-template`'s Four Laws / guardrail-gaps-2026 specs.
- aiggp-04: content filtering — an AI guardrail (what agents may emit), not
  org DLP; its PII/financial categories stay bundle-declared and optional.
- aiggp-05: sandbox isolation — runtime containment for coding agents is an
  AI guardrail; only its enrollment citations were bridged.
- aiggp-07: GitLab forge — additive CI coverage; the seven-template count was
  corrected this session.
- aiggp-08: evidence stitching / proof parity — maps to shipped
  evidence-validate + attestation.
- aiggp-10: unification — kept with direction fixed, because pulling the
  guardrails system in IS the AIGGP goal.