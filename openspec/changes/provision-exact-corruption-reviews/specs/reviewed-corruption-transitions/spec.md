# Reviewed corruption transitions

## Purpose
Allow a trusted evaluator to report an exact, centrally reviewed corruption transition as an advisory while ordinary checks remain strict and unrelated findings remain blocking.

## ADDED Requirements

### Requirement: Strict corruption checking remains the default
<!-- id: scan-corruption-reviewed-default-01 -->
The corruption evaluator SHALL keep existing modes strict. It SHALL enter reviewed behavior only when the trusted caller explicitly selects `--reviewed-transitions --range BASE..HEAD` with an authenticated exact range.

#### Scenario: Existing invocation omits reviewed mode
- **WHEN** the evaluator is invoked without the explicit option
- **THEN** findings retain existing strict disposition and no catalog record changes the result

### Requirement: Reviewed mode uses protected external authority
<!-- id: scan-corruption-reviewed-authority-01 -->
Reviewed mode SHALL accept authority only from the fixed catalog and run binding in privileged, read-only directory mounts. The evaluator SHALL reopen and validate both files before applying any reviewed disposition. Subject files, allowlists and CLI overrides cannot authorize a finding.

#### Scenario: Controller installs the authority files
- **WHEN** the privileged controller provisions a checkout
- **THEN** it installs the catalog at `/etc/aiggp/corruption-reviews.json` and the binding at `/run/aiggp/corruption-reviews/<sha256(canonical-checkout-path)>.json` outside the subject checkout
- **AND** it mounts the containing protected directories read-only so atomic file replacement remains visible

#### Scenario: Evaluator reads an issued catalog and binding
- **WHEN** reviewed mode starts
- **THEN** it requires an `aiggp.corruption-review-catalog/v1` catalog with an `exceptions` array and an `aiggp.corruption-review-binding/v1` binding
- **AND** the binding fixes the canonical checkout, immutable `github:<host>:<numeric repository id>`, full base and head, UTC issuance and expiry, and SHA-256 of the raw catalog

#### Scenario: Subject checkout supplies apparent authority
- **WHEN** a subject file or CLI option attempts to supply or replace authority inputs
- **THEN** the evaluator uses only the fixed protected inputs

#### Scenario: Binding mismatches authenticated run
- **WHEN** checkout, repository, full base/head, validity, schema, or catalog digest differs
- **THEN** reviewed mode fails closed without reviewing findings

### Requirement: Exception records identify one exact finding transition
<!-- id: scan-corruption-reviewed-exact-01 -->
A reviewed record SHALL apply to one substitution only when the subject, detector, path, ordered blob IDs, new-side line and validity all match the finding. The record SHALL identify its owner and approving authority and carry the reason, remediation reference and enforcement treatment.

#### Scenario: Evaluator validates a review record
- **WHEN** the evaluator loads a record
- **THEN** it requires `exception_id`, `subject_ref`, `subject_path`, `assertion_id`, `finding_fingerprint`, `owner`, `reason`, `approving_authority`, `created_at`, `expires_at`, `remediation_ref` and `enforcement_treatment`
- **AND** the fingerprint contains the matching `assertion_id`, integer `assertion_version` (currently 1), `subject_location` equal to `subject_path` and `substitution-flip:<before-blob>:<after-blob>:<new-line>`

#### Scenario: Exact transition matches
- **WHEN** a finding matches one valid record's full identity and transition tuple
- **THEN** output retains that finding as `EXCEPTION-ADVISORY` with the exception ID and evaluates all other findings

#### Scenario: Nearby or reordered transition differs
- **WHEN** repository, detector, path, blob order, line, or validity differs
- **THEN** the record does not apply and the finding remains blocking

### Requirement: Reviewed findings remain visible and other gates remain active
<!-- id: scan-corruption-reviewed-visible-01 -->
The evaluator SHALL retain each reviewed finding as a distinct advisory and SHALL fail for every unmatched blocking finding. Reviewed handling SHALL NOT bypass full-tree corruption checks, secret scanning, or bulk/mass-rewrite protections.

#### Scenario: Advisory and unmatched finding coexist
- **WHEN** one finding matches and another does not
- **THEN** output shows the first as advisory and second as blocking, and the gate exits unsuccessfully

#### Scenario: Independent bulk or secret finding occurs
- **WHEN** reviewed mode encounters a bulk/mass-rewrite violation or secret finding
- **THEN** its existing blocking behavior remains

### Requirement: Trust inputs expire and revocation invalidates stale bindings
<!-- id: scan-corruption-reviewed-lifecycle-01 -->
The control plane SHALL constrain records and bindings by UTC validity. The evaluator SHALL re-read the current protected inputs before applying a reviewed disposition so an in-flight run cannot rely on a withdrawn catalog or stale binding. Any catalog change or withdrawal SHALL alter raw catalog digest and invalidate bindings against the previous digest. Missing, malformed, ambiguous, expired, revoked, or unreadable inputs SHALL fail closed.

#### Scenario: Catalog is withdrawn
- **WHEN** the catalog changes after a binding was issued
- **THEN** digest mismatch rejects the binding and reviews no finding

#### Scenario: Record is expired or malformed
- **WHEN** a selected record is invalid by time or schema
- **THEN** reviewed mode fails closed instead of silently skipping it
