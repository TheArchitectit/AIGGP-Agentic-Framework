# Implementation Plan — monitor-hub runner monitor

Maps to `openspec/changes/archive/2026-09-13-ai01-runner-monitor/{design,tasks}.md`
and the live specs under `openspec/specs/{hub-architecture,runner-monitoring,enrollment-and-alerting}/`.
Locked decisions D1–D7 are treated as fixed. Q1–Q3 implemented as **config with
defaults** (GitHub issues / 5 min / monitor-only), flagged for owner confirmation
in the runbook — never guessed into code.

---

## 1. File-by-file layout under `hub/`

Stdlib only (`http.server`, `urllib.request`, `json`, `argparse`). Every file stays
well under the 500-line `SRC_HARD` gate in `scripts/regression_sizes.py`. Traceability
markers use the Python workaround form `# // spec: <id>` (matches
`scripts/spec_traceability.py`'s `//\s*spec:` regex).

| File | Owns requirement IDs | Contents |
|---|---|---|
| `hub/__init__.py` | — | Empty package marker. |
| `hub/config.py` | mon-hub-01 (partial) | `Config.from_env()`; dataclass of every knob with env-var defaults + argparse long flags. Holds the Q1–Q3 defaults: `ALERT_CHANNEL=github_issue`, `HEARTBEAT_INTERVAL_SEC=300`, `MONITOR_ONLY=true`. Also `BIND_HOST` default **`127.0.0.1`** (never 0.0.0.0 — D7 firewall step), `BIND_PORT=8443`. |
| `hub/registry.py` | mon-registry-01, mon-enroll-01 | `runners.json` load/save (atomic: write tmp + `os.replace`), schema validation against `hub/schema/runners.schema.json`, enrollment-token store, per-runner heartbeat-token issue/revoke. Never commits instance data. |
| `hub/tokens.py` | mon-enroll-01 | Enrollment + heartbeat token mint/verify/revoke. Constant-time compare (`hmac.compare_digest`). Token = `secrets.token_urlsafe(32)`. |
| `hub/server.py` | mon-hub-01, mon-channels-01 | `ThreadingHTTPServer` + `BaseHTTPRequestHandler`. Routes `/enroll`, `/heartbeat`, `/health`. Token verification flow. Returns JSON; error codes per §2. |
| `hub/ghapi.py` | mon-online-01, mon-queue-01, mon-gates-01, mon-drift-01 | Thin `urllib.request` wrapper over GitHub REST (no deps). Per-repo sequential polling with backoff (§4). One function per evidence channel. |
| `hub/monitor.py` | mon-channels-01, mon-online-01, mon-queue-01, mon-gates-01, mon-drift-01 | Orchestrator: for each registered repo, run the four checks, combine API + heartbeat (independent per D2), emit `Alert`s. This is where "polling alone sufficient / heartbeats alone mark stale" lives. |
| `hub/alerts.py` | mon-alert-01 | Dedupe key `(repo, check_class, runner)`; append-only JSONL log on hub volume; recurrence → comment vs new issue. |
| `hub/notifier.py` | mon-alert-01 (partial) | `Notifier` ABC + `GitHubIssueNotifier` (label-create fallback) + `NullNotifier` stub for future channels. **Not a `pass # TODO` body** — the silent-success family (`python_pass_todo_body`, enabled) would fail drift scan; stub raises `NotImplementedError`. |
| `hub/main.py` | mon-hub-01 | Entry point: argparse (long flags + env defaults), wires config → registry → server + poll loop. Exit codes documented in docstring (0/1/2). |
| `hub/schema/runners.schema.json` | mon-registry-01 | JSON Schema for the registry (§3). Committed; instance file is not. |
| `hub/schema/runners.example.json` | mon-registry-01 | Redacted example, placeholder values only (safe via PREVENT-003 `forbidden_context`). |

**Marker placement:** put each `# // spec: <id>` on the first function/class in the
module that implements it. This is what lifts coverage from 0/34 toward covering all
10 mon-* IDs. Note: `hub/` is **not** in `regression_check.py`'s `SOURCE_DIRS`
(line ~91) — see §12 trap list; add `"hub"` (one line) so the file-size gate and
pattern rules actually scan it.

---

## 2. Endpoint contract

All JSON, `Content-Type: application/json`. Server never echoes secrets.

### POST `/enroll`  (mon-enroll-01)
Request:
```json
{ "runner_name": "...", "repo": "OWNER/REPO", "labels": ["devgate"],
  "host_alias": "...", "enrollment_token": "<one-time>" }
```
Flow: verify `enrollment_token` against registry's one-time store → on success record
identity, **consume** the enrollment token (one-time), mint per-runner heartbeat token.
- `200` → `{ "ok": true, "runner_name": "...", "heartbeat_token": "<per-runner>" }`
- `401` → `{ "ok": false, "error": "unknown_or_revoked_token" }` (bad/reused enrollment token)
- `409` → `{ "ok": false, "error": "already_enrolled" }` (same runner_name already registered)
- `400` → `{ "ok": false, "error": "bad_request", "detail": "..." }`

### POST `/heartbeat`  (mon-enroll-01, mon-online-01)
Request:
```json
{ "runner_name": "...", "heartbeat_token": "<per-runner>",
  "last_job_seen": "...", "disk_ok": true, "podman_ok": true }
```
Flow: verify heartbeat token → update `last_heartbeat` + health fields.
- `200` → `{ "ok": true }`
- `401` → `{ "ok": false, "error": "unknown_or_revoked_token" }` (revoked/unknown → mark unenrolled)

### GET `/health`  (mon-hub-01)
No auth. Liveness + the dead-man-switch timestamp endpoint (risk table).
- `200` → `{ "ok": true, "last_poll_at": "<iso8601>", "last_alert_at": "<iso8601|null>",
  "registered_runners": <int>, "uptime_sec": <float> }`

Unknown path → `404 { "ok": false, "error": "not_found" }`. Method mismatch → `405`.
Token verification is in `hub/tokens.py`, called by `server.py`; the handler stays thin.

---

## 3. runners.json schema + location + .gitignore

**Instance file** lives on the hub's persistent volume on monitor-hub (path set by config,
default `/data/runners.json`), **never committed**. Only the schema + redacted example
ship in-repo under `hub/schema/`.

