"""Tests for scripts/runner-image-cycle.sh — the fleet-side image cycle.

The gate never pulls (coh-rt-01), so the pinned evaluator bytes have to be
present on the host before the job starts. Nothing used to put them there:
the image appeared in no runner template, not in runner-enroll.sh, not in
hub/ — and the runner container mounts exactly one volume (/_work), so the
job's podman is not automatically the host's. Enrollment now installs this
timer (templates/runner/README.md, "The evaluator image on a runner host"),
which makes the mounted-volume fact a DOCUMENTED per-fleet choice rather than
something the script can discover. The failure mode this suite exists to
prevent is the quiet one — a cycler that reports success into a store the gate
cannot see, next to a doctor that SKIPs for a missing image. That is why the
store is an input here and why every assertion about it is about the store,
not about "did a pull happen".

The stubbed podman and the host fixture live in `image_cycle_harness.py`
beside this file, because they are the instrument rather than the subject:
what is asserted here is the script's behaviour, and the instrument is shared
so it cannot drift between consumers.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_image_cycle.py`
runs them too.
"""
import sys
from pathlib import Path

# The harness is a sibling module, not an installed package: this keeps the
# file runnable both under pytest (rootdir on sys.path) and directly, the way
# the rest of the suite's dual-runnable scripts are.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from image_cycle_harness import (  # noqa: E402
    BASH, IMAGE, OTHER, PODMAN_STUB, RECORDED, REF, REPO_ROOT, SCRIPT, Host,
)

import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests
# shell out to things that do not exist on Windows, so they cannot run there.
# A test that cannot run must SKIP, not fail -- failing here is indistinguishable
# from real breakage, and a Windows developer cannot tell which failures matter.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")


# --- convergence (img-cycle-01) -------------------------------------------------

def test_absent_image_is_pulled_by_digest_and_converges(tmp_path):
    h = Host(tmp_path)
    h.attach()  # empty store
    res = h.runs()
    assert res.returncode == 0, f"cycle failed on a pullable host: {res.stderr}"
    assert h.pull_refs() == [REF], f"pulled {h.pull_refs()}, expected [{REF}]"


def test_present_image_is_not_pulled(tmp_path):
    h = Host(tmp_path)  # attach(REF) in __init__
    res = h.runs()
    assert res.returncode == 0
    assert not h.pull_refs(), "a host already holding the pinned digest was re-pulled"


def test_a_converged_host_says_so(tmp_path):
    """stdout is the whole of what a fleet operator sees (the timer's journal),
    so a convergence that prints nothing is indistinguishable from a tick that
    never ran. The line must also come LAST — it is a claim about the store, so
    printing it before the checks that could contradict it means the one line
    grepped for says the opposite of the exit code."""
    h = Host(tmp_path)
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert "converged" in res.stdout.lower(), (
        f"a converged host did not say so: {res.stdout!r}")
    assert REF in res.stdout, f"the claim did not name the ref: {res.stdout!r}"


def test_the_target_is_digest_qualified_never_a_tag(tmp_path):
    """coh-rt-01: the executed bytes are resolved by digest. A cycle that
    follows a tag would provision whatever the tag points at today."""
    h = Host(tmp_path)
    h.attach()  # empty store, so this host must pull for the check to have a subject
    res = h.runs()
    assert h.pull_refs(), "nothing was pulled, so the target was never exercised"
    for ref in h.pull_refs():
        assert ref == REF, f"pulled something other than the recorded identity: {ref}"


# --- the store is the thing that matters (img-cycle-02, design D3) --------------

def test_every_podman_call_is_addressed_to_the_configured_store(tmp_path):
    """A cycle that converges into the ambient store while the gate reads
    another one is the failure this tick exists to prevent — and it is
    invisible unless the store is named on every call."""
    h = Host(tmp_path)
    h.attach()
    h.stock(("bbbb", IMAGE, OTHER))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert h.roots() == {h.store}, (
        f"calls addressed {h.roots()} instead of the configured store {h.store!r}")


