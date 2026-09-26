"""Tests for scripts/secret-scan.sh — the push-path secret gate.

The repository ships a secret-scanning workflow template it never ran on
itself, so every push to main passed six jobs without one of them looking for
a credential. This suite pins the gate that closes that hole.

The failure mode it is written against is the one this repository keeps
meeting: a scanner that does not run produces no findings, and no findings
reads as clean. So "scanner missing" must exit non-zero, "which scope" must be
explicit, and a finding must be reported by location — never by value, because
a scanner that prints the secret has published it to a wider audience than the
commit did.

Every assertion runs against a stubbed `gitleaks` on PATH. The stub always
writes the TRUE value into its report, redaction flag or not: the gate's job is
to never echo what the report contains, and a stub that pre-redacted would let
the gate off that hook.

Dual-runnable: pytest collects test_*; `python3 tests/test_secret_scan.py` runs
them too.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "secret-scan.sh"
BASH = shutil.which("bash") or "/bin/bash"
GIT = shutil.which("git")
# A value the stub always reports as the matched secret. If this string ever
# reaches the gate's output, the gate republished it.
CANARY = "ghp_Zz9CanaryValueNeverPrinted0Qw7"

FINDING = {
    "RuleID": "github-pat",
    "File": "src/app.py",
    "StartLine": 42,
    "Commit": "abc123def456",
    "Secret": CANARY,
    "Match": f'token = "{CANARY}"',
    "Fingerprint": "abc123def456:src/app.py:github-pat:42",
}

# Answers the invocations the gate makes, from JSON state plus env knobs:
#   STUB_FINDINGS   JSON array of findings this run reports (default: none)
#   STUB_RC         forced exit code, to model a scanner that crashes
# The report file is written whenever --report-path is passed, and it always
# contains the unredacted Secret — see the module docstring for why.
GITLEAKS_STUB = r'''#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\n")

findings = json.loads(os.environ.get("STUB_FINDINGS", "[]"))

def opt(name):
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
    return None

forced = os.environ.get("STUB_RC")
rc = int(forced) if forced is not None else (1 if findings else 0)

fmt, path = opt("--report-format"), opt("--report-path")
if path and fmt == "json":
    with open(path, "w") as fh:
        json.dump(findings, fh)

if findings:
    sys.stderr.write("WRN leaks found: %d\n" % len(findings))
else:
    sys.stderr.write("INF no leaks found\n")
sys.exit(rc)
'''


class Gate:
    """A scratch repository with a stubbed gitleaks on PATH."""

    def __init__(self, tmp_path, findings=(), **knobs):
        self.root = tmp_path
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        p = bindir / "gitleaks"
        p.write_text(GITLEAKS_STUB, encoding="utf-8")
        p.chmod(0o755)
        self.bindir = bindir
        self.log = tmp_path / "gitleaks.jsonl"
        self.log.write_text("", encoding="utf-8")
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        self.env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "STUB_LOG": str(self.log),
            "STUB_FINDINGS": json.dumps(list(findings)),
        }
        self.env.update({k: str(v) for k, v in knobs.items()})

    # --- repo state -------------------------------------------------------------
    def allowlist(self, entries):
        d = self.root / ".guardrails"
        d.mkdir(exist_ok=True)
        (d / "secret-allowlist.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")

    def allowlist_raw(self, text):
        d = self.root / ".guardrails"
        d.mkdir(exist_ok=True)
        (d / "secret-allowlist.json").write_text(text, encoding="utf-8")

    def _git(self, *args):
        res = subprocess.run([GIT, "-C", str(self.root), *args],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        return res.stdout.strip()

    def git_repo(self):
        """A real repository, for the scopes that consult the commit history."""
        (self.root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "t")
        return self.commit("initial")

    def commit(self, message):
        (self.root / "CHANGELOG").open("a").write(f"{message}\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD")

    # --- inspection -------------------------------------------------------------
    def calls(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l]

    def log_opts(self):
        """The history scope the gate asked for, from either argv spelling —
        the assertion is which commits were scanned, not how the flag was
        written."""
        out = []
        for c in self.calls():
            for i, a in enumerate(c):
                if a == "--log-opts" and i + 1 < len(c):
                    out.append(c[i + 1])
                elif a.startswith("--log-opts="):
                    out.append(a.split("=", 1)[1])
        return out

    def runs(self, *args, report=None, env=None, path_prefix=None):
        argv = [BASH, str(SCRIPT), "--repo", str(self.root), *args]
        if report:
            argv += ["--report", str(report)]
        env = dict(self.env if env is None else env)
        if path_prefix is not None:
            env["PATH"] = path_prefix
        return subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)


# --- the scan runs, and says what it scanned (secret-scan-01) -------------------

def test_clean_run_exits_zero_and_names_its_scope(tmp_path):
    g = Gate(tmp_path)
    res = g.runs("--tree")
    assert res.returncode == 0, f"a clean scan failed: {res.stderr}"
    assert "tree" in (res.stdout + res.stderr).lower(), \
        "the gate did not say what it scanned"


def test_a_missing_scanner_is_a_failure_not_a_clean_repository(tmp_path):
    """No scanner produces no findings, and no findings reads as clean. The one
    thing this gate may not do is confuse those."""
    g = Gate(tmp_path)
    empty = tmp_path / "empty-bin"
    empty.mkdir(exist_ok=True)
    res = g.runs("--tree", path_prefix=str(empty))
    assert res.returncode != 0, "an absent scanner reported a clean repository"
    assert "gitleaks" in (res.stdout + res.stderr), \
        "the failure did not name the missing scanner"


def test_a_scanner_that_crashes_is_not_a_clean_repository(tmp_path):
    """Exit 2 is a distinct state from exit 0 on purpose: a scanner that died
    part-way has not cleared anything."""
    g = Gate(tmp_path, findings=[FINDING], STUB_RC=2)
    res = g.runs("--tree")
    assert res.returncode == 2, f"a crashed scanner exited {res.returncode}"
    assert "unusable" in (res.stdout + res.stderr).lower(), \
        "the failure did not say the scanner failed rather than the repo"


def test_no_scope_is_a_usage_error(tmp_path):
    """Which scope is a decision, not a default: the per-push range and the
    full-history sweep answer different questions."""
    g = Gate(tmp_path)
    res = g.runs()
    assert res.returncode == 3, f"a scopeless invocation was accepted: {res.stdout!r}"
    assert not g.calls(), "the scanner ran without a decided scope"


def test_a_range_with_no_usable_base_falls_back_and_says_so(tmp_path):
    """A first push or a forced update has no base commit. Scanning nothing and
    exiting 0 would be the worst possible reading of that."""
    g = Gate(tmp_path)
    g.git_repo()
    res = g.runs("--range", "0000000000000000000000000000000000000000..HEAD")
    text = res.stdout + res.stderr
    assert res.returncode == 0, f"the fall-back run failed: {text}"
    assert "fall" in text.lower() or "no usable base" in text.lower(), \
        f"the fall-back was silent: {text!r}"
    assert "all" in text.lower(), "the fall-back did not say it swept the history"


def test_range_scope_is_the_pushed_range_not_the_history(tmp_path):
    """The base exists here, so this is the range path and not the fall-back:
    if a usable base silently fell through to a sweep, the assertion on the
    requested scope would be the only thing to catch it."""
    g = Gate(tmp_path)
    base = g.git_repo()
    head = g.commit("second")
    res = g.runs("--range", f"{base}..{head}")
    assert res.returncode == 0, res.stderr
    assert g.log_opts() == [f"{base}..{head}"], \
        f"the range scope was not passed: {g.log_opts()}"
    assert "falling back" not in (res.stdout + res.stderr).lower(), \
        "a resolvable base was treated as missing"


def test_the_working_tree_is_scanned_and_is_not_a_history_scan(tmp_path):
    """Every scope includes the working tree — an uncommitted credential is
    still a credential — and the tree scan must be a file scan, not a git scan
    that would quietly drag the history into a scope that did not ask for it."""
    g = Gate(tmp_path)
    g.runs("--tree")
    assert any("--no-git" in c for c in g.calls()), \
        f"the working tree was scanned as a git scan: {g.calls()}"
    assert g.log_opts() == [], "a tree-only run swept commit history"


def test_a_range_run_scans_the_working_tree_too(tmp_path):
    """The push gate is 'the pushed commits plus what is on disk'; a run that
    scanned only the commits would miss the credential in the editor."""
    g = Gate(tmp_path)
    base = g.git_repo()
    g.commit("second")
    g.runs("--range", f"{base}..HEAD")
    assert any("--no-git" in c for c in g.calls()), \
        f"the range run did not scan the working tree: {g.calls()}"
    assert len(g.calls()) == 2, f"expected a tree scan and a history scan: {g.calls()}"


def test_history_sweep_is_an_explicit_scope(tmp_path):
    g = Gate(tmp_path)
    res = g.runs("--all")
    assert res.returncode == 0, res.stderr
    assert g.log_opts() == ["--all"], \
        f"the full-history sweep was not requested: {g.log_opts()}"
    assert "history" in (res.stdout + res.stderr).lower(), \
        "the sweep did not name its scope"


# --- a finding fails, and never carries the value (secret-scan-02) --------------

def test_a_finding_fails_the_gate(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    res = g.runs("--tree")
    assert res.returncode == 1, f"a finding did not fail the gate: {res.returncode}"


def test_a_finding_is_reported_by_location_not_by_value(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    res = g.runs("--tree")
    text = res.stdout + res.stderr
    assert "github-pat" in text, "the finding's rule was not reported"
    assert "src/app.py" in text, "the finding's path was not reported"
    assert "42" in text, "the finding's line was not reported"
    assert CANARY not in text, (
        "the gate printed the matched value — a scanner that echoes the secret "
        "publishes it to a wider audience than the commit did")


def test_the_written_report_never_carries_the_value(tmp_path):
    """The stub writes the true value into its report; whatever the gate writes
    out for humans must not pass that through."""
    g = Gate(tmp_path, findings=[FINDING])
    out = tmp_path / "report.json"
    g.runs("--tree", report=out)
    assert out.exists(), "no report was written"
    assert CANARY not in out.read_text(encoding="utf-8"), "the gate's own report carried the value"


def test_the_scanner_is_always_invoked_with_redaction(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    g.runs("--tree")
    assert g.calls(), "the scanner was never invoked"
    for c in g.calls():
        assert "--redact" in c, f"a scanner invocation without redaction: {c}"


# --- dispositions (secret-scan-03) ---------------------------------------------

def test_an_allowlisted_finding_passes_and_is_named(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    g.allowlist([{"rule": "github-pat", "path": "src/app.py",
                  "reason": "fixture value, not a credential"}])
    res = g.runs("--tree")
    assert res.returncode == 0, f"a dispositioned finding still failed: {res.stderr}"
    assert "src/app.py" in (res.stdout + res.stderr), \
        "the dispositioned finding was not named"


def test_an_allowlisted_rule_in_another_path_still_fails(tmp_path):
    """An entry covers a location, not a rule. Otherwise one disposition of one
    false positive silently immunises the whole ruleset."""
    other = dict(FINDING, File="src/other.py",
                 Fingerprint="abc123def456:src/other.py:github-pat:42")
    g = Gate(tmp_path, findings=[other])
    g.allowlist([{"rule": "github-pat", "path": "src/app.py",
                  "reason": "fixture value, not a credential"}])
    res = g.runs("--tree")
    assert res.returncode == 1, "a finding outside the dispositioned path passed"


def test_an_allowlist_entry_without_a_reason_is_refused(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    g.allowlist([{"rule": "github-pat", "path": "src/app.py"}])
    res = g.runs("--tree")
    assert res.returncode != 0, "a reasonless disposition was accepted"
    assert not g.calls(), "the scan ran before the allowlist was validated"


def test_an_unmatched_allowlist_entry_is_reported(tmp_path):
    """An allowlist nobody prunes is a list of bugs the team agreed to keep."""
    g = Gate(tmp_path)
    g.allowlist([{"rule": "github-pat", "path": "src/gone.py",
                  "reason": "was a fixture, file was deleted"}])
    res = g.runs("--all")
    text = res.stdout + res.stderr
    assert res.returncode == 0, res.stderr
    assert "src/gone.py" in text, f"an unmatched entry went unreported: {text!r}"
    assert "stale" in text.lower(), "the unmatched entry was not called stale"


def test_a_malformed_allowlist_is_not_a_pass(tmp_path):
    g = Gate(tmp_path, findings=[FINDING])
    g.allowlist_raw("{not json")
    res = g.runs("--tree")
    assert res.returncode != 0, "an unparseable allowlist was treated as empty"


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
