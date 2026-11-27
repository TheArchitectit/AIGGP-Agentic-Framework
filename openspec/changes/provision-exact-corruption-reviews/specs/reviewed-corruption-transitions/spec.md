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
Reviewed mode SHALL read the catalog only from `/etc/aiggp/corruption-reviews.json` and the binding only from `/run/aiggp/corruption-reviews/<sha256(canonical-checkout-path)>.json`. The privileged control plane SHALL install these files outside the subject checkout and mount the containing protected directories read-only, not individual files, so atomic host-side replacement is visible. The evaluator SHALL reopen and revalidate the binding and catalog before applying reviewed dispositions. Subject files, allowlists, CLI overrides, or checkout content SHALL NOT authorize a finding.

The catalog SHALL use API version `aiggp.corruption-review-catalog/v1` with an `exceptions` array. The binding SHALL use `aiggp.corruption-review-binding/v1` and bind canonical checkout, immutable `github:<host>:<numeric repository id>`, exact full base/head, UTC issuance/expiry, and SHA-256 of raw catalog bytes.

#### Scenario: Subject checkout supplies apparent authority
- **WHEN** a subject file or CLI option attempts to supply or replace authority inputs
- **THEN** the evaluator uses only the fixed protected inputs

#### Scenario: Binding mismatches authenticated run
- **WHEN** checkout, repository, full base/head, validity, schema, or catalog digest differs
- **THEN** reviewed mode fails closed without reviewing findings

### Requirement: Exception records identify one exact finding transition
<!-- id: scan-corruption-reviewed-exact-01 -->
Each record SHALL provide `exception_id`, `subject_ref`, `subject_path`, `assertion_id`, `finding_fingerprint`, `owner`, `reason`, `approving_authority`, `created_at`, `expires_at`, `remediation_ref`, and `enforcement_treatment`. The `finding_fingerprint` object SHALL contain `assertion_id`, integer `assertion_version` (currently 1), `subject_location` equal to `subject_path`, and bind ordered blob IDs and exact new-side line in `substitution-flip:<before-blob>:<after-blob>:<new-line>`. It applies only if every identity, detector, path, blob order, location, and validity field matches.

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