def test_a_store_other_than_the_configured_one_fails_closed(tmp_path):
    """`--root` is a request; `info` is the answer. If podman's graph root is
    not the configured path, this tick cannot claim those bytes are where the
    gate will look — so it must not."""
    h = Host(tmp_path, STUB_GRAPH_ROOT="/somewhere/else")
    h.attach()
    res = h.runs()
    assert res.returncode != 0, "a mismatched store reported convergence"
    msg = res.stdout + res.stderr
    assert "/somewhere/else" in msg and h.store in msg, (
        f"the store mismatch was not named on both sides: {msg!r}")
    assert not h.pull_refs(), "pulled into a store it had not verified"


def test_a_trailing_slash_on_the_store_is_not_a_mismatch(tmp_path):
    """MEASURED 2026-09-24 (podman 6.1.1): `--root /tmp/ps1/` answers
    `/tmp/ps1`. The comparison is between two NAMES for one directory, so a
    spelling difference — a trailing slash, an ordinary EnvironmentFile typo —
    must not be read as two different stores. Compared as raw strings it is,
    and the tick then refuses to converge on a host that is configured
    correctly."""
    h = Host(tmp_path, store_exists=True)
    h.env["COHERENCE_PODMAN_STORE"] = h.store + "/"
    res = h.runs()
    assert res.returncode == 0, (
        f"a trailing slash made a correctly provisioned host read as a store "
        f"mismatch: {res.stdout + res.stderr!r}")
    assert "mismatch" not in (res.stdout + res.stderr).lower(), res.stdout


def test_a_podman_that_fails_is_not_reported_as_a_store_mismatch(tmp_path):
    """A podman that cannot answer is not a wrong path. `|| true` collapses the
    failure to an empty string, which equals no configured store — so every
    cause (a broken store, a permission problem, a podman that will not start)
    arrived as "store mismatch" and sent the operator to edit a path that was
    already correct. Each cause needs its own words."""
    h = Host(tmp_path, STUB_INFO_RC=125)
    h.attach()
    res = h.runs()
    msg = (res.stdout + res.stderr)
    assert res.returncode != 0, "a podman that could not answer reported convergence"
    assert "store mismatch" not in msg.lower(), (
        f"a failure to answer was rendered as a store mismatch: {msg!r}")
    assert "podman" in msg.lower(), f"the failure did not name podman: {msg!r}"
    assert not h.pull_refs(), "pulled without ever verifying the store"


def test_the_store_is_never_created_by_the_cycle(tmp_path):
    """MEASURED 2026-09-24: `podman --root X info` MATERIALISES X when it is
    missing (one run left X/{db.sql,libpod} behind). The store is a mount, so
    creating it on a host whose mount has not come up leaves an empty store on
    the underlying filesystem — one that outlives the mount, is filled by the
    pull that follows, and is invisible from the mount the gate actually reads.
    So existence is checked before podman is asked anything."""
    h = Host(tmp_path, store_exists=False)
    res = h.runs()
    msg = (res.stdout + res.stderr)
    assert res.returncode != 0, "a host with no store reported convergence"
    assert h.store in msg, f"the missing store was not named: {msg!r}"
    assert not Path(h.store).exists(), (
        "the cycle created the store it was pointed at — a cycle must not "
        "bring up storage that has not been mounted")
    assert not h.calls(), "asked podman about a store that does not exist"


def test_the_pinned_image_is_still_there_after_the_prune(tmp_path):
    """Exit 0 claims the recorded bytes are in this store. The prune reaps IDs,
    and `podman rmi <id>` takes every row that ID carries — so the reap set is
    decided by reasoning about podman's listing, and reasoning is exactly what
    this repository does not accept in place of a check. MEASURED 2026-09-24:
    the listing's `.Digest` and `inspect`'s `.Digest` are DIFFERENT values for
    the same bytes, so a listing can legitimately report a digest that is not
    the recorded one for the pinned image — which is how the guard below lets
    the pinned ID into the reap set. Re-verifying afterwards is what turns the
    invariant into an observation."""
    h = Host(tmp_path)
    # The listing names ID `aaaa` with the digest OTHER, while `aaaa` is what
    # the pinned ref resolves to — the listing's digest is not the ref. So the
    # guard reads `aaaa` as a superseded build of this repo (same repository,
    # untagged, digest not the recorded one) and reaps the pinned image.
    h.stock(("aaaa", IMAGE, OTHER, "<none>", [REF]))
    h.attach(REF)
    res = h.runs()
    assert "aaaa" in h.rmis(), "the scenario did not exercise the reap at all"
    assert res.returncode != 0, (
        "the prune removed the pinned image and the tick still reported "
        "convergence")
    assert "converged" not in res.stdout.lower(), res.stdout


