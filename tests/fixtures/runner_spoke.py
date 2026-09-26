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
    """Mirror of the lib's set_unit_paths() — tests must use the same
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
        self.curl_log.write_text("", encoding="utf-8")
        self.systemctl_log.write_text("", encoding="utf-8")
        for name, body in (("curl", CURL_STUB), ("systemctl", SYSTEMCTL_STUB)):
            p = bindir / name
            p.write_text(body, encoding="utf-8")
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
        #
        # SECRET_SCAN_* is deliberately NOT scrubbed, and an earlier revision
        # scrubbed it on a justification that does not hold: it claimed an
        # ambient SECRET_SCAN_DECLARED "decides which branch the not-provisioned
        # tests exercise". Nothing on the enroll path reads the ambient
        # variable — the provisioning key is read from the runner's own env file
        # (measured: with an ambient value set, the generated unit still carries
        # the systemd token and the timer is still not enabled). That made the
        # scrub a guard no test could distinguish, which is the same inert-guard
        # shape the sweep's own `-z` branch was deleted for. It also removed the
        # only way to exercise the hazard the escaping actually prevents, which
        # is a value from enroll's environment being frozen into the unit: see
        # test_an_ambient_declaration_is_not_baked_into_the_unit.
        #
        # XDG_RUNTIME_DIR is pinned into the sandbox for the same reason, one
        # step further out: enrollment resolves the fleet sweep's report path
        # from it (systemd's %t for a user unit IS this variable), so
        # inheriting the host's would bake THIS machine's /run/user/1000 into
        # the generated env file and write a test's report into the real
        # runtime directory — a test that passes because of where it ran.
        self.env = {
            **{k: v for k, v in os.environ.items()
               if not k.startswith("COHERENCE_")},
            "HOME": str(self.home),
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "STUB_CURL_LOG": str(self.curl_log),
            "STUB_SYSTEMCTL_LOG": str(self.systemctl_log),
            "TMPDIR": str(self.home),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"),
        }
        (tmp_path / "run").mkdir(exist_ok=True)

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

    def fleet_helper(self):
        """The fleet secret sweep's installed copy."""
        return self.home / ".config" / "containers" / "devgate-secret-scan-fleet.sh"

    def gate_helper(self):
        """The gate's installed copy — the sweep resolves it as a sibling of
        itself ($(dirname $0)/secret-scan.sh), so the two must land together,
        AND under that literal name."""
        return self.home / ".config" / "containers" / "secret-scan.sh"

    def fleet_units(self, runner):
        """(service, timer) for the fleet sweep, named per runner."""
        s = slug(runner)
        return (self.units / f"devgate-secretscan-{s}.service",
                self.units / f"devgate-secretscan-{s}.timer")

    def token_of(self, runner):
        env = self.env_file(runner)
        assert env.exists(), f"per-runner env file was never written: {env}"
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("HEARTBEAT_TOKEN="):
                return line.split("=", 1)[1]
        return None

    # --- actions --------------------------------------------------------------
    def enroll(self, runner):
        return subprocess.run(
            ["bash", str(SCRIPT), HUB, "enroll-secret",
             "--repo", "owner/repo", "--runner-name", runner],
            env=self.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def revoke(self, runner):
        """Revoke the way the CLI spells it: the token and the runner name are
        POSITIONAL after --revoke — `--runner-name` is the enroll-mode flag and
        sets a different variable, so a revoke test written with it would silently
        revoke the hostname-derived default."""
        return subprocess.run(
            ["bash", str(SCRIPT), "--revoke", HUB, f"tok-{runner}", runner],
            env=self.env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def requests(self, path=None):
        rows = [json.loads(l) for l in self.curl_log.read_text(encoding="utf-8").splitlines() if l]
        return [r for r in rows if path is None or r["path"] == path]

    def systemctl_calls(self):
        return [l for l in self.systemctl_log.read_text(encoding="utf-8").splitlines() if l]

    def _env_from_file(self, runner, extra=None):
        """The environment systemd would give a unit: the runner's own env file
        layered over the host's, with any test-supplied knobs on top."""
        envf = self.env_file(runner)
        assert envf.exists(), f"per-runner env file was never written: {envf}"
        env = dict(self.env)
        for line in envf.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
        env.update(extra or {})
        return env

    def run_helper(self, runner, **extra_env):
        """Run the installed helper the way systemd would: env from the file."""
        helper = self.helper()
        assert helper.exists(), f"heartbeat helper was never installed: {helper}"
        return subprocess.run(["bash", str(helper)],
                              env=self._env_from_file(runner, extra_env),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)

    def run_fleet_helper(self, runner, declared, *args):
        """Run the INSTALLED sweep the way its unit does — which is the only way
        to catch a helper that is present, executable and useless.

        The declaration path is normally expanded by systemd out of the env
        file; the tests pass it explicitly so they can vary it, then hand the
        rest of the environment over exactly as the unit would.
        """
        helper = self.fleet_helper()
        assert helper.exists(), f"the sweep helper was never installed: {helper}"
        return subprocess.run(
            ["bash", str(helper), "--declared", str(declared), *args],
            env=self._env_from_file(runner), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120)

    # --- the sweep's collaborator ---------------------------------------------
    def stub_gitleaks(self, findings=None, rc=None):
        """Put a gitleaks stub on this Spoke's PATH.

        Opt-in like stub_podman, and for the same reason: what the gate does
        with a FINDING is `tests/test_secret_scan.py`'s subject, and a stub that
        appeared unconditionally would change what every test here observes
        about a host with no scanner at all.

        This stub exists to let the installed chain run end to end — helper →
        the gate it resolves as its own sibling → scanner — because the failure
        this fixture was extended to catch was a helper that ran and then died
        looking for a gate under a name it does not have.
        """
        p = Path(self.env["PATH"].split(":")[0]) / "gitleaks"
        p.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "args = sys.argv[1:]\n"
            "if '--version' in args or args[:1] == ['version']:\n"
            "    print('8.30.1'); sys.exit(0)\n"
            "def opt(n):\n"
            "    for i, a in enumerate(args):\n"
            "        if a == n and i + 1 < len(args): return args[i + 1]\n"
            "    return None\n"
            "if opt('--report-format') == 'json' and opt('--report-path'):\n"
            "    with open(opt('--report-path'), 'w') as fh:\n"
            f"        json.dump({findings or []!r}, fh)\n"
            f"sys.exit({rc if rc is not None else (1 if findings else 0)})\n", encoding="utf-8")
        p.chmod(0o755)
        return p

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
            '  info, encoding="utf-8")\n'
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

