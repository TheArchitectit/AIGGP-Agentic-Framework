# Proposal: harden-security-boundaries

## Problem

The 2026-09-19 review found security-relevant defects across three layers —
none previously tracked. The coherence service's own threat model says
"repository-supplied content is untrusted", and two of the findings violate it
directly.

**A. Coherence service (trusted boundary violations)**

1. `hub/coherence/package.py:48-61` — package.json `normative_inventory`
   entry `path` values are joined to the package root with no containment
   check (`root_p / path`). A malicious package manifest can name
   `../../../etc/passwd` (or any host path): the service reads it, digests it,
   and errors on digest mismatch — a file-existence oracle and length/prefix
   side channel, plus arbitrary host-file reads inside the evaluator context.
   `manifest._check_safe` already exists for exactly this class and is not
   applied here.
2. `hub/coherence/evaluators.py:181-189` — `_extract` file selectors take
   `Path(subject_root) / path` with no normalization or containment check:
   assertion-supplied selectors can read outside the subject tree (contents
   are matched against `_IDENTITY_RE` and the captured match lands in findings/
   evidence — an exfiltration path into sealed output).
3. `hub/coherence/manifest.py:171-186` — each file is read twice (size from
   `read_bytes()`, digest from `_digest_file()`): a mutation between the reads
   yields an internally inconsistent entry (size from one version, digest from
   another). Read once, hash and count from the same bytes.

**B. Monitor hub (operational security)**

4. `hub/main.py:92-93` — the serve loop calls `server.handle_request()`, which
   blocks in `select()` indefinitely; per PEP 475 the syscall is retried after
   the SIGTERM handler merely sets an Event. **SIGTERM/SIGINT shutdown hangs
   until the next request arrives** — systemd `stop` degrades to timeout-kill
   (SIGKILL), losing the clean-shutdown exit-0 contract documented in
   `main.py:12`.
5. `hub/server.py:142-157` — the `already_enrolled` check runs outside
   `with_registry`'s lock; two concurrent enrolls of the same name can both
   pass and double-register (TOCTOU).
6. `hub/server.py:83-88` — `_read_json` trusts `Content-Length` with no cap;
   a single unauthenticated request can force a multi-GB read (memory DoS) if
   the bind is ever widened beyond loopback. Same family: no per-IP/overall
   rate budget on `/enroll` token attempts.
7. `hub/registry.py:134-140` — revocation keeps the `heartbeat_token` value
   at rest; registry stores raw token strings (external-audit-2026-09-14 LOW,
   still true). Hash-at-rest (per-runner salt or keyed HMAC) cuts volume-read
   blast radius; `tokens.verify`'s constant-time contract can be preserved.
8. `hub/monitor.py` correctness feeding security signal:
   `run.get("run_id", "?")` (line 252) is not a GitHub API field (it is `id`),
   so queue-stall alerts all dedupe to key `("?")`; `watched_branches`
   defaults to `["default"]` (config.py:44), which is not a real branch name,
   so `_check_gate_results` silently 404s on a default deployment; and
   `get_with_backoff` reads `Retry-After` from the JSON body (line 95) where
   GitHub sends it as an HTTP header — backoff is always the exponential
   default. Monitoring gaps are security gaps for a dead-man switch.
9. `hub/monitor.py:152` — the poll thread reads `registry.runners()` while
   HTTP threads mutate and save under `HubState._lock`; iteration during
   `save()` can raise (threading contract is undocumented).

**C. Shipped templates (consumer security)**

10. `templates/github-workflows/secret-validation.yml:40-42` — third-party
    `gitleaks/gitleaks-action@v2` referenced by mutable tag AND granted
    `secrets.GITHUB_TOKEN`. All template actions are mutable-tag; the live
    repo SHA-pins checkout but not `setup-node@v4` (drift-scan.yml:34).
11. `scripts/runner-enroll.sh:228-242` — JSON payload built by string
    interpolation (a quote/backslash in a label or alias yields a malformed
    or hostile payload), the hub response **including the heartbeat token is
    echoed to stdout** (leaks into terminal scrollback/CI logs), and the
    heartbeat curl has no `--max-time` (a hung hub wedges the oneshot unit).
12. Quadlet secrets documentation is internally contradictory and unparseable
    as written (`templates/runner-monitor/devgate-hub.container:16-19` raw
    env-file drop-in vs `self-hosted-runner.container:36-38` vs
    `templates/runner/README.md:42` vs `add-a-runner.md:43-55`, which cites an
    `EnvironmentFile=` the shipped quadlet does not declare); the runner
    template ships `Image=...actions-runner:latest` (line 25) while its own
    header says "pin a digest"; `templates/runner-monitor/Containerfile` uses
    unpinned `python:3.12-slim`.

## Solution

Apply `manifest._check_safe`-style containment to every repository-supplied
path (inventory entries, selector paths), single-read file hashing, a
request-size cap and locked enroll check, `serve_forever()`/`shutdown()` (or
`timeout=1`) for signal-safe shutdown, corrected monitor field names and
defaults, hashed-at-rest tokens, SHA-pinned template actions with a documented
gitleaks pin, escaped JSON via `python3 -j json.tool`-style construction or
jq-less printf templates, token-silent enroll output, bounded curls, one
canonical quadlet-secrets mechanism, and digest-pinned template images. Each
fix carries a behavioral test (containment rejection, shutdown completes under
signal, oversized body rejected, hashed-token verify still constant-time).

## Impact

- `hub/coherence/{package,evaluators,manifest}.py`; `hub/{main,server,registry,
  monitor,config}.py`; `scripts/runner-enroll.sh`;
  `templates/github-workflows/*.yml` (pinning), `templates/runner*/*`.
- Tests: containment, signal-shutdown, body-cap, monitor fixtures.
- Spec deltas: MODIFIES coherence `package-resolution` + `assertions-and-
  evaluators` containment requirements and hub `hub-architecture` /
  `enrollment-and-alerting` deltas (added under this change's specs/).
