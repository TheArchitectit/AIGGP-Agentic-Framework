# Tasks: harden-security-boundaries

## 1. Coherence path containment (A1-A3)

- [x] 1.1 `package.resolve`: validate each inventory entry's `path` against
       root containment (reuse `manifest._check_safe` semantics); traversal
       attempts are PackageError (exit 30), never reads.
- [x] 1.2 `evaluators._extract`: normalize + contain file-selector paths under
       subject_root; reject `..`/absolute/symlink-escape as Unresolved with a
       stable reason.
- [x] 1.3 `manifest.build`: single read — hash and size from the same bytes
       (stream: update digest and counter from each chunk).
- [x] 1.4 Behavioral tests: hostile inventory path rejected without reading;
       hostile selector cannot exfiltrate a file outside the subject tree
       (assert no host-path content in findings/evidence); mid-run mutation
       still detected by `verify_read`.

## 2. Hub runtime hardening (A4-A9 = B-layer)

- [x] 2.1 `hub/main.py`: signal-safe serve loop (`serve_forever()` +
       `shutdown()` from the handler, or `server.timeout` polling) — SIGTERM
       exits 0 promptly; test with a real signal on a bound ephemeral port.
- [x] 2.2 `server._handle_enroll`: move the duplicate-name check inside the
       registry lock (`with_registry` carries it); concurrency test with two
       simultaneous enrolls → exactly one 409/one 200.
- [x] 2.3 `server._read_json`: cap `Content-Length` (default 1 MiB, env
       override); oversized → 413/400 envelope; negative/absurd lengths
       rejected; test with a large body.
- [x] 2.4 `registry`: store `heartbeat_token` as
       `hmac-sha256:<hex>(key=server-secret, msg=token)` (or per-runner salted
       hash); `verify` stays constant-time; migration reads legacy plaintext
       entries and upgrades on first successful heartbeat. Revocation clears
       the stored verifier.
- [x] 2.5 `monitor._check_queue_drain`: `run.get("id")` (fix dedupe key);
       include `html_url`/`name` in the detail.
- [x] 2.6 `config.watched_branches` default: resolve the repo default branch
       via API when "default" sentinel (or require explicit config + loud
       WARNING when unusable) — the gates check must not silently no-op.
- [x] 2.7 `GitHubClient.get_with_backoff`: read `Retry-After` from the
       HTTPError headers (`e.headers.get("Retry-After")`); guard `.get` on
       dict bodies.
- [x] 2.8 Monitor thread: snapshot `runners()` under `HubState._lock`
       (add a locked accessor); document the threading contract in
       `HubState`.
- [x] 2.9 Dead code removal: `server._parse_ts`, unused `owner` locals in
       monitor (`_check_runner_status`, `_check_queue_drain`).

## 3. Template and spoke hardening (C-layer)

- [x] 3.1 SHA-pin every action in every template + live workflows (checkout,
       setup-node, setup-python, gitleaks — record the gitleaks SHA +
       version in a comment; note the pin-rotation procedure in
       templates/README.md).
- [x] 3.2 `runner-enroll.sh`: build JSON via `python3 - <<PY` heredoc (json.dumps)
       or a strict escaper; never `echo` the raw hub response — extract and
       print only `runner_name`/status, write the token straight to the 0600
       env file; add `--max-time` to every curl including the heartbeat
       ExecStart.
- [x] 3.3 One canonical secrets mechanism across all three runner docs +
       quadlets (pick `EnvironmentFile=` drop-in or quadlet `[Container]
       Environment=`, implement it in the shipped quadlet, fix all three docs
       to match, and verify the documented form actually parses with
       `podman-systemd` CI or a documented manual check).
- [x] 3.4 Pin template images: `actions-runner` by digest;
       `python:3.12-slim-bookworm@sha256:...` in runner-monitor Containerfile;
       add a HEALTHCHECK hitting `/health` (long-running HTTP service).
- [x] 3.5 `detect-host-ci.py`: word-boundary the redaction alternation (drop
       bare `ak|sk`), handle rglob errors, support `*.yaml` workflows.
- [x] 3.6 Tests: enroll payload escaping (label with quote/backslash);
       hub response with token never appears on stdout (assert on captured
       output).

## 4. Registry and advisory

- [x] 4.1 Failure-registry entries for the containment and token-echo classes.
- [x] 4.2 docs/runner-monitor-monitor-hub.md: document the hashed-at-rest
       token format and the body-size cap; reconcile the TLS note.
