#!/usr/bin/env bash
# Behavioral tests for scripts/runner-enroll.sh (audit hardening):
#   * the enroll payload is built by json.dumps — quotes/backslashes in labels
#     produce VALID JSON and cannot break out of the string;
#   * the issued heartbeat token never reaches stdout/stderr (it goes only to
#     the 0600 env file);
#   * curl calls are time-bounded (--max-time) so a hung hub cannot wedge the
#     systemd oneshot unit.
#
# Fully sandboxed: HOME and XDG_CONFIG_HOME point into a temp dir, and
# curl/systemctl are stubbed on PATH (no network, no real units installed).
#
# Run: bash tests/test_runner_enroll.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/runner-enroll.sh"

failures=0
check() {
    local name="$1" cond="$2" detail="${3:-}"
    if [ "$cond" = "0" ]; then
        echo "ok - $name"
    else
        failures=$((failures + 1))
        echo "FAIL - $name${detail:+: $detail}"
    fi
}

run_case() {
    local label="$1" extra_labels="$2"
    local tmp stub
    tmp="$(mktemp -d)"
    stub="$tmp/bin"
    mkdir -p "$stub" "$tmp/config"

    # Stub curl: capture argv, emit a canned hub response carrying a token.
    cat > "$stub/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CURL_CAPTURE"
printf '{"ok": true, "runner_name": "r1", "heartbeat_token": "HB-SECRET-TOKEN-42"}'
EOF
    # Stub systemctl: no-op (never touch the real user manager).
    cat > "$stub/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$stub/curl" "$stub/systemctl"

    CURL_CAPTURE="$tmp/curl-args.txt"
    export CURL_CAPTURE
    out="$(
        HOME="$tmp" XDG_CONFIG_HOME="$tmp/config" PATH="$stub:$PATH" \
        bash "$SCRIPT" http://hub.invalid:8443 ENROLL-TOK \
            --repo owner/repo --runner-name r1 \
            --labels "$extra_labels" --host-alias h1 2>&1
    )"
    rc=$?

    check "$label: exit 0" "$([ "$rc" -eq 0 ] && echo 0 || echo 1)" "rc=$rc out=$out"
    check "$label: token never on stdout/stderr" \
        "$(printf '%s' "$out" | grep -q 'HB-SECRET-TOKEN-42' && echo 1 || echo 0)"

    payload="$(python3 - "$CURL_CAPTURE" <<'PY'
import json, sys
args = open(sys.argv[1]).read()
# curl argv is space-joined; the JSON body is the argument after -d.
body = args.split(" -d ", 1)[1].split(" http", 1)[0]
doc = json.loads(body)
print(json.dumps(doc))
PY
    )"
    check "$label: payload is valid JSON" "$([ -n "$payload" ] && echo 0 || echo 1)"

    labels_ok="$(python3 - "$payload" <<'PY'
import json, sys
doc = json.loads(sys.argv[1])
labels = doc.get("labels")
assert isinstance(labels, list), labels
assert doc["runner_name"] == "r1"
assert doc["repo"] == "owner/repo"
assert doc["enrollment_token"] == "ENROLL-TOK"
print("0")
PY
    )"
    check "$label: payload fields correct" "$labels_ok"

    check "$label: curl is time-bounded" \
        "$(grep -q -- '--max-time' "$CURL_CAPTURE" && echo 0 || echo 1)"

    # Per-runner env file (coh-int-07): units and env are name-scoped so a
    # host can enroll several spokes without them clobbering each other.
    envfile="$tmp/.config/containers/devgate-heartbeat-r1.env"
    if [ -f "$envfile" ]; then
        perms="$(stat -c '%a' "$envfile")"
        check "$label: env file is 0600" "$([ "$perms" = "600" ] && echo 0 || echo 1)" "perms=$perms"
        check "$label: token written to env file" \
            "$(grep -q 'HB-SECRET-TOKEN-42' "$envfile" && echo 0 || echo 1)"
    else
        check "$label: env file written" 1 "$envfile missing"
    fi

    rm -rf "$tmp"
    export -n CURL_CAPTURE
}

# --- 1. plain labels ---------------------------------------------------------
run_case "plain-labels" "devgate,linux"

# --- 2. hostile label: quote + backslash must be escaped, not break out ------
run_case "hostile-labels" 'a, b"q\z'

# --- 3. hostile runner name is SANITIZED, not rejected (upstream design) ------
# The slug keeps only characters systemd accepts, so a hostile name yields a
# usable unit AND never corrupts the heartbeat JSON (payload is json.dumps'd).
tmp="$(mktemp -d)"; stub="$tmp/bin"; mkdir -p "$stub" "$tmp/config"
cat > "$stub/curl" <<'STUB'
#!/usr/bin/env bash
if [ -n "${CURL_CAPTURE:-}" ]; then printf '%s\n' "$*" >> "$CURL_CAPTURE"; fi
printf '{"ok": true, "runner_name": "bad-name", "heartbeat_token": "HB-TOKEN"}'
STUB
printf '#!/usr/bin/env bash\nexit 0\n' > "$stub/systemctl"
chmod +x "$stub/curl" "$stub/systemctl"
out="$(HOME="$tmp" PATH="$stub:$PATH" bash "$SCRIPT" http://h.invalid:8443 T \
    --repo o/r --runner-name 'bad"name' 2>&1)"
rc=$?
check "hostile runner name sanitized (enroll proceeds)" \
    "$([ "$rc" -eq 0 ] && echo 0 || echo 1)" "rc=$rc"
check "sanitized slug names the env file" \
    "$(test -f "$tmp/.config/containers/devgate-heartbeat-bad-name.env" && echo 0 || echo 1)" \
    "$(ls "$tmp/.config/containers/" 2>/dev/null)"
rm -rf "$tmp"

echo
if [ "$failures" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "$failures TEST(S) FAILED"
exit 1