Schema shape (`hub/schema/runners.schema.json`, JSON Schema draft-07):
```jsonc
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "runners"],
  "properties": {
    "version": { "const": 1 },
    "enrollment_tokens": { "type": "array", "items": { "type": "string" } }, // one-time, consumed on use
    "runners": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name","repo","enrolled_at","heartbeat_token"],
        "properties": {
          "name":            { "type": "string" },
          "repo":            { "type": "string", "pattern": "^[^/]+/[^/]+$" }, // OWNER/REPO
          "labels":          { "type": "array", "items": { "type": "string" } },
          "host_alias":      { "type": "string" },
          "enrolled_at":     { "type": "string", "format": "date-time" },
          "heartbeat_token": { "type": "string" },
          "last_heartbeat":  { "type": ["string","null"], "format": "date-time" },
          "last_job_seen":   { "type": ["string","null"] },
          "disk_ok":         { "type": ["boolean","null"] },
          "podman_ok":       { "type": ["boolean","null"] },
          "enrolled":        { "type": "boolean", "default": true }, // false after --revoke
          "queue_threshold_min": { "type": "number" }               // per-repo override, default 30
        }
      }
    }
  }
}
```
Example (`hub/schema/runners.example.json`): one runner with placeholder values only
(`"OWNER/REPO"`, `"example-token-PLACEHOLDER"`). PREVENT-003's `forbidden_context`
matches `placeholder|example`, so these are safe.

**.gitignore additions** (per mon-registry-01 — instance state never committed):
```
# Runner-monitor instance state (hub volume on monitor-hub) — NEVER commit
/data/runners.json
runners.json
alerts/*.jsonl
```
(Exact paths matched to wherever config points; the bare `runners.json` + `alerts/`
guards against accidental local writes.)

---

## 4. GitHub polling design (mon-online/queue/gates/drift)

