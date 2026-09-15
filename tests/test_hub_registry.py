"""Tests for hub/registry.py + hub/tokens.py (Sprints 1.2, 2.2).

Locks the mon-registry-01 / mon-enroll-01 contract: atomic load/save,
one-time enrollment tokens, per-runner heartbeat token issue/revoke.
A registry that silently corrupts or reuses a one-time token is worse than
no registry — the fleet's enrollment state is security-relevant.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_registry.py` runs them too.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import tokens  # noqa: E402
from hub.registry import Registry, RegistryError  # noqa: E402


def test_fresh_registry_defaults(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))
    assert reg.runners() == []
    reg.save()
    reloaded = Registry(str(tmp_path / "runners.json"))
    assert reloaded.runners() == []


def test_save_is_atomic_roundtrip(tmp_path):
    path = tmp_path / "runners.json"
    reg = Registry(str(path))
    runner = reg.enroll("r1", "OWNER/REPO", ["devgate"], "monitor-hub")
    assert runner["heartbeat_token"]
    reg.save()
    reloaded = Registry(str(path))
    stored = reloaded.find_runner("r1")
    assert stored is not None
    assert stored["repo"] == "OWNER/REPO"
    assert stored["enrolled"] is True


def test_missing_required_key_raises(tmp_path):
    path = tmp_path / "runners.json"
    path.write_text(json.dumps({"version": 1}))  # no "runners" key
    try:
        Registry(str(path), auto_init=False)
        raise AssertionError("expected RegistryError")
    except RegistryError as exc:
        assert "enrollment_tokens" in str(exc)


def test_missing_file_auto_init(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))  # hub startup mode
    assert reg.runners() == []
    try:
        Registry(str(tmp_path / "absent.json"), auto_init=False)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_enrollment_token_one_time(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))
    reg.add_enrollment_token(tokens.mint_token())
    presented = list(reg._data["enrollment_tokens"])[0]
    assert reg.consume_enrollment_token(presented) is True
    # replay of the same one-time token must fail (mon-enroll-01)
    assert reg.consume_enrollment_token(presented) is False


def test_heartbeat_token_issue_and_revoke(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))
    runner = reg.enroll("r1", "OWNER/REPO", [], "")
    good = runner["heartbeat_token"]
    assert reg.verify_heartbeat_token("r1", good) is True
    assert reg.verify_heartbeat_token("r1", "wrong-token") is False
    # revoked runner: token no longer verifies, heartbeat refused
    assert reg.revoke("r1") is True
    assert reg.verify_heartbeat_token("r1", good) is False
    assert reg.heartbeat("r1", None, None, None) is False


def test_heartbeat_updates_freshness(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))
    reg.enroll("r1", "OWNER/REPO", [], "")
    assert reg.heartbeat("r1", "job-42", True, False) is True
    runner = reg.find_runner("r1")
    assert runner["last_heartbeat"] is not None
    assert runner["last_job_seen"] == "job-42"
    assert runner["disk_ok"] is True
    assert runner["podman_ok"] is False


def test_unknown_runner_rejected(tmp_path):
    reg = Registry(str(tmp_path / "runners.json"))
    assert reg.heartbeat("ghost", None, None, None) is False
    assert reg.verify_heartbeat_token("ghost", "anything") is False
    assert reg.revoke("ghost") is False


def test_token_verify_constant_time_helpers():
    assert tokens.verify("", None) is False
    assert tokens.verify(None, "x") is False
    assert tokens.verify("abc", "abc") is True
    assert tokens.verify("abc", "abd") is False


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
