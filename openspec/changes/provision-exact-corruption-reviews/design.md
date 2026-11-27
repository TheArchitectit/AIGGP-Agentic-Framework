# Design

## Context
The existing corruption check is fail closed and remains strict for ordinary calls. Reviewed handling is opt-in for an authenticated base/head range. The checkout is untrusted and cannot provide its own authority, catalog, or path allowlist.

## Decisions

### Strict mode remains default
Only explicit `--reviewed-transitions --range BASE..HEAD` selects this mode. Existing invocations and all other gate modes retain strict behavior. The trusted runner, not repository-controlled workflow data, chooses the installed evaluator and supplies authenticated repository identity and exact range.

### Authority is external to the subject checkout
The privileged control plane provisions a root-owned catalog at `/etc/aiggp/corruption-reviews.json` and a root-owned per-run binding at `/run/aiggp/corruption-reviews/<sha256(canonical-checkout-path)>.json`. These fixed paths cannot be overridden by the subject. The containing protected directories are mounted read-only, not individual files, so atomic host-side replacement is visible. The evaluator reopens and revalidates the run binding and current catalog digest immediately before applying reviewed dispositions. Authority is the independent privileged provisioning boundary and its binding to the current catalog digest; this design does not claim a new signature layer.

The catalog has API version `aiggp.corruption-review-catalog/v1` and an `exceptions` array. A binding has API version `aiggp.corruption-review-binding/v1` and contains canonical `checkout`, immutable `subject_ref` (`github:<host>:<numeric repository id>`), exact full `base` and `head`, UTC `issued_at` and `expires_at`, and `catalog_sha256` over raw catalog bytes.

### One record identifies one finding transition
Each record uses `exception_id`, `subject_ref`, `subject_path`, `assertion_id`, `finding_fingerprint`, `owner`, `reason`, `approving_authority`, `created_at`, `expires_at`, `remediation_ref`, and `enforcement_treatment`. The `finding_fingerprint` object contains `assertion_id`, integer `assertion_version` (currently 1), `subject_location` equal to `subject_path`, and an ordered `violation_key` of `substitution-flip:<before-blob>:<after-blob>:<new-line>`. Blob IDs are full Git object IDs; line is the exact new-side finding line. All repository, detector, path, order, location, validity, and treatment fields must match. Subject-managed path allowlists never authorize reviewed findings.

### Bind each run and fail closed
The trusted runner installs a binding for the canonical checkout path. The evaluator verifies fixed location, API versions, checkout, immutable repository identity, exact full range, UTC validity, catalog raw-byte digest, catalog schema, and matching records. Missing or duplicate trust inputs, malformed data, ambiguous identities, mismatch, expiry, unavailable Git objects, and digest changes fail closed. No consumer option overrides authority paths.

Catalog amendment or withdrawal changes its digest and invalidates old bindings. The control plane must stop issuing or refresh bindings; stale bindings cannot authorize the changed catalog.

### Preserve findings and independent gates
An exact accepted finding stays visible as `EXCEPTION-ADVISORY` with its exception ID and bounded disposition; it is not a clean scan. Unmatched corruption findings still fail. Full-tree corruption checks remain enabled. Secret scanning remains an independent CI gate and is not suppressed by reviewed mode. Bulk/mass-rewrite handling retains the existing configured disposition; reviewed mode cannot change it.

The evaluator reads both commits and their blobs through a temporary bare Git repository. The installed Linux Git binary, its environment, and the diff algorithm are selected by the evaluator. The controller selects approval and binding durations under its local review policy.

## Risks and Trade-offs
- The privileged provisioning boundary is security-critical; restrict writers and retain audit history.
- Clock errors can create ambiguous validity; use synchronized UTC and reject invalid times.
- Require full object IDs and verify commits/blobs exist in the authenticated checkout.
- Preserve distinct advisory status/counts so an advisory cannot be mistaken for a green result.
- The evaluator and focused tests are present on this branch, but production controller provisioning, upstream approval, and protected CI rollout remain pending. No real exception is authorized.