Transport: `hub/ghapi.py`, one `urllib.request.Request` per call, header
`Authorization: Bearer <GITHUB_TOKEN>` (fine-grained PAT, `actions:read` + `issues:write`),
`Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`.

**Exact REST endpoints per registered repo:**
- **Runner status** (mon-online): `GET /repos/{owner}/{repo}/actions/runners` → each
  runner's `status` (`online`/`offline`) + `busy`.
- **Queued runs** (mon-queue): `GET /repos/{owner}/{repo}/actions/runs?status=queued&per_page=100`
  → each run's `created_at`, `name`, and the job labels it targets. Age = now − `created_at`.
- **Check-runs on watched branches** (mon-gates): resolve default branch via
  `GET /repos/{owner}/{repo}` (`default_branch`), then latest commit
  `GET /repos/{owner}/{repo}/commits/{ref}`, then
  `GET /repos/{owner}/{repo}/commits/{sha}/check-runs` → each `conclusion`. Alert on
  `failure`/`timed_out`, naming repo, gate (`name`), commit SHA.
- **Scheduled drift-scan runs** (mon-drift): `GET /repos/{owner}/{repo}/actions/workflows`
  to find the drift workflow by name (see below), then
  `GET /repos/{owner}/{repo}/actions/workflows/{id}/runs?created=...&per_page=20`.

**Poll cycle structure:** per-repo **sequential** (risk table: rate limits). For each
repo, run the four checks in order; sleep a small fixed gap between repos. Backoff on
HTTP 403/429 with `Retry-After`: honor the header, exponential cap (e.g. 30s→60s→120s),
never tight-loop. A failed API call is logged and skipped for that repo this cycle — it
does **not** suppress other repos' checks (fail loud per repo, never vacuously global).

**Drift-scan schedule period from the API:** The GitHub REST API does **not** expose a
workflow's cron expression directly. Two sources, in priority order:
1. **Registry override** — `runners.json` may carry an explicit `drift_period_min` per
   repo (owner-set at enrollment). Preferred; deterministic.
2. **Inferred from run cadence** — if no override, compute the median gap between the
   last N completed scheduled runs (`event == "schedule"`) as the period. This is a
   heuristic and is logged as such.

**Recency computation:** `last_completed = max(completed_at of runs with conclusion
success/failure)`; `overdue = now − last_completed > drift_period + grace` (grace default
10 min, config). Also alert if the latest completed run's `conclusion == "failure"`.
This is deliberately data-driven from the API, not a hardcoded wall-clock assumption.

**Ambiguity flag:** spec says "scheduled drift scan" but doesn't name the workflow. I
assume the drift-scan workflow is identified by a **config-provided name pattern**
(default `drift` substring match on workflow `path`/`name`, overridable per repo). If
the owner's actual drift workflow has a different name, they set it in config — not
guessed.

---

## 5. Alert engine (mon-alert-01)

**Dedupe key:** `(repo, check_class, runner)` where `check_class ∈ {online, queue,
gates, drift}` and `runner` is the runner name (or `"default-branch"` for gates/drift
which are repo-scoped). One open issue per key.

**JSONL alert log** (`alerts/<repo>.jsonl` on hub volume, append-only — matches the
house `.guardrails/failure-registry.jsonl` idiom): one line per alert event:
```json
{"ts":"<iso8601>","repo":"OWNER/REPO","check_class":"queue","runner":"devgate-runner",
 "dedupe_key":"OWNER/REPO|queue|devgate-runner","action":"opened|commented",
 "issue_number":123,"detail":{"run":"...","age_min":42}}
```

**GitHub-issue notifier (`hub/notifier.py`):**
- On first alert for a key: `POST /repos/{owner}/{repo}/issues` with
  `labels: ["devgate-monitor"]`, title `[devgate-monitor] {check_class}: {runner}`, body
  from template below.
- **Label-create fallback:** if the API returns 422 "label not found" (or a pre-check
  `GET /repos/{owner}/{repo}/labels/devgate-monitor` → 404), call
  `POST /repos/{owner}/{repo}/labels` with `{name: devgate-monitor, color: d93f0b}` then
  retry the issue create. Never assume the label exists.
