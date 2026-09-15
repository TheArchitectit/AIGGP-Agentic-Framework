"""hub.main — entry point for the DevGate runner-monitor hub.

Usage:
    python3 -m hub.main [--config-from-env]

Environment (see hub/config.py): HUB_BIND_HOST (default 127.0.0.1 — never
0.0.0.0 by default, D7 firewall step), HUB_BIND_PORT (default 8443),
HUB_DATA_DIR (hub volume; runners.json + alerts/ live here), GITHUB_TOKEN
(fine-grained PAT for the polling loop), HUB_ENROLLMENT_TOKENS
(comma-separated one-time tokens loaded into the registry at startup).

Exit codes: 0 clean shutdown (SIGTERM/SIGINT), 1 fatal startup error,
2 usage error. The poll loop starts only when GITHUB_TOKEN is present;
without it the hub serves enrollment/heartbeat/health and logs that polling
is disabled — a monitor with no evidence channel must say so loudly, not
pass vacuously (mon-channels-01).

// spec: mon-hub-01
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time

from .config import Config
from .server import create_server


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hub.main",
        description="DevGate runner-monitor hub (hub-and-spoke fleet monitoring).",
    )
    parser.add_argument("--bind-host", default=None, help="override HUB_BIND_HOST")
    parser.add_argument("--bind-port", type=int, default=None, help="override HUB_BIND_PORT")
    parser.add_argument("--data-dir", default=None, help="override HUB_DATA_DIR")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    config = Config.from_env()
    if args.bind_host:
        config.bind_host = args.bind_host
    if args.bind_port is not None:
        config.bind_port = args.bind_port
    if args.data_dir:
        config.data_dir = args.data_dir

    server = create_server(config)
    state = server.hub_state  # type: ignore[attr-defined]

    # Load one-time enrollment tokens from the env drop-in (never committed).
    # // spec: mon-monitor-hub-01 — the credential half of the requirement: hub
    # secrets are env-only, so no committed file carries a token. The runbook
    # half (machine duties documented off-repo) is docs/runner-monitor-monitor-hub.md.
    for raw in filter(None, os.environ.get("HUB_ENROLLMENT_TOKENS", "").split(",")):
        state.registry.add_enrollment_token(raw.strip())
    state.registry.save()

    stop = threading.Event()

    def _shutdown(signum, _frame):
        print(f"[hub] signal {signum}, shutting down")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    poll_thread = None
    if os.environ.get("GITHUB_TOKEN"):
        from .alerts import build_notifier
        from .monitor import MonitorLoop  # imported here: polling needs ghapi
        notifier = build_notifier(config)
        state.polling_enabled = True
        poll_thread = threading.Thread(
            target=MonitorLoop(state, alert_sink=notifier).run,
            args=(stop,), daemon=True)
        poll_thread.start()
    else:
        print("[hub] WARNING: GITHUB_TOKEN not set — API polling disabled; "
              "enrollment/heartbeat/health only (mon-channels-01)")

    print(f"[hub] listening on {config.bind_host}:{server.server_address[1]} "
          f"data_dir={config.data_dir} monitor_only={config.monitor_only}")
    try:
        while not stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        print("[hub] closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
