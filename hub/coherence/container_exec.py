# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04, coh-dec-04
"""Host-side containerized execution driver (`--launch-config`).

Validates the launch configuration OUTSIDE the container against the
execution-profile registry (coh-rt-02: a container never self-certifies;
coh-id-04: the declared profile and platform manifest digest must resolve and
match the registry), rewrites the request so every root points at its
container mount target, and executes the pinned image under the launcher's
enforced flag set (coh-rt-01, coh-rt-05, coh-rt-07).

The rewritten request is staged INSIDE the output directory (bound at
/output): the in-container CLI emits every envelope beside its request file,
so staging there is what makes in-container error envelopes reach the host
through the single designated output bind. `request.outputs` names the
HOST-side output directory; inside the container it is always rewritten to
/output. The output directory must be readable and writable by the container
user.

Every failure mode maps onto the frozen exit-code contract (coh-dec-04):
a launch that fails validation never reaches assertions (exit 30, ERROR
class); a container killed for exceeding its time or output limits is
incomplete execution (exit 32 — coh-rt-05: exhaustion is ERROR, never PASS);
a completed container whose exit code and result bundle disagree — or whose
exit code is not a contract code at all (podman-level failure) — is ERROR
(coh-dec-01: disagreement is never resolved in favor of the permissive
signal). A coherent completed run relays the container's own exit code and
canonical result untouched.
"""
import json
import os
from pathlib import Path

from . import launcher, profiles, result

STAGED_REQUEST_NAME = "request.container.json"
REQUEST_TARGET = "/output/" + STAGED_REQUEST_NAME
OUTPUT_TARGET = "/output"

# Exit code -> the only decision state a parseable result may carry for it
# (coh-dec-04: every exit code maps to exactly one decision state). A code
# outside this table is not a contract exit and can never be relayed.
_DECISION_FOR_CODE = {0: "PASS", 10: "ADVISORY", 20: "FAIL",
                      30: "ERROR", 31: "ERROR", 32: "ERROR",
                      33: "ERROR", 40: "ERROR"}


def _fail(out_dir: str, error_class: str, reason: str, stage: str,
          identities: dict = None) -> int:
    env = result.error_envelope(error_class, reason, stage, identities or {})
    result.emit_with_fallback(out_dir, result.to_canonical(env))
    _, code = result.decide([], 0, error_class=error_class)
    return code


def _container_path(root: str, mounts: list):
    """Container target for a host root, through the longest matching
    readonly mount source (exact path or path-prefix). None if uncovered."""
    real = os.path.realpath(root)
    best = None
    for mt in mounts:
        if not isinstance(mt, dict):
            continue
        src = os.path.realpath(mt.get("source") or "")
        tgt = mt.get("target")
        if not isinstance(tgt, str) or not tgt:
            continue
        if real == src or real.startswith(src + os.sep):
            if best is None or len(src) > best[0]:
                best = (len(src), tgt + real[len(src):])
    return best[1] if best else None


def _rewrite_roots(req: dict, mounts: list) -> dict:
    """Rewrite the request for execution inside the container: each root is
    expressed as its container mount target, and outputs become the single
    designated output bind. A root with no covering mount cannot run honestly
    inside the container — reject before launch (exit-30 class)."""
    out = json.loads(json.dumps(req))
    for section in ("subject", "openspec", "policy", "context"):
        node = out.get(section)
        root = node.get("root") if isinstance(node, dict) else None
        if not isinstance(root, str) or not root:
            # Malformed roots stay untouched: the in-container service
            # rejects them against the frozen request contract.
            continue
        target = _container_path(root, mounts)
        if target is None:
            raise launcher.LaunchError(f"unmounted-root:{section}")
        out[section]["root"] = target
    out["outputs"] = OUTPUT_TARGET
    return out


