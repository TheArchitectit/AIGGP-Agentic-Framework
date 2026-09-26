"""Tests for scripts/hub-watchdog.sh — the spoke-side dead-man check.

The watchdog asks one question: is the hub still doing anything? It must
answer honestly in the two situations where /health's last_poll_at is null
for opposite reasons — polling never enabled (fine) vs. the poll loop wedged
(a real failure) — and it must never exit 0 when it could not actually check.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_watchdog.py` runs them too.
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "hub-watchdog.sh"


def _iso(delta_sec: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_sec)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _run_watchdog(tmp_path: Path, health: str, *args: str) -> int:
    """Run the watchdog with a stub `curl` on PATH that returns `health`."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "curl"
    stub.write_text('#!/usr/bin/env bash\necho "$STUB_HEALTH"\n', encoding="utf-8")
    stub.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "HUB_URL": "http://hub.invalid",
        "STUB_HEALTH": health,
    }
    proc = subprocess.run(["bash", str(SCRIPT), *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    return proc.returncode


def test_missing_hub_url_is_a_config_error_not_a_pass(tmp_path):
    """A check that cannot run must not exit 0 — the whole point."""
    env = {k: v for k, v in os.environ.items() if k != "HUB_URL"}
    proc = subprocess.run(["bash", str(SCRIPT)], env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert proc.returncode == 2, proc.stderr
    assert "HUB_URL is not set" in proc.stderr


def test_healthy_hub_passes(tmp_path):
    health = (f'{{"ok":true,"last_poll_at":"{_iso()}","polling_enabled":true,'
              f'"poll_interval_sec":60,"uptime_sec":600}}')
    assert _run_watchdog(tmp_path, health) == 0


def test_stale_poll_loop_fails(tmp_path):
    """last_poll_at 2h old with a 60s interval -> the loop is wedged."""
    health = (f'{{"ok":true,"last_poll_at":"{_iso(-7200)}","polling_enabled":true,'
              f'"poll_interval_sec":60,"uptime_sec":9000}}')
    assert _run_watchdog(tmp_path, health) == 1


def test_polling_disabled_warns_but_passes(tmp_path):
    """No GITHUB_TOKEN -> last_poll_at is null by design, not a failure.

    This is the distinction polling_enabled exists for: without it, a hub
    that was never given a PAT would read identically to a dead one.
    """
    health = ('{"ok":true,"last_poll_at":null,"polling_enabled":false,'
              '"poll_interval_sec":60,"uptime_sec":9000}')
    assert _run_watchdog(tmp_path, health) == 0


def test_enabled_but_never_polled_fails_once_past_grace(tmp_path):
    health = ('{"ok":true,"last_poll_at":null,"polling_enabled":true,'
              '"poll_interval_sec":60,"uptime_sec":9000}')
    assert _run_watchdog(tmp_path, health) == 1


def test_enabled_but_fresh_boot_passes(tmp_path):
    """A hub that just started has not had time to poll yet."""
    health = ('{"ok":true,"last_poll_at":null,"polling_enabled":true,'
              '"poll_interval_sec":60,"uptime_sec":10}')
    assert _run_watchdog(tmp_path, health) == 0


def test_unparseable_health_fails(tmp_path):
    assert _run_watchdog(tmp_path, "this is not json") == 1


def test_grace_override_is_honored(tmp_path):
    """--grace-sec lets an operator widen the window without editing the script."""
    health = (f'{{"ok":true,"last_poll_at":"{_iso(-600)}","polling_enabled":true,'
              f'"poll_interval_sec":60,"uptime_sec":9000}}')
    # 10 min stale: fails at default grace (300s max(interval*5)), passes at 1h.
    assert _run_watchdog(tmp_path, health) == 1
    assert _run_watchdog(tmp_path, health, "--grace-sec", "3600") == 0


def main() -> int:
    import inspect
    import tempfile
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            with tempfile.TemporaryDirectory() as td:
                if "tmp_path" in inspect.signature(fn).parameters:
                    fn(Path(td))
                else:
                    fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())