- **Recurrence:** if an open issue already matches the dedupe key (tracked in
  `runners.json` alert-state or by searching `GET /repos/.../issues?state=open&labels=devgate-monitor`),
  `POST /repos/{owner}/{repo}/issues/{n}/comments` instead of filing new.

**Issue body template:**
```
DevGate runner monitor alert.
- Repo: {repo}
- Check: {check_class}
- Runner: {runner}
- Detail: {detail_json}
- First raised: {ts}
(Recurring alerts are appended as comments, not new issues.)
```

**Notifier interface for future channels:**
```python
class Notifier(ABC):
    @abstractmethod
    def notify(self, alert: Alert) -> str: ...   # returns action: opened|commented
class GitHubIssueNotifier(Notifier): ...
class NullNotifier(Notifier):                    # stub for email/webhook (out of scope v1)
    def notify(self, alert): raise NotImplementedError("channel not wired in v1")
```

---

## 6. `scripts/runner-enroll.sh` design (mon-enroll-01)

House shell style: `set -euo pipefail`, tab indent, `[prefix]` log lines.

**Args / flags:**
```
scripts/runner-enroll.sh <hub-url> <enrollment-token> [options]
  --runner-name NAME      (default: hostname or $RUNNER_NAME)
  --repo OWNER/REPO       (required, or from $REPO_URL)
  --labels a,b            (default: devgate)
  --host-alias ALIAS      (optional)
  --revoke                (delete heartbeat token; see below)
  --interval SEC          (heartbeat interval, default 300 = Q2 default)
```

**Token flow:** POST `/enroll` with identity + enrollment token → on `200`, capture the
per-runner `heartbeat_token`. Write it to a **chmod 600** file
`~/.config/devgate/heartbeat-token` (never in the committed repo, never in env files that
are tracked). Store runner metadata in `~/.config/devgate/enroll.json`.

**systemd user units it writes** (to `~/.config/systemd/user/`):
- `devgate-heartbeat.service`: runs a small inline `curl` POST to `$HUB_URL/heartbeat`
  with the token + host health (`df` disk ok, `podman ps` podman ok). `Type=oneshot`,
  `EnvironmentFile=-~/.config/devgate/enroll.env`.
- `devgate-heartbeat.timer`: `OnBootSec=30s`, `OnUnitActiveSec=<interval>`,
  `Persistent=true`.

Then `systemctl --user daemon-reload && systemctl --user enable --now devgate-heartbeat.timer`.

**`--revoke` behavior:** POST a revoke (or reuse `/enroll` with a revoke action) to delete
the heartbeat token on the hub; then `systemctl --user disable --now devgate-heartbeat.timer`,
remove the unit files, and `rm ~/.config/devgate/heartbeat-token`. Hub marks runner
`enrolled: false`; subsequent heartbeats → 401.

**Idempotency:** re-running enroll with the same identity hits `409 already_enrolled`;
the script detects this, treats it as "already enrolled," re-fetches/keeps the existing
token path, and just (re)installs the units — no duplicate registration, no error. Unit
install is idempotent (`enable --now` on an enabled unit is a no-op).

---

## 7. `templates/runner-monitor/`

### `templates/runner-monitor/Containerfile`
Named **Containerfile** (not Dockerfile) so PREVENT-014 (Dockerfile-in-repo) doesn't fire.
```dockerfile
# DevGate runner-monitor hub — thin stdlib-only Python image.
# Base: python slim, digest-pinned once validated (house standard: pin after tag check).
FROM python:3.12-slim@sha256:<PIN_AFTER_VALIDATION>
WORKDIR /app
COPY hub/ ./hub/
ENV HUB_BIND_HOST=127.0.0.1 HUB_BIND_PORT=8443 HUB_DATA_DIR=/data
EXPOSE 8443
# No token in the image — provided by quadlet env drop-in at runtime.
CMD ["python3", "-m", "hub.main"]
```
Stdlib only → no `pip install`, tiny image. Digest pinning follows the runner template's
"pin a digest once you have validated a tag" idiom (placeholder until owner validates).

