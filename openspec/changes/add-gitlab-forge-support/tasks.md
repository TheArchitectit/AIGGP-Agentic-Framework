# Tasks: add-gitlab-forge-support

- [ ] Sprint 0 (instance discovery): document the lab GitLab (version, URL, auth shape, tailnet posture); backup/restore drill; pin version. Hard gate — nothing below starts until this is evidenced.
- [ ] Sprint 1 (runner standard): extend `scripts/runner-enroll.sh` + `hub/schema/runners.schema.json` with a forge field; rootless podman GitLab runners; digest pinning; fail-closed registration.
- [ ] Sprint 2 (templates): create `templates/gitlab-ci/`; mirror every template in `templates/github-workflows/` (seven at writing time) as thin includes over the shared scripts; add the mirror-count check.
- [ ] Sprint 3 (forge adapter): `hub/forge/` — webhooks (secret-verified), auth, API walk; extend the fleet declaration walk with GitLab sources; evidence through the shipped sealed-bundle format with `forge` metadata.
- [ ] Sprint 4 (parity drill): seeded-failure corpus; run on both forges; identical-findings gate; make the drill blocking in CI.
- [ ] Sprint 5 (hardening): monitoring, docs, external-instance configuration guide; per-instance ownership declaration (GLF-13) shipped as deployer config.

## Verification

- Parity drill green in CI on a pinned corpus version (GLF-01).
- `scripts/evidence-validate.py` accepts GitLab-emitted bundles with `forge` metadata (GLF-03).
- Runner-standard check fails a tag-pinned GitLab runner image (GLF-11).
- Mirror-count check fails when the two template families differ (GLF-12).
- Adapter refuses an undeclared instance; GitLab.com off by default (GLF-13).
- Backup restore drill evidenced before any gate dependency (GLF-10).