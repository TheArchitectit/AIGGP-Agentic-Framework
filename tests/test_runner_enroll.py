"""Tests for scripts/runner-enroll.sh — per-runner units and the ExecStart defect.

Two fleet incidents this locks down:

1. The heartbeat unit shipped an inline `bash -c '…'` ExecStart. systemd
   expands $ in ExecStart against the unit's own environment, so the variables
   the body defined for itself (DISK_OK, PODMAN_OK) arrived empty, the JSON went
   out malformed, the hub rejected it, and the unit exited 22 on *every tick*
   while enrollment itself reported success. The fix is a copied helper script;
   the test asserts the unit references it rather than describing that.

2. Unit and env paths were hard-coded (devgate-heartbeat.*), so enrolling a
   second runner on one host overwrote the first runner's token and the wrong
   runner reported. The fix derives every name from the runner; the test
   enrolls two runners and asserts both survive.

Nothing touches a real hub or a real systemd: `curl` and `systemctl` are stubbed
on PATH and HOME points into tmp_path, so the assertions run against the real
generated files.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_enroll.py`
runs them too.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Only so `tests.fixtures` imports in the standalone run (`python3
# tests/test_runner_enroll.py`, whose sys.path[0] is tests/ and not the repo
# root); pytest resolves it either way. The anchor that MATTERS is the
# fixture's own, and that one is checked rather than trusted.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.runner_spoke import (  # noqa: E402
    HEARTBEAT, HUB, SCRIPT, Spoke, slug,
)

import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests shell out
# to things that do not exist on Windows, so they cannot run there. A test that
# cannot run must SKIP, not fail -- failing here is indistinguishable from real
# breakage, and a Windows developer cannot tell which failures matter.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")


# --- incident #1: ExecStart must not be an inline shell body ------------------

def test_execstart_is_a_copied_helper_not_inline_bash(tmp_path):
    """systemd expands $ in ExecStart; an inline body cannot survive that."""
    s = Spoke(tmp_path)
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    unit = s.units / "devgate-hb-alpha.service"
    assert unit.exists(), "per-runner service unit was not written"
    text = unit.read_text(encoding="utf-8")

    assert "bash -c" not in text, "incident #1: inline ExecStart gets mangled by systemd"

    exec_line = [l for l in text.splitlines() if l.startswith("ExecStart=")]
    assert len(exec_line) == 1, f"expected one ExecStart, got {exec_line}"
    helper = Path(exec_line[0].split("=", 1)[1])
    assert helper.is_file(), f"ExecStart points at a missing file: {helper}"
    assert os.access(helper, os.X_OK), f"ExecStart target is not executable: {helper}"


def test_heartbeat_posts_valid_json_and_exits_zero(tmp_path):
    """The real payload: booleans stay booleans, token matches the runner."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = s.run_helper("alpha")
    assert res.returncode == 0, f"helper failed: {res.stderr}"

    posts = s.requests("/heartbeat")
    assert posts, "no heartbeat was POSTed"
    body = json.loads(posts[-1]["data"])
    assert body["runner_name"] == "alpha"
    assert body["heartbeat_token"] == s.token_of("alpha")
    assert isinstance(body["disk_ok"], bool), body
    assert isinstance(body["podman_ok"], bool), body