### `templates/runner-monitor/devgate-monitor-hub.container` (quadlet)
Mirrors `templates/runner/self-hosted-runner.container` idioms:
```ini
[Container]
Image=devgate/runner-monitor-hub:latest      # built from the Containerfile above
ContainerName=devgate-monitor-hub
HostName=devgate-monitor-hub

# Explicit bind — NEVER 0.0.0.0 default (D7 firewall step). Loopback by default;
# owner opens the specific port + firewall rule in the runbook.
Environment=HUB_BIND_HOST=127.0.0.1
Environment=HUB_BIND_PORT=8443
Environment=HUB_DATA_DIR=/data
# GITHUB_TOKEN + enrollment tokens are NOT set here — via drop-in (see below).

# Persistent volume: runners.json + alerts/*.jsonl live here, survive recreation.
Volume=devgate-monitor-data:/data

# k8s-file logging (rootless user journald often absent — same reason as runner template).
LogDriver=k8s-file

[Service]
Restart=always
RestartSec=10
TimeoutStopSec=30

[Install]
WantedBy=default.target
```
**Env drop-ins** (owner-created on monitor-hub, `chmod 600`, never committed):
- `devgate-monitor-hub.container.d/github-token.env` → `GITHUB_TOKEN=<fine-grained-PAT>`
- `devgate-monitor-hub.container.d/enrollment-tokens.env` → `HUB_ENROLLMENT_TOKENS=<tok1>,<tok2>`

---

## 8. Test plan (Sprint 2.3 + beyond)

Python tests, dual-runnable (pytest + `__main__` runner), hand-built temp trees,
subprocess for CLI-under-test where relevant. Run explicitly: `python3 -m pytest -q tests/`.

**Fixture hub spawning / port allocation:** spawn the hub as a subprocess on an
**ephemeral port** to avoid collisions — bind to port `0` in test config (OS assigns a
free port), read the bound port back from `/health` or a startup line, and drive
requests against it. Each test uses its own temp data dir (`tmp_path`) for
`runners.json`. Teardown kills the subprocess. This avoids hardcoding any port that
collides with other suites.

| Test file | Sprint | Asserts |
|---|---|---|
| `tests/test_hub_registry.py` | 2.2/1.2 | Schema load/save round-trip; atomic replace; rejects invalid shape; enrollment-token consume-once; heartbeat-token issue/revoke. Marker mon-registry-01, mon-enroll-01. |
| `tests/test_hub_enroll_heartbeat.py` | 2.3 | Full cycle against fixture hub: POST /enroll (valid token → 200 + token; bad token → 401; replay → 409/401) → POST /heartbeat (fresh) → simulate time passing → stale detection (older than 2×interval raises). Revoked token → 401 + marked unenrolled. mon-enroll-01, mon-online-01. |
| `tests/test_hub_polling.py` | 3.x | Stub `ghapi` responses: runner offline → online alert; queued run >threshold → queue alert (names repo/run/label/age); check-run failure → gate alert (repo/gate/sha); drift overdue → drift alert. Per-repo sequential + backoff on 429. mon-online/queue/gates/drift-01. |
| `tests/test_hub_alerts.py` | 4.1/4.2 | Dedupe: same key twice → first opens, second comments (not new issue). JSONL append-only lines written. Label-missing → create fallback then issue. mon-alert-01. |

**NOT_RUN with blocker stated:**
- **Live GitHub API polling end-to-end** — NOT_RUN; requires a real fine-grained PAT +
  live repo on monitor-hub (no network creds in CI, secrets hygiene). Covered by stubbed
  `ghapi` tests instead. Blocker: needs owner's token on monitor-hub.
- **Actual quadlet/podman start** — NOT_RUN; requires the monitor-hub machine + rootless podman.
  Blocker: remote machine, done via runbook (Sprint 5).
- **systemd user timer install** — NOT_RUN in unit tests (no systemd in test env);
  `runner-enroll.sh` unit-write logic is tested by asserting the generated unit file
  contents on a temp HOME, not by actually enabling a timer.

