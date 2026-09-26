# // spec: coh-int-01, coh-int-05, coh-rt-01
"""hub.coherence.invoke — the ONE request/launch builder.

The CI template and the local developer command both used to hand-write the
`request.json`/`launch.json` payload. Two implementations of one contract, and
the CI copy silently drifted to three of the seven required fields — a gate that
exits 30 on its own input (round-18 D1). This module is the single source that
replaces both copies: it lives under `hub/` so `COPY hub/` puts it INSIDE the
pinned image, which makes coh-int-01's byte-equivalence provable — CI and a
local checkout run the identical builder bytes from the identical image, rather
than asserting equivalence between two shells.

What the builder must get right that a shell cannot:
  * the request is validated against `request.schema.json` by the service before
    any assertion runs, so all seven fields — and an `expected_digest` on every
    inputRef — must be present and real;
  * `policy.expected_digest` is sourced from the context's signed
    `policy_binding`, NOT recomputed from the policy bytes. Recomputing would
    make `policy.resolve`'s identity check a tautology (design.md round-18):
    the authority is the signed binding, and a builder that derives the claim
    from the same bytes it later verifies proves nothing.
"""
from __future__ import annotations

from . import context as _context
from . import manifest as _manifest
from . import package as _package

# The four input mounts, by target. `/output` is deliberately absent: it is the
# launcher's single writable bind, added in run_containerized, never declared
# here (naming it would hand the container a writable path the isolation
# profile forbids). Target names follow design.md round-15.
_MOUNT_TARGETS = (("subject_root", "/input"), ("openspec_root", "/openspec"),
                  ("policy_root", "/policy"), ("context_root", "/context"))


def build_request(subject_root: str, openspec_root: str, policy_root: str,
                  context_root: str, outputs: str,
                  semantics: str = "fresh-promotion",
                  request_id: str | None = None) -> dict:
    """Emit a request.schema.json-valid request.

    Digests are computed from the real input content, except the policy digest,
    which is read from the context's signed policy_binding (see module note).
    The context is loaded through `context.load`, so a context this service would
    refuse to run (unsigned under a configured control-plane key, unparseable,
    stale) is refused here too — the builder cannot launder a bad context into a
    well-formed request.
    """
    subject_digest = _manifest.build(subject_root)["subject_digest"]
    openspec_digest = _package.resolve(openspec_root)["package_digest"]
    ctx = _context.load(context_root)
    context_digest = ctx["context_digest"]

    # No None-guard here on purpose: context.load validated the context against
    # evaluation-context.schema.json, which makes policy_binding and its
    # expected_digest required, so the indexing below cannot fail. A defensive
    # `if not policy_digest: raise` would be an unreachable branch — the exact
    # false-confidence guard round-18 exists to keep out (see design.md).
    policy_digest = ctx["policy_binding"]["expected_digest"]

    req = {
        "api_version": "devgate.spec-coherence/v1",
        "subject": {"kind": "source-tree", "root": subject_root,
                    "expected_digest": subject_digest},
        "openspec": {"root": openspec_root, "expected_digest": openspec_digest},
        "policy": {"root": policy_root, "expected_digest": policy_digest},
        "context": {"root": context_root, "expected_digest": context_digest},
        "semantics": semantics,
        "outputs": outputs,
    }
    if request_id:
        req["request_id"] = request_id
    return req


def build_launch(image: str, profile: str, manifest_digest: str,
                 subject_root: str, openspec_root: str, policy_root: str,
                 context_root: str, *, user: str = "1000:1000",
                 limits: dict | None = None) -> dict:
    """Emit a launch config that `launcher.validate_launch` accepts.

    The isolation defaults below are the reference profile (network=none,
    read-only rootfs, cap_drop ALL, one non-root user). One mount per input
    root, all read-only, unique targets. The driver rewrites the request's
    host-side roots to these targets before launch, so a root with no covering
    mount here is an `unmounted-root` rejection at run time — which is why this
    builder, and not the CI shell, owns the mount list.
    """
    roots = {"subject_root": subject_root, "openspec_root": openspec_root,
             "policy_root": policy_root, "context_root": context_root}
    mounts = [{"source": roots[attr], "target": target, "readonly": True}
              for attr, target in _MOUNT_TARGETS]
    return {
        "image": f"{image}@{manifest_digest}",
        "user": user,
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "cap_add": [],
        "network": "none",
        "mounts": mounts,
        "scratch": {"size": "64m"},
        "limits": limits or {"memory": "256m", "cpus": "1.0", "time_s": 300,
                             "pids": 64, "nofile": 128, "output_bytes": 1048576},
        "profile": profile,
        "image_manifest_digest": manifest_digest,
    }


def _main(argv=None) -> int:
    """CLI entry: write request.json + launch.json for the driver to consume.

    The CI template calls this and nothing else in the request-construction
    path — no heredoc, no inline digest math. That is the point: shell
    assembling a payload is how D1 shipped, and keeping the shell's job to a
    single command is what makes the CI and local paths byte-equivalent rather
    than "equivalent in spirit."
    """
    import argparse
    ap = argparse.ArgumentParser(
        prog="python -m hub.coherence.invoke",
        description="Build a coherence request + launch config from input roots.")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--openspec", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--context", required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--manifest-digest", required=True)
    ap.add_argument("--semantics", default="fresh-promotion")
    ap.add_argument("--request-id", default=None)
    ap.add_argument("--request-out", default="request.json")
    ap.add_argument("--launch-out", default="launch.json")
    args = ap.parse_args(argv)

    import json as _json
    from pathlib import Path as _P
    req = build_request(args.subject, args.openspec, args.policy,
                        args.context, args.outputs,
                        semantics=args.semantics, request_id=args.request_id)
    cfg = build_launch(args.image, args.profile, args.manifest_digest,
                       args.subject, args.openspec, args.policy, args.context)
    _P(args.request_out).write_text(_json.dumps(req, sort_keys=True), encoding="utf-8")
    _P(args.launch_out).write_text(_json.dumps(cfg, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
