"""Shared fixture for the runner-image-cycle tests.

Not a test module: pytest collects nothing here. It exists so the stubbed
`podman`, the host fixture, and the identity constants have one home — the
cycle's tests are about the script's behaviour, and the stub is the instrument
that makes those behaviours observable, so the instrument should not be
rewritten (or silently forked) per test file.

`tests/test_runner_image_cycle.py` imports from here; the mutation battery
(`tests/mutation_battery_image_cycle.py`) edits the stub in THIS file to prove
the fixture's own side effects are load-bearing.

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