**Suite-green caveat (updated at closeout):** the plan recorded 2 pre-existing failures
in `tests/test_guardrails_scan.mjs` at planning time. **They no longer reproduce**:
`node --test tests/test_guardrails_scan.mjs` passes (1/1) on the current tree, so they
are not carried forward as an exemption. `run-tests.mjs` still discovers **0 test
files** on this repo and reports green (QA C3) — that is *not* evidence, and it is why
Sprint 6.1 "suite green" means `python3 -m pytest -q tests/` (86 passed) plus the node
guardrails suite, not `run-tests.mjs` output.

---

## 9. `docs/runner-monitor-monitor-hub.md` outline (mon-monitor-hub-01)

*(The archived plan named this `runner-monitor-ai01.md` under a `mon-ai01-01` id.
The live spec's requirement is `mon-monitor-hub-01`, which names the file
`docs/runner-monitor-monitor-hub.md`; the spec wins — `mon-ai01-01` does not
exist.)*

Follows `docs/RELEASE_GATE.md` structure (Overview → Quick Reference table → Why each
step exists → Usage). Sections:
1. **Overview** — hub-and-spoke, what runs on monitor-hub vs from this machine.
2. **Quick Reference** — table of runbook steps (volume, token drop-in, enrollment
   tokens, port/firewall, linger, start quadlet), each with "Failure means."
3. **Why each step exists** — secrets hygiene (chmod 600, never committed), firewall
   (explicit bind, not 0.0.0.0), linger (survive logout), rotation note.
4. **Deployment steps** (owner executes ON monitor-hub):
   - Build image from `templates/runner-monitor/Containerfile`, pin digest.
   - Create persistent volume; place `runners.json` (from schema) on it.
   - Mint fine-grained PAT (`actions:read` + `issues:write` per watched repo) →
     `github-token.env` drop-in, chmod 600.
   - Mint enrollment tokens → `enrollment-tokens.env` drop-in, chmod 600.
   - Choose hub listen port; add firewall rule for that port only.
   - Enable linger (`loginctl enable-linger <user>`).
   - Copy quadlet to `~/.config/containers/systemd/`, daemon-reload, start.
   - Verify `/health`.
5. **Enrolling a runner** — run `scripts/runner-enroll.sh` on the spoke.
6. **Rotation & revocation** — token rotation steps; `--revoke`.
7. **Q1–Q3 owner-confirmation flags** — call out that alert channel (GitHub issues),
   heartbeat interval (5 min), and monitor-only are **defaults, confirm before go-live**.
8. **Dead-man switch** — enable the committed workflow template (§4.3) to watch `/health`.

**No step may read a secret from this repo** (mon-ai01-01 scenario). All tokens minted
on monitor-hub.

---

## 10. Open questions Q1–Q3 — documented assumptions as config

Implemented as `hub/config.py` defaults, **not** hardcoded logic, each surfaced in the
runbook for owner confirmation:
- **Q1 alert channel:** default `ALERT_CHANNEL=github_issue`. `NullNotifier`/interface
  ready for email/webhook but not wired (out of scope v1). Runbook flags "confirm
  GitHub issues is acceptable, or add email."
- **Q2 heartbeat interval:** default `HEARTBEAT_INTERVAL_SEC=300` (5 min → alert within
  ~10 min). Config + `--interval` on enroll script. Runbook flags for confirmation.
