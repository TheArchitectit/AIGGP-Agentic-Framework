# Runbook: Evidence Bundles and Attestations

**Scope:** what an operator does with a sealed coherence output directory —
verify it, transport it, store it — and how every tamper class is refused.

## What a sealed output directory contains

| File | What it is |
|---|---|
| `result.json` | the canonical decision (frozen schema; contains NO attestation material — coh-ev-01) |
| `evidence-manifest.json` + `evidence/findings/*.json` | minimum-disclosure evidence, digest-sealed (coh-ev-02/06) |
| `decision.claim.json` (+ `.digest`) | the pipeline's claim — bound to every input digest, state OBSERVED (a producer cannot self-certify; fw-*) |
| `attestation.json` | detached signature over the exact decision bytes — present only when signing is configured (S5) |

## Verify a bundle offline

```bash
# Evidence integrity + claim consistency (no key material needed):
python3 scripts/evidence-validate.py <out-dir> --expected <manifest-digest>

# Attestation (needs the control-plane-issued signer-set document):
python3 -m hub.coherence --verify-run <out-dir> --signer-set signer-set.json
```

`--verify` prints a stable reason on rejection — the reason IS the
diagnosis:

| Reason | Meaning | Action |
|---|---|---|
| `decision-digest-mismatch` | the decision bytes differ from the attested ones | do not trust the bundle; re-run the evaluation |
| `bound-digest-mismatch:<key>` | decision's inputs differ from the attested inputs | the bundle was recombined; re-run |
| `evidence-tamper` | a sealed evidence object no longer matches its manifest digest | tamper; treat as hostile |
| `signature-mismatch` | the attestation block was edited after signing | tamper; treat as hostile |
| `signer-revoked` | signer revoked in the control-plane set | trust nothing signed by it, before or after |
| `signer-identity-mismatch` | key_id exists but identity disagrees | the set and the attestation disagree; investigate |
| `signer-not-in-set` | signer absent from the set you supplied | you are holding the wrong signer set |
| `missing-artifact` / `unparseable-artifact` | bundle incomplete or corrupt | regenerate; do not hand-patch |

## Transport and store

```python
from hub.coherence.store import LocalBundleStore, upload_bundle
store = LocalBundleStore("/data/evidence-store")   # offline local-bundle mode
out = upload_bundle(store, "<out-dir>")            # retryable, resumable
assert out["failed"] == []
```

- Objects are content-addressed and immutable: a retried upload re-verifies
  and skips what the store already holds; a stored object that differs from
  the sealed payload is a hard error, never a silent skip.
- Decide cache reuse with the total key (`store.decision_cache_key`) and
  check validity with `store.cache_entry_valid` — TTL **and** retention
  must both be open; expired entries miss, never hit (coh-ev-04).

## Reproducibility

Before trusting any single decision as evidence for an enforcement action,
confirm the evaluation is deterministic on your fixture:

```bash
python3 scripts/determinism_drill.py --runs 100
```

A decision that varies between identical runs cannot back an enforcement
action regardless of how often it is correct (S8 determinism criterion).
