# Stated assumptions — global index (SA-1 … SA-11)

**Status: index, not a decision record.** Numbering is global across the
aiggp walk-through (2026-10-01) and the kernel retirement (2026-10-02). Each
SA's full text lives in the package named below; this file exists so a reader
can find them all in one pass. New assumptions continue the sequence — do not
renumber.

An SA is a judgment call recorded per the acceptance-evidence rule ("Ask the
owner only when 100% blocked; record every other judgment call in the repo's
adoption evidence as a stated assumption"). Overturning one is an owner
decision recorded at the assumption's home location, then reflected here.

| SA | Package / location | Assumption (one line) |
|---|---|---|
| SA-1 | `aiggp-02-fleet-spec-coherence/reconciliation.md` | AIGGP-02's three novel items stay `## ADDED` deltas with no ID markers; dispositions "not built — program not started". |
| SA-2 | `aiggp-02-fleet-spec-coherence/reconciliation.md` | The coherence-service archive publishes `coh-*` IDs; it does **not** imply the AIGGP program has started. |
| SA-3 | `aiggp-02-fleet-spec-coherence/reconciliation.md` | Even though `## MODIFIED` deltas are now name-resolvable, AIGGP-02 keeps "no `## MODIFIED` deltas" for this iteration. |
| SA-4 | `AIGGP-RETIREMENT-2026-10-02.md` (home moved; was `aiggp-00` Q1, package retired) | Per-install key rotation is local; CA rotation (deployments that run a CA) does not retroactively invalidate evidence. CA-less deployments have no CA rotation story. Now subordinate to SA-9. |
| SA-5 | `aiggp-03-prompt-injection-defense/acceptance.md` (Q6.1) | v1 heuristics have no runtime cost budget beyond "fast"; the model second-opinion budget is per-deployment in `policy-bundles/[bundle].toml`. |
| SA-6 | `aiggp-04-semantic-content-filtering/acceptance.md` (Q7) | Local classification is microseconds; the hosted-classifier budget is per-deployment in `policy-bundles/[bundle].toml`, never a default. |
| SA-7 | `aiggp-04-semantic-content-filtering/acceptance.md` (Q8) | Resolved envelope's `routed_identity_hash` is checked at resolution time against the bundle's current routed identity; holds at the old identity expire after a grace window. |
| SA-8 | `aiggp-10-repository-unification-migration/acceptance.md` (Q14.3) | Two clocks, two audiences: shim expiry is a fixed 90-day consumer promise for every profile; freeze/stabilization windows are the deployer's client-chosen rollback exposure. |
| SA-9 | `AIGGP-RETIREMENT-2026-10-02.md` | Evidence trust is DevGate's shipped HMAC attestation (`hub/coherence/attest.py`). Asymmetric signing, CAs, and enrollment certificates are out of scope until a concrete AI-guardrail requirement demands them; if that day comes, CAs stay client-chosen optional (owner, 2026-10-01). |
| SA-10 | `AIGGP-RETIREMENT-2026-10-02.md` | The unit of durable truth is the sealed evidence bundle plus the coherence run ledger. An append-only cross-run ledger is not required by any kept package. |
| SA-11 | `AIGGP-RETIREMENT-2026-10-02.md` | Repository unification means the agent guardrails system moving INTO the DevGate/AIGGP repo — the reverse of ADR-001 as drafted. `guardrails-control-plane`'s submodule composition stays valid until AIGGP-10 executes. |

## Cross-cutting frame (owner, 2026-10-01; scope confirmed 2026-10-02)

The product is a **guardrail framework for AI coding, not a security
framework for an environment**. Owner cut rule (2026-10-02): *"anything that
is AI guardrails is good, like the prompt injection etc."* — AI-guardrail
packages stay; kernel-level hardening (envelope/CA/ledger/waivers, fleet
enrollment/identity) was retired with `aiggp-00` and `aiggp-09`. Evidence
trust rides on DevGate's shipped machinery (SA-9/SA-10). AIGGP the *name*
stands: it is the portmanteau goal of pulling the agent guardrails system
into DevGate (SA-11) — the repo already carries it.