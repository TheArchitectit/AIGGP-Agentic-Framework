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

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "hub" / "schema"


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


# --- evaluator-image state: three states, not two (img-cycle-03) -------------
#
# The registry treats None as "no news" for every field: a heartbeat that
# omits disk_ok leaves the last reading. That rule is WRONG for the image, and
# the tests below are what make the difference load-bearing rather than
# decorative — a null must clear a stored ref (or a host that lost its image
# keeps showing as ready to gate), and an omitted field must not (or a body
# that does not speak about images would wipe one).

REF = "ghcr.io/owner/repo/devgate-coherence@sha256:" + "a" * 64


def test_reported_null_image_clears_a_stored_ref(tmp_path):
    """The host that converged and then lost its image must stop reading ready."""
    reg = Registry(str(tmp_path / "runners.json"))
    reg.enroll("r1", "OWNER/REPO", [], "")
    reg.heartbeat("r1", None, None, None, REF, None)
    assert reg.find_runner("r1")["image_digest"] == REF

    # Explicit null, with the reason the script would give.
    reg.heartbeat("r1", None, None, None, None, "podman not on PATH")
    runner = reg.find_runner("r1")
    assert runner["image_digest"] is None
    assert runner["image_reason"] == "podman not on PATH"


def test_an_omitted_image_field_leaves_the_last_report_alone(tmp_path):
    """A body that says nothing about images is not a body saying "no image"."""
    reg = Registry(str(tmp_path / "runners.json"))
    reg.enroll("r1", "OWNER/REPO", [], "")
    reg.heartbeat("r1", None, None, None, REF, None)

    reg.heartbeat("r1", "job-1", True, True)     # four-arg call: nothing said
    assert reg.find_runner("r1")["image_digest"] == REF


def test_a_freshly_enrolled_runner_has_no_image_and_no_reason(tmp_path):
    """Enrollment is not convergence: the field starts null, never true."""
    reg = Registry(str(tmp_path / "runners.json"))
    reg.enroll("r1", "OWNER/REPO", [], "")
    runner = reg.find_runner("r1")
    assert runner["image_digest"] is None
    assert runner["image_reason"] is None


def test_a_registry_saved_before_the_image_fields_existed_still_loads(tmp_path):
    """Forward compatibility, in the direction the fleet will actually move.

    monitor-hub's volume already holds a registry written by the previous
    build — no image keys at all. Loading it must not raise, and the missing
    keys must read as unknown rather than as healthy.
    """
    path = tmp_path / "runners.json"
    path.write_text(json.dumps({
        "version": 1, "enrollment_tokens": [],
        "runners": [{"name": "r1", "repo": "OWNER/REPO", "labels": [],
                     "host_alias": "", "enrolled_at": "2026-09-01T00:00:00Z",
                     "heartbeat_token": "x", "last_heartbeat": None,
                     "last_job_seen": None, "disk_ok": True, "podman_ok": True,
                     "enrolled": True}],
    }))
    reg = Registry(str(path), auto_init=False)
    runner = reg.find_runner("r1")
    assert runner["disk_ok"] is True
    from hub.registry import image_missing
    assert image_missing(runner) is True, "a pre-image registry host is not ready"


def test_every_field_the_registry_writes_is_declared_in_the_schema(tmp_path):
    """The drift invariant, standing in for validation that does not happen.

    Nothing in this repository validates a registry against
    hub/schema/runners.schema.json — jsonschema is not installed and CI
    installs only pytest — so a field the registry writes and the schema does
    not declare is invisible until a human reads both files side by side.
    That is exactly how `image_digest` would have shipped undeclared.

    It is also the shape of the mistake this test is here to catch twice over:
    the example is checked too, because an example that violates its own
    schema teaches the wrong shape to whoever copies it.

    What it does NOT do is validate. It compares KEY NAMES, and types for the
    handful of fields named below — so a value that is the wrong type everywhere
    else (`"name": 42`) passes. Claiming more than that would be the kind of
    overstatement this file exists to prevent; the invariant that earns its
    keep here is the drift half (`written <= declared`), which is what catches
    a field shipping undeclared.
    """
    schema = json.loads((SCHEMA_DIR / "runners.schema.json").read_text())
    example = json.loads((SCHEMA_DIR / "runners.example.json").read_text())

    declared = set(schema["definitions"]["runner"]["properties"])
    root_declared = set(schema["properties"])

    reg = Registry(str(tmp_path / "runners.json"))
    reg.enroll("r1", "OWNER/REPO", ["devgate"], "monitor-hub")
    reg.heartbeat("r1", "job", True, True, REF, None)
    written = set(reg.find_runner("r1"))

    assert written <= declared, (
        f"registry writes fields the schema does not declare: {written - declared}")
    assert set(example) <= root_declared, (
        f"the example carries undeclared top-level keys: {set(example) - root_declared}")
    for runner in example["runners"]:
        assert set(runner) <= declared, (
            f"the example runner carries undeclared keys: {set(runner) - declared}")

    # Nullable, not merely declared: every field the heartbeat can report as
    # absent must accept null, or the schema would describe a shape the hub
    # itself never writes.
    for field in ("image_digest", "image_reason", "disk_ok", "podman_ok",
                  "last_heartbeat", "last_job_seen"):
        assert "null" in schema["definitions"]["runner"]["properties"][field]["type"], \
            f"{field} is written as null but the schema does not allow it"

    # And the example's values for those fields must be the TYPE the schema
    # declares, which the key-name walk above cannot see: `"image_digest": 42`
    # is declared-and-present and would have passed. The example is the shape
    # an operator copies, so a number where a ref belongs is worse than a
    # missing key.
    props = schema["definitions"]["runner"]["properties"]
    for runner in example["runners"]:
        for field, value in runner.items():
            if field not in props or value is None:
                continue
            allowed = props[field].get("type")
            if allowed is None:
                continue
            allowed = [allowed] if isinstance(allowed, str) else allowed
            json_types = {"string": str, "number": (int, float), "integer": int,
                          "boolean": bool, "array": list, "object": dict}
            expected = tuple(json_types[t] for t in allowed if t in json_types)
            assert isinstance(value, expected), (
                f"example field {field!r} is {type(value).__name__}, "
                f"schema declares {allowed}")


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
