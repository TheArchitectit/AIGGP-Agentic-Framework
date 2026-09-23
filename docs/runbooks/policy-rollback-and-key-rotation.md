# Runbook: Policy Rollback and Key Rotation

**Scope:** rejected policy bundles (coh-pol-02 anti-rollback) and signer
key lifecycle for coherence attestations. Both mechanisms are implemented
in `hub/coherence/attest.py`, `hub/coherence/issue.py`, and the CLI's
policy-resolution stage.

## Policy rollback: anti-rollback rejection at policy resolution

**Meaning:** the policy bundle on disk declares `bundle_epoch: N`, and the
control-plane BINDING (carried in the signed context, digest-verified at
load) requires `min_bundle_epoch >= M > N`. The bundle is
trusted-but-obsolete — the rejection is the anti-rollback gate working as
designed (coh-pol-02; see `hub/coherence/policy.py`, the binding check).
A bundle with no valid `bundle_epoch` at all is also rejected whenever a
binding exists.

**Diagnosis**

```bash
python3 - <<'PY'
import json
pol = json.load(open("<policy-root>/policy.json"))
print("bundle epoch:", pol.get("bundle_epoch"))
# The binding rides in the signed context:
import glob
for p in glob.glob("<ctx-root>/*"):
    doc = json.load(open(p))
    b = doc.get("policy_binding") or {}
    if b:
        print(p, "-> min_bundle_epoch:", b.get("min_bundle_epoch"))
PY
```

**Recovery — exactly one of:**

1. **The bundle is genuinely old (an attack or a bad deploy):** restore the
   current bundle from the control plane. Do NOT edit the binding — it is
   bound into the signed context precisely so repository-side edits cannot
   weaken it.
2. **The floor is wrong (control-plane error):** re-issue the context with
   a corrected binding through the control-plane issuance path
   (`hub/coherence/issue.py` / the stage registry workflow).
3. **Grandfather window:** the design records explicit grandfather windows
   for obsolete bundles; opening one is a control-plane action, never a
   repository-side file edit.

## Signer key rotation (attestations)

**Mechanism:** the signing key arrives via `HUB_COHERENCE_SIGNER_KEY` with
its identity under `HUB_COHERENCE_SIGNER_IDENTITY` and its identifier under
`HUB_COHERENCE_SIGNER_KEY_ID` (`hub/coherence/attest.py`). Verification is
key_id-based against a control-plane-issued SIGNER-SET document
(`devgate.spec-coherence.signer-set/v1`): membership, identity match,
revocation, and validity window each fail closed
(`signer-not-in-set` / `signer-identity-mismatch` / `signer-revoked` /
window reasons). The symmetric stand-in ships verification keys INSIDE the
set; production splits signing/verification keys (ADR-018).

**Rotate (planned):**

1. Issue a NEW signer-set with the new key entry (key_id, identity, key,
   validity window) alongside the old entry, unrevoked.
2. Switch evaluators to the new signing key
   (`HUB_COHERENCE_SIGNER_KEY` / `HUB_COHERENCE_SIGNER_KEY_ID` /
   `HUB_COHERENCE_SIGNER_IDENTITY`). New decisions attest under the new
   key_id.
3. Verify offline: `python3 -m hub.coherence --verify-run <out-dir>
   --signer-set <new-set.json>` -> "verification ok".
4. Retire the old key: set `revoked: true` (+ `revoked_at`) on its set
   entry. From then on even structurally valid signatures from it are
   rejected (`signer-revoked`).

**Cached decisions are not exposed by rotation or revocation:** the
decision-cache key includes the signer validity component
(`hub/coherence/cache.py` — coh-ctx-05 consults signer validity through a
caller predicate), so entries minted under a retired key cannot be reused
as if current.

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
