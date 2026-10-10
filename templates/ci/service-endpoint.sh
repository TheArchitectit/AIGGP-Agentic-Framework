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
#   ALLOW_NON_TAILNET if set to 1, permits a non-tailnet host (escape hatch for
#                     a deliberately public endpoint). Default off: the wrapper
#                     enforces that the resolved host is a tailnet address.
#
# Transport policy: CI services are reached over the tailnet ONLY. The wrapper
# therefore fails closed unless the resolved host is in a tailnet range (CGNAT
# 100.64.0.0/10 for the IPv4 fleet). No public address and no stale host can
# leak in through the discovery path.
#
# Exit: 0 prints host:port; 1 fail-closed with a clear stderr message.
set -euo pipefail

HUB_URL="${HUB_URL:-http://100.99.118.48:8443}"
SERVICE_MAP_FILE="${SERVICE_MAP_FILE:-}"
ALLOW_NON_TAILNET="${ALLOW_NON_TAILNET:-0}"

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
endpoint="$(ALLOW_NON_TAILNET="$ALLOW_NON_TAILNET" python3 - "$NAME" "$raw" <<'PY'
import ipaddress
import json
import os
import sys


def _is_tailnet(host):
    """True when host is a tailnet IPv4 address (CGNAT 100.64.0.0/10)."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.version != 4:
        return False
    return addr in ipaddress.ip_network("100.64.0.0/10")


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

# Transport policy: tailnet only unless explicitly overridden.
allow = os.environ.get("ALLOW_NON_TAILNET", "0") == "1"
if not allow and not _is_tailnet(host):
    sys.stderr.write(
        f"service-endpoint: service {name!r} resolved to non-tailnet host "
        f"{host!r}; refusing (set ALLOW_NON_TAILNET=1 to override)\n")
    sys.exit(1)

sys.stdout.write(f"{host}:{port}\n")
PY
)" || exit 1

printf '%s\n' "$endpoint"
