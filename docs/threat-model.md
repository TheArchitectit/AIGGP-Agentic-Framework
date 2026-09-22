# Threat Model — Spec Coherence Service

Scope: `hub/coherence/` (the signed-evaluation service), the evaluator
container, and the consumer-repo boundary. This document is factual: every
row cites the test that defeats the adversary class, or says **UNCOVERED**.
Anything UNCOVERED must not be marketed as covered.

## Trust boundaries

| Boundary | Who controls it | Note |
|---|---|---|
| Control plane → evaluator | control plane (stand-in: `HUB_COHERENCE_*` env + issued contexts) | Real KMS/key management is ADR-018; the HMAC stand-in is explicitly a pilot scope |
| Evaluator container → host | host launcher (`hub/coherence/launcher.py`) | read-only, non-root, cap-drop ALL, network=none |
| Consumer repo → evaluator | repository content (specs, overlays, assertion files) | repository content establishes identity, never authority (coh-pol-02) |

## Assets

- Signing keys (stand-in env keys) and the control-plane signer set
- The policy bundle (epoch, required assertions, approved evaluators/signers)
- Sealed evidence + canonical decisions (the things consumers act on)
- The decision cache (a wrong hit replays a stale verdict)

## Adversary classes and controls

| # | Adversary / attack class | Control | Test that defeats it |
|---|---|---|---|
| A1 | Forged countersignature on an evaluation context | HMAC verify at context load; unsigned context refused wherever a CP key is configured | `tests/test_hub_coherence_issue.py` (context signature guards); **UNCOVERED** for a full forged-signature negative control against a live key — see note |
| A2 | Replayed evaluation context (stale time / reused decision) | `semantics: replay` is structurally labeled non-promotion-authorizing; `attest.required()` demands fresh-promotion for signing | `tests/test_hub_coherence_ladder.py` (replay demotion); decision-cache TTL via `cache.py` predicates |
| A3 | Older-but-signed policy bundle accepted without a grandfather window | Anti-rollback: bundle `bundle_epoch` vs binding `min_bundle_epoch`; binding rides the signed context | `scripts/negative_controls.py` nc-09 (rolled-back bundle → exit 31); unit pins in `tests/test_hub_coherence_conformance.py` |
| A4 | Payload substitution under a still-valid attestation | Offline verification chain: statement digest, bound digests, signature, signer set, revocation, evidence re-verify | `scripts/negative_controls.py` nc-10 (substituted decision → `decision-digest-mismatch`); `tests/test_hub_coherence_attest.py` (7 fail-closed reasons) |
| A5 | Policy-refusal ambiguity (caller mistakes ERROR for FAIL/PASS) | Frozen exit matrix; decision/exit agreement asserted at the container boundary | `tests/test_hub_coherence_exitcodes.py`; `tests/test_coherence_adapter_default_deny.py` (timeout/unparseable → ERROR, never neutral) |
| A6 | Evidence tamper after sealing | Digest-sealed evidence + manifest; verify recomputes every object; containment on attacker-influenced paths | `tests/test_hub_coherence.py` tamper tests; `tests/test_hub_coherence_fw.py` (consistent-escaping bundle rejected); mutation-checked 21/21 |
| A7 | Evaluator image substitution | Digest-pinned refs; launcher injects executed digest; profile registry match | `tests/test_hub_coherence_container.py`; CI `container-image` job (digest vs identity registry, notice-only while S4 publish is in flight) |
| A8 | Cache poisoning / stale-hit | Total cache key (subject+package+policy+context+image+plugins+facts+TTL+retention+signer); TTL from trusted `evaluation_time`; malformed entries miss | `tests/test_hub_coherence_cache.py` (component drift, as_of TTL); retention via caller predicates |
| A9 | Evaluator-code mutation that verification cannot see | Mutation testing of the evidence module | `scripts/mutation_check.py` — evidence.py 21/21 killed; CI `evaluator-integrity` job |
| A10 | Malicious repository overlay (weaken central policy) | Overlay may strengthen only: unknown evaluator, severity below floor, disabling required, capability grants — all rejected | `tests/test_hub_coherence_conformance.py::TestOverlayCannotWeaken` |
| A11 | Gaming the benchmark (hardcode to pass hidden checks) | Hidden verifiers receive the repo under test as argv[1]; shipped GAMING strategy must stay rejected | CI `evaluator-integrity`: "Gaming strategy rejected" step; `.benchmarks/` control phase |
| A12 | Compromised runner (spoke) | One-time enrollment tokens; per-runner revocable heartbeat tokens; salted hashes at rest | `tests/test_hub_enroll_heartbeat.py`; `scripts/fleet_drill.py` (forged token 401, post-revoke 401, restart persistence) |

**Note on A1:** the countersignature guard is covered at the load/verify
level by the issue tests; a dedicated forged-signature negative control in
the style of nc-10 (craft a context, tamper the signature byte, assert the
rejection reason) would close the last gap and is welcome.

## Known-uncovered surface (honest list)

- Key management is a symmetric stand-in (ADR-018 open): no HSM/KMS, no
  asymmetric separation of signing vs verification keys.
- The published evaluator image identity is OPEN (digest mismatch vs the
  registry is notice-only until the S4 publish retires it).
- External review of this service has not happened; this document and its
  test matrix are the prep package for that review (see MAINTAINERS.md).
