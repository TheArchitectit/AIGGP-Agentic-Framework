# Proposal: add-gitlab-forge-support

## Why

The lab runs GitLab; DevGate gates GitHub only. Repos on the lab instance get
no gate truth at all, and GitLab support bolted on later risks divergent
behavior — the same change passing on one forge and failing on the other.
Forge identity must stay metadata, never meaning.

This package replaces the imported draft `aiggp-07-gitlab-forge-support`
(retired with the 2026-10-02 kernel retirement; owner salvage decision
"Retire + salvage GitLab"). The draft was written against an imaginary
platform kernel; this spec is written against the DevGate surface that
actually ships:

- the seven workflow templates in `templates/github-workflows/`
  (guardrails-compliance, secret-validation, file-size-check, smoke-gate,
  drift-scan, spec-coherence, specs);
- the gate scripts they launch (`scripts/guardrails-scan.mjs`,
  `scripts/semantic-scan.mjs`, `scripts/silent-success-scan.sh`,
  `scripts/secret-scan.sh`, `scripts/regression_check.py`,
  `scripts/run-tests.mjs`, `scripts/spec_traceability.py`,
  `python -m hub.coherence`);
- the fleet machinery (`scripts/secret-scan-declared.sh` declaration walk,
  `hub/monitor.py`, `hub/server.py`);
- the runner standard (`scripts/runner-enroll.sh`,
  `hub/schema/runners.schema.json`, digest-pinned images, rootless podman);
- the evidence machinery (`hub/coherence/evidence.py` sealed bundles,
  `scripts/evidence-validate.py`, HMAC attestation in
  `hub/coherence/attest.py`).

The two owner decisions carried from the draft's walk-through (Q11.1
per-instance bundle-declared ownership; Q11.2 self-hosted-vs-hosted as a
downstream consequence of the CI platform, with the two-axes terminology
note) are locked into `design.md` below, unchanged in substance.

## What Changes

- **Sprint 0 — instance discovery.** Document the lab GitLab instance
  (version, URL, auth shape, network posture: tailnet-only), pin it, and
  restore-test its backup before any gate work depends on it. Discovery
  gates everything else.
- **GitLab runner standard.** Mirror the GitHub fleet's runner contract:
  rootless podman, digest-pinned images, fail-closed registration — the
  same standard `scripts/runner-enroll.sh` and `hub/schema/runners.schema.json`
  already express, extended with a forge field rather than forked.
- **Mirrored CI templates.** `templates/gitlab-ci/` ships one GitLab CI
  include per GitHub workflow template, 1:1 across the shipped set, each a
  thin launcher invoking the identical gate script the GitHub template
  invokes. No gate logic lives in either template family.
- **Forge adapter in the hub.** `hub/forge/` (new): the only component that
  talks the GitLab API (webhooks, auth, repo walk). The fleet declaration
  walk (`secret-scan-declared.sh` pattern) gains GitLab sources; evidence
  from GitLab runs lands in the same sealed-bundle format
  (`hub/coherence/evidence.py`) with `forge` as a metadata field.
- **Parity drill.** A seeded-failure corpus pushed to both forges must
  produce identical findings (gate, rule, severity, file evidence). The
  drill is blocking in CI and runs forever after — it is the definition of
  done for this package.

## Product boundary

This adds a forge, not new gates. Gate logic is forge-neutral and shared;
only webhooks, auth, CI template syntax, and API surfaces are
forge-specific. Forge-specific verdict behavior is a defect by definition.
GitLab instance administration beyond backup verification is out of scope.
The existing GitHub surface (including self-hosted runners — what the fleet
runs today) is not rewritten or regressed by this package.

## Impact

- New: `templates/gitlab-ci/`, `hub/forge/`, parity-drill harness + seeded
  corpus, runner-standard extension.
- Modified: fleet declaration walk (GitLab sources), runners schema (forge
  field), CI (parity drill job).
- Specs: two delta specs added (`specs/forge-parity/`,
  `specs/instance-and-runner/`) with `GLF-` requirement IDs.
- No change to any gate script's verdict behavior; that is the point.