def test_non_200_is_exit_22_and_never_zero(tmp_path):
    """A rejected heartbeat must fail its unit, not look like a pass."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = s.run_helper("alpha", STUB_HEARTBEAT_STATUS="400")
    assert res.returncode == 22, f"expected 22, got {res.returncode}: {res.stderr}"


def test_missing_env_is_a_config_error_not_a_pass(tmp_path):
    """No EnvironmentFile means we cannot check — that must never exit 0."""
    res = subprocess.run(["bash", str(HEARTBEAT)],
                         env={"PATH": os.environ["PATH"], "TMPDIR": str(tmp_path)},
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert res.returncode != 0, "helper exited 0 without any env — vacuous pass"
    assert res.returncode == 1, res.stderr


# --- incident #2: a second enroll must not clobber the first ------------------

def test_second_enroll_does_not_clobber_the_first(tmp_path):
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    assert s.enroll("beta").returncode == 0

    assert s.token_of("alpha") == "tok-alpha"
    assert s.token_of("beta") == "tok-beta", "beta's enroll overwrote alpha's env"

    for name in ("alpha", "beta"):
        for suffix in ("timer", "service"):
            assert (s.units / f"devgate-hb-{name}.{suffix}").exists()
            assert (s.units / f"devgate-watchdog-{name}.{suffix}").exists()


def test_units_started_are_named_for_the_runner(tmp_path):
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    calls = s.systemctl_calls()
    assert any("start devgate-hb-alpha.timer" in c for c in calls), calls
    assert any("start devgate-watchdog-alpha.timer" in c for c in calls), calls
    assert not any("start devgate-heartbeat.timer" in c for c in calls), \
        "legacy fixed-name unit was started"


def test_env_file_is_600_and_holds_the_token(tmp_path):
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    env = s.env_file("alpha")
    assert env.exists()
    mode = oct(env.stat().st_mode & 0o777)
    assert mode == "0o600", f"token file is {mode}, expected 0o600"
    text = env.read_text(encoding="utf-8")
    assert "RUNNER_NAME=alpha" in text
    assert "HEARTBEAT_TOKEN=tok-alpha" in text


def test_reenroll_preserves_hand_added_provisioning_lines(tmp_path):
    """Re-enrolling truncates the env file and rewrites four keys. The image
    cycle's three variables live in that SAME file (design D3.1: one
    EnvironmentFile per runner), and nothing enrolls them — so an operator
    provisions a host by hand, and a routine re-enroll would silently delete
    the provisioning. The host then reports "not provisioned" for a mount that
    is mounted and a store that is filled, which is the kind of alert an
    operator learns to ignore."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    env = s.env_file("alpha")
    hand_added = [
        "# provisioning added by hand — enroll must not own these",
        "COHERENCE_IMAGE=ghcr.io/example/devgate-coherence",
        "COHERENCE_IMAGE_MANIFEST_DIGEST=sha256:" + "a" * 64,
        "COHERENCE_PODMAN_STORE=/var/lib/devgate/store",
        "IMAGE_CYCLE_PRUNE=0",
    ]
    env.write_text(env.read_text(encoding="utf-8") + "\n".join(hand_added) + "\n", encoding="utf-8")

    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    after = env.read_text(encoding="utf-8")
    for line in hand_added:
        assert line in after, (
            f"re-enrolling deleted an operator's line, and nothing else in "
            f"this repository writes it: {line!r}\n--- file now ---\n{after}")
    # The managed keys are still rewritten (and still exactly once).
    assert after.count("HEARTBEAT_TOKEN=") == 1, after
    assert f"HEARTBEAT_TOKEN={s.token_of('alpha')}" in after, after


def test_reenroll_keeps_the_env_file_600_with_preserved_lines(tmp_path):
    """Preserving lines must not be a way to widen the token file's mode: the
    write is still a rewrite of a file holding a live token."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    env = s.env_file("alpha")
    env.write_text(env.read_text(encoding="utf-8") + "COHERENCE_PODMAN_STORE=/var/lib/devgate/store\n", encoding="utf-8")

    assert s.enroll("alpha").returncode == 0
    mode = oct(env.stat().st_mode & 0o777)
    assert mode == "0o600", f"token file is {mode}, expected 0o600"


def test_unit_names_stay_valid_for_an_awkward_runner_name(tmp_path):
    """A name systemd would reject in a unit must be sanitized, not emitted."""
    s = Spoke(tmp_path)
    res = s.enroll("prod/web 1")
    assert res.returncode == 0, res.stderr

    names = [p.name for p in s.units.glob("devgate-*")]
    assert names, "no units written"
    for n in names:
        assert " " not in n and "/" not in n, f"invalid unit name written: {n}"
    assert any(n.startswith("devgate-hb-") for n in names), names


# --- migration off the legacy fixed-name layout -------------------------------

def test_legacy_units_are_retired_for_the_runner_being_reenrolled(tmp_path):
    s = Spoke(tmp_path)
    s.units.mkdir(parents=True, exist_ok=True)
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n", encoding="utf-8")
    (s.units / "devgate-heartbeat.service").write_text("[Service]\n", encoding="utf-8")
    (s.home / ".devgate-heartbeat.env").write_text(
        "HUB_URL=%s\nRUNNER_NAME=alpha\n" % HUB, encoding="utf-8")

    assert s.enroll("alpha").returncode == 0
    assert not (s.units / "devgate-heartbeat.timer").exists(), \
        "legacy unit for THIS runner should have been retired"
    assert (s.units / "devgate-hb-alpha.timer").exists()


def test_legacy_units_are_left_when_they_belong_to_another_runner(tmp_path):
    """Not destructive: someone else's working units must survive our enroll."""
    s = Spoke(tmp_path)
    s.units.mkdir(parents=True, exist_ok=True)
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n", encoding="utf-8")
    (s.home / ".devgate-heartbeat.env").write_text(
        "HUB_URL=%s\nRUNNER_NAME=gamma\n" % HUB, encoding="utf-8")

    assert s.enroll("alpha").returncode == 0
    assert (s.units / "devgate-heartbeat.timer").exists(), \
        "another runner's legacy units were destroyed"
    assert (s.units / "devgate-hb-alpha.timer").exists()


