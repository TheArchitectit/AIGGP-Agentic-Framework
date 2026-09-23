# Security Policy

## Reporting

Report vulnerabilities via GitHub **private vulnerability reporting**
(Security tab → Report a vulnerability) on this repository. If that is
unavailable, open a regular issue titled `security: <area>` WITHOUT
exploit details and request a private channel.

## Scope

- `hub/coherence/**` — signing, attestation, anti-rollback, evidence
  sealing, cache. Threat model: `docs/threat-model.md`.
- `scripts/deploy.sh` — gated publish pipeline.
- `container/Containerfile` — evaluator image contents.
- `hub/**` — the runner-monitor hub (network service).

## Commitments

- Vulnerabilities in the coherence trust surface are treated as
  release-blocking for any version tag that advertises the affected
  capability.
- Fixes ship with a negative-control test that fails when the defense is
  bypassed (see `docs/threat-model.md` A1–A12 for the required pattern).
- Known-uncovered surface is listed honestly in the threat model; reports
  against UNCOVERED rows are especially welcome.
