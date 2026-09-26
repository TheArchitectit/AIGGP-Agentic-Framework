"""Tests for scripts/secret-scan-fleet.sh — the periodic fleet sweep.

The push gate answers "did this push add a credential" for one repository, at
the moment of the push. Nothing answers the other question: is there a
credential sitting in a repository we own that nobody has pushed to in months.
That is a different scope with a different owner, and `secret-scan-04` keeps
them apart — the sweep is asked for by name rather than being run inside the
per-push path.

What this suite is written against is `secret-scan-07`, whose whole subject is
the difference between "we scanned it and it was clean" and "we have no idea".
A sweep that silently drops a repository it could not fetch renders a fleet of
n failures as a shorter, greener list — and that is not a hypothetical shape
here, it is the shape of every scanner bug this repository has already met. So
each declared repository must appear in the report exactly once, with a state
and, when it could not be scanned, a reason.

The exit code is the summary an operator's cron job reads, so it distinguishes
the states rather than collapsing them to non-zero:

  0   every declared repository was scanned and none had an uncovered finding
  1   at least one uncovered finding
  2   the scanner is unusable — nothing about any repository can be claimed
  3   bad invocation (no declaration, an empty one, an unreadable file)
  4   at least one declared repository could not be scanned

3 outranks 2 outranks 1 outranks 4: a bad invocation means nothing ran, a
scanner fault means no verdict is trustworthy, and a real leak in one
repository outranks an unknown in another. Exit 4 is still non-zero, so an
unfetchable repository is never *reported* as healthy even when nothing found
anything — the report carries the reason.

Every assertion runs against a stubbed `gitleaks` on PATH and against real git
repositories reached over `file://` URLs, so the fetch path is exercised by
fetching rather than by a stub agreeing with the script about what fetching
means.

Dual-runnable: pytest collects test_*; `python3 tests/test_secret_scan_fleet.py`
runs them too.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests
# shell out to things that do not exist on Windows, so they cannot run there.
# A test that cannot run must SKIP, not fail -- failing here is indistinguishable
# from real breakage, and a Windows developer cannot tell which failures matter.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "secret-scan-fleet.sh"
BASH = shutil.which("bash") or "/bin/bash"
GIT = shutil.which("git")
# The value the stub always reports as the matched secret. If this string ever
# reaches the sweep's output or its report, the sweep republished it.
CANARY = "ghp_Zz9CanaryValueNeverPrinted0Qw7"
# A file whose presence in the fetched repository is what makes the stub report
# a finding. It travels through the clone because it is committed, so "this
# repository has a finding" is a property of the repository rather than of the
# order the sweep happened to run in.
LEAK_MARKER = ".stub-leak"

FINDING = {
    "RuleID": "github-pat",
    "File": "src/app.py",
    "StartLine": 42,
    "Commit": "abc123def456",
    "Secret": CANARY,
    "Match": f'token = "{CANARY}"',
    "Fingerprint": "abc123def456:src/app.py:github-pat:42",
}

# Answers the invocations the gate makes, from the fetched repository's own
# contents plus env knobs:
#   STUB_RC   forced exit code, to model a scanner that crashes
# The report file is written whenever --report-path is passed, and it always
# contains the unredacted Secret — a stub that pre-redacted would let the gate
# off the hook that matters. See test_secret_scan.py's docstring.
GITLEAKS_STUB = r'''#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\n")

def opt(name):
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
    return None

source = opt("--source") or ""
marker = os.environ["STUB_LEAK_MARKER"]
finding = json.loads(os.environ["STUB_FINDING"])
findings = [finding] if os.path.exists(os.path.join(source, marker)) else []

forced = os.environ.get("STUB_RC")
rc = int(forced) if forced is not None else (1 if findings else 0)

fmt, path = opt("--report-format"), opt("--report-path")
if path and fmt == "json":
    with open(path, "w") as fh:
        json.dump(findings, fh)

sys.stderr.write("WRN leaks found: %d\n" % len(findings) if findings
                 else "INF no leaks found\n")
sys.exit(rc)
'''


# --- the sweep's state vocabulary, shared by the tests and the battery -------

STATE_CLEAN = "clean"
STATE_FINDINGS = "findings"
STATE_UNFETCHABLE = "unfetchable"
STATE_UNSCANNABLE = "unscannable"
ALL_STATES = (STATE_CLEAN, STATE_FINDINGS, STATE_UNFETCHABLE, STATE_UNSCANNABLE)


class Fleet:
    """A scratch fleet: real origin repositories, a stubbed gitleaks on PATH."""

    def __init__(self, tmp_path, **knobs):
        self.root = tmp_path
        self.origins = tmp_path / "origins"
        self.origins.mkdir()
        bindir = tmp_path / "bin"
        bindir.mkdir()
        stub = bindir / "gitleaks"
        stub.write_text(GITLEAKS_STUB, encoding="utf-8")
        stub.chmod(0o755)
        self.log = tmp_path / "gitleaks.jsonl"
        self.log.write_text("", encoding="utf-8")
        self.work = tmp_path / "work"
        self.env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "STUB_LOG": str(self.log),
            "STUB_LEAK_MARKER": LEAK_MARKER,
            "STUB_FINDING": json.dumps(FINDING),
        }
        self.env.update({k: str(v) for k, v in knobs.items()})

    # --- origins ------------------------------------------------------------
    def _git(self, root, *args):
        return subprocess.run([GIT, "-C", str(root), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout

    def repo(self, name, leaky=False, allowlist=None):
        """A real origin repository, cloneable over file://."""
        d = self.origins / name
        (d / "src").mkdir(parents=True)
        (d / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        if leaky:
            (d / LEAK_MARKER).write_text("marker\n", encoding="utf-8")
        if allowlist is not None:
            (d / ".guardrails").mkdir(exist_ok=True)
            (d / ".guardrails" / "secret-allowlist.json").write_text(allowlist, encoding="utf-8")
        self._git(d, "init", "-q", "-b", "main")
        self._git(d, "config", "user.email", "t@example.com")
        self._git(d, "config", "user.name", "t")
        self._git(d, "add", "-A")
        self._git(d, "commit", "-q", "-m", "initial")
        return d

    def url(self, name):
        return (self.origins / name).as_uri()

    def declare(self, *urls, comment=True):
        """The declaration file. URLs, because that is what the hub holds and
        what makes the fetch path real."""
        f = self.root / "declared.txt"
        lines = ["# declared public repositories"] if comment else []
        lines += list(urls)
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return f

    # --- inspection ---------------------------------------------------------
    def calls(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l]

    def run(self, declared, *args):
        argv = [BASH, str(SCRIPT), "--declared", str(declared), *args]
        return subprocess.run(argv, env=self.env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)

    def run_report(self, declared, *args):
        report = self.root / "fleet-report.json"
        res = self.run(declared, "--report", str(report), *args)
        return res, (json.loads(report.read_text(encoding="utf-8")) if report.exists() else None)

    @staticmethod
    def by_name(report):
        return {r["name"]: r for r in report["repos"]}


# --- the report is its own contract, because a second reader now has it -----

def test_the_report_is_replaced_and_never_truncated_where_a_reader_will_find_it(tmp_path):
    """The heartbeat reads this file on its own timer, from another process, so
    the write has to be a replace rather than an in-place rewrite.

    Measured as an INODE CHANGE, which is exactly the difference between the
    two writes: `open(path, "w")` truncates the file it already has, so a reader
    arriving mid-write sees a zero-length or half-finished report under the same
    inode; writing a sibling and renaming keeps the old file whole until one
    atomic step puts the new one in its place, which necessarily yields a new
    inode. (The new file is created before the rename, while the old one is
    still on disk, so the allocator cannot hand back the same number.)

    Necessary for atomicity and not proof of it. The other half of the guarantee
    lives in the reader: the heartbeat renders a report it cannot parse as
    `unreadable`, never as an empty — and therefore clean — fleet.
    """
    f = Fleet(tmp_path)
    f.repo("alpha")
    declared = f.declare(f.url("alpha"))
    report = f.root / "fleet-report.json"

    first = f.run(declared, "--report", str(report))
    assert first.returncode == 0, first.stderr
    inode = report.stat().st_ino

    second = f.run(declared, "--report", str(report))
    assert second.returncode == 0, second.stderr
    assert report.stat().st_ino != inode, \
        "the report was rewritten in place; a concurrent reader can see it truncated"

    # And the temporary the write went through is gone: a leftover would be
    # picked up by anything globbing the directory for reports.
    leftovers = [p.name for p in f.root.glob(".*secretscan*")]
    assert leftovers == [], leftovers


def test_a_report_write_that_fails_leaves_no_temporary_and_no_half_report(tmp_path):
    """The other half of the atomic write, and the half nothing exercised: the
    cleanup on the failure path.

    Forced by aiming `--report` at a path that is already a DIRECTORY. Every
    earlier step succeeds — the scan runs, the records are written, mkstemp
    creates its sibling in the same directory — and `os.replace` then fails,
    which is the one way to reach the except branch without mocking anything.
    Three things have to hold afterwards: the sweep does not report success, the
    temporary does not stay on disk (a glob for reports would pick it up), and
    the path it could not write is left exactly as it was rather than turned
    into a truncated file.

    An interrupted write is the case an operator actually meets: a full
    filesystem, a lost runtime directory, a unit killed between the two steps.
    """
    f = Fleet(tmp_path)
    f.repo("alpha")
    declared = f.declare(f.url("alpha"))
    occupied = f.root / "fleet-report.json"
    occupied.mkdir()

    res = f.run(declared, "--report", str(occupied))
    assert res.returncode != 0, "a report that could not be written is not a success"
    assert occupied.is_dir(), "the write clobbered what was already at the path"
    assert list(occupied.iterdir()) == [], "a half-written report was left in place"

    leftovers = [p.name for p in f.root.glob(".*secretscan*")]
    assert leftovers == [], f"the temporary survived a failed write: {leftovers}"


def test_a_relative_report_path_is_written_where_the_caller_meant(tmp_path):
    """The only caller that passes a relative `--report` is a person running the
    sweep by hand, and for them "the report went somewhere else" is the failure
    that wastes the run.

    This pins the BEHAVIOUR for the relative spelling — the report lands in the
    process's own directory, with nothing left beside it — and not the
    sibling-of-the-report property the atomicity comment rests on. That property
    is unobservable from here: the temp lands beside the report whether the path
    is resolved or not (`mkstemp(dir="")` resolves against the process
    directory), and `os.replace` succeeds either way on a single filesystem.
    Written down because a mutation battery was built for the line that used to
    resolve the path, survived, and was removed with the line — see
    tests/mutation_battery_scan_report.py's note where S18 would be."""
    f = Fleet(tmp_path)
    f.repo("alpha")
    declared = f.declare(f.url("alpha"))
    workdir = f.root / "cwd"
    workdir.mkdir()

    res = subprocess.run([BASH, str(SCRIPT), "--declared", str(declared),
                          "--report", "relative-report.json"],
                         cwd=workdir, env=f.env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=120)
    assert res.returncode == 0, res.stderr
    written = workdir / "relative-report.json"
    assert written.exists(), f"no report at {written}: {res.stderr}"
    assert json.loads(written.read_text(encoding="utf-8"))["repos"], "the report is empty"
    leftovers = [p.name for p in workdir.glob(".*secretscan*")]
    assert leftovers == [], leftovers


# --- it scans what it was told to, and says so (secret-scan-04) -------------

def test_a_clean_fleet_exits_zero_and_names_every_repository(tmp_path):
    f = Fleet(tmp_path)
    f.repo("alpha")
    f.repo("beta")
    res, report = f.run_report(f.declare(f.url("alpha"), f.url("beta")))
    assert res.returncode == 0, f"a clean fleet was not clean: {res.stderr}"
    assert report is not None, "the sweep wrote no report"
    states = {r["name"]: r["state"] for r in report["repos"]}
    assert states == {"alpha": STATE_CLEAN, "beta": STATE_CLEAN}, states


def test_the_sweep_covers_history_and_the_working_tree(tmp_path):
    """`secret-scan-04`'s sweep is "every reachable commit", and the gate is
    asked for it by name. A sweep that quietly ran the tree scan only would
    miss the credential that was committed and then deleted — the case the
    sweep exists for."""
    f = Fleet(tmp_path)
    f.repo("alpha")
    res, _ = f.run_report(f.declare(f.url("alpha")))
    assert res.returncode == 0, res.stderr
    opts = []
    for call in f.calls():
        for i, a in enumerate(call):
            if a == "--log-opts" and i + 1 < len(call):
                opts.append(call[i + 1])
            elif a.startswith("--log-opts="):
                opts.append(a.split("=", 1)[1])
    assert "--all" in opts, \
        f"the sweep did not ask for the full history: {opts}"
    assert any("--no-git" in c for c in f.calls()), \
        "the sweep did not scan the working tree"


# --- a state per declared repository, and never an omission (secret-scan-07) -

def test_a_finding_in_one_repository_is_named_and_exits_nonzero(tmp_path):
    f = Fleet(tmp_path)
    f.repo("alpha")
    f.repo("leaky", leaky=True)
    res, report = f.run_report(f.declare(f.url("alpha"), f.url("leaky")))
    assert res.returncode == 1, \
        f"a fleet with a finding did not exit 1: {res.returncode}\n{res.stdout}"
    repos = f.by_name(report)
    assert repos["leaky"]["state"] == STATE_FINDINGS
    assert repos["alpha"]["state"] == STATE_CLEAN, \
        "a finding in one repository marked another as unclean"


def test_an_unfetchable_repository_is_reported_not_omitted(tmp_path):
    """The scenario the requirement names. The failure mode is a shorter list:
    the repository that could not be fetched simply is not in the report, and
    the fleet reads as entirely clean."""
    f = Fleet(tmp_path)
    f.repo("alpha")
    res, report = f.run_report(
        f.declare(f.url("alpha"), "file:///nonexistent/devgate-absent.git"))
    assert res.returncode == 4, \
        f"an unscannable fleet exited {res.returncode}, not 4"
    repos = f.by_name(report)
    assert len(report["repos"]) == 2, \
        f"a declared repository was dropped from the report: {report['repos']}"
    absent = repos["devgate-absent"]
    assert absent["state"] == STATE_UNFETCHABLE, absent
    assert absent["reason"], "an unfetchable repository carries no reason"
    assert repos["alpha"]["state"] == STATE_CLEAN, \
        "one unfetchable repository stopped the others being scanned"


def test_a_directory_that_is_not_a_repository_is_unfetchable(tmp_path):
    """A declared URL that resolves to something that is not a git repository
    is a fetch failure, and it must read as one rather than as an empty
    repository with nothing in it."""
    f = Fleet(tmp_path)
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    (plain / "README").write_text("not a repository\n", encoding="utf-8")
    res, report = f.run_report(f.declare(plain.as_uri()))
    assert res.returncode == 4, res.returncode
    assert report["repos"][0]["state"] == STATE_UNFETCHABLE, report["repos"][0]


def test_a_repository_whose_gate_refuses_is_unscannable_not_clean(tmp_path):
    """A repository that fetches but whose own configuration makes the gate
    refuse is not a clean repository — the gate never scanned it."""
    f = Fleet(tmp_path)
    f.repo("broken", allowlist="{ this is not json")
    res, report = f.run_report(f.declare(f.url("broken")))
    assert res.returncode == 4, \
        f"a repository the gate refused exited {res.returncode}, not 4"
    assert report["repos"][0]["state"] == STATE_UNSCANNABLE, report["repos"][0]


def test_the_unscannable_reason_is_the_failure_not_a_line_that_reads_like_a_scan(tmp_path):
    """The recorded reason is what an operator reads instead of the gate's log,
    so it has to be the failure. The gate prints its scope before it configures
    anything — taking the FIRST line of its output would record
    "scope: full history (all refs), plus the working tree" as the reason a
    repository could not be scanned, which reads as a successful scan."""
    f = Fleet(tmp_path)
    f.repo("broken", allowlist="{ this is not json")
    _, report = f.run_report(f.declare(f.url("broken")))
    reason = report["repos"][0]["reason"] or ""
    assert "allowlist" in reason, reason
    assert "scope" not in reason.lower(), reason


def test_the_abort_reason_is_the_scanner_fault_not_the_scope_line(tmp_path):
    """The abort branch, which is where the choice between the first and last
    line of the gate's output is actually observable: the gate echoes its scope
    before it runs the scanner, so a run that dies on the scanner has the scope
    line first and the fault last. Reading the first line would record
    "scope: full history (all refs), plus the working tree" as the reason a
    repository could not be scanned."""
    f = Fleet(tmp_path, STUB_RC=7)
    f.repo("alpha")
    _, report = f.run_report(f.declare(f.url("alpha")))
    reason = report["repos"][0]["reason"] or ""
    assert "scanner unusable" in reason, reason
    assert "scope" not in reason.lower(), reason


def test_the_unfetchable_reason_is_gits_diagnosis(tmp_path):
    """The mirror of the check above, and the opposite choice: git puts its
    diagnosis first and follows it with advice, so the LAST line of its output
    is "and the repository exists." — measured, not assumed."""
    f = Fleet(tmp_path)
    _, report = f.run_report(f.declare("file:///nonexistent/devgate-absent.git"))
    reason = report["repos"][0]["reason"] or ""
    assert "does not appear to be a git repository" in reason, reason


def test_every_declared_repository_appears_exactly_once(tmp_path):
    f = Fleet(tmp_path)
    f.repo("alpha")
    f.repo("leaky", leaky=True)
    _, report = f.run_report(f.declare(
        f.url("alpha"), f.url("leaky"), "file:///nonexistent/gone.git"))
    names = [r["name"] for r in report["repos"]]
    assert len(names) == len(set(names)) == 3, names
    assert report["declared"] == 3, report
    for r in report["repos"]:
        assert r["state"] in ALL_STATES, r
        assert r["url"], r
    assert report["states"] == {
        STATE_CLEAN: 1, STATE_FINDINGS: 1,
        STATE_UNFETCHABLE: 1, STATE_UNSCANNABLE: 0}, report["states"]


# --- an unusable scanner is not a clean fleet ------------------------------

def test_a_scanner_that_crashes_aborts_the_sweep_rather_than_reporting_clean(tmp_path):
    """The repository's recurring failure: a scanner that did not run produces
    no findings, and no findings reads as clean. This is the sweep's version,
    and the answer is that no repository gets a verdict at all."""
    f = Fleet(tmp_path, STUB_RC=7)
    f.repo("alpha")
    res, report = f.run_report(f.declare(f.url("alpha")))
    assert res.returncode == 2, \
        f"an unusable scanner exited {res.returncode}, not 2"
    states = [r["state"] for r in (report or {}).get("repos", [])]
    assert STATE_CLEAN not in states, \
        f"the sweep reported a clean repository off a scanner that crashed: {states}"


# --- the declaration is a decision, not a default --------------------------

def test_an_empty_declaration_is_not_a_clean_fleet(tmp_path):
    """Zero repositories scanned is not a green fleet; it is a sweep that
    measured nothing wearing the same exit code as success. Same rule as
    run-tests.mjs refusing to report success on zero discovered tests."""
    f = Fleet(tmp_path)
    res = f.run(tmp_path / "declared.txt")  # the file does not exist
    assert res.returncode == 3, \
        f"an absent declaration exited {res.returncode}, not 3"


def test_a_declaration_naming_nothing_is_not_a_clean_fleet(tmp_path):
    f = Fleet(tmp_path)
    f.repo("alpha")
    res = f.run(f.declare(comment=True))  # comments only
    assert res.returncode == 3, res.returncode
    assert "declar" in (res.stdout + res.stderr).lower(), \
        "the sweep did not say the declaration was empty"


def test_the_declaration_may_carry_comments_and_blank_lines(tmp_path):
    f = Fleet(tmp_path)
    f.repo("alpha")
    d = tmp_path / "declared.txt"
    d.write_text(f"# a comment\n\n   \n{f.url('alpha')}\n\n# another\n", encoding="utf-8")
    res, report = f.run_report(d)
    assert res.returncode == 0, res.stderr
    assert [r["name"] for r in report["repos"]] == ["alpha"], report["repos"]


# --- nothing here prints a value -------------------------------------------

def test_no_secret_value_reaches_the_report_or_the_output(tmp_path):
    """The gate's own rule, carried into the layer that aggregates it: a
    finding is a location, not a value. An aggregating sweep is a second place
    a value can be written to a file that gets uploaded or attached to a
    ticket."""
    f = Fleet(tmp_path)
    f.repo("leaky", leaky=True)
    report_path = tmp_path / "fleet-report.json"
    res = f.run(f.declare(f.url("leaky")), "--report", str(report_path))
    for text in (res.stdout, res.stderr, report_path.read_text(encoding="utf-8")):
        assert CANARY not in text, "the sweep published the matched value"
    repo = json.loads(report_path.read_text(encoding="utf-8"))["repos"][0]
    assert repo["state"] == STATE_FINDINGS
    assert repo["scope"], "a scanned repository did not report its scope"
    assert repo["scanned_at"], "a scanned repository did not report when"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
