#!/usr/bin/env bash
#
# service-endpoint.sh — resolve a CI service endpoint from the fleet at run time.
#
# Usage:
#   service-endpoint.sh <name>        # -> prints "host:port" on stdout
#
# CI must NOT bake literal hosts/IPs into repo variables or workflow files
# (mon-svcdisco-01). Instead a job asks the DevGate hub for the service by its
# stable name; the hub resolves the enrolled runner that provides it.
#
# Env:
#   HUB_URL           base URL of the hub (default http://100.99.118.48:8443)
#   SERVICE_MAP_FILE  optional checked-in fallback map, used only when the hub
#                     is unreachable/unknown. Parsed the same way: the entry for
#                     <name> must carry a literal "host" (and "port"). Without
#                     it, or when the entry is unresolved, the script fails.
#
# Exit: 0 prints host:port; 1 fail-closed with a clear stderr message.
set -euo pipefail

HUB_URL="${HUB_URL:-http://100.99.118.48:8443}"
SERVICE_MAP_FILE="${SERVICE_MAP_FILE:-}"

die() { printf 'service-endpoint: %s\n' "$*" >&2; exit 1; }

if [ "$#" -ne 1 ]; then
  die "usage: service-endpoint.sh <service-name>"
fi
NAME="$1"

# --- fetch the resolved entry from the hub (empty on any failure) ----------
raw=""
if raw="$(curl -fsS --max-time 10 "${HUB_URL}/services/${NAME}" 2>/dev/null)"; then
  :
else
  raw=""
fi

# --- optional checked-in fallback map, only when the hub did not answer -----
if [ -z "$raw" ] && [ -n "$SERVICE_MAP_FILE" ]; then
  if [ -f "$SERVICE_MAP_FILE" ]; then
    raw="$(python3 - "$SERVICE_MAP_FILE" "$NAME" <<'PY'
import json
import sys

path, name = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except (OSError, ValueError):
    sys.exit(0)
entry = (data.get("services") or {}).get(name)
if entry is None:
    sys.exit(0)
print(json.dumps(entry))
PY
)"
  fi
fi

if [ -z "$raw" ]; then
  die "service '${NAME}' unknown or hub unreachable (HUB_URL=${HUB_URL})"
fi

# --- resolve host/port, fail closed on unresolved ---------------------------
endpoint="$(python3 - "$NAME" "$raw" <<'PY'
import json
import sys

name, raw = sys.argv[1], sys.argv[2]
try:
    entry = json.loads(raw)
except ValueError:
    sys.stderr.write(f"service-endpoint: invalid JSON for service {name!r}\n")
    sys.exit(1)

host = entry.get("host")
port = entry.get("port")
resolved = entry.get("resolved")
if resolved is None:
    resolved = host is not None

if not resolved or not host or port is None:
    sys.stderr.write(
        f"service-endpoint: service {name!r} unresolved "
        f"(host={host!r}, resolved={resolved!r})\n")
    sys.exit(1)

sys.stdout.write(f"{host}:{port}\n")
PY
)" || exit 1

printf '%s\n' "$endpoint"
