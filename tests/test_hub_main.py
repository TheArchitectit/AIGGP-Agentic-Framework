#!/usr/bin/env python3
"""hub.main entry contract: env→config wiring, the no-token branch, shutdown.

harden-test-suite item 6, paired with harden-security-boundaries 2.1. The
idle-SIGTERM case (F2: handle_request blocks until the next request) is
locked in tests/test_hub_hardening.py; this file covers the entry point
itself — how HUB_* and the CLI flags become a Config, what a hub says when
GITHUB_TOKEN is absent (mon-channels-01: a monitor with no evidence channel
must say so loudly, not pass vacuously), that enrollment tokens refuse
unexpanded placeholders on the way in, and that SIGINT takes the same
clean-exit-0 path as SIGTERM.

    python3 -m pytest tests/test_hub_main.py
    python3 tests/test_hub_main.py
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.config import Config  # noqa: E402
from hub.main import load_enrollment_tokens, parse_args  # noqa: E402
from hub.registry import Registry  # noqa: E402


# --- env → Config wiring ----------------------------------------------------


def test_default_bind_is_loopback_not_wildcard():
    """D7 firewall step: a hub that forgets HUB_BIND_HOST must not expose
    0.0.0.0. This is the default the env wiring starts from."""
    assert Config().bind_host == "127.0.0.1"


def test_from_env_reads_the_documented_knobs(monkeypatch):
    monkeypatch.setenv("HUB_BIND_HOST", "127.0.0.2")
    monkeypatch.setenv("HUB_BIND_PORT", "9001")
    monkeypatch.setenv("HUB_DATA_DIR", "/tmp/hubdata")
    monkeypatch.setenv("HUB_MONITOR_ONLY", "false")
    monkeypatch.setenv("HUB_WATCHED_BRANCHES", "main,release")
    cfg = Config.from_env()
    assert cfg.bind_host == "127.0.0.2"
    assert cfg.bind_port == 9001
    assert cfg.data_dir == "/tmp/hubdata"
    assert cfg.monitor_only is False
    assert cfg.watched_branches == ["main", "release"]


def test_cli_flags_override_env(monkeypatch):
    """main() applies parse_args onto Config.from_env(); each of the three
    flags must win over the corresponding env var."""
    monkeypatch.setenv("HUB_BIND_HOST", "127.0.0.2")
    monkeypatch.setenv("HUB_BIND_PORT", "9001")
    monkeypatch.setenv("HUB_DATA_DIR", "/tmp/from-env")
    args = parse_args(["--bind-host", "127.0.0.3",
                       "--bind-port", "9002",
                       "--data-dir", "/tmp/from-cli"])
    cfg = Config.from_env()
    if args.bind_host:
        cfg.bind_host = args.bind_host
    if args.bind_port is not None:
        cfg.bind_port = args.bind_port
    if args.data_dir:
        cfg.data_dir = args.data_dir
    assert cfg.bind_host == "127.0.0.3"
    assert cfg.bind_port == 9002
    assert cfg.data_dir == "/tmp/from-cli"


def test_parse_args_defaults_are_unset_so_env_survives():
    args = parse_args([])
    assert args.bind_host is None
    assert args.bind_port is None
    assert args.data_dir is None


# --- enrollment-token load rule (mon-monitor-hub-01 credential half) --------


def _registry(tmp_path) -> Registry:
    return Registry(str(tmp_path / "runners.json"))


def test_load_enrollment_tokens_accepts_mint_shape(tmp_path):
    reg = _registry(tmp_path)
    accepted = load_enrollment_tokens(reg, "abcdefghijklmnop, qrstuvwxyz123456")
    assert accepted == ["abcdefghijklmnop", "qrstuvwxyz123456"]
    assert reg._data["enrollment_tokens"] == accepted


def test_load_enrollment_tokens_refuses_placeholder_and_says_why(tmp_path, capsys):
    """`$NEW` is exactly the unexpanded shape the live hub once loaded.
    Refusal must be loud but value-free (a near-miss may still be a secret)."""
    reg = _registry(tmp_path)
    accepted = load_enrollment_tokens(reg, "$NEW,shorttoken,abcdefghijklmnop")
    assert accepted == ["abcdefghijklmnop"]
    err = capsys.readouterr().err
    assert "REJECTED" in err and "mint-shaped" in err
    assert "$NEW" not in err, "refusal must not echo the near-miss value"


def test_load_enrollment_prunes_stored_placeholders(tmp_path, capsys):
    """A placeholder that an older hub let in must be healed by this startup,
    not ride the volume forever."""
    reg = _registry(tmp_path)
    reg.add_enrollment_token("$OLD")
    accepted = load_enrollment_tokens(reg, "abcdefghijklmnop")
    assert accepted == ["abcdefghijklmnop"]
    assert "$OLD" not in reg._data["enrollment_tokens"]
    err = capsys.readouterr().err
    assert "PRUNED" in err
    assert "$OLD" not in err


# --- integration: the hub process itself ------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_hub(tmp_path, *, extra_env=None, extra_args=(), strip_github_token=True,
               watch_port=None):
    port = watch_port if watch_port is not None else _free_port()
    env = {k: v for k, v in os.environ.items()}
    if strip_github_token:
        env.pop("GITHUB_TOKEN", None)
    env.update({"HUB_BIND_HOST": "127.0.0.1",
                "HUB_BIND_PORT": str(port),
                "HUB_DATA_DIR": str(tmp_path)})
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, "-m", "hub.main", *extra_args],
        cwd=str(REPO), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 10
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            proc.stdout = None
            raise AssertionError(f"hub exited early rc={proc.returncode}: {out}")
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                return proc, port
        except OSError:
            time.sleep(0.05)
    proc.kill()
    raise AssertionError("hub did not start listening")


def _stop_and_read(proc, signum=signal.SIGTERM) -> tuple[int, str]:
    proc.send_signal(signum)
    try:
        rc = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise AssertionError("hub did not shut down within 5s")
    out = proc.stdout.read() if proc.stdout else ""
    return rc, out


def test_no_token_branch_says_so_loudly(tmp_path):
    """mon-channels-01: no GITHUB_TOKEN is a degraded monitor, not a green one.
    The hub must name the missing channel and keep serving enrollment only."""
    proc, _port = _start_hub(tmp_path)
    try:
        rc, out = _stop_and_read(proc, signal.SIGTERM)
        assert rc == 0, out
        assert "GITHUB_TOKEN not set" in out, out
        assert "mon-channels-01" in out, out
        assert "API polling disabled" in out, out
    finally:
        if proc.poll() is None:
            proc.kill()


def test_cli_bind_port_listens_where_the_flag_says(tmp_path):
    """The --bind-* flags are the documented override; a hub started with one
    must listen there, not wherever HUB_* pointed."""
    env_port = _free_port()  # deliberately a port nobody will listen on
    cli_port = _free_port()
    proc, port = _start_hub(tmp_path,
                            watch_port=cli_port,
                            extra_env={"HUB_BIND_PORT": str(env_port)},
                            extra_args=("--bind-port", str(cli_port)))
    try:
        assert port == cli_port != env_port
        rc, out = _stop_and_read(proc, signal.SIGTERM)
        assert rc == 0, out
        assert f"listening on 127.0.0.1:{cli_port}" in out, out
    finally:
        if proc.poll() is None:
            proc.kill()


def test_sigint_is_the_same_clean_exit_as_sigterm(tmp_path):
    """Both handlers are registered; a missing SIGINT path would make Ctrl-C
    (and any supervisor that sends INT) lose the exit-0 contract."""
    proc, _port = _start_hub(tmp_path)
    try:
        rc, out = _stop_and_read(proc, signal.SIGINT)
        assert rc == 0, out
        assert "closed" in out, out
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))