# --- audit findings: names that must not break a tick -------------------------

def test_helper_survives_a_runner_name_containing_a_slash(tmp_path):
    """A '/' in the name must not break the response file open — curl exit 23
    would kill the tick under set -e before the HTTP status is ever checked."""
    s = Spoke(tmp_path)
    assert s.enroll("prod/web 1").returncode == 0

    res = s.run_helper("prod/web 1")
    assert res.returncode == 0, f"helper failed: {res.stderr}"
    assert s.requests("/heartbeat"), "no heartbeat was POSTed"


def test_colliding_runner_names_are_refused_not_merged(tmp_path):
    """Two names that sanitize to one slug must not silently share a token —
    accepting them would recreate the clobber this change exists to remove."""
    s = Spoke(tmp_path)
    assert s.enroll("ci runner").returncode == 0
    first_token = s.token_of("ci runner")

    res = s.enroll("ci/runner")
    assert res.returncode != 0, "colliding slug was accepted — incident #2 back"
    assert "already belongs to" in (res.stdout + res.stderr), (res.stdout, res.stderr)

    assert s.token_of("ci runner") == first_token, "first runner's token was clobbered"


def test_reenrolling_the_same_runner_still_succeeds(tmp_path):
    """The collision guard must be scoped to a DIFFERENT owner, not block
    an ordinary re-enroll of the same runner."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    assert s.token_of("alpha") == "tok-alpha"


def test_revoke_does_not_delete_another_runners_units(tmp_path):
    """Re-audit finding: --revoke derived names from the revoked runner with no
    owner check, so revoking 'ci/runner' silently destroyed 'ci runner'."""
    s = Spoke(tmp_path)
    assert s.enroll("ci runner").returncode == 0
    first_token = s.token_of("ci runner")

    res = subprocess.run(
        ["bash", str(SCRIPT), "--revoke", HUB, "tok-ci-slash-runner", "ci/runner"],
        env=s.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    assert (s.units / "devgate-hb-ci-runner.service").exists(), \
        "revoke of a colliding name deleted another runner's units"
    assert (s.units / "devgate-hb-ci-runner.timer").exists()
    assert s.token_of("ci runner") == first_token, "another runner's token was deleted"
    assert res.returncode == 0, res.stderr


def test_revoke_still_removes_its_own_units(tmp_path):
    """The owner check must not turn revoke into a no-op for the real owner."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = subprocess.run(
        ["bash", str(SCRIPT), "--revoke", HUB, "tok-alpha", "alpha"],
        env=s.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    assert res.returncode == 0, res.stderr
    assert not (s.units / "devgate-hb-alpha.service").exists(), "own unit survived"
    assert not s.env_file("alpha").exists(), "own token file survived"


def test_refused_enroll_never_reaches_the_hub(tmp_path):
    """A slug conflict must die BEFORE POST /enroll, or the hub is left with a
    registered runner that will never heartbeat — and prints its token."""
    s = Spoke(tmp_path)
    assert s.enroll("ci runner").returncode == 0

    res = s.enroll("ci/runner")
    assert res.returncode != 0, "colliding enroll was accepted"

    assert len(s.requests("/enroll")) == 1, \
        "the refused enroll still reached the hub — ghost registration"
    assert "Enrolled successfully" not in res.stdout, \
        "claimed success before the failure: " + res.stdout


def test_unattributable_env_file_is_not_overwritten(tmp_path):
    """A token-bearing file with no RUNNER_NAME line must be refused rather
    than treated as ours and clobbered."""
    s = Spoke(tmp_path)
    envdir = s.home / ".config" / "containers"
    envdir.mkdir(parents=True, exist_ok=True)
    target = envdir / "devgate-heartbeat-alpha.env"
    target.write_text("HEARTBEAT_TOKEN=PRECIOUS\n", encoding="utf-8")

    res = s.enroll("alpha")
    assert res.returncode != 0, "token file without an owner was overwritten"
    assert "PRECIOUS" in target.read_text(encoding="utf-8"), "the token was lost"