def run_containerized(request_path: str, launch_cfg_path: str,
                      registry_path: str) -> int:
    out_dir = str(Path(request_path).resolve().parent)
    try:
        req = json.loads(Path(request_path).read_text())
        cfg = json.loads(Path(launch_cfg_path).read_text())
    except (OSError, json.JSONDecodeError, ValueError) as e:
        return _fail(out_dir, "invalid-input",
                     f"malformed request or launch config: {e}", "invocation")
    if not isinstance(req, dict) or not isinstance(cfg, dict):
        return _fail(out_dir, "invalid-input",
                     "request and launch config must be JSON objects",
                     "invocation")
    raw_out = req.get("outputs")
    if isinstance(raw_out, str) and "\x00" in raw_out:
        return _fail(out_dir, "invalid-input",
                     "outputs contains an embedded NUL character", "invocation")
    host_out = raw_out.strip() if isinstance(raw_out, str) else ""
    if not host_out:
        host_out = out_dir

    try:
        reg = profiles.load_registry(registry_path)
        # Validate the complete launch config BEFORE anything is rewritten
        # into the request.
        ctx = launcher.validate_launch(
            cfg, [p["label"] for p in reg["profiles"]])
        profiles.resolve_profile(reg, ctx["profile"])
        profiles.check_launch_digest(reg, ctx["profile"],
                                     ctx["image_manifest_digest"])
        # Round-8 spec audit (coh-rt-01/coh-id-04): the registry pin must
        # bind the EXECUTED ref, not just the declared manifest field — a
        # config declaring the pinned digest while pointing the ref at other
        # bytes would run unverified content. The registry pins exactly one
        # digest per profile, so the ref must carry that pin itself.
        if ctx["image"].rsplit("@", 1)[1] != ctx["image_manifest_digest"]:
            raise launcher.LaunchError(
                f"image-ref-digest-mismatch:{ctx['profile']}")
        # Staging inside a mount source would write the request (and every
        # in-container envelope) into the very input tree being evaluated
        # (round-7 finding 4): the designated output bind must lie outside
        # every input source. Validation already realpath-normalized the
        # sources, so the comparison is identity-exact.
        real_out = os.path.realpath(host_out)
        for mt in ctx["mounts"]:
            src = mt["source"]
            if real_out == src or real_out.startswith(src + os.sep):
                return _fail(host_out, "invalid-input",
                             f"outputs-inside-mount-source:{src}", "launch")
        container_req = _rewrite_roots(req, ctx["mounts"])
        # Staged through result.emit (round-7): a canonical path never holds
        # partial bytes — an interrupted staging leaves a temp fragment,
        # never a half-written request.
        result.emit(str(Path(host_out) / STAGED_REQUEST_NAME),
                    json.dumps(container_req, sort_keys=True).encode("utf-8"))
    except (profiles.ProfileRegistryError, launcher.LaunchError, OSError,
            ValueError, TypeError) as e:
        return _fail(host_out, "invalid-input", f"launch rejected: {e}",
                     "launch")

    # The digest-pinned ref is content-addressed: podman runs exactly these
    # bytes (coh-rt-01), so the ref digest is the executed evaluator identity.
    eval_digest = ctx["image"].rsplit("@", 1)[1]
    ids = {"evaluator_image_digest": eval_digest}
    try:
        rr = launcher.run(ctx, output_dir=Path(host_out),
                          container_args=["--request", REQUEST_TARGET],
                          env={"HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST": eval_digest})
    except OSError as e:
        return _fail(host_out, "execution", f"launcher failed: {e}",
                     "evaluation", ids)

    # coh-rt-05: a killed run is an ERROR, never a truncated pass.
    if rr.status == "timeout":
        return _fail(host_out, "execution",
                     "launch-timeout: container exceeded the time limit "
                     "and was killed", "evaluation", ids)
    if rr.status == "output-overflow":
        return _fail(host_out, "execution",
                     "launch-output-overflow: container exceeded the output "
                     "cap and was killed", "evaluation", ids)

    # coh-dec-04: callers MUST use both the exit code and the parsed result;
    # coh-dec-01: disagreement is never resolved in favor of the permissive
    # signal, so the relay fails ERROR instead of passing a bare code on.
    try:
        parsed = json.loads(
            (Path(host_out) / "result.json").read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        parsed = None
    decision = parsed.get("decision") if isinstance(parsed, dict) else None
    expected = _DECISION_FOR_CODE.get(rr.returncode)
    if expected is None or decision != expected:
        return _fail(host_out, "execution",
                     f"container exited {rr.returncode} without a result "
                     f"bundle agreeing with the exit-code contract "
                     f"(decision: {decision!r})", "launch", ids)
    # coh-dec-01 (round-7 finding 3): a success-family exit whose bundle
    # still carries an error field is an exit/result disagreement — never
    # resolved in favor of the permissive signal.
    if rr.returncode in (0, 10, 20) and parsed.get("error") is not None:
        return _fail(host_out, "execution",
                     f"container exited {rr.returncode} with decision "
                     f"{decision!r} but a non-null error field in the result "
                     f"bundle", "launch", ids)
    return rr.returncode
