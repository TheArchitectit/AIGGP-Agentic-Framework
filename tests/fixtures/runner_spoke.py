# // spec: mon-online-01
"""The fake runner host this suite enrolls against.

`scripts/runner-enroll.sh` generates systemd units, an EnvironmentFile and a
heartbeat helper, then starts them with systemctl. Testing that means giving it
a host to do it on. This is that host: HOME inside a tmp directory, `curl` and
`systemctl` stubbed at the front of PATH, and no network, no real systemd and
no real hub anywhere in it.

The curl stub is a router, not a recorder: it answers /enroll, /heartbeat and
/revoke the way the hub does, deriving the issued token from the runner name so
that two enrollments provably differ, and appending every request to a log the
tests assert against.

It lives here rather than in the suite because it is a fixture and this is
where the repository keeps them (`tests/fixtures/repin.py` is the sibling), and
because the suite that used to hold it inline crossed the 600-line hard limit
for test files — the honest response to that gate being to stop growing the
file rather than to move the limit.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# The DevGate checkout this harness ships in. Named by parent-count, which is a
# stable anchor only while this file stays where it is — so it is checked
# rather than trusted. The same move broke the re-pin harness one directory
# up (its REPO silently became tests/), and the contract is the repository's
# own: a root that resolves somewhere else must refuse, not fail far away
# (scripts/lib/project_root.py, root-anchor-01).
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "runner-enroll.sh"
HEARTBEAT = REPO_ROOT / "scripts" / "runner-heartbeat.sh"
# The unit-installer library SCRIPT sources. Checked here too, because it is a
# file the script cannot run without: `source` on a missing path is an error
# runner-enroll.sh dies on, and a checkout that lost it should fail at import
# with the file named, not at enroll time on a host.
UNIT_LIB = REPO_ROOT / "scripts" / "lib" / "runner-units.sh"
for _required in (SCRIPT, HEARTBEAT, UNIT_LIB):
    if not _required.is_file():
        raise RuntimeError(
            f"the runner harness resolved the DevGate checkout as {REPO_ROOT}, "
            f"where {_required.relative_to(REPO_ROOT)} does not exist — this "
            "file has moved, and the parent-count above needs adjusting")

HUB = "http://hub.test:8443"

# Serves /enroll (issuing a token derived from the runner name, so two enrolls
# provably get different tokens), /heartbeat, and /revoke. Logs every request so
# tests can assert on what was actually POSTed.
CURL_STUB = r'''#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
data = outfile = write_fmt = url = None
fail_on_error = False
i = 0
while i < len(args):
    a = args[i]
    if a in ("-d", "--data"):
        data = args[i + 1]; i += 2
    elif a in ("-o", "--output"):
        outfile = args[i + 1]; i += 2
    elif a in ("-w", "--write-out"):
        write_fmt = args[i + 1]; i += 2
    elif a in ("-X", "--request", "-H", "--header", "--connect-timeout"):
        i += 2
    elif a == "-f" or a == "-sf" or (a.startswith("-") and len(a) <= 3 and "f" in a):
        if "f" in a and not a.startswith("--"):
            fail_on_error = True
        i += 1
    elif a.startswith("-"):
        i += 1
    else:
        url = a; i += 1

path = "/"
if url and "://" in url:
    tail = url.split("://", 1)[1]
    if "/" in tail:
        path = "/" + tail.split("/", 1)[1]

if path == "/enroll":
    payload = json.loads(data or "{}")
    runner = payload.get("runner_name", "unknown")
    status = int(os.environ.get("STUB_ENROLL_STATUS", "200"))
    body = json.dumps({"ok": True, "runner_name": runner,
                       "heartbeat_token": "tok-" + runner})
elif path == "/heartbeat":
    status = int(os.environ.get("STUB_HEARTBEAT_STATUS", "200"))
    body = json.dumps({"ok": status == 200})
else:
    status = int(os.environ.get("STUB_REVOKE_STATUS", "200"))
    body = json.dumps({"ok": True})

with open(os.environ["STUB_CURL_LOG"], "a") as fh:
    fh.write(json.dumps({"url": url, "path": path, "data": data,
                         "status": status}) + "\n")

if outfile:
    with open(outfile, "w") as fh:
        fh.write(body)

if write_fmt:
    sys.stdout.write(write_fmt.replace("%{http_code}", str(status)))
else:
    sys.stdout.write(body)

sys.exit(22 if (fail_on_error and status >= 400) else 0)
'''

SYSTEMCTL_STUB = '''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_SYSTEMCTL_LOG"
exit 0
'''


def slug(name):
    """Mirror of runner-enroll.sh set_unit_paths() — tests must use the same
    transformation the script does, or awkward names assert against nothing."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", name)


