# Tasks: add-gitlab-forge-support

> **Status audit 2026-11-13.** Sprints 0–5 were ticked wholesale by `9c46180`
> (2026-11-02) in the same commit that landed the code. Re-checked against the
> tree on 2026-11-13, Sprints 0, 3 (in part), 4 and 5 are **not** complete: the
> instance-dependent work is still blocked, the parity drill does not actually
> exercise gate logic, and the hardening/docs deliverables do not exist. The
> boxes below reflect what is evidenced, not what was claimed.

- [ ] Sprint 0 (instance discovery): document the lab GitLab (version, URL, auth shape, tailnet posture); backup/restore drill; pin version. Hard gate — nothing below starts until this is evidenced.
  - **Blocked on the operator.** Discovery on 2026-10-23 found no self-hosted GitLab instance: the private infra KB lists a GitLab *runner* host only, no server, and no GitLab endpoint responded on the fleet network. Re-checked 2026-11-13 — still no server entry. The operator must supply the instance (URL, version, auth shape, reachability) before this can close.
  - The backup/restore drill has a validator (`hub/forge/instance.py` `validate_backup_restore_drill`) and a synthetic test report; no drill has been run against a real instance.
- [x] Sprint 1 (runner standard): extend `scripts/runner-enroll.sh` + `hub/schema/runners.schema.json` with a forge field; rootless podman GitLab runners; digest pinning; fail-closed registration.
- [x] Sprint 2 (templates): create `templates/gitlab-ci/`; mirror every template in `templates/github-workflows/` (seven at writing time) as thin includes over the shared scripts; add the mirror-count check.
  - Shipped: 10 GitHub workflow templates, 10 GitLab CI mirrors; `hub/forge/instance.py` `verify_gitlab_ci_template_mirrors` fails when a GitHub template has no GitLab mirror or a mirror's image is not `@sha256` pinned, and `tests/test_gitlab_forge_support.py` enforces it in CI. (The walk goes GitHub → GitLab; a stray GitLab-only template is not flagged.)
- [ ] Sprint 3 (forge adapter): `hub/forge/` — webhooks (secret-verified), auth, API walk; extend the fleet declaration walk with GitLab sources; evidence through the shipped sealed-bundle format with `forge` metadata.
  - Shipped: `hub/forge/adapter.py` (constant-time webhook verification, diff-context extraction, status reports for both forges), `forge` metadata in `hub/coherence/evidence.py`, and a `forge` field on runner enrollment (`hub/registry.py`).
  - **Not shipped:** the fleet declaration walk is not extended with GitLab sources, and there is no "refuse an undeclared instance / GitLab.com off by default" guard — `get_forge_adapter("gitlab")` returns an adapter unconditionally (verification item 5 below).
- [ ] Sprint 4 (parity drill): seeded-failure corpus; run on both forges; identical-findings gate; make the drill blocking in CI.
  - Partial: the 5-case seeded corpus and `run_forge_parity_drill` exist and run under `pytest` in CI. But `evaluate_seeded_case` derives pass/fail/rule-ID from the fixture's own flags (`has_secret_marker`, `line_count`, …) instead of running a gate, so both forges agree by construction and the drill cannot detect a real parity divergence. No second live forge exists to run against until Sprint 0 closes.
- [ ] Sprint 5 (hardening): monitoring, docs, external-instance configuration guide; per-instance ownership declaration (GLF-13) shipped as deployer config.
  - Partial: GLF-13 ownership validation exists as a library (`validate_instance_declaration`) with tests. No monitoring, no documentation, and no external-instance configuration guide ship in the tree.

## Verification

- [ ] Parity drill green in CI on a pinned corpus version (GLF-01). — it runs in CI, but the drill is synthetic and cannot fail on a real parity divergence (Sprint 4).
- [x] `scripts/evidence-validate.py` accepts GitLab-emitted bundles with `forge` metadata (GLF-03).
- [x] Runner-standard check fails a tag-pinned GitLab runner image (GLF-11).
- [x] Mirror-count check fails when the two template families differ (GLF-12). — GitHub → GitLab direction only.
- [ ] Adapter refuses an undeclared instance; GitLab.com off by default (GLF-13).
- [ ] Backup restore drill evidenced before any gate dependency (GLF-10).
