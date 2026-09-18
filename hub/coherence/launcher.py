# // spec: coh-rt-01, coh-rt-02, coh-rt-05, coh-rt-07, coh-id-04
"""Reference launcher: validates a launch configuration against the
isolation profile OUTSIDE the container, derives the enforced Podman
security context from the validated fields only, and executes the derived
invocation under the configured time and output limits.

The container never self-certifies (coh-rt-02): every isolation property
is either declared in the launch config and re-derived here, or rejected.
A launch configuration claiming isolation it does not receive is a launch
failure for the reconciliation fields (user, rootfs, network, capability
drop, profile); declared mounts/scratch/limits are out of the
reconciliation contract — they are enforced regardless of what is
declared. The executed platform image manifest digest is required
(coh-id-04 MUST-distinguish); the index digest is optional ("if any").

Writable space: every ephemeral tmpfs target the launcher creates
(/scratch, /tmp, /run) is size-bounded by the launch config's scratch
bound, and /dev/shm is pinned via --shm-size. Output goes to the single
designated bound mount. Time and output limits are enforced by this
process in run(): timeout and overflow both kill the container and are
reported as non-completed statuses, never as a truncated pass.
"""
import os
import re
import select
import subprocess
import time
from collections import namedtuple
from pathlib import Path

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
_USER_RE = re.compile(r"(\d{1,10})(?::(\d{1,10}))?")
_LIMIT_KEYS = ("memory", "cpus", "time_s", "pids", "nofile", "output_bytes")
_SIZE_SUFFIX = {"k": 10**3, "m": 10**6, "g": 10**9}
_TMPFS_TARGETS = ("/scratch", "/tmp", "/run")

LaunchRun = namedtuple("LaunchRun", "returncode output status")
# status: "completed" | "timeout" | "output-overflow"


class LaunchError(ValueError):
    """Launch configuration rejected (exit-30 class, before assertions)."""


def _parse_size(v) -> int:
    """Bytes from an int or a "<n><k|m|g>" decimal-suffix string."""
    if isinstance(v, bool) or not isinstance(v, (int, str)):
        raise ValueError("size must be int or str")
    if isinstance(v, int):
        if v <= 0:
            raise ValueError("size must be positive")
        return v
    s = v.strip().lower()
    if s.isdigit():
        n = int(s)
        if n <= 0:
            raise ValueError("size must be positive")
        return n
    m = re.fullmatch(r"(\d+)([kmg])", s)
    if not m:
        raise ValueError(f"unparseable size: {v!r}")
    return int(m.group(1)) * _SIZE_SUFFIX[m.group(2)]


def _validate_image(ref) -> str:
    if not isinstance(ref, str) or "@" not in ref:
        raise LaunchError("tag-only-image")
    name, dig = ref.rsplit("@", 1)
    if not name:
        raise LaunchError("tag-only-image")
    if not _DIGEST_RE.fullmatch(dig):
        raise LaunchError("bad-image-digest")
    return ref


def _validate_user(u) -> str:
    if not isinstance(u, str):
        raise LaunchError("missing-field:user")
    s = u.strip()
    if s.lower() == "root":
        raise LaunchError("root-user")
    m = _USER_RE.fullmatch(s)
    if not m:
        raise LaunchError("bad-user")
    uid, gid = int(m.group(1)), int(m.group(2) or m.group(1))
    if uid == 0 or gid == 0:
        raise LaunchError("root-user")
    return s


def _validate_mounts(mounts) -> list:
    if not isinstance(mounts, list):
        raise LaunchError("missing-field:mounts")
    out = []
    for mt in mounts:
        if not isinstance(mt, dict):
            raise LaunchError("bad-mount")
        src, tgt = mt.get("source"), mt.get("target")
        if not isinstance(src, str) or not isinstance(tgt, str) or not src or not tgt:
            raise LaunchError("bad-mount")
        if src.split("/")[-1].endswith(".sock"):
            raise LaunchError(f"host-socket-bind:{src}")
        if mt.get("readonly") is not True:
            raise LaunchError(f"writable-mount:{tgt}")
        out.append({"source": src, "target": tgt, "readonly": True})
    out.sort(key=lambda m: (m["target"], m["source"]))
    return out


def _validate_limits(limits) -> dict:
    if not isinstance(limits, dict):
        raise LaunchError("missing-field:limits")
    out = {}
    for k in _LIMIT_KEYS:
        if k not in limits:
            raise LaunchError(f"missing-limit:{k}")
        v = limits[k]
        try:
            n = _parse_size(v) if k == "memory" else float(v) if k == "cpus" else int(v)
        except (ValueError, TypeError):
            raise LaunchError(f"bad-limit:{k}") from None
        if n <= 0:
            raise LaunchError(f"bad-limit:{k}")
        out[k] = n if k != "cpus" else float(v)
    return out


def _check_declared(cfg: dict, ctx: dict) -> None:
    """Reconcile a container-declared isolation block (self-report) against
    the launcher-derived context for the reconciliation fields only
    (user, read_only_rootfs, network, cap_drop, profile — coh-rt-02). The
    launcher's derivation wins; any disagreement is a launch failure, not
    a warning."""
    declared = cfg.get("declared")
    if declared is None:
        return
    if not isinstance(declared, dict):
        raise LaunchError("bad-declared")
    for field, derived in (("user", ctx["user"]),
                           ("read_only_rootfs", ctx["read_only_rootfs"]),
                           ("network", ctx["network"]),
                           ("profile", ctx["profile"])):
        if field in declared and declared[field] != derived:
            raise LaunchError(f"self-report-mismatch:{field}")
    if "cap_drop" in declared and "ALL" not in declared["cap_drop"]:
        raise LaunchError("self-report-mismatch:cap_drop")