class Spoke:
    """A fake runner host: HOME in tmp_path, curl+systemctl stubbed on PATH."""

    def __init__(self, tmp_path):
        self.home = tmp_path / "home"
        self.home.mkdir(exist_ok=True)
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        self.curl_log = tmp_path / "curl.jsonl"
        self.systemctl_log = tmp_path / "systemctl.log"
        self.tools_dir = tmp_path / "tools"
        self.curl_log.write_text("")
        self.systemctl_log.write_text("")
        for name, body in (("curl", CURL_STUB), ("systemctl", SYSTEMCTL_STUB)):
            p = bindir / name
            p.write_text(body)
            p.chmod(0o755)
        # Ambient COHERENCE_* is scrubbed, not inherited. These are the very
        # variables the image probe branches on, so a host that HAS been
        # provisioned decides which branch the unprovisioned test exercises —
        # and on such a host the suite goes red with nothing wrong in the code
        # (measured: with COHERENCE_IMAGE/_MANIFEST_DIGEST/_PODMAN_STORE
        # exported, the not-provisioned test failed). CI is the same hazard
        # from the other side: the environment would silently choose the
        # branch under test. Scrubbed here rather than per test so no later
        # test can reintroduce the coupling by forgetting to unset them.
        self.env = {
            **{k: v for k, v in os.environ.items()
               if not k.startswith("COHERENCE_")},
            "HOME": str(self.home),
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "STUB_CURL_LOG": str(self.curl_log),
            "STUB_SYSTEMCTL_LOG": str(self.systemctl_log),
            "TMPDIR": str(self.home),
        }

    # --- paths the script generates ------------------------------------------
    @property
    def units(self):
        return self.home / ".config" / "systemd" / "user"

    def env_file(self, runner):
        return self.home / ".config" / "containers" / f"devgate-heartbeat-{slug(runner)}.env"

    def helper(self):
        return self.home / ".config" / "containers" / "devgate-heartbeat.sh"

    def cycle_helper(self):
        return self.home / ".config" / "containers" / "devgate-image-cycle.sh"

    def cycle_units(self, runner):
        """(service, timer) for the image cycle, named per runner like the rest."""
        s = slug(runner)
        return (self.units / f"devgate-imgcycle-{s}.service",
                self.units / f"devgate-imgcycle-{s}.timer")

    def token_of(self, runner):
        env = self.env_file(runner)
        assert env.exists(), f"per-runner env file was never written: {env}"
        for line in env.read_text().splitlines():
            if line.startswith("HEARTBEAT_TOKEN="):
                return line.split("=", 1)[1]
        return None

    # --- actions --------------------------------------------------------------
    def enroll(self, runner):
        return subprocess.run(
            ["bash", str(SCRIPT), HUB, "enroll-secret",
             "--repo", "owner/repo", "--runner-name", runner],
            env=self.env, capture_output=True, text=True, timeout=60)

    def requests(self, path=None):
        rows = [json.loads(l) for l in self.curl_log.read_text().splitlines() if l]
        return [r for r in rows if path is None or r["path"] == path]

    def systemctl_calls(self):
        return [l for l in self.systemctl_log.read_text().splitlines() if l]

    def run_helper(self, runner, **extra_env):
        """Run the installed helper the way systemd would: env from the file."""
        envf = self.env_file(runner)
        assert envf.exists(), f"per-runner env file was never written: {envf}"
        helper = self.helper()
        assert helper.exists(), f"heartbeat helper was never installed: {helper}"
        env = dict(self.env)
        for line in envf.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
        env.update(extra_env)
        return subprocess.run(["bash", str(self.helper())], env=env,
                              capture_output=True, text=True, timeout=60)

    # --- the image probe's collaborator ---------------------------------------
    def stub_podman(self):
        """Put a podman stub on this Spoke's PATH; returns the stub's path.

        Opt-in rather than always present, deliberately: the heartbeat reports
        `podman_ok` from `podman info`, so a stub that appeared unconditionally
        would change what every other test in this file observes about a host
        with no podman at all.

        It answers the way real podman was MEASURED to (2026-09-24, podman
        6.1.1 on this host), including the two behaviours that are easy to get
        wrong by writing the obvious stub:

        - The graph root it reports is NORMALISED, not echoed: `--root
          /tmp/ps1/` answers `/tmp/ps1`, and `--root /tmp//ps1` answers
          `/tmp/ps1` too. A stub echoing its argument verbatim would encode
          the false premise that a byte comparison of the two strings is a
          comparison of the two stores — the defect this fixture exists to
          catch, introduced by the fixture.
        - It MATERIALISES the store it is pointed at (one run left
          `<root>/{db.sql,libpod}` behind). That is what makes "the tick must
          not create the store" a real test: with a stub that created nothing,
          the assertion would hold whatever the tick did.

        Knobs: STUB_IMAGE_EXISTS_RC (the presence answer), STUB_GRAPH_ROOT (a
        different root, to reach the mismatch branch), STUB_INFO_RC (a podman
        that fails, which is not the same fault as a mismatch).
        """
        p = Path(self.env["PATH"].split(":")[0]) / "podman"
        p.write_text(
            "#!/usr/bin/env bash\n"
            'if [ "${1:-}" = "--root" ]; then store="${2:-}"; shift 2; fi\n'
            'case "${1:-}" in\n'
            '  info)\n'
            '    [ -z "${store:-}" ] || mkdir -p "$store"\n'
            '    rc="${STUB_INFO_RC:-0}"\n'
            '    [ "$rc" = "0" ] || exit "$rc"\n'
            '    realpath -m -- "${STUB_GRAPH_ROOT:-${store:-}}"\n'
            "    exit 0 ;;\n"
            '  image) exit "${STUB_IMAGE_EXISTS_RC:-0}" ;;\n'
            "esac\n"
            "exit 0\n")
        p.chmod(0o755)
        return p

    def path_without_podman(self):
        """A PATH carrying only the tools the heartbeat needs — and no podman.

        `stub_podman` makes podman PRESENT; absence cannot be produced the
        same way, because the machine running this suite very likely has a
        real podman (which is why the branch needs covering: a fleet's hosts
        vary). Prepending a stub cannot hide a later PATH entry, so the whole
        PATH is rebuilt from symlinks to the tools the tick actually invokes.

        It doubles as a pin on that tool set: if the heartbeat grows an
        external dependency, or reaches for podman before this probe, the
        branch stops being exercised and this test fails rather than passing
        for a different reason.
        """
        self.tools_dir.mkdir(exist_ok=True)
        for name in ("bash", "cat", "df", "python3", "sed", "tail", "tr"):
            link = self.tools_dir / name
            if not link.exists():
                real = shutil.which(name)
                assert real, f"no {name} on the host PATH to link into the sandbox"
                link.symlink_to(real)
        stubs = self.env["PATH"].split(":")[0]
        return f"{stubs}:{self.tools_dir}"

