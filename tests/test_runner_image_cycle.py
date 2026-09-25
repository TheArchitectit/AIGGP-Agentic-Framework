"""Tests for scripts/runner-image-cycle.sh — the fleet-side image cycle.

The gate never pulls (coh-rt-01), so the pinned evaluator bytes have to be
present on the host before the job starts. Nothing used to put them there:
the image appeared in no runner template, not in runner-enroll.sh, not in
hub/, and the runner container mounts exactly one volume (/_work), so the
job's podman is not automatically the host's. The failure mode this suite
exists to prevent is the quiet one — a cycler that reports success into a
store the gate cannot see, next to a doctor that SKIPs for a missing image.
That is why the store is an input here and why every assertion about it is
about the store, not about "did a pull happen".

Every assertion runs against a stubbed `podman` on PATH (no real store, no
network, no pulling): the stub records argv and answers `info`, `image
exists`, `pull`, `image inspect`, `images`, `rmi` from a JSON state file.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_image_cycle.py`
runs them too.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "runner-image-cycle.sh"
# Resolved once, before any test clobbers PATH: the no-podman case deliberately
# runs with an empty PATH, and bash must still be launchable to observe it.
BASH = shutil.which("bash") or "/bin/bash"
IMAGE = "ghcr.io/example/devgate-coherence"
RECORDED = "sha256:f470110ce0caa14bb78eabc633c1bbbf63aeb9f49b15e50cd5866788964f2c6c"
OTHER = "sha256:61170a5c2ee56ce23a485709f5110a044bdcf27b97113d3f3108e97bacbf7445"
REF = f"{IMAGE}@{RECORDED}"

# Answers the podman verbs the cycle uses, from JSON state plus env knobs:
#   STUB_PULL_RC       exit code for `podman pull`            (default 0)
#   STUB_RMI_RC        exit code for `podman rmi`             (default 0)
#   STUB_INFO_RC       exit code for `podman info`            (default 0)
#   STUB_INSPECT       what `image inspect {{.Digest}}` prints on success
#   STUB_GRAPH_ROOT    what `info {{.Store.GraphRoot}}` prints (default: the
#                      normalised --root, which is what podman actually answers)
#
# The stub reproduces two MEASURED side effects, because each is the only thing
# that makes a test non-vacuous: `info` materialises the store it is pointed at
# (so "the cycle did not create the store" means something), and `rmi` removes
# the ID's rows and the refs they own (so "the pinned image survived the prune"
# can fail).
# Global flags before the verb are parsed and recorded, so a test can assert the
# cycle addressed the store it was configured with rather than the ambient one.
# `podman images` answers from the state file's "images" list (see Host.stock),
# honouring --filter the way real podman does, and every `--format` is honoured
# field-by-field and in order: the script parses these outputs positionally, so
# a format that stops emitting a field the script reads would silently stop
# pruning while every behavioral test stayed green.
# A successful pull ADDS the ref to the store, so a post-pull verification
# sees exactly what a real one would.
PODMAN_STUB = r'''#!/usr/bin/env python3
import json, os, re, sys

state_path = os.environ["STUB_STATE"]
state = json.load(open(state_path)) if os.path.exists(state_path) else {"present": []}

raw = sys.argv[1:]
root, rest, i = None, [], 0
while i < len(raw):
    if raw[i] == "--root" and i + 1 < len(raw):
        root, i = raw[i + 1], i + 2
    else:
        rest.append(raw[i])
        i += 1

with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write(json.dumps({"root": root, "args": rest}) + "\n")

def save():
    with open(state_path, "w") as fh:
        json.dump(state, fh)

def fmt_of(arglist, default):
    """Field names from --format, in order. Dotted paths allowed (Store.GraphRoot)."""
    for i, a in enumerate(arglist):
        if a == "--format" and i + 1 < len(arglist):
            return re.findall(r"\{\{\.([\w.]+)\}\}", arglist[i + 1]) or default
    return default

def emit(fields, row):
    print(" ".join(row.get(f, "<none>") for f in fields))

if not rest:
    sys.exit(125)

if rest[0] == "info":
    # MEASURED 2026-09-24 (podman 6.1.1): `podman --root <path> info --format
    # '{{.Store.GraphRoot}}'` answers with the path NORMALISED, not verbatim —
    # `--root /tmp/ps1/` answers `/tmp/ps1`, and `--root /tmp//ps1` answers
    # `/tmp/ps1` too. So this stub normalises as well. It did not always: it
    # used to echo its argument, which encoded the opposite premise and meant
    # the real comparison in the script was never exercised against the answer
    # podman actually gives. A verbatim stub agrees with a byte comparison, so
    # the two masked each other and a trailing-slash typo read as a mismatch.
    #
    # `podman --root X info` also MATERIALISES X when it does not exist
    # (measured: one run left X/{db.sql,libpod} behind). That side effect is
    # reproduced here rather than omitted, because it is the only thing that
    # makes an assertion about the store NOT being created mean anything.
    if root and root != "<none>":
        os.makedirs(os.path.realpath(root), exist_ok=True)
    row = {"Store.GraphRoot": os.environ.get("STUB_GRAPH_ROOT")
           or (os.path.realpath(root) if root else ""),
           "Host.Security.Rootless": "false"}
    if os.environ.get("STUB_INFO_RC"):
        sys.stderr.write("Error: cannot connect to Podman\n")
        sys.exit(int(os.environ["STUB_INFO_RC"]))
    emit(fmt_of(rest, ["Store.GraphRoot"]), row)
    sys.exit(0)

if rest[:2] == ["image", "exists"]:
    sys.exit(0 if rest[2] in state["present"] else 1)

if rest[0] == "pull":
    ref = rest[-1]
    rc = int(os.environ.get("STUB_PULL_RC", "0"))
    if rc == 0:
        state.setdefault("present", []).append(ref)
        save()
    else:
        sys.stderr.write("Error: manifest unknown\n")
    sys.exit(rc)

if rest[:2] == ["image", "inspect"]:
    ref = rest[-1]
    if ref not in state["present"]:
        sys.stderr.write("Error: no such image\n")
        sys.exit(125)
    # A real store answers with the ref's own manifest digest (that is the
    # pullable identity, measured 2026-09-23); STUB_INSPECT overrides it to
    # model a store holding different bytes under the same ref.
    digest = os.environ.get("STUB_INSPECT") or (ref.rsplit("@", 1)[-1] if "@" in ref else "<none>")
    row = {"Digest": digest, "Id": "<none>", "RepoTags": "<none>",
           "RepoDigests": ["[%s]" % ref] if "@" in ref else []}
    emit(fmt_of(rest, ["Digest"]), row)
    sys.exit(0)

if rest[0] == "images":
    ref_filter = None
    i = 1
    while i < len(rest):
        if rest[i] == "--filter" and i + 1 < len(rest):
            ref_filter = rest[i + 1].split("=", 1)[-1]
            i += 2
        else:
            i += 1
    # MEASURED 2026-09-24 on real podman: `--filter reference=<repo>` matches
    # the image NAME, not the repository. Asked about
    # `ghcr.io/thearchitectit/.../devgate-coherence`, podman ALSO listed
    # `localhost/devgate-coherence:latest` — a different registry entirely.
    # Emulated here, because otherwise a test could not tell whether the
    # script's own scoping check (or merely the filter) is doing the work.
    want = ref_filter.rsplit("/", 1)[-1].split(":")[0] if ref_filter else None
    for img in state.get("images", []):
        have = img["repository"].rsplit("/", 1)[-1].split(":")[0]
        if want is not None and want != have:
            continue
        emit(fmt_of(rest, ["ID", "Repository", "Tag", "Digest"]),
             {"ID": img["id"], "Repository": img["repository"],
              "Tag": img.get("tag", "<none>"), "Digest": img["digest"]})
    sys.exit(0)

if rest[0] == "rmi":
    rc = int(os.environ.get("STUB_RMI_RC", "0"))
    if rc != 0:
        sys.stderr.write("Error: image is in use by a container\n")
        sys.exit(rc)
    # MEASURED 2026-09-24: `podman rmi <id>` removes every row that ID carries,
    # and the image leaves the store. The stub used to return 0 without
    # touching state, so "the pinned image survived the prune" was an assertion
    # about a store where nothing could ever be removed — green whatever the
    # script did. Reaping the rows here is what gives the post-prune
    # re-verification something to catch.
    target = rest[-1]
    reaped = [i for i in state.get("images", []) if i["id"] == target]
    gone = set()
    for i in reaped:
        gone.update(i.get("refs") or ["%s@%s" % (i["repository"], i["digest"])])
    state["images"] = [i for i in state.get("images", []) if i["id"] != target]
    state["present"] = [r for r in state.get("present", []) if r not in gone]
    save()
    sys.exit(0)

sys.stderr.write("stub: unhandled argv %r\n" % (rest,))
sys.exit(125)
'''


class Host:
    """A fake runner host with podman stubbed on PATH."""

    def __init__(self, tmp_path, store_exists=True, **knobs):
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        self.log = tmp_path / "podman.jsonl"
        self.log.write_text("")
        self.state = tmp_path / "podman-state.json"
        self.state.write_text("")
        p = bindir / "podman"
        p.write_text(PODMAN_STUB)
        p.chmod(0o755)
        self.bindir = bindir
        # A provisioned host's store is a MOUNT that exists before anything
        # runs, so it exists here by default. `store_exists=False` models the
        # host whose mount has not come up — the case where an empty store
        # written onto the underlying filesystem outlives the mount.
        self.store = str(tmp_path / "store")
        if store_exists:
            (tmp_path / "store").mkdir(exist_ok=True)
        self.env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "STUB_LOG": str(self.log),
            "STUB_STATE": str(self.state),
            "COHERENCE_IMAGE": IMAGE,
            "COHERENCE_IMAGE_MANIFEST_DIGEST": RECORDED,
            "COHERENCE_PODMAN_STORE": self.store,
        }
        self.env.update({k: str(v) for k, v in knobs.items()})
        self.attach(REF)  # a host that already has the pinned image

    # --- store -----------------------------------------------------------------
    def _state(self):
        text = self.state.read_text()
        return json.loads(text) if text.strip() else {"present": []}

    def _save(self, state):
        self.state.write_text(json.dumps(state))

    def attach(self, *refs):
        """Refs the store resolves. A digest-qualified ref carries the digest
        it was pulled by — which is the manifest digest, per the 2026-09-23
        measurement — so an attached ref verifies unless STUB_INSPECT lies."""
        state = self._state()
        state["present"] = list(refs)
        self._save(state)

    def stock(self, *images):
        """Publish the `podman images` listing: (id, repository, digest[, tag[,
        refs]]) rows. Tag defaults to `<none>`, which is how podman lists an
        image pulled by digest and never tagged.

        `refs` names the store refs that ID owns — what `image exists` would
        answer true for, and what `rmi <id>` takes away. It defaults to
        `repository@digest`, which is right for a digest-pulled row, and exists
        as an override for the case MEASURED 2026-09-24 where a row's digest is
        NOT the ref: the listing's `.Digest` and `inspect`'s `.Digest` are two
        different values for the same bytes (`sha256:294b683c…` vs
        `sha256:d56c381f…` for one alpine pull), so a listing can name an ID
        with a digest that is not the one the record pins while that ID is
        exactly what the pinned ref resolves to."""
        state = self._state()
        state["images"] = [
            {"id": r[0], "repository": r[1], "digest": r[2],
             "tag": r[3] if len(r) > 3 else "<none>",
             "refs": list(r[4]) if len(r) > 4 else None}
            for r in images]
        self._save(state)

    # --- inspection ------------------------------------------------------------
    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines() if l]

    def verbs(self):
        return [c["args"][0] for c in self.calls() if c["args"]]

    def roots(self):
        """Every --root the cycle passed; `None` for a call that omitted it."""
        return {c["root"] for c in self.calls()}

    def pull_refs(self):
        return [c["args"][-1] for c in self.calls()
                if c["args"] and c["args"][0] == "pull"]

    def rmis(self):
        return [c["args"][-1] for c in self.calls()
                if c["args"] and c["args"][0] == "rmi"]

    def runs(self, env=None, path_prefix=None, **extra):
        env = dict(self.env if env is None else env)
        env.update({k: str(v) for k, v in extra.items()})
        if path_prefix is not None:
            env["PATH"] = path_prefix
        return subprocess.run([BASH, str(SCRIPT)], env=env,
                              capture_output=True, text=True, timeout=60)


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
        h.log.write_text("")  # each case judged on its own calls
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
