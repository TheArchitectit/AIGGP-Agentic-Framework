# Require an installation token for fleet enrollment

## Why

The enrollment workflow falls back to the repository workflow token when the
mint step returns an empty installation token. This conflicts with
`fleet-app-06`. Its authentication shell step also writes the selected token
to a second workflow output file. DG-05 tracks source evidence for the
existing enrollment contract and exposed both gaps during independent review.

## What Changes

- Stop enrollment when either required credential configuration or the minted
  installation token is missing.
- Pass the installation token to the reconciler through its process
  environment and remove the workflow's extra credential-bearing output.
- Document the issuer's transport and verify the workflow locally with inert
  fixtures and no live fleet requests.

## Capabilities

### New Capabilities

- `fleet-enrollment-token-handoff` specifies workflow authentication and
  credential delivery to the reconciler.

### Modified Capabilities

None.

## Impact

The AIGGP fleet enrollment workflow, its workflow-contract tests, and the
evidence for existing `fleet-app-06` and `fleet-app-08` requirements.
