# GitLab Forge Support

Status: the adapter, deployer configuration, API walk, fleet-source merge,
monitoring, and the pinned parity drill ship in this repository. **No live
GitLab instance has been discovered or contacted.** Sprint 0 of
`openspec/changes/add-gitlab-forge-support` is still an operator-supplied hard
gate, so nothing here is evidence that gates run on a GitLab instance.

This guide is the external-instance configuration guide named by Sprint 5. It
never names a real instance, owner, backup path, or token.

## What ships

- `hub/forge/adapter.py` — constant-time webhook verification, diff-context
  extraction, and status payloads for GitHub and GitLab.
- `hub/forge/api.py` — the only component that talks the GitLab REST API.
  Authenticated project walk with `X-Next-Page` pagination.
- `hub/forge/instance.py` — instance declaration, backup/restore drill
  validation, runner image digest pin, CI template mirror check.
- `hub/forge/deployment.py` — parses deployer configuration and binds an
  adapter to a **declared** instance. Undeclared instances are refused.
- `hub/forge/fleet.py` — merges GitLab project URLs into the fleet scan
  declaration consumed by `scripts/secret-scan-fleet.sh`.
- `hub/forge/monitor.py` — declaration-level audit (owner, cadence, version,
  backup-drill evidence, hosted opt-in).
- `hub/forge/parity.py` + `scripts/forge_parity_drill.py` — the pinned,
  blocking parity drill over real gates.
- `templates/gitlab-ci/` — one digest-pinned GitLab CI include per GitHub
  workflow template, each using a shared pinned-checkout bootstrap include.

## Use a GitLab CI mirror

The mirror templates are selectable alongside the GitHub workflows. Consumers
can include one from the AIGGP GitLab project or copy it into their own
repository. In either case, they declare the exact DevGate source commit its
jobs should run.

### Include from the AIGGP GitLab project

Pin the AIGGP template project/ref and the DevGate source commit:

```yaml
include:
  - project: "<AIGGP GitLab project path>"
    ref: "<immutable template ref>"
    file: "/templates/gitlab-ci/guardrails-compliance.gitlab-ci.yml"

variables:
  DEVGATE_SHA: "<40-character lowercase commit SHA>"
```

