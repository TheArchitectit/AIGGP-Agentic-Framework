# Tasks: add-gitlab-forge-support

> **Status audit 2026-11-13.** Sprints 0–5 were ticked wholesale by `9c46180`
> (2026-11-02) in the same commit that landed the code. Re-checked against the
> tree on 2026-11-13, Sprints 0, 3 (in part), 4 and 5 are **not** complete: the
> instance-dependent work is still blocked, the parity drill does not actually
> exercise gate logic, and the hardening/docs deliverables do not exist. The
> boxes below reflect what is evidenced, not what was claimed.
>
> **Update 2026-11-15.** Sprint 3 and Sprint 5 were completed hermetically
> (adapter API walk, fleet-source merge, deployer config, monitoring, docs); the
> parity drill now runs real gates and is pinned and blocking in CI. **Still
> open and blocked on the operator:** Sprint 0 (no instance), Sprint 4's live
> two-forge half, GLF-01's two-platform green, and GLF-10's real backup/restore
> drill. No live GitLab instance was contacted.
>
> **OWNER DECISION 2026-11-15 — this re-frames the whole package.** The owner:
> *"we are just adding git lab as a option not swaping to it"* and, on whether
> the option needs proving against a live server, **"b is fine"** — i.e. the
> fixture is enough. GitHub remains the main forge and nothing about it
> changes. GitLab is a second forge you can point at if you happen to run one.
> **It is recorded as SUPPORTED, tested against a fixture, NOT proven live.**
> No server was started. The instance-dependent boxes below are therefore
> **owner-deferred**, not blocked: they close when someone actually wants to
> use GitLab, at which point proving it is a half-hour job. Sprint 0's "hard
> gate — nothing below starts" is superseded by this decision for the
> *hermetic* work (which is already done and stays done) and remains real only
> for the *live* work, which is deliberately not being done now.

