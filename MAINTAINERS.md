# Maintainers

## Roles

| Role | Holder | Responsibility |
|---|---|---|
| Lead / release | TheArchitectit | merges PRs, cuts tags, owns branch protection |
| Security review | **OPEN — see below** | review required for `hub/coherence/**` and `scripts/deploy.sh` changes |
| Fleet operations | operator of the monitor host | hub container, runner enrollment, alert triage |

## Single-maintainer risk (stated plainly)

This project is currently developed and maintained by one account working
with AI agents. That is a bus factor of 1 on security-critical code. The
mitigations in place — machine-enforced gates, negative controls, mutation
strength floors, drills — reduce but do not remove the risk that a single
reviewer (human or agent) shares a blind spot with the author.

**Second security reviewer wanted.** If you can review signing,
attestation, anti-rollback, or container-isolation code, see
`docs/threat-model.md` for the attack matrix and `CONTRIBUTING.md` for the
process. A PR review that says "I checked A1–A12 against the tests" is the
single most valuable contribution available right now.

## Review requirements

- `hub/coherence/**` and `scripts/deploy.sh`: require review from the
  security-review role (branch protection enforces once an admin enables
  it; until then this file is the record of intent).
- Everything else: CI green + lead merge.
