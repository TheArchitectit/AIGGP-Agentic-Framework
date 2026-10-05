# S-E0 Inventory and Quarantine Plan

Gate 0 evidence for `openspec/changes/harden-oap-evidence-verification`.
Scope: every caller of `hub/coherence/ed25519.py` and
`hub/coherence/oap_evidence.py` at the remediation revision.

## Finding (confirmed)

`hub/coherence/ed25519.py` accepted the identity public key
(`01` + 31 zero bytes) with identity R and S=0 as a valid signature for
**arbitrary** messages. Noncanonical `y >= p`, low-order A/R, and the
`x=0`/`sign=1` encoding were also accepted. A successful `verify` was
therefore not an authenticity claim.

## Caller inventory

| Caller | Kind | Uses | Owner |
|--------|------|------|-------|
| `hub/coherence/oap_evidence.py` | production module | `ed25519.public_key`, `sign`, `verify`, size constants | Security review (`hub/coherence/**`; role currently OPEN — interim accountable: Lead / TheArchitectit) |
| `tests/test_oap_evidence_signature.py` | test | `ed25519` primitive + `oap_evidence` sign/verify envelope | Lead / TheArchitectit |
| `tests/test_oap_evidence_schema.py` | test | schema shape only (`hub.coherence.schemacheck`); does **not** import ed25519/oap_evidence | Lead / TheArchitectit |
| `.github/workflows/ci.yml` | CI | collects `tests/` via `pytest` and `scripts/run-tests.mjs`; no direct import of these modules | Lead / TheArchitectit |

No other production, test, script, or workflow file imports
`hub.coherence.ed25519` or `hub.coherence.oap_evidence` (verified by
repository-wide search at this revision).

## Artifact consumers and accepted evidence

- **Live consumers:** none. `add-oap-evidence-consumer` remains proposed.
  No OAP integration, grant, effect engine, or mandatory gate ships this path.
- **Evidence already accepted at the affected revision:** none in production.
  All current outputs are test fixtures / observe-only envelopes produced and
  consumed inside `tests/test_oap_evidence_signature.py`. Nothing was
  grandfathered, promoted, or used for a release decision.

## Quarantine status (Gate 0.2)

Both modules carry `NON_AUTHORIZING = True` and an explicit module-level
notice: a mathematical `verify`/`verify_envelope` success is **not**
authenticity and **must not** satisfy a mandatory, promotion, release, or
OAP-effect check. There is no unsigned/HMAC fallback, stale-cache
acceptance, exception path, or legacy-key bypass.

Enforced by `tests/test_oap_evidence_signature.py`
(`TestQuarantineNonAuthorizing`, `TestMandatoryCheckRejectsIdentityForgery`).

## Rollback / re-enrollment / re-verification (Gate 0.3)

1. **Rollback:** default is deny / observe-only / non-authorizing. Any
   regression returns to this state. No artifact verified solely by the
   pre-quarantine path may re-enter a mandatory lane by cache, waiver, or
   signature re-label.
2. **Re-enrollment:** only after Gates 1–3 complete (vetted verifier,
   frozen v2 contract, trust roots, semantic checks, conformance) and an
   independent security reviewer plus the OAP owner approve one named
   receiving operation.
3. **Re-verification:** previously produced artifacts are **not**
   grandfathered. Restore authority only via trusted fresh reevaluation
   under the remediated verifier and current policy. Re-sign with a
   production key is allowed only under the vetted provider decided in
   Gate 1 — never with the pure-Python signer as a timing-sensitive
   production key path.

## Residual risk

- Security review for `hub/coherence/**` is still an open role
  (`MAINTAINERS.md`); this inventory names the interim owner but does not
  close that gap.
- Pure-Python scalar arithmetic is not constant-time (documented in
  `ed25519.py`). Gate 1 must decide the production provider before any
  mandatory use.