- [ ] Sprint 0 (instance discovery): document the lab GitLab (version, URL, auth shape, tailnet posture); backup/restore drill; pin version. ~~Hard gate — nothing below starts until this is evidenced.~~ **DORMANT, not pending — owner decision 2026-11-15.** GitLab is an option on top of GitHub, not a swap, and the fixture is enough: live instance proof is NOT required for the option to ship. This box is not open work; it is a condition that activates only if someone adopts GitLab. It closes when they do.
  - **Blocked on the operator.** Discovery on 2026-10-23 found no self-hosted GitLab instance: the private infra KB lists a GitLab *runner* host only, no server, and no GitLab endpoint responded on the fleet network. Re-checked 2026-11-13 — still no server entry. The operator must supply the instance (URL, version, auth shape, reachability) before this can close. The initial discovery summary is preserved in [PR #33](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/33) as dated provenance; the later owner decision above governs current scope.
  - The backup/restore drill has a validator (`hub/forge/instance.py` `validate_backup_restore_drill`) and a synthetic test report; no drill has been run against a real instance.
  - **Operator-supplied data still missing, exactly (re-checked 2026-11-15):**
    (1) instance base URL and its internal host alias;
    (2) exact GitLab version, to be pinned in `supported_version`;
    (3) auth shape — token type/scopes for API reads and the runner
    registration path, supplied through the environment, never a file;
    (4) tailnet posture — whether every gate runner can reach the instance,
    and whether TLS validates on that path;
    (5) the backup archive location and a completed restore-drill report
    (commit, merge-request count, CI-variable digest) that
    `validate_backup_restore_drill` accepts;
    (6) owner identity plus security-patch and upgrade cadence;
    (7) confirmation of whether `gitlab.com` is in scope (it stays off by
    default until an explicit hosted declaration is supplied).
    No value above is invented here; `hub/forge/instances.toml` ships with
    zero declarations for that reason.
- [x] Sprint 1 (runner standard): extend `scripts/runner-enroll.sh` + `hub/schema/runners.schema.json` with a forge field; rootless podman GitLab runners; digest pinning; fail-closed registration.
- [x] Sprint 2 (templates): create `templates/gitlab-ci/`; mirror every template in `templates/github-workflows/` (seven at writing time) as thin includes over the shared scripts; add the mirror-count check.
  - Shipped: 10 GitHub workflow templates, 10 GitLab CI mirrors; `hub/forge/instance.py` `verify_gitlab_ci_template_mirrors` fails when a GitHub template has no GitLab mirror or a mirror's image is not `@sha256` pinned, and `tests/test_gitlab_forge_support.py` enforces it in CI. (The walk goes GitHub → GitLab; a stray GitLab-only template is not flagged.)
- [x] Sprint 3 (forge adapter): `hub/forge/` — webhooks (secret-verified), auth, API walk; extend the fleet declaration walk with GitLab sources; evidence through the shipped sealed-bundle format with `forge` metadata.
  - Shipped: `hub/forge/adapter.py` (constant-time webhook verification, diff-context extraction, status reports for both forges), `forge` metadata in `hub/coherence/evidence.py`, and a `forge` field on runner enrollment (`hub/registry.py`).
  - **Completed 2026-11-15, hermetically — no live instance contacted.**
    `hub/forge/api.py` is the authenticated GitLab REST client
    (`PRIVATE-TOKEN`, `X-Next-Page` pagination, plain-HTTP and
    credentials-in-URL refused); it is exercised against a local
    `ThreadingHTTPServer` stub by
    `tests/test_gitlab_forge_deployment.py::test_glf02_api_walk_paginates_against_a_local_stub`
    ("local stub, no live instance"). `hub/forge/fleet.py`
    (`build_fleet_declaration`, `walk_gitlab_sources`) merges GitLab project
    URLs into the declaration `scripts/secret-scan-fleet.sh` consumes, refusing
    an undeclared instance, a declared instance with no walk client, and an
    empty declaration. The runnable entry point is
    `scripts/forge-fleet-declared.py`: it takes the GitHub declaration file,
    walks each declared GitLab instance, and writes the merged one-URL-per-line
    file; `test_glf13_fleet_declared_cli_merges_github_and_gitlab` drives it
    through a local HTTP stub (archived projects excluded) and proves an empty
    token is refused with exit 2. Sealed-bundle `forge` metadata was already
    shipped and is pinned by
    `test_glf02_evidence_bundle_records_and_verifies_forge_metadata`. The
    adapter-to-instance binding (`resolve_instance_adapter`) is Sprint 5 /
    GLF-13's refusal guard, below. Live connectivity remains Sprint 0's gate.
- [ ] Sprint 4 (parity drill): seeded-failure corpus; run on both forges; identical-findings gate; make the drill blocking in CI.
  - Partial: the 5-case seeded corpus and `run_forge_parity_drill` exist and run under `pytest` in CI. But `evaluate_seeded_case` derives pass/fail/rule-ID from the fixture's own flags (`has_secret_marker`, `line_count`, …) instead of running a gate, so both forges agree by construction and the drill cannot detect a real parity divergence. No second live forge exists to run against until Sprint 0 closes.
  - **Rebuilt 2026-11-15 (still open on the live half).** The synthetic
    evaluator is gone: each case now runs real repository gates as subprocesses
    (`scripts/evidence_claim_check.py`, `surface_reach_check.py`,
    `open_item_aging_check.py`, `secret_rotation_check.py`) against a seeded
    tree, and the drill fails if a seed no longer trips its gate. The
    GitHub and GitLab paths then normalize that one outcome and must produce an
    identical finding set and the same pass/fail state
    (`assert_finding_parity`); a forge-conditional normalization is detected by
    `test_glf03_drill_detects_a_forge_conditional_normalization`. The corpus is
    pinned (`hub/forge/corpus.lock.json`, version `2026-11-15.1`), the drill is
    a blocking CI step (`python3 scripts/forge_parity_drill.py` in
    `.github/workflows/ci.yml`), and it runs green locally: 5 cases, identical
    findings on both forge paths, exit 0. **Still open:** there is no second
    live forge to run the corpus on. This is adapter-layer parity, not
    two-platform parity.
- [x] Sprint 5 (hardening): monitoring, docs, external-instance configuration guide; per-instance ownership declaration (GLF-13) shipped as deployer config.
  - **Shipped 2026-11-15, hermetically.** `hub/forge/deployment.py` parses and
    validates deployer configuration (`hub/forge/instances.toml`, override
    `FORGE_INSTANCES_CONFIG`) and binds an adapter only to a declared
    instance. `hub/forge/instances.toml` ships with **zero declarations** (a
    fresh deployment refuses every GitLab instance); the filled-in format is
    `hub/forge/instances.example.toml`, using reserved example values only.
    `docs/GITLAB-FORGE.md` is the external-instance configuration guide.
    `hub/forge/monitor.py` audits declarations, cadence/version completeness,
    backup-drill evidence, and hosted opt-in; `audit_deployment` returns
    `green: false` with named findings, and does not claim live probing.
    Ownership is deployer config, never code (GLF-13).

## Verification

- [x] Hermetic adapter/template/interoperability parity remains green on the
  pinned corpus (`hub/forge/corpus.lock.json`, `2026-11-15.1`). Windows tests
  pass 23 cases and the direct drill passes all five expected gate outcomes.
  A Linux temporary copy with shell files normalized to Linux line endings
  also passes 23 cases and the same five-case drill. The host-portable JSON
  seed test covers `corpus-02-surface-divergence` (GLF-14). No live forge was
  contacted.
- [ ] Two-live-forge parity (GLF-01 live half) is optional operator
  acceptance after explicit GitLab adoption. Keep this task open; no two-
  platform green result is claimed.
- [x] `scripts/evidence-validate.py` accepts GitLab-emitted bundles with `forge` metadata (GLF-03).
- [x] Runner-standard check fails a tag-pinned GitLab runner image (GLF-11).
- [x] Mirror-count check fails when the two template families differ (GLF-12). — GitHub → GitLab direction only.
- [x] Adapter refuses an undeclared instance; GitLab.com off by default (GLF-13).
  - Evidenced 2026-11-15: `resolve_instance_adapter("gitlab", id, {})` raises
    `OwnershipValidationError` naming the missing declaration; the shipped
    `hub/forge/instances.toml` declares nothing; `gitlab.com` loads only with
    an explicit `surface = "hosted"` declaration and a mismatched id/surface
    pair is refused; `hosted_surface_enabled` is false for a self-hosted-only
    deployment. Tests: `tests/test_gitlab_forge_deployment.py`
    (`test_glf13_*`). This is configuration-level proof; the adapter is still
    not bound to any live instance.
- [ ] Backup restore drill evidenced before any gate depends on an adopted
  GitLab instance (GLF-10). It is optional operator acceptance before
  adoption; `validate_backup_restore_drill` and `audit_deployment` still
  require real restore evidence before such a dependency is enabled.

**DORMANT SET, 2026-11-18.** Sprint 0, Sprint 4, GLF-01 and GLF-10 are the same
condition: live proof against a real second forge. The owner decided GitLab is
an **option on top of GitHub, not a swap**, and the fixture is enough — live
instance proof is not required for the option to ship. These are not open
work; they are conditions that activate only if someone adopts GitLab. The
hermetic halves (adapter, templates, parity drill over a pinned corpus, the
discovery gate) are landed and green.

**OWNER SCOPE CONFIRMED, 2026-11-25.** The product goal is to support GitLab
alongside GitHub. Selecting or enrolling a real GitLab instance, proving
two-live-forge parity, and conducting a live backup/restore drill are optional
operator acceptance after explicit adoption; none is a prerequisite to ship
the GitLab support option. No live instance, two-forge result, or restore
result is claimed by this decision. Sprint 0, the live half of Sprint 4, and
GLF-10 remain unchecked, adoption-triggered tasks. The hermetic template,
adapter, and parity evidence remains required and is verified separately.