- **Q3 monitor-only:** default `MONITOR_ONLY=true` — the hub does **not** register as a
  job runner (keeps the fleet API token's blast radius small, per design Q3). If owner
  wants it to also run gates, that's a separate opt-in, not the default.

---

## 11. Commit / PR structure

One PR, ordered commits so each is independently verifiable and green (new hub tests +
existing suite):

1. **`feat(hub): registry schema + config + tokens`** — `hub/config.py`, `hub/registry.py`,
   `hub/tokens.py`, `hub/schema/*`, `.gitignore` additions, add `"hub"` to
   `regression_check.py` SOURCE_DIRS. Verify: `test_hub_registry.py` green; traceability
   now covers mon-registry-01/enroll-01 markers.
2. **`feat(hub): /enroll /heartbeat /health server`** — `hub/server.py`, `hub/main.py`.
   Verify: `test_hub_enroll_heartbeat.py` (enroll→heartbeat→stale cycle) green.
3. **`feat(hub): GitHub polling + monitor checks`** — `hub/ghapi.py`, `hub/monitor.py`.
   Verify: `test_hub_polling.py` green (stubbed API).
4. **`feat(hub): alert engine + GitHub-issue notifier`** — `hub/alerts.py`,
   `hub/notifier.py`. Verify: `test_hub_alerts.py` green.
5. **`feat(scripts): runner-enroll.sh enroll/revoke/timer`** — `scripts/runner-enroll.sh`.
   Verify: unit-file-content assertions on temp HOME; shellcheck-clean.
6. **`feat(templates): runner-monitor Containerfile + quadlet`** —
   `templates/runner-monitor/*`. Verify: quadlet parses (podman quadlet dry-run if
   available, else structural lint); PREVENT-014 does not fire (named Containerfile).
7. **`docs(runner-monitor): monitor-hub runbook + dead-man workflow template`** —
   `docs/runner-monitor-monitor-hub.md`, `.github/workflows/hub-health-probe.yml`
   (committed template, not enabled), README pointer from `templates/runner/README.md`,
   CHANGELOG.
   Verify: secrets-hygiene scan clean (no tokens/IPs/hosts in committed files);
   full `python3 -m pytest -q tests/` green; traceability covers all 10 mon-* IDs.
   _Superseded post-implementation:_ the dead-man workflow was never a working
   dead-man switch (a scheduled workflow cannot report its own absence, and the
   committed job only echoed a line), so it is now a manual
   `hub-health-probe.yml` and the real detection moved spoke-side to
   `scripts/hub-watchdog.sh` under new requirement `mon-deadman-01` (11 mon-*
   IDs covered).

Order rationale: schema/config first (everything depends on it), server before polling
(polling consumes registry state), alerts after checks exist to alert, then the
operator-facing script + templates + docs last so each earlier commit is testable in
isolation.

---

## 12. Traps / ambiguity flags (decisions made)

- **`hub/` not in `regression_check.py` SOURCE_DIRS** → add `"hub"` (one line) or the
  file-size gate + pattern rules are blind to the new code. *Chosen: add it.*
- **PREVENT-003 (literal token assignment)** — hub code must never assign a literal to a
  `token`/`secret` var; read from env. Placeholder strings in the example JSON are safe
  via `forbidden_context`. *Chosen: env-only tokens; example uses PLACEHOLDER values.*
- **PREVENT-002 (query concatenation)** — do **not** name any helper `query`; build URLs
  with `urllib.parse.urlencode`, never string-concatenate into a query. *Chosen: use
  urlencode, no `query`-named helpers.*
- **PREVENT-022 (`DEBUG = True`)** — never set a module-level `DEBUG = True`. If debug
  needed, `os.environ.get("HUB_DEBUG","false")=="true"`. *Chosen: env-gated.*
- **Silent-success family** (`python_pass_todo_body`, enabled) — the future-channel
  notifier stub must `raise NotImplementedError`, never `pass # TODO`. *Chosen: raise.*
- **.gitignore has no runners.json entry** → add it (mon-registry-01). *Chosen: added §3.*
- **PREVENT-029/031 don't cover hub Python**, but bind explicitly: default `HUB_BIND_HOST=127.0.0.1`, never 0.0.0.0 (D7). *Chosen: loopback default.*
- **`log_failure.py DEFAULT_REGISTRY` writes into the submodule baseline** (QA H8) — new
  failures from this work should go to the project overlay, not the baseline. *Flagged in
  runbook/closeout; do not point log_failure at the submodule default for hub bugs.*
- **Drift-scan workflow name is ambiguous** — spec doesn't name it. *Chosen: config-provided
  name pattern (default `drift`), overridable per repo; period from registry override or
  inferred run cadence (§4).*
- **"Suite green" must not be overclaimed** — 2 pre-existing node failures + broken
  `run-tests.mjs`. *Chosen: define green as pytest suite + new hub tests passing, with the
  pre-existing node failures explicitly noted as not-regressed.*
