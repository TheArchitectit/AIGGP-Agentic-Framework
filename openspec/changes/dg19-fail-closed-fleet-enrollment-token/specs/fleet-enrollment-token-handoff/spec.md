# Fleet enrollment token handoff

## Purpose

Keep enrollment on its authorized GitHub App installation identity and
confine credentials to the verified handoff to the existing reconciler.

## ADDED Requirements

### Requirement: Enrollment requires a minted installation token
<!-- id: fleet-enroll-auth-01 -->

The workflow SHALL require the complete App credential pair and a nonempty
minted installation token before calling the reconciler. Its only accepted
enrollment identity SHALL be the minted App installation token.

#### Scenario: The mint step returns an empty value

- **WHEN** the App credential pair is present but installation token issuance
  returns an empty value
- **THEN** the workflow stops before reconciliation and reports the missing
  token without credential data

#### Scenario: An App configuration value is absent

- **WHEN** either configured half of the App credential pair is missing
- **THEN** the workflow identifies the missing configuration and stops before
  token issuance

### Requirement: Reconciler credentials use the verified environment handoff
<!-- id: fleet-enroll-auth-02 -->

The workflow SHALL deliver App credentials to the reconciler through its
environment. Workflow-authored steps SHALL keep raw keys and tokens out of
outputs, files, command arguments, logs, and enrollment reports. Evidence for
the existing file-handling requirement SHALL include the issuer's transport.

#### Scenario: Token issuance succeeds

- **WHEN** the workflow receives a valid App installation token
- **THEN** the reconciler receives it through its environment and workflow
  outputs, files, command arguments, logs, and reports omit credential values