# --- fail-closed paths (img-cycle-01, img-cycle-02) -----------------------------

def test_pull_failure_is_not_a_pass(tmp_path):
    h = Host(tmp_path, STUB_PULL_RC=1)
    h.attach()
    res = h.runs()
    assert res.returncode != 0, "a failed pull reported success"
    assert "pull failed" in res.stderr and REF in res.stderr, (
        f"the cycle's own failure did not name what could not be fetched: {res.stderr!r}")


def test_digest_mismatch_after_pull_fails_closed(tmp_path):
    """D2: a pulled ref whose manifest digest is not the recorded one is not
    the pinned bytes — the exact axis the S4 pin once shipped wrong."""
    h = Host(tmp_path, STUB_INSPECT=OTHER)
    h.attach()
    res = h.runs()
    assert res.returncode != 0, "a store holding different bytes reported convergence"
    assert OTHER in (res.stdout + res.stderr) and RECORDED in (res.stdout + res.stderr), \
        "the mismatch was not named on both sides"


def test_podman_missing_is_a_failure_not_a_skip(tmp_path):
    """A tick that cannot evaluate must not look like a converged host."""
    h = Host(tmp_path)
    empty = tmp_path / "empty-bin"
    empty.mkdir(exist_ok=True)
    res = h.runs(path_prefix=str(empty))
    assert res.returncode != 0, "no podman reported success"
    assert "podman" in (res.stdout + res.stderr).lower(), (
        f"the failure did not say podman was the problem: {res.stderr!r}")


def test_missing_env_is_a_refusal_not_a_crash(tmp_path):
    """Each required input, absent, must produce a DELIBERATE refusal that
    names it. Exit code alone is not enough: a script that dies on
    `set -u` also exits non-zero with nothing but "unbound variable", which
    tells an operator nothing about which EnvironmentFile line is missing —
    and reads identically to a refusal to any caller that checks only rc."""
    h = Host(tmp_path)
    for missing in ("COHERENCE_IMAGE", "COHERENCE_IMAGE_MANIFEST_DIGEST",
                    "COHERENCE_PODMAN_STORE"):
        h.log.write_text("", encoding="utf-8")  # each case judged on its own calls
        env = {k: v for k, v in h.env.items() if k != missing}
        res = h.runs(env=env)
        msg = res.stdout + res.stderr
        assert res.returncode != 0, f"a cycle with {missing} unset reported success"
        assert not h.calls(), "reached podman before validating its own input"
        assert f"{missing} is not set" in msg, (
            f"{missing} unset did not produce a refusal naming it — a crash is "
            f"not a refusal: {msg!r}")


def test_a_tag_in_the_digest_variable_is_refused(tmp_path):
    """Provisioning `:main` where a digest belongs is how a host ends up
    running unreviewed bytes while reporting convergence. A *truncated* or
    malformed digest is worse than useless: it pulls the wrong bytes and never
    matches at prune time."""
    for bad in ("main", "sha256:abc", "sha256:" + "f" * 63, "sha256:" + "g" * 64):
        h = Host(tmp_path, COHERENCE_IMAGE_MANIFEST_DIGEST=bad)
        h.attach(f"{IMAGE}:main")
        res = h.runs()
        assert res.returncode != 0, f"a non-digest identity was accepted: {bad!r}"
        assert not h.calls(), f"reached podman with a non-digest identity: {bad!r}"


