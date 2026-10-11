# Design: add-gitlab-forge-support

## Design principles

- Additive, never divergent: GitLab adds coverage; it changes no verdict.
- Thin forge layer: everything forge-specific lives behind the adapter
  interface (`hub/forge/`); gate scripts never see forge credentials or
  forge conditionals.
- Same scripts, same images: both forges execute identical gate scripts on
  identical digest-pinned images.
- Discovery before dependency: an undocumented instance is not
  infrastructure.
- Forge identity is metadata: `forge` is a field on the sealed evidence
  bundle, never a branch in verdict logic.

## Locked decisions

Carried from the owner walk-through of the predecessor draft
(`aiggp-07` Q11.1/Q11.2, answered 2026-10-01), re-anchored to shipped
DevGate surfaces by the 2026-10-02 kernel retirement:

1. **Instance posture** — tailnet-only for the lab instance, pinned
   version, backup restore-tested before reliance.
2. **Runner standard** — rootless podman, digest-pinned images, fail-closed
   registration; expressed through the existing `scripts/runner-enroll.sh` +
   `hub/schema/runners.schema.json` contract extended with a forge field.
3. **Template shape** — GitLab CI includes invoking the same gate scripts
   as the GitHub workflow templates, 1:1 across the shipped set in
   `templates/github-workflows/` (seven at writing time: guardrails
   compliance, secret validation, file size, smoke gate, scheduled drift
   scan, spec-coherence, specs-validation). The set is counted from that
   directory; adding or retiring a GitHub template updates the mirror in
   the same change.
4. **Hub integration** — forge adapter (`hub/forge/`) emitting the shipped
   sealed-evidence-bundle format (`hub/coherence/evidence.py`), attested
   via `hub/coherence/attest.py` (HMAC, per SA-9); `forge` is a bundle
   metadata field.
5. **Parity drill** — seeded-failure corpus run on both forges; identical
   findings required; drill is blocking in CI. The drill is the definition
   of done.
6. **Per-instance ownership (was Q11.1)** — ownership identity,
   security-patch cadence, upgrade cadence, and adapter-supported version
   are declared per forge instance in deployer configuration (the draft's
   `policy-bundles/[bundle].toml`; until that repo exists, a
   `hub/forge/instances.toml`-shaped deployer file). No hardcoded
   ownership or cadence in code. Identity is a key-hash allowlist entry
   when no CA runs (CA-optional per SA-9). The forge matrix is
   multi-forge from day one: GitHub with self-hosted runners — what the
   fleet runs today — is a first-class adapter surface alongside GitLab,
   and this package does not regress it.
7. **Self-hosted axes (was Q11.2)** — "self-hosted" names two independent
   axes: self-hosted *runners* (CI job machines — today's GitHub fleet) and
   a self-hosted *forge instance* (a GitLab server someone operates, vs
   GitLab.com). They vary independently and are declared per instance. The
   GitLab adapter's contract covers both self-hosted GitLab and GitLab.com
   as surfaces of one adapter. Enabling GitLab.com for a deployment is an
   opt-in exposure decision (third-party ingress for evidence), never
   default-on.

## Major components

1. Instance discovery and documentation runbook (Sprint 0).
2. GitLab runner standard + setup automation (extension of runner-enroll).
3. Mirrored CI templates (`templates/gitlab-ci/` includes).
4. Forge adapter (`hub/forge/`: webhooks, auth, API) behind the forge
   interface.
5. Parity-drill harness and seeded corpus.
6. Backup/restore verification drill.

## Trust boundaries

- The adapter is the only component that talks the GitLab API; gate scripts
  never see forge credentials.
- Forge webhooks are unauthenticated input until verified against instance
  secrets.
- Instance admin credentials stay outside gate infrastructure entirely.
- Evidence leaving a GitLab run passes through the same validation
  (`scripts/evidence-validate.py`) as GitHub evidence; there is no
  forge-trusted shortcut.

## ADRs

- ADR-001: Additive second forge, never a fork. Rationale: one truth model
  across forges is the platform promise. Consequence: parity is a permanent
  CI cost, accepted.
- ADR-002: Discovery gates everything. Rationale: the lab instance is
  undocumented; assumptions here poison everything downstream. Consequence:
  Sprint 0 is a hard gate.
- ADR-003: Thin templates, shared scripts. Rationale: CI syntax diverges;
  scripts must not. Consequence: template changes are trivial by design.
- ADR-004: Tailnet-first, not tailnet-only. Rationale: the lab is the
  first consumer; external GitLab adopters matter for the open-source
  play. Consequence: adapter configuration is instance-generic.
- ADR-005 (new, 2026-10-02): DevGate-native evidence, not a kernel
  envelope. Rationale: aiggp-00 was retired; the shipped sealed-bundle +
  HMAC-attestation machinery is the truth substrate (SA-9/SA-10).
  Consequence: `forge` is added as bundle metadata; no new evidence schema
  is invented for this package.