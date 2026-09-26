"""Tests for the heartbeat's evaluator-image probe (img-cycle-03, design D5).

Split out of `test_runner_enroll.py`, which had grown past the 600-line hard
limit: these test `runner-heartbeat.sh`'s image fields, not enrollment. They
still enroll a runner first, because the probe reads its configuration from
the unit's EnvironmentFile and that file is what enrollment writes — so the
enrollment is setup here, not the subject.

The heartbeat REPORTS image state and never enforces it: a heartbeat that
dies blinds the whole fleet, which is strictly worse than an image field that
reads unknown. So every failure below is an absence WITH A REASON and the
tick still exits 0 — asserted in each test, because that is the property most
likely to regress into "the probe acquired a hard dependency".

The reasons are the cycle's own vocabulary (podman missing, store mismatch,
absent), so a fleet view says which fault it is and therefore which fix.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_heartbeat_image.py`
runs them too.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# Only so `tests.fixtures` imports in the standalone run (`python3
# tests/test_runner_heartbeat_image.py`, whose sys.path[0] is tests/ and not
# the repo root); pytest resolves it either way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.runner_spoke import Spoke  # noqa: E402


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
                   env=s.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
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