def test_a_tag_in_the_image_variable_is_refused(tmp_path):
    """`repo:tag@sha256:…` is not a ref podman resolves by digest, and a tag
    here silently stops the prune comparison from ever matching — superseded
    builds then accumulate invisibly."""
    h = Host(tmp_path, COHERENCE_IMAGE=f"{IMAGE}:main")
    h.attach(f"{IMAGE}:main@{RECORDED}")
    res = h.runs()
    assert res.returncode != 0, "a tagged repository was accepted where a repo belongs"
    assert not h.calls(), "reached podman with a tagged repository"


# --- pruning is scoped to this repo (disk hygiene, never a data loss) ----------

def test_superseded_build_of_the_same_repo_is_pruned(tmp_path):
    h = Host(tmp_path)
    h.stock(("aaaa", IMAGE, RECORDED), ("bbbb", IMAGE, OTHER))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert "bbbb" in h.rmis(), "the superseded build of this repo was left behind"
    assert "aaaa" not in h.rmis(), "the pinned image itself was removed"


def test_prune_never_removes_an_image_from_another_repository(tmp_path):
    """Measured 2026-09-24 on real podman: `podman images --filter
    reference=<repo>` is NOT repository-scoped. Asked about
    `ghcr.io/.../devgate-coherence`, podman also listed
    `localhost/devgate-coherence:latest` — a different registry whose name
    happens to match. Pruning that listing would delete a host's local
    devgate-coherence build, which is exactly the tag the CI build job
    creates. So the script's own repository comparison has to be the thing
    that excludes it — a filter in the argv is not a scope guarantee."""
    h = Host(tmp_path)
    h.stock(("aaaa", IMAGE, RECORDED),
            ("cccc", "localhost/devgate-coherence", OTHER))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert "cccc" not in h.rmis(), (
        "an image from a different repository was pruned — podman's reference "
        "filter is not a scope guarantee")


def test_prune_never_removes_an_id_carrying_another_name(tmp_path):
    """Measured 2026-09-24: one image ID can carry two repository names, and
    `podman rmi <id>` removes all of them. Reaping an ID because one of its
    names is scoped would take the other name down with it."""
    h = Host(tmp_path)
    h.stock(("dddd", IMAGE, OTHER), ("dddd", "localhost/devgate-coherence", OTHER))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert "dddd" not in h.rmis(), (
        "an ID carrying a name outside this repository was reaped whole")


def test_a_locally_built_tag_of_this_repo_is_not_pruned(tmp_path):
    """A digest-pulled image that was never tagged lists with Tag `<none>`; one
    built or pulled under a name lists WITH that name. Only the former is a
    superseded registry build — the latter is someone's working image, under
    the very repo name the CI build job uses.

    MEASURED 2026-09-24, correcting what this docstring and the script's own
    comment used to claim: a local build lists WITH a digest
    (`sha256:df67b148…` for a `FROM scratch` build), not "a tag and no digest".
    The Tag is therefore the whole of the discrimination — the digest
    comparison cannot be doing any of this work, and a reader who believed it
    was would think a tagged build was excluded twice over."""
    h = Host(tmp_path)
    h.stock(("eeee", IMAGE, "<none>", "latest"))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert "eeee" not in h.rmis(), "a locally built, tagged image of this repo was pruned"


def test_a_failed_prune_does_not_fail_the_cycle(tmp_path):
    """Convergence is the contract; reclaiming disk is hygiene. A build held
    by a running container must not turn a converged host red."""
    h = Host(tmp_path, STUB_RMI_RC=1)
    h.stock(("bbbb", IMAGE, OTHER))
    res = h.runs()
    assert res.returncode == 0, "a prune failure failed a converged host"
    assert "bbbb" in (res.stdout + res.stderr), \
        "the prune failure was silent — nothing named what was left behind"


def test_pruning_can_be_turned_off(tmp_path):
    h = Host(tmp_path, IMAGE_CYCLE_PRUNE=0)
    h.stock(("bbbb", IMAGE, OTHER))
    res = h.runs()
    assert res.returncode == 0, res.stderr
    assert not h.rmis(), "pruning ran despite IMAGE_CYCLE_PRUNE=0"


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
