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


# --- incident #1: ExecStart must not be an inline shell body ------------------

def test_execstart_is_a_copied_helper_not_inline_bash(tmp_path):
    """systemd expands $ in ExecStart; an inline body cannot survive that."""
    s = Spoke(tmp_path)
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    unit = s.units / "devgate-hb-alpha.service"
    assert unit.exists(), "per-runner service unit was not written"
    text = unit.read_text()

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
                         capture_output=True, text=True, timeout=30)
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
    text = env.read_text()
    assert "RUNNER_NAME=alpha" in text
    assert "HEARTBEAT_TOKEN=tok-alpha" in text


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
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n")
    (s.units / "devgate-heartbeat.service").write_text("[Service]\n")
    (s.home / ".devgate-heartbeat.env").write_text(
        "HUB_URL=%s\nRUNNER_NAME=alpha\n" % HUB)

    assert s.enroll("alpha").returncode == 0
    assert not (s.units / "devgate-heartbeat.timer").exists(), \
        "legacy unit for THIS runner should have been retired"
    assert (s.units / "devgate-hb-alpha.timer").exists()


def test_legacy_units_are_left_when_they_belong_to_another_runner(tmp_path):
    """Not destructive: someone else's working units must survive our enroll."""
    s = Spoke(tmp_path)
    s.units.mkdir(parents=True, exist_ok=True)
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n")
    (s.home / ".devgate-heartbeat.env").write_text(
        "HUB_URL=%s\nRUNNER_NAME=gamma\n" % HUB)

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
        env=s.env, capture_output=True, text=True, timeout=60)

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
        env=s.env, capture_output=True, text=True, timeout=60)

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
    target.write_text("HEARTBEAT_TOKEN=PRECIOUS\n")

    res = s.enroll("alpha")
    assert res.returncode != 0, "token file without an owner was overwritten"
    assert "PRECIOUS" in target.read_text(), "the token was lost"


def test_unattributable_legacy_units_are_left_alone(tmp_path):
    """An owner we cannot read is not permission to delete (F1): the legacy
    guard must fail closed exactly like the per-runner guard does."""
    s = Spoke(tmp_path)
    s.units.mkdir(parents=True, exist_ok=True)
    (s.units / "devgate-heartbeat.timer").write_text("[Timer]\n")
    (s.home / ".devgate-heartbeat.env").write_text("HEARTBEAT_TOKEN=LEGACY-SECRET\n")

    assert s.enroll("newcomer").returncode == 0
    assert (s.units / "devgate-heartbeat.timer").exists(), \
        "legacy units deleted on an owner we could not read"
    assert "LEGACY-SECRET" in (s.home / ".devgate-heartbeat.env").read_text()


def test_a_runner_named_like_the_sentinel_cannot_claim_a_file(tmp_path):
    """F2: 'UNKNOWN' is a legal runner name, so an internal sentinel value
    must not be reachable through it."""
    s = Spoke(tmp_path)
    envdir = s.home / ".config" / "containers"
    envdir.mkdir(parents=True, exist_ok=True)
    target = envdir / "devgate-heartbeat-UNKNOWN.env"
    target.write_text("HEARTBEAT_TOKEN=UNATTRIBUTABLE\n")

    res = s.enroll("UNKNOWN")
    assert res.returncode != 0, "sentinel name claimed an unattributable file"
    assert "UNATTRIBUTABLE" in target.read_text()


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


# --- evaluator-image state rides the heartbeat (img-cycle-03, design D5) -----
#
# The heartbeat REPORTS image state and never enforces it: a heartbeat that
# dies blinds the whole fleet, which is strictly worse than an image field that
# reads unknown. So every failure below is an absence WITH A REASON and the
# tick still exits 0 — asserted in each test, because that is the property most
# likely to regress into "the probe acquired a hard dependency".
#
# The reasons are the cycle's own vocabulary (podman missing, store mismatch,
# absent), so a fleet view says which fault it is and therefore which fix.

IMG = "ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence"
IMG_DIGEST = "sha256:" + "a" * 64
IMG_REF = f"{IMG}@{IMG_DIGEST}"