Each mirror inherits a shared hidden `before_script` through a nested
`include:local`. GitLab resolves that local include in the repository and ref
containing the mirror file, so this include-from-project path does not require
copying the bootstrap helper. See [GitLab `include:local`](https://docs.gitlab.com/ci/yaml/#include-local).

### Copy a mirror into the consumer repository

Copy the selected `templates/gitlab-ci/<mirror>.gitlab-ci.yml` and
`templates/gitlab-ci/includes/devgate-bootstrap.yml` into the same paths in the
consumer repository. Then include the copied mirror locally:

```yaml
include:
  - local: "/templates/gitlab-ci/guardrails-compliance.gitlab-ci.yml"

variables:
  DEVGATE_SHA: "<40-character lowercase commit SHA>"
```

Add `.devgate/` to the consumer's `.gitignore`; do not register DevGate in
`.gitmodules`.

Before any gate command, bootstrap checks the consumer root, requires the
full immutable `DEVGATE_SHA`, fetches that commit to `.devgate/`, verifies
`HEAD`, confirms the checkout root, and checks each mirror's explicitly
declared required files. Malformed pins, failed or partial fetches, wrong
roots, and missing scripts/rules/registries fail setup. Existing incomplete
checkouts are left in place for review and are never reported as passing.

The default source is the public AIGGP GitHub repository. Override
`DEVGATE_SOURCE_URL` only when the consumer uses another approved source. If
private fetch authentication is needed, supply `DEVGATE_GIT_USERNAME` and
`DEVGATE_GIT_TOKEN` as masked, protected GitLab CI variables; the token is
provided through a temporary askpass helper and is not embedded in a URL or
printed. The checkout tests use a local bare synthetic repository only; they
do not require or imply adoption of a live GitLab instance.

## What is blocked

- **Instance discovery and backup/restore drill (Sprint 0, GLF-10).** The
  operator must supply the instance URL, version, auth shape, tailnet
  posture, and a restore-drill report.
- **Two-live-forge parity (Sprint 4, GLF-01).** The local drill proves the
  adapter layer does not alter a verdict; it cannot prove two CI platforms
  agree until a second live forge exists.
- **Live monitoring.** `hub/forge/monitor.py` audits declarations and recorded
  drill reports. It does not open a connection to an instance.

## Configure an external instance

1. Copy `hub/forge/instances.example.toml` to `hub/forge/instances.toml` in the
   deployment, or point `FORGE_INSTANCES_CONFIG` at another file. The shipped
   `instances.toml` declares nothing, so every GitLab instance is refused until
   one is declared.
2. Fill one `[[instance]]` table per self-hosted GitLab. Every field is
   required except `surface` and `ip_repo_visibilities`:

   | Field | Meaning |
   |-------|---------|
   | `instance_id` | Stable id used to bind the adapter |
   | `forge` | Must be `gitlab` |
   | `host_alias` | Internal hostname; not a public URL in this repo |
   | `service_name` | Instance service name |
   | `owner` | Designated owner identity (GLF-13) |
   | `backup_path` | Absolute backup directory used by the drill |
   | `runner_scope` | `instance-dedicated`, `group-dedicated`, or `repo-scoped` |
   | `default_visibility` | `private` or `internal` |
   | `tls_valid` | Must be `true`; a failed TLS health check blocks the instance |
   | `security_patch_cadence_days` | Positive integer (GLF-13) |
   | `upgrade_cadence_days` | Positive integer (GLF-13) |
   | `supported_version` | Adapter-supported GitLab version, e.g. `17.4` |
   | `surface` | `self-hosted` (default) or `hosted` |

   `ip_repo_visibilities` is a table of repository name to `private` or
   `internal`; a public visibility for an intellectual-property repository is
   refused.

3. **GitLab.com is off by default.** It is enabled only by adding a second
   declaration with `instance_id = "gitlab.com"` and `surface = "hosted"`.
   That declaration is the opt-in exposure decision (third-party ingress for
   evidence). A `gitlab.com` id with `surface = "self-hosted"` is refused as
   inconsistent.

4. Provide the access token through the environment as `GITLAB_TOKEN`. Never
   put a token in `instances.toml`, a URL, or a log line. The API client
   refuses a plain-HTTP base URL unless the caller explicitly opts in for a
   tailnet-only instance, and refuses a URL carrying userinfo.

5. Run the backup/restore drill against a scratch restore and record a
   `BackupDrillReport`; `validate_backup_restore_drill` checks the repository
   commit, merge-request count, and CI-variable digest against pre-backup
   state. Until that report validates, scheduling gate work that depends on
   the instance is blocked and the block names the missing drill evidence.

## Fleet declaration walk

The GitHub half is derived by `scripts/secret-scan-declared.sh`. The GitLab
half is derived from the declared instances and merged by
`scripts/forge-fleet-declared.py`:

```bash
scripts/secret-scan-declared.sh --out gh.txt
GITLAB_TOKEN=... scripts/forge-fleet-declared.py \
  --github-declaration gh.txt --out all.txt
scripts/secret-scan-fleet.sh --declared all.txt --report sweep.json
```

The library form is `build_fleet_declaration(github_urls, declarations,
clients)`. Both refuse three shapes rather than shortening the sweep silently:
a client for an undeclared instance, a declared instance with no walk client,
and an empty merged declaration. The token is read from `GITLAB_TOKEN`
(override with `--token-env`) and is never written to the declaration.

## Parity drill

```bash
python3 scripts/forge_parity_drill.py
```

The corpus is pinned in `hub/forge/corpus.lock.json` (version + SHA-256 +
case ids). Change the corpus deliberately and bump the pin:

```bash
python3 scripts/forge_parity_drill.py --write-lock
```

The drill runs real repository gates (`evidence_claim_check.py`,
`surface_reach_check.py`, `open_item_aging_check.py`,
`secret_rotation_check.py`) against seeded trees, normalizes the outcome
through both forge paths, and fails on any difference in the finding set or in
the pass/fail state. Forge identity stays metadata.

## Monitoring

```python
from hub.forge import audit_deployment
report = audit_deployment(declarations, drill_reports, requested=["gitlab.com"])
```

`report["green"]` is false when a declaration is incomplete, a backup drill is
missing or invalid, or a requested instance is undeclared. This audits
configuration, not a live instance.
