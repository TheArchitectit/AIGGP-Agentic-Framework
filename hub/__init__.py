"""DevGate runner-monitor hub — hub-and-spoke fleet monitoring service.

Stdlib-only (http.server + urllib.request). Instance state (runners.json,
alerts/*.jsonl) lives on the hub volume on monitor-hub and is never committed;
only the schema and a redacted example ship in-repo (mon-registry-01).
"""
