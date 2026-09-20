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

# Attestation (needs the approved signer set + signer keys in env):
python3 -m hub.coherence --verify <out-dir> --signers signers.json
```

`--verify` prints a stable reason on rejection — the reason IS the
diagnosis:

| Reason | Meaning | Action |
|---|---|---|
| `statement-substitution` | the decision bytes differ from the attested ones | do not trust the bundle; re-run the evaluation |
| `bound-input-substitution:<role>` | decision's inputs differ from the attested inputs | the bundle was recombined; re-run |
| `signature-mismatch` | the bound block was edited after signing | tamper; treat as hostile |
| `revoked-signer:<id>` | signer revoked in the approved set | trust nothing signed by it, before or after |
| `key-mismatch` | key rotated without re-attestation | re-attest under the current key |
| `signer-outside-validity-window:<field>` | checked against the reference time you supplied | supply the context's evaluation_time (`--reference-time`), not "now" |
| `unknown-signer:<id>` | signer not in the set you supplied | you are holding the wrong signer set |

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
