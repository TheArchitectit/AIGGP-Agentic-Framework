#!/usr/bin/env python3
"""Opt-in real-OS protected-store smoke, isolated in a rootless disposable container.

Run from the repository root with:
    python3 tests/protected_store_smoke.py --run

The outer mode builds a short-lived image from a digest-pinned Python base and
runs it with no host bind mounts, no network, and tmpfs overlays at the two
production policy directories. The inner mode refuses to write unless those
exact paths are tmpfs mounts in a root container namespace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

BASE_IMAGE = (
    "docker.io/library/python:3.12-slim@"
    "sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"
)
POLICY_DIRS = ("/etc/aiggp", "/run/aiggp")


def run(argv: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, check=False, text=True, capture_output=True, timeout=timeout
    )


def host_smoke() -> int:
    podman = shutil.which("podman")
    if podman is None:
        print("protected-store smoke: FAIL - rootless podman is required", file=sys.stderr)
        return 2
    info = run([podman, "info", "--format", "{{.Host.Security.Rootless}}"], timeout=30)
    if info.returncode or info.stdout.strip().lower() != "true":
        print("protected-store smoke: FAIL - podman must be rootless", file=sys.stderr)
        return 2

    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="aiggp-protected-store-smoke-") as temp:
        context = Path(temp)
        for source, target in (
            ("scripts/check_corruption.py", "scripts/check_corruption.py"),
            ("scripts/corruption_diff.py", "scripts/corruption_diff.py"),
            ("scripts/corruption_reviews.py", "scripts/corruption_reviews.py"),
            ("scripts/gate_common.py", "scripts/gate_common.py"),
            ("scripts/lib/project_root.py", "scripts/lib/project_root.py"),
            (".guardrails/scope.json", ".guardrails/scope.json"),
            ("tests/test_corruption_reviews.py", "tests/test_corruption_reviews.py"),
            ("tests/protected_store_smoke.py", "tests/protected_store_smoke.py"),
        ):
            destination = context / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / source, destination)

        (context / "Containerfile").write_text(
            f"""FROM {BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends git \\
    && rm -rf /var/lib/apt/lists/*
COPY scripts/ /opt/aiggp/scripts/
COPY .guardrails/ /opt/aiggp/.guardrails/
COPY tests/ /opt/aiggp/tests/
WORKDIR /
ENTRYPOINT ["python3", "-I", "/opt/aiggp/tests/protected_store_smoke.py", "--inside-container"]
""",
            encoding="utf-8",
        )
        image = "localhost/aiggp-protected-store-smoke:" + uuid.uuid4().hex
        build = run([podman, "build", "--pull=missing", "-f", str(context / "Containerfile"),
                     "-t", image, str(context)])
        if build.returncode:
            print("protected-store smoke: FAIL - isolated image build failed", file=sys.stderr)
            if build.stderr:
                print(build.stderr[-4000:], file=sys.stderr)
            return build.returncode or 1

        command = [
            podman, "run", "--rm",
            "--network=none",
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
            "--tmpfs", "/etc/aiggp:rw,nosuid,nodev,noexec,size=1m,mode=0755",
            "--tmpfs", "/run/aiggp:rw,nosuid,nodev,noexec,size=1m,mode=0755",
            image,
        ]
        try:
            result = run(command, timeout=300)
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            return result.returncode
        finally:
            removed = run([podman, "image", "rm", "--force", image], timeout=30)
            if removed.returncode:
                print("protected-store smoke: WARNING - ephemeral image cleanup failed",
                      file=sys.stderr)


def inside_smoke() -> int:
    if os.geteuid() != 0:
        print("protected-store smoke: FAIL - isolated setup must run as container root",
              file=sys.stderr)
        return 2
    mounts = {}
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        before, separator, after = line.partition(" - ")
        fields = before.split()
        tail = after.split()
        if separator and len(fields) > 4 and len(tail) > 1:
            mountpoint = fields[4].replace("\\040", " ")
            mounts[mountpoint] = tail[0]
    if any(mounts.get(path) != "tmpfs" for path in POLICY_DIRS):
        print("protected-store smoke: FAIL - required policy tmpfs mounts absent",
              file=sys.stderr)
        return 2
    uid_map = Path("/proc/self/uid_map").read_text(encoding="ascii").splitlines()
    mapping = uid_map[0].split() if uid_map else []
    if len(mapping) != 3 or mapping[0] != "0" or mapping[1] == "0":
        print("protected-store smoke: FAIL - container root must map to a non-root host UID",
              file=sys.stderr)
        return 2
    if any(any(Path(path).iterdir()) for path in POLICY_DIRS):
        print("protected-store smoke: FAIL - policy tmpfs mounts must start empty",
              file=sys.stderr)
        return 2

    try:
        return real_store_checks()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"protected-store smoke: FAIL - {type(error).__name__}: {error}",
              file=sys.stderr)
        return 1


def real_store_checks() -> int:
    sys.path.insert(0, "/opt/aiggp/tests")
    from test_corruption_reviews import CommitReviews
    import corruption_reviews as cr

    marker_paths = [Path(path) / ".aiggp-protected-store-smoke" for path in POLICY_DIRS]
    for marker in marker_paths:
        marker.write_text("disposable tmpfs only\n", encoding="ascii")
        marker.chmod(0o400)

    case = CommitReviews()
    try:
        case.setUp()

        cr.CATALOG.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        cr.RUN_BINDINGS.mkdir(parents=True, mode=0o755, exist_ok=True)
        private = [cr.CATALOG, case.binding_path]

        def install() -> None:
            # Guard every write: accidental direct execution outside our two
            # verified tmpfs mounts must stop before touching protected paths.
            for path in POLICY_DIRS:
                if not (Path(path) / ".aiggp-protected-store-smoke").is_file():
                    raise AssertionError("isolated mount marker missing")
            for item in private:
                item.write_bytes(case.documents[item])
                item.chmod(0o644)
                info = item.stat()
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise AssertionError("fixture trust file is not protected")

        def verify(label: str, expected: int, *flags: str,
                   contains: str | None = None) -> None:
            proc = subprocess.run(
                [sys.executable, "-I", "/opt/aiggp/scripts/check_corruption.py",
                 "--repo", str(case.root), "--range", case.oid_range, *flags],
                text=True, capture_output=True, user=65534, group=65534, extra_groups=[],
            )
            output = proc.stdout + proc.stderr
            if proc.returncode != expected or (contains and contains not in output):
                probe = subprocess.run(
                    [sys.executable, "-I", "-c",
                     "import pathlib,sys; p=pathlib.Path(sys.argv[1]); "
                     "print('\\n'.join(f'{x}:{x.stat().st_uid}:{oct(x.stat().st_mode & 0o777)}' "
                     "for x in reversed((p, *p.parents))) )",
                     str(case.root / ".guardrails" / "corruption-allowlist.json")],
                    text=True, capture_output=True, user=65534, group=65534, extra_groups=[],
                )
                raise AssertionError(
                    f"{label} status={proc.returncode} expected={expected} "
                    f"uid-probe={(probe.stdout + probe.stderr)[:700]!r} gate-output={output[:2000]!r}"
                )
            print(f"{label}: exit={proc.returncode} expected={expected}", flush=True)

        install()
        reviewed = "--reviewed-transitions"

        # Exercise the production re-read against atomic replacement using the
        # real fixture owner before dropping the checkout to the unprivileged UID.
        with cr.open_reviews(case.root, case.base, case.head) as current:
            assert current.match(case.path, 1) == case.grant["exception_id"]
            replacement = cr.CATALOG.with_name("catalog.next")
            replacement.write_bytes(json.dumps(
                {"api_version": cr.CATALOG_TYPE, "exceptions": []}
            ).encode())
            replacement.chmod(0o644)
            os.replace(replacement, cr.CATALOG)
            try:
                current.check_current()
            except cr.ReviewError:
                print("atomic catalog revocation: detected before disposition", flush=True)
            else:
                raise AssertionError("atomic catalog replacement was not detected")

        case.provision([case.grant])
        install()
        guardrails = case.root / ".guardrails"
        guardrails.mkdir(mode=0o755)
        guardrails.chmod(0o755)
        case.root.parent.chmod(0o711)
        for path in [case.root, *case.root.rglob("*")]:
            os.chown(path, 65534, 65534, follow_symlinks=False)
        os.chown(guardrails, 65534, 65534, follow_symlinks=False)
        verify("ordinary strict finding", 1, contains="substitution flip")
        verify("exact advisory through protected OS reads", 0, reviewed,
               contains="VIOLATED EXCEPTION-ADVISORY")
        cr.CATALOG.chmod(0o666)
        verify("writable catalog rejected", 2, reviewed)
        install()
        sibling = cr.CATALOG.with_suffix(".fixture")
        cr.CATALOG.rename(sibling)
        cr.CATALOG.symlink_to(sibling)
        verify("symlink catalog rejected", 2, reviewed)
        cr.CATALOG.unlink()
        case.provision([])
        install()
        verify("revoked synthetic finding remains blocking", 1, reviewed,
               contains="substitution flip")
        case.binding_path.unlink()
        verify("missing binding fails closed", 2, reviewed)

        for marker in marker_paths:
            marker.unlink()
        print("protected-store smoke: PASS (rootless, no host mounts, network disabled)",
              flush=True)
        return 0
    finally:
        case.doCleanups()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true",
                       help="build and run the disposable rootless Podman smoke")
    group.add_argument("--inside-container", action="store_true",
                       help=argparse.SUPPRESS)
    args = parser.parse_args()
    return inside_smoke() if args.inside_container else host_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
