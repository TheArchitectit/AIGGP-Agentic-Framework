# Runbook: Policy Rollback and Key Rotation

**Scope:** rejected policy bundles (coh-pol-02 anti-rollback) and signer
key lifecycle for coherence attestations. Both mechanisms are implemented
in `hub/coherence/attest.py`, `hub/coherence/issue.py`, and the CLI's
policy-resolution stage.

## Policy rollback: "policy rollback: bundle epoch floor N is below the
control-plane floor M"

**Meaning:** the evaluation context (issued by the control plane) carries a
`policy_epoch_floor` of M; the policy bundle on disk declares
`min_bundle_epoch: N < M`. The bundle is treated as trusted-but-obsolete —
this rejection is the anti-rollback gate working as designed.

**Diagnosis**

```bash
python3 - <<'PY'
import json
ctx = json.load(open("<ctx-root>/context.json"))
pol = json.load(open("<policy-root>/policy.json"))
print("context floor:", ctx.get("policy_epoch_floor"))
print("bundle epoch:  ", pol.get("min_bundle_epoch"))
PY
```

**Recovery — exactly one of:**

1. **The bundle is genuinely old (an attack or a bad deploy):** restore the
   current bundle from the control plane. Do NOT lower the context floor —
   the floor lives in the SIGNED context for exactly this reason.
2. **The floor is wrong (control-plane error):** re-issue the context with
   the corrected floor:

```bash
python3 - <<'PY'
from hub.coherence.issue import issue_context
issue_context("<ctx-root>", "<policy-root>", repo="<owner/repo>",
              registry_path="<stage-registry.json>",
              evaluation_time="<now-ISO>", policy_epoch_floor=1)
PY
```

3. **Grandfathered evaluation:** a context issued WITHOUT
   `policy_epoch_floor` disables epoch enforcement for that evaluation
   (this is the recorded-window grandfather path; use deliberately, never
   as a default).

Note: a bundle with NO `min_bundle_epoch` at all is rejected whenever a
floor exists — pre-epoch bundles cannot satisfy anti-rollback.

## Signer key rotation (attestations)

**Mechanism:** `key_id` is derived (`sha256(key)[:16]`, `attest.py`), so a
rotated key produces a different `key_id`. At verification a mismatch is
`key-mismatch` — fail-closed, even for a valid signature.

**Rotate (planned):**

1. Generate the new key; compute its derived key_id
   (`attest.key_id_for(bytes.fromhex(<new-hex>))`).
2. Add the NEW entry to the policy bundle's `approved_signers` (keep the
   old one, unrevoked) and re-issue/re-sign the policy.
3. Switch runners to the new key (`HUB_COHERENCE_SIGNER_KEYS` +
   `HUB_COHERENCE_SIGNER_IDENTITY`). New decisions attest under the new
   key_id.
4. Verify offline: `python3 -m hub.coherence --verify <out-dir> --signers
   signers.json` → `attestation OK` with the new key_id.
5. Retire the old key: set `revoked: true` on its `approved_signers` entry.
   From then on even old-but-valid signatures from that key are rejected
   (`revoked-signer:<identity>`).

**Rotate (emergency, key compromised):** skip steps 2–3 ordering concerns —
revoke FIRST (`revoked: true`), then deploy the new key. Anything signed by
the compromised key after revocation fails closed. Cached decisions are not
exposed by revocation: the decision cache key includes the signer key_id
and the evaluator image digest, so entries minted under the compromised
identity cannot be replayed as entries of the new one (coh-ctx-05).

## Verification after any of the above

```bash
python3 scripts/negative_controls.py --only nc-09   # rollback rejection
python3 scripts/negative_controls.py --only nc-10   # attestation substitution
python3 scripts/mutation_check.py --self-check      # evaluator sanity
```
