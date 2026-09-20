"""hub.config — every hub knob as a dataclass with env-var defaults.

Q1–Q3 of the archived design are config defaults, not hardcoded logic:
ALERT_CHANNEL (default github_issue), HEARTBEAT_INTERVAL_SEC (default 300),
MONITOR_ONLY (default true). Each is flagged for owner confirmation in
docs/runner-monitor-monitor-hub.md.

// spec: mon-hub-01
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    """All hub configuration. Every field has an env-var override (HUB_*)."""

    # --- network ---------------------------------------------------------
    bind_host: str = "127.0.0.1"          # never 0.0.0.0 by default (D7 firewall step)
    bind_port: int = 8443

    # --- instance state (hub volume on monitor-hub, never committed) --------------
    data_dir: str = "/data"               # runners.json + alerts/*.jsonl live here

    # --- Q1–Q3 defaults (owner confirmation in the runbook) ----------------
    alert_channel: str = "github_issue"   # Q1: github_issue | null (notifier interface only)
    heartbeat_interval_sec: int = 300     # Q2: 5 min → stale after two intervals
    monitor_only: bool = True             # Q3: hub does not register as a job runner

    # --- monitoring thresholds --------------------------------------------
    queue_threshold_min: float = 30.0     # mon-queue-01 default, per-runner override
    drift_grace_min: float = 10.0         # mon-drift-01 grace window
    drift_workflow_match: str = "drift"   # config-provided name pattern (spec does not name it)
    coherence_workflow_match: str = "coherence"  # separate matcher: the two must not shadow each other (coh-int-07)
    watched_branches: list[str] = field(default_factory=lambda: ["default"])

    # Minimum seconds between recurrence comments on the same open issue.
    # Without this the poll loop re-comments every cycle and trips GitHub's
    # secondary content-creation rate limit (observed 2026-09-15).
    comment_cooldown_sec: float = 3600.0

    # --- GitHub API ---------------------------------------------------------
    github_api_base: str = "https://api.github.com"
    poll_interval_sec: int = 60           # between full cycles
    api_backoff_max_sec: int = 120        # cap for 403/429 Retry-After backoff

    @property
    def registry_path(self) -> str:
        return os.path.join(self.data_dir, "runners.json")

    @property
    def alerts_dir(self) -> str:
        return os.path.join(self.data_dir, "alerts")

    @classmethod
    def from_env(cls) -> "Config":
        """Build a Config from HUB_* environment variables (explicit > env > default)."""
        cfg = cls()
        if v := os.environ.get("HUB_BIND_HOST"):
            cfg.bind_host = v
        if v := os.environ.get("HUB_BIND_PORT"):
            cfg.bind_port = int(v)
        if v := os.environ.get("HUB_DATA_DIR"):
            cfg.data_dir = v
        if v := os.environ.get("HUB_ALERT_CHANNEL"):
            cfg.alert_channel = v
        if v := os.environ.get("HUB_HEARTBEAT_INTERVAL_SEC"):
            cfg.heartbeat_interval_sec = int(v)
        cfg.monitor_only = _env_bool("HUB_MONITOR_ONLY", cfg.monitor_only)
        if v := os.environ.get("HUB_QUEUE_THRESHOLD_MIN"):
            cfg.queue_threshold_min = float(v)
        if v := os.environ.get("HUB_DRIFT_GRACE_MIN"):
            cfg.drift_grace_min = float(v)
        if v := os.environ.get("HUB_DRIFT_WORKFLOW_MATCH"):
            cfg.drift_workflow_match = v
        if v := os.environ.get("HUB_COHERENCE_WORKFLOW_MATCH"):
            cfg.coherence_workflow_match = v
        if v := os.environ.get("HUB_WATCHED_BRANCHES"):
            cfg.watched_branches = [b for b in v.split(",") if b]
        if v := os.environ.get("GITHUB_API_BASE"):
            cfg.github_api_base = v
        if v := os.environ.get("HUB_POLL_INTERVAL_SEC"):
            cfg.poll_interval_sec = int(v)
        if v := os.environ.get("HUB_COMMENT_COOLDOWN_SEC"):
            cfg.comment_cooldown_sec = float(v)
        return cfg