def test_unattributable_legacy_units_are_left_alone(tmp_path):
    """An owner we cannot read is not permission to delete (F1): the legacy
    guard must fail closed exactly like the per-runner guard does."""
    s = Spoke(tmp_path)
    s.units.mkdir(parents=True, exist_ok=True)
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n", encoding="utf-8")
    (s.home / ".devgate-heartbeat.env").write_text("HEARTBEAT_TOKEN=LEGACY-SECRET\n", encoding="utf-8")

    assert s.enroll("newcomer").returncode == 0
    assert (s.units / "devgate-heartbeat.timer").exists(), \
        "legacy units deleted on an owner we could not read"
    assert "LEGACY-SECRET" in (s.home / ".devgate-heartbeat.env").read_text(encoding="utf-8")


def test_a_runner_named_like_the_sentinel_cannot_claim_a_file(tmp_path):
    """F2: 'UNKNOWN' is a legal runner name, so an internal sentinel value
    must not be reachable through it."""
    s = Spoke(tmp_path)
    envdir = s.home / ".config" / "containers"
    envdir.mkdir(parents=True, exist_ok=True)
    target = envdir / "devgate-heartbeat-UNKNOWN.env"
    target.write_text("HEARTBEAT_TOKEN=UNATTRIBUTABLE\n", encoding="utf-8")

    res = s.enroll("UNKNOWN")
    assert res.returncode != 0, "sentinel name claimed an unattributable file"
    assert "UNATTRIBUTABLE" in target.read_text(encoding="utf-8")


def test_a_directory_at_the_env_path_fails_before_the_hub(tmp_path):
    """F3: a non-regular file must not read as 'no file' — otherwise the enroll
    reaches the hub, prints success, and only then dies on the write."""
    s = Spoke(tmp_path)
    envdir = s.home / ".config" / "containers"
    envdir.mkdir(parents=True, exist_ok=True)
    (envdir / "devgate-heartbeat-alpha.env").mkdir()

    res = s.enroll("alpha")
    assert res.returncode != 0, "enroll proceeded against a directory"
    assert len(s.requests("/enroll")) == 0, "reached the hub before failing"
    assert "Enrolled successfully" not in res.stdout


# --- the image cycle is installed beside the heartbeat (img-cycle-02, D3) ----
#
# The cycle is the out-of-band half: the gate never pulls (coh-rt-01), so the
# pinned bytes have to be on the host before the job starts. Enroll therefore
# installs it the way it installs the heartbeat — a COPIED helper, an
# EnvironmentFile, a per-runner timer — because the two share one file and one
# naming scheme (design D3.1).
#
# What enroll must NOT do is pretend the cycle can run on a host nobody has
# provisioned. The three COHERENCE_* variables are a per-fleet choice (D3: the
# store is either inside the runner container or socket-shared from the host)
# and enroll does not own them, so a host without them gets the units on disk
# and NO running timer — rather than a unit that exits 5/6/7 every cycle and
# trains an operator to ignore it.

CYC_KEYS = ("COHERENCE_IMAGE", "COHERENCE_IMAGE_MANIFEST_DIGEST",
            "COHERENCE_PODMAN_STORE")


def _provision(s, runner, store=None):
    """Add the cycle's three variables to the shared env file, by hand.

    By hand is the point: enroll owns four keys of that file and carries the
    rest over as found, so this is exactly what an operator does — which is
    also why the truncation bug destroyed it silently.
    """
    envf = s.env_file(runner)
    assert envf.exists(), f"enroll did not write {envf}"
    store = store or (tmp_store(s))
    with envf.open("a") as fh:
        fh.write("# provisioning added by hand — enroll must not own these\n")
        fh.write("COHERENCE_IMAGE=ghcr.io/thearchitectit/devgate-coherence\n")
        fh.write('COHERENCE_IMAGE_MANIFEST_DIGEST=sha256:%s\n' % ("a" * 64))
        fh.write("COHERENCE_PODMAN_STORE=%s\n" % store)


def tmp_store(s):
    store = s.home / "podman-store"
    store.mkdir(exist_ok=True)
    return store


