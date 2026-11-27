# Review exact corruption transitions through trusted provisioning

## Why
The corruption gate must remain strict by default, including for historical findings. A narrowly reviewed transition may need an auditable disposition when an exact finding moves between two reviewed source blobs. A subject checkout cannot authorize its own finding; a broad path or content exception could hide unrelated changes.

## What Changes
- Specify explicit `check_corruption.py --reviewed-transitions --range BASE..HEAD`; existing invocations remain strict.
- Bind evaluation to a trusted per-run controller binding and detached central catalog outside the subject checkout.
- Match exact repository identity, detector assertion, path, ordered before/after Git blob IDs, and finding line; keep matches visible as `EXCEPTION-ADVISORY`.
- Fail closed on missing, stale, malformed, mismatched, expired, or revoked trust inputs. Continue full-tree, secret, and bulk-rewrite checks.
- Document the operator and control-plane contract. Enforcement and CI remain pending in the owning implementation work.

## Capabilities
### New Capabilities
- `reviewed-corruption-transitions`: trusted, exact, time-bounded dispositions for individual findings.
### Modified Capabilities
None.

## Impact
The explicitly selected evaluator mode, privileged control-plane provisioning, audit output, and operator procedures. No exception grant, credential, or subject-specific approval is included.
