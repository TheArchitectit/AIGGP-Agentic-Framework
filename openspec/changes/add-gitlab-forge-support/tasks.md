# Tasks: add-gitlab-forge-support

- [ ] Sprint 0 (instance discovery): document the lab GitLab (version, URL, auth shape, tailnet posture); backup/restore drill; pin version. Hard gate — nothing below starts until this is evidenced.
  - **Blocked on the operator: the lab GitLab instance is not identified
    anywhere, and it is not reachable from the fleet tailnet.** Discovery
    attempted 2026-10-23, evidence recorded so it is not redone:
    - `infra-info/hosts.md:255` names only `172.16.30.16` CN `gitlab-runners`
      — the CI *runners*, not the server. No other file in `infra-info`
      mentions GitLab (whole-tree grep).
    - Probe of `172.16.30.16` on 80/443/8080/8929 (http and https): every
      request timed out (`000`, exit 28) — the host is not routable from here.
    - `tailscale status`: no host carries a GitLab name. Probed every online
      fleet node (ai01–ai05, ucs03, dell-u2, localhost-0) for
      `/users/sign_in` on 80/443/8080/8929: only `404`/`400`, plus ai01:80
      `301` → its own `https://` origin (whose `/users/sign_in` is `404`). No
      GitLab sign-in surface.
  - What the operator must supply to unblock: instance URL, version, auth
    shape (token type/scopes), tailnet or subnet reachability, and approval
    for a backup/restore drill. Nothing in Sprint 1–5 is started until then.
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