def _image_env(tmp_path, store_absent=False, **over):
    """The image variable set as the unit's EnvironmentFile supplies it.

    The store DIRECTORY is created unless `store_absent` says otherwise: a
    provisioned host has one, and the probe deliberately refuses to create it
    (a tick pointed at a store mount that has not come up must not leave an
    empty store on the filesystem underneath — measured: real podman creates
    one as a side effect of `info`).
    """
    store = tmp_path / "store"
    if not store_absent:
        store.mkdir(exist_ok=True)
    env = {"COHERENCE_IMAGE": IMG,
           "COHERENCE_IMAGE_MANIFEST_DIGEST": IMG_DIGEST,
           "COHERENCE_PODMAN_STORE": str(store)}
    env.update(over)
    return env


def _last_heartbeat_body(s):
    posts = s.requests("/heartbeat")
    assert posts, "no heartbeat was POSTed"
    return json.loads(posts[-1]["data"])


def test_heartbeat_reports_the_pinned_ref_when_the_store_holds_it(tmp_path):
    """Converged: the digest-qualified ref, and no reason to give."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    res = s.run_helper("alpha", **_image_env(tmp_path))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] == IMG_REF, body
    assert body["image_reason"] is None, body


def test_heartbeat_reports_absence_with_a_reason_when_the_image_is_not_there(tmp_path):
    """Absent is a fact the fleet needs, and it is not the same as unknown."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    res = s.run_helper("alpha", STUB_IMAGE_EXISTS_RC="1", **_image_env(tmp_path))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] is None, body
    assert "absent" in body["image_reason"], body


def test_heartbeat_reports_a_store_mismatch_rather_than_convergence(tmp_path):
    """The D3 defect, from the fleet view: green cycler, gate cannot see it.

    A probe that asked "is the ref present?" of whichever store podman
    answered for would report convergence for a host whose gate reads a
    different store. The mismatch branch exists so that host is visible, and
    it names both paths because the fix is an EnvironmentFile edit.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    res = s.run_helper("alpha", STUB_GRAPH_ROOT="/somewhere/else",
                       **_image_env(tmp_path))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] is None, body
    assert "store mismatch" in body["image_reason"], body
    assert "/somewhere/else" in body["image_reason"], body
    assert str(tmp_path / "store") in body["image_reason"], body


def test_heartbeat_names_the_unset_variable_when_the_cycle_is_not_provisioned(tmp_path):
    """Which variable is missing, because that is the operator's next action.

    A reason that named every variable, or none, would send an operator
    looking through the whole EnvironmentFile — and on today's enrolled hosts
    none of these are set at all, which is exactly the state this renders.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = s.run_helper("alpha", COHERENCE_IMAGE=IMG,
                       COHERENCE_IMAGE_MANIFEST_DIGEST=IMG_DIGEST)
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    reason = _last_heartbeat_body(s)["image_reason"]
    assert "COHERENCE_PODMAN_STORE" in reason, reason
    # Only the missing one: \b keeps the prefix COHERENCE_IMAGE from matching
    # the longer COHERENCE_IMAGE_MANIFEST_DIGEST, which IS set in this run.
    assert not re.search(r"\bCOHERENCE_IMAGE\b", reason), reason

    # And all three, when the unit predates the cycle entirely — which is the
    # state of every already-enrolled host today.
    res = s.run_helper("alpha")
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    bare = _last_heartbeat_body(s)["image_reason"]
    for var in ("COHERENCE_IMAGE", "COHERENCE_IMAGE_MANIFEST_DIGEST",
                "COHERENCE_PODMAN_STORE"):
        assert var in bare, f"{var} not named in: {bare}"


def test_a_trailing_slash_on_the_store_is_not_a_mismatch(tmp_path):
    """A correct host with a trailing slash must read as converged.

    podman normalises the graph root it reports (measured 2026-09-24, podman
    6.1.1: `--root /tmp/ps1/` answers `/tmp/ps1`). Comparing the two paths as
    raw strings therefore calls a correctly provisioned host a mismatch — and
    since the mismatch branch skips the presence check, that host is reported
    as unable to gate until someone edits a path that was already right. The
    probe asks which DIRECTORY each name denotes instead.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    res = s.run_helper("alpha",
                       **_image_env(tmp_path,
                                    COHERENCE_PODMAN_STORE=str(tmp_path / "store") + "/"))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] == IMG_REF, body
    assert body["image_reason"] is None, body


def test_a_store_that_does_not_exist_is_named_and_never_created(tmp_path):
    """The absent-store fault, and the side effect the probe must not have.

    `podman --root X info` CREATES X when it does not exist (measured: one run
    left X/{db.sql,libpod} behind). On a host whose store mount has not come
    up that is worse than a wrong answer: an empty store is left on the
    underlying filesystem, outliving the mount, and the reason it produces
    ("pinned image absent") sends the operator to the pull path rather than to
    the mount. So the store is checked for existence before podman is asked
    anything — and the stub materialises the store exactly as podman does, so
    "it was not created" is evidence the tick never called podman rather than
    a fact that would hold anyway.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    store = tmp_path / "store"
    res = s.run_helper("alpha", **_image_env(tmp_path, store_absent=True))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] is None, body
    assert "store does not exist" in body["image_reason"], body
    assert str(store) in body["image_reason"], body
    assert not store.exists(), (
        "the tick created the store it was pointed at — a probe must not "
        "materialise a mount that has not come up")


def test_a_podman_that_fails_is_not_reported_as_a_path_mismatch(tmp_path):
    """Two faults, two fixes: broken podman is not a wrong store path.

    `graph_root="$(... || true)"` collapsed them — an empty answer never
    equals the configured store, so a store podman cannot open, a permission
    problem, or a podman that will not start all read as "store mismatch" and
    sent the operator to edit a path that was already correct.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_podman()

    res = s.run_helper("alpha", STUB_INFO_RC="125", **_image_env(tmp_path))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] is None, body
    assert "podman info failed" in body["image_reason"], body
    # It must not DIAGNOSE a mismatch. The parenthetical it does carry ("not a
    # path mismatch") is the operator's guidance — the wrong label is what the
    # old code produced, so the assertion is on the diagnosis, not the word.
    assert "store mismatch:" not in body["image_reason"], body


def test_the_podman_stub_materialises_the_store_like_podman_does(tmp_path):
    """The stub creates the store, so "the tick did not create it" MEANS something.

    Real podman materialises the store it is pointed at (measured: one run left
    `<root>/{db.sql,libpod}` behind), and the probe is built not to lean on that
    — it checks for the store before asking podman anything. That check's test
    asserts the directory is still absent afterwards, which is only evidence if
    something would have created it. This pins the stub's half: without it, the
    assertion would hold no matter what the tick did.
    """
    s = Spoke(tmp_path)
    stub = s.stub_podman()
    store = tmp_path / "never-provisioned"
    assert not store.exists()

    subprocess.run([str(stub), "--root", str(store), "info"],
                   env=s.env, capture_output=True, text=True, timeout=30)
    assert store.is_dir(), "the stub must create the store the way podman does"


def test_the_spoke_environment_carries_no_ambient_coherence_variables(tmp_path):
    """The probe's own inputs must not arrive from the ambient environment.

    These three decide which branch of the probe runs. Inheriting them would
    make the not-provisioned test's result depend on whether the machine
    running the suite happens to be provisioned — red on a provisioned host,
    and in CI a silent choice of the branch under test. The fixture scrubs
    them; this pins that, because the coupling is invisible on a host that
    does not set them (which is why it took an audit to find).
    """
    s = Spoke(tmp_path)
    leaked = sorted(k for k in s.env if k.startswith("COHERENCE_"))
    assert not leaked, f"the Spoke inherited ambient {leaked}"


def test_heartbeat_reports_podman_missing_rather_than_the_image_missing(tmp_path):
    """Two faults, two fixes — a single "no image" reason would hide both."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0          # no podman stub on PATH

    res = s.run_helper("alpha", PATH=s.path_without_podman(),
                       **_image_env(tmp_path))
    assert res.returncode == 0, f"the probe must not fail the tick: {res.stderr}"
    body = _last_heartbeat_body(s)
    assert body["image_digest"] is None, body
    assert body["image_reason"] == "podman not on PATH", body
    # podman_ok says the same thing about the same host, and the two fields
    # are not redundant: podman_ok is "can this host run a job at all", the
    # image fields are "can it run the job the pin names".
    assert body["podman_ok"] is False, body


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