def validate_launch(cfg: dict, supported_profiles) -> dict:
    """Validate a launch configuration and return the effective isolation
    context the launcher will enforce. Raises LaunchError on any violation.

    `supported_profiles` is the declared execution-profile registry (labels
    the launch acceptance promises byte-equivalence within, and declared
    semantic equivalence across — coh-id-04).
    """
    if not isinstance(cfg, dict):
        raise LaunchError("bad-config")
    if not isinstance(supported_profiles, (list, tuple, set)):
        raise LaunchError("bad-profile-registry")
    ctx = {}
    ctx["image"] = _validate_image(cfg.get("image"))
    if "user" not in cfg:
        raise LaunchError("missing-field:user")
    ctx["user"] = _validate_user(cfg["user"])
    if cfg.get("read_only_rootfs") is not True:
        raise LaunchError("writable-rootfs")
    ctx["read_only_rootfs"] = True
    if cfg.get("cap_drop") != ["ALL"]:
        raise LaunchError("cap-drop-missing")
    if cfg.get("cap_add"):
        raise LaunchError("cap-add-forbidden")
    ctx["cap_drop"] = ["ALL"]
    if cfg.get("network") != "none":
        net = cfg.get("network")
        raise LaunchError("host-network" if net == "host" else "network-not-none")
    ctx["network"] = "none"
    ctx["mounts"] = _validate_mounts(cfg.get("mounts", []))
    if "scratch" not in cfg or not isinstance(cfg["scratch"], dict) \
            or "size" not in cfg["scratch"]:
        raise LaunchError("unbounded-scratch")
    try:
        ctx["scratch_bytes"] = _parse_size(cfg["scratch"]["size"])
    except ValueError:
        raise LaunchError("unbounded-scratch") from None
    ctx["limits"] = _validate_limits(cfg.get("limits"))
    profile = cfg.get("profile")
    if not isinstance(profile, str) or not profile:
        raise LaunchError("missing-field:profile")
    if profile not in supported_profiles:
        raise LaunchError(f"undeclared-profile:{profile}")
    ctx["profile"] = profile
    manifest = cfg.get("image_manifest_digest")
    if manifest is None:
        raise LaunchError("missing-field:image_manifest_digest")
    if not isinstance(manifest, str) or not _DIGEST_RE.fullmatch(manifest):
        raise LaunchError("bad-image_manifest_digest")
    ctx["image_manifest_digest"] = manifest
    idx = cfg.get("image_index_digest")
    if idx is not None:
        if not isinstance(idx, str) or not _DIGEST_RE.fullmatch(idx):
            raise LaunchError("bad-image_index_digest")
    ctx["image_index_digest"] = idx
    _check_declared(cfg, ctx)
    return ctx


def podman_args(ctx: dict, *, output_dir: Path) -> list:
    """Derive the enforced `podman run` argument list from a validated
    context. Every isolation property is expressed as a launcher-side
    flag; nothing is delegated to the image's own configuration. Each
    writable tmpfs target gets the launch config's scratch bound as its
    per-mount size; /dev/shm is pinned explicitly.
    """
    lim = ctx["limits"]
    args = [
        "podman", "run", "--rm",
        "--read-only", "--read-only-tmpfs",
        f"--user={ctx['user']}",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--network=none",
        f"--memory={lim['memory']}",
        f"--cpus={lim['cpus']}",
        f"--pids-limit={lim['pids']}",
        "--ulimit", f"nofile={lim['nofile']}:{lim['nofile']}",
        "--shm-size=64m",
    ]
    for target in _TMPFS_TARGETS:
        args += ["--tmpfs", f"{target}:size={ctx['scratch_bytes']},noexec,nodev"]
    args += ["-v", f"{output_dir}:/output"]
    for mt in ctx["mounts"]:
        args += ["-v", f"{mt['source']}:{mt['target']}:ro"]
    args.append(ctx["image"])
    return args


def run(ctx: dict, *, output_dir: Path, container_args=None) -> LaunchRun:
    """Execute the derived invocation under the configured limits (coh-rt-05):
    the container is killed when the time limit or the output cap is
    exhausted, and the LaunchRun status says so — a killed run is never
    reported as completed. Output limits apply to the merged stdout+stderr
    stream; the decision contract (result bundle in /output) is unaffected.
    """
    args = podman_args(ctx, output_dir=output_dir) + list(container_args or [])
    cap = ctx["limits"]["output_bytes"]
    deadline = time.monotonic() + ctx["limits"]["time_s"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    buf = bytearray()
    status = "completed"
    fd = proc.stdout.fileno()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            status = "timeout"
            break
        ready, _, _ = select.select([fd], [], [], min(remaining, 0.5))
        if not ready:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        buf += chunk
        if len(buf) > cap:
            status = "output-overflow"
            break
    if status != "completed":
        proc.kill()
    proc.wait()
    return LaunchRun(proc.returncode, bytes(buf), status)