def test_enroll_installs_the_image_cycle_helper_beside_the_heartbeat(tmp_path):
    """A copied helper, byte-identical to the shipped script and executable.

    Copied for the reason the heartbeat's is: it is installed as a FILE the
    unit points at, so the unit can never grow an inline shell body — which is
    what made every heartbeat tick exit 22 (incident #1).
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    helper = s.cycle_helper()
    assert helper.is_file(), f"the cycle helper was not installed: {helper}"
    assert helper.stat().st_mode & 0o777 == 0o755, oct(helper.stat().st_mode)
    src = (Path(__file__).resolve().parent.parent
           / "scripts" / "runner-image-cycle.sh")
    assert helper.read_bytes() == src.read_bytes(), "helper differs from its source"


def test_an_existing_cycle_helper_is_left_unchanged_and_flagged(tmp_path):
    """Same policy as the heartbeat helper: never clobber a host's copy in
    silence. A helper that has diverged is a stale fix, and the operator has to
    be told, because the enrollment still succeeds."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    helper = s.cycle_helper()
    helper.write_text("#!/usr/bin/env bash\n# locally patched\n", encoding="utf-8")

    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    assert "locally patched" in helper.read_text(encoding="utf-8"), "the host's helper was overwritten"
    assert "WARNING" in res.stdout and str(helper) in res.stdout, res.stdout


def test_the_cycle_unit_points_at_the_helper_and_the_shared_env_file(tmp_path):
    """One EnvironmentFile per runner (D3.1): the cycle reads the SAME file the
    heartbeat does, which is why its store setting has a single source."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    service, timer = s.cycle_units("alpha")
    assert service.is_file() and timer.is_file(), "cycle units were not written"

    body = service.read_text(encoding="utf-8")
    assert f"EnvironmentFile={s.env_file('alpha')}" in body, body
    assert f"ExecStart={s.cycle_helper()}" in body, body
    assert "Type=oneshot" in body, body
    assert "bash -c" not in body, "inline ExecStart gets mangled by systemd"

    # Its own cadence, deliberately not the heartbeat's. A pull every 300s,
    # on every host in the fleet, is a hammering of the registry that a local
    # POST does not resemble — and it buys nothing, because the desired state
    # is a pinned digest that changes only when someone re-pins it (D1).
    tbody = timer.read_text(encoding="utf-8")
    assert "OnUnitActiveSec=3600" in tbody, tbody
    assert "OnUnitActiveSec=300" not in tbody, tbody


def test_the_cycle_timer_does_not_start_unprovisioned(tmp_path):
    """The units land, the timer does not run, and the missing keys are named.

    A timer that fired here would exit 1 (config) on every tick for a host
    that was never provisioned — and on a shape-(a) fleet, which never sets
    these on the host at all, it would exit 6/7 forever. Either way the unit
    is noise that teaches operators to ignore the one that matters.
    """
    s = Spoke(tmp_path)
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    _, timer = s.cycle_units("alpha")
    assert timer.is_file(), "the timer file should still be installed"
    assert not any("devgate-imgcycle" in c for c in s.systemctl_calls()), \
        s.systemctl_calls()
    for key in CYC_KEYS:
        assert key in res.stdout, f"{key} not named in the output: {res.stdout}"


def test_the_cycle_timer_starts_once_the_host_is_provisioned(tmp_path):
    """Provisioning is the switch. An operator adds the three keys by hand; the
    next enroll enables the timer, and does not touch what they added."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    _provision(s, "alpha")

    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    calls = s.systemctl_calls()
    assert any("enable devgate-imgcycle-alpha.timer" in c for c in calls), calls
    assert any("start devgate-imgcycle-alpha.timer" in c for c in calls), calls
    # …and the provisioning itself is untouched (the truncation bug's cousin).
    env = s.env_file("alpha").read_text(encoding="utf-8")
    for key in CYC_KEYS:
        assert f"{key}=" in env, env


def test_revoke_removes_the_image_cycle_units(tmp_path):
    """The cycle reads its store from the env file revoke deletes, so leaving
    the timer behind would leave a unit failing forever on a config error."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    token = s.token_of("alpha")
    service, timer = s.cycle_units("alpha")
    assert service.is_file() and timer.is_file()

    res = subprocess.run(
        ["bash", str(SCRIPT), "--revoke", HUB, token, "alpha"],
        env=s.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert res.returncode == 0, res.stderr
    assert not service.exists() and not timer.exists(), \
        f"cycle units survived revoke: {service.exists()} {timer.exists()}"


def _main():
    import tempfile
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as d:
                try:
                    fn(Path(d))
                    print(f"PASS {name}")
                except AssertionError as exc:
                    failed += 1
                    print(f"FAIL {name}: {exc}")
    print(f"\n{failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
