#!/usr/bin/env python3
"""Tests for spec-fleet-walk.sh's report capping + dedup shape (SGA-13).

The walk itself shells out to git clone, so these tests use local directory
paths (which the walk treats as already-present trees) instead of network
clones, plus stub `git` binaries where the clone path itself is under test.
Dual-runnable: pytest collects test_*.
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALK = HERE.parent / "scripts" / "spec-fleet-walk.sh"
CLASSIFIER = HERE.parent / "scripts" / "spec-fleet-classify.py"
WORKFLOW = HERE.parent / ".github" / "workflows" / "spec-fleet.yml"

sys.path.insert(0, str(HERE))

import workflow_read as wr  # noqa: E402


def _stub_bin(tmp_path: Path, git_body: str) -> Path:
    """A PATH entry whose `git` is the supplied script body."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text("#!/usr/bin/env bash\n" + git_body, encoding="utf-8")
    git.chmod(0o755)
    return bin_dir


def _run_walk(tmp_path: Path, declared_lines, *, env):
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared_lines) + "\n", encoding="utf-8")
    report = tmp_path / "report.json"
    res = subprocess.run(
        ["bash", str(WALK), "--declared", str(decl),
         "--report", str(report), "--work", str(tmp_path / "work")],
        capture_output=True, text=True, env=env)
    return res, report


def make_walk_repo(tmp: Path, *, state_label: str, openspec: bool = True) -> Path:
    root = tmp / state_label
    root.mkdir()
    if openspec:
        (root / "openspec" / "specs" / "foo").mkdir(parents=True)
        (root / "openspec" / "specs" / "foo" / "spec.md").write_text(
            "# foo\n\n### Requirement: x <!-- id: foo-01 -->\n")
    return root


def test_cap_and_omitted_shape(tmp_path):
    """The report keeps every repo and never drops unspaced names (SGA-13)."""
    declared = []
    for i in range(5):
        make_walk_repo(tmp_path, state_label=f"repo-{i}", openspec=(i % 2 == 0))
        declared.append(str(tmp_path / f"repo-{i}"))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    work = tmp_path / "work"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(work)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["declared"] == 5
    assert len(data["repos"]) == 5  # every declared repo appears exactly once
    names = {entry["name"] for entry in data["repos"]}
    assert names == {f"repo-{i}" for i in range(5)}
    # unspaced repos are named, never red
    for entry in data["repos"]:
        if entry["state"] == "unspaced":
            assert entry["red"] is False


def test_capped_summary_lists_and_omitted_counts(tmp_path):
    """unspaced[] / invalid[] / gaps_top[] are capped at 40 with omitted counts."""
    declared = []
    for i in range(45):
        make_walk_repo(tmp_path, state_label=f"unspaced-{i:03d}", openspec=False)
        declared.append(str(tmp_path / f"unspaced-{i:03d}"))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    # the full list is never truncated...
    assert data["declared"] == 45
    assert len(data["repos"]) == 45
    # ...and the summary lists are capped at 40 with the remainder counted
    assert len(data["unspaced"]) == 40
    assert data["unspaced_omitted"] == 5
    assert data["unspaced"][0]["name"] == "unspaced-000"
    assert isinstance(data["invalid"], list)
    assert isinstance(data["gaps_top"], list)


def test_provenance_findings_travel_with_the_row(tmp_path):
    """A drift finding must reach the report, or the sweep reads clean forever.

    The workflow's provenance step reads `provenance` off each report row; a
    row that drops it makes every nightly say "provenance: clean" while the
    templates drift. Pin the field, the drift list, and the red flag.
    """
    root = tmp_path / "repo"
    root.mkdir()
    (root / "templates" / "openspec").mkdir(parents=True)
    vendored = root / "templates" / "openspec" / "spec.md"
    vendored.write_text("# local copy that no longer matches the pin\n")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None,
        "pinned_sha256": "0" * 64,
        "vendored_path": "templates/openspec/spec.md",
    }}}))
    decl = tmp_path / "declared.txt"
    decl.write_text(str(root) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work"),
                        "--lock-file", str(lock)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    row = json.loads(report.read_text(encoding="utf-8"))["repos"][0]
    prov = row["provenance"]
    assert [d["kind"] for d in prov["drift"]] == ["local"]
    # findings travel, and they are findings (issue), not red (SGA-21 vs 22)
    assert row["provenance_findings"] is True
    assert row["provenance_red"] is False


def test_lock_provenance_is_checked_once_not_per_repo(tmp_path):
    """Pin-integrity is a property of the lock, not of every scanned tree."""
    content = tmp_path / "upstream.md"
    content.write_text("# upstream copy\n")
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"templates": {"openspec-spec": {
        "source": None,
        "pin_source": content.as_uri(),
        "pinned_sha256": "2" * 64,
        "vendored_path": None,
    }}}))
    declared = []
    for i in range(3):
        root = tmp_path / f"repo-{i}"
        root.mkdir()
        declared.append(str(root))
    decl = tmp_path / "declared.txt"
    decl.write_text("\n".join(declared) + "\n")
    report = tmp_path / "report.json"
    r = subprocess.run(["bash", str(WALK), "--declared", str(decl),
                        "--report", str(report), "--work", str(tmp_path / "work"),
                        "--lock-file", str(lock)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["lock_provenance"]["fault"] is True
    for row in data["repos"]:
        assert not (row.get("provenance") or {}).get("fault")


# --- authenticated clones (SPEC_FLEET_CLONE_TOKEN) -------------------------
#
# The report is committed to docs/qa/spec-sweeps/ in a PUBLIC repository, so
# the App token must never reach git's argv, the report, or a log. These tests
# drive the failure path with a stub `git` that would echo a secret if it had
# one, and assert it never comes back out.


def test_no_token_keeps_the_historical_clone_failure_reason(tmp_path):
    """Unset token: no askpass helper, no env override, and the reason stays
    the historical `str(exc)` — clone stderr is NOT folded in, exactly as
    before this feature existed."""
    fake_shape = "ghp_" + "".join(["B"] * 30)
    argv_out = tmp_path / "argv.txt"
    bin_dir = _stub_bin(
        tmp_path,
        'printf "%s\\n" "$@" > "$STUB_GIT_ARGV"\n'
        f'printf "fatal: could not read Password for https://x-access-token:{fake_shape}@github.com\\n" >&2\n'
        "exit 128\n")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["STUB_GIT_ARGV"] = str(argv_out)
    env.pop("SPEC_FLEET_CLONE_TOKEN", None)

    res, report = _run_walk(
        tmp_path, ["https://github.com/TheArchitectit/rad-gateway"], env=env)

    assert res.returncode == 0, res.stderr
    row = json.loads(report.read_text(encoding="utf-8"))["repos"][0]
    assert row["state"] == "unscannable"
    assert row["reason"].startswith("Command "), row["reason"]
    assert "could not read Password" not in row["reason"]
    assert "***" not in row["reason"]
    assert not (tmp_path / "work" / ".git-askpass.sh").exists()
    assert "authenticated clone mode" not in res.stdout


def test_a_clone_failure_never_leaks_the_token_into_the_report(tmp_path):
    """Set token: the askpass helper exists at mode 700 and carries no
    credential, git's argv carries no token, and a stderr line that echoes it
    is redacted before it reaches the report."""
    fake = "ghs_" + "".join(["C"] * 36)
    argv_out = tmp_path / "argv.txt"
    bin_dir = _stub_bin(
        tmp_path,
        'printf "%s\\n" "$@" > "$STUB_GIT_ARGV"\n'
        'printf "fatal: Authentication failed for '
        'https://x-access-token:%s@github.com/TheArchitectit/rad-gateway\\n" '
        '"$SPEC_FLEET_ASKPASS_TOKEN" >&2\n'
        "exit 128\n")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["STUB_GIT_ARGV"] = str(argv_out)
    env["SPEC_FLEET_CLONE_TOKEN"] = fake

    res, report = _run_walk(
        tmp_path, ["https://github.com/TheArchitectit/rad-gateway"], env=env)

    assert res.returncode == 0, res.stderr
    report_text = report.read_text(encoding="utf-8")
    row = json.loads(report_text)["repos"][0]
    assert row["state"] == "unscannable"
    assert fake not in report_text, "the clone token reached the public report"
    assert fake not in row["reason"]
    assert "***" in row["reason"], row["reason"]
    assert fake not in argv_out.read_text(encoding="utf-8"), (
        "the clone token reached git's argv")
    askpass = tmp_path / "work" / ".git-askpass.sh"
    assert askpass.exists()
    assert stat.S_IMODE(askpass.stat().st_mode) == 0o700, oct(
        askpass.stat().st_mode)
    assert fake not in askpass.read_text(encoding="utf-8"), (
        "the askpass helper must read the secret from its environment, "
        "not store it")


def test_auth_clone_clears_the_checkout_extraheader_on_argv(tmp_path):
    """actions/checkout persists the workflow token as
    `http.https://github.com/.extraheader` in the workspace's local config,
    and that header overrides the App askpass token — the measured cause of
    run 44359038399's positive-control failure ("repository not found" on a
    repo the App can read). The clone must clear it ON ARGV: the equivalent
    GIT_CONFIG_KEY_n env form was measured NOT to override it."""
    argv_out = tmp_path / "argv.txt"
    bin_dir = _stub_bin(
        tmp_path,
        'printf "%s\\n" "$@" > "$STUB_GIT_ARGV"\n'
        "exit 128\n")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["STUB_GIT_ARGV"] = str(argv_out)
    env["SPEC_FLEET_CLONE_TOKEN"] = "ghs_" + "".join(["D"] * 36)

    res, _ = _run_walk(
        tmp_path, ["https://github.com/TheArchitectit/rad-gateway"], env=env)

    assert res.returncode == 0, res.stderr
    args = argv_out.read_text(encoding="utf-8").splitlines()
    assert "-c" in args and "http.https://github.com/.extraheader=" in args, args
    # and it is an argv -c pair, not merely an env entry
    idx = args.index("http.https://github.com/.extraheader=")
    assert args[idx - 1] == "-c", args


def test_no_token_clone_does_not_touch_the_extraheader(tmp_path):
    """Without a token the clone command stays exactly the historical one —
    no config overrides that a public mirror's own auth might depend on."""
    argv_out = tmp_path / "argv.txt"
    bin_dir = _stub_bin(
        tmp_path,
        'printf "%s\\n" "$@" > "$STUB_GIT_ARGV"\n'
        "exit 128\n")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["STUB_GIT_ARGV"] = str(argv_out)
    env.pop("SPEC_FLEET_CLONE_TOKEN", None)

    res, _ = _run_walk(
        tmp_path, ["https://github.com/example/public-mirror"], env=env)

    assert res.returncode == 0, res.stderr
    args = argv_out.read_text(encoding="utf-8").splitlines()
    assert args == ["clone", "--depth", "1",
                    "https://github.com/example/public-mirror", args[-1]], args
    assert not any("extraheader" in a for a in args)


# --- the declaration step's re-admit rule ----------------------------------
#
# The drop/re-admit decision lives in the workflow step, so the test pulls the
# step's inline python out of spec-fleet.yml and runs it. That keeps the test
# on the shipped code path rather than a copy of it.


def _declaration_transform_code() -> str:
    wf = wr.read_workflow(WORKFLOW.read_text(encoding="utf-8"))
    step = next(s for s in wf.jobs["sweep"]["steps"]
                if str(s.get("name", "")).startswith("Generate the declaration"))
    lines = str(step["run"]).splitlines()
    start = next(i for i, line in enumerate(lines) if "<<'PY'" in line)
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "PY")
    return "\n".join(lines[start + 1:end])


def _run_declaration(tmp_path, *, mode, raw_lines, include_lines, private):
    bin_dir = tmp_path / f"bin-{mode}"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    hits = "|".join(f"repos/{full}" for full in private)
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f'case "$2" in {hits}) printf "true\\n" ;; *) printf "false\\n" ;; esac\n',
        encoding="utf-8")
    gh.chmod(0o755)

    raw = tmp_path / f"raw-{mode}.txt"
    raw.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    include = tmp_path / f"include-{mode}.txt"
    include.write_text("\n".join(include_lines) + "\n", encoding="utf-8")
    out = tmp_path / f"declared-{mode}.txt"

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["TOKEN_MODE"] = mode
    env.pop("GH_TOKEN", None)
    res = subprocess.run(
        [sys.executable, "-", str(raw), str(out), str(include)],
        input=_declaration_transform_code(), capture_output=True, text=True, env=env)
    return res, (out.read_text(encoding="utf-8") if out.exists() else "")


def test_curated_private_entries_are_readmitted_only_in_app_mode(tmp_path):
    raw = [
        "https://github.com/TheArchitectit/rad-gateway",          # curated
        "https://github.com/TheArchitectit/some-generated-private",  # not curated
        "https://github.com/TheArchitectit/public-thing",         # public
    ]
    include = ["https://github.com/TheArchitectit/rad-gateway"]
    private = ["TheArchitectit/rad-gateway",
               "TheArchitectit/some-generated-private"]

    app_res, app_out = _run_declaration(
        tmp_path, mode="app", raw_lines=raw, include_lines=include, private=private)
    assert app_res.returncode == 0, app_res.stderr
    app_lines = app_out.splitlines()
    assert "https://github.com/TheArchitectit/rad-gateway" in app_lines
    assert "https://github.com/TheArchitectit/public-thing" in app_lines
    assert "https://github.com/TheArchitectit/some-generated-private" not in app_lines
    assert "re-admitted 1 curated private repo(s)" in app_res.stdout, app_res.stdout
    assert "rad-gateway" in app_res.stdout

    wf_res, wf_out = _run_declaration(
        tmp_path, mode="workflow", raw_lines=raw, include_lines=include,
        private=private)
    assert wf_res.returncode == 0, wf_res.stderr
    wf_lines = wf_out.splitlines()
    assert wf_lines == ["https://github.com/TheArchitectit/public-thing"], wf_lines
    assert "re-admitted" not in wf_res.stdout
    assert "dropped 2 private repo(s)" in wf_res.stdout, wf_res.stdout


def test_app_mode_has_a_positive_control_that_cannot_leak_the_token():
    """The control is what turns a mis-scoped App installation into a named
    error at the top of the run instead of four `unscannable` repos at the
    bottom, so its shape is pinned: app-only, before the walk, read-only, and
    using the same askpass mechanism as the walk."""
    wf = wr.read_workflow(WORKFLOW.read_text(encoding="utf-8"))
    steps = wf.jobs["sweep"]["steps"]
    names = [str(s.get("name", "")) for s in steps]
    pc_i = next(i for i, n in enumerate(names) if n.startswith("Positive control"))
    walk_i = names.index("Run the walk")
    assert pc_i < walk_i, "the positive control must run before the walk"

    control = steps[pc_i]
    assert "token_mode == 'app'" in str(control.get("if", ""))
    run = str(control["run"])
    assert "TheArchitectit/rad-gateway" in run
    assert "ls-remote" in run
    assert "GIT_ASKPASS" in run
    assert "add-mask" in run
    assert '"$CLONE_TOKEN"' in run, "the token travels as an env value"
    assert "clone" not in run.replace("ls-remote", "")

    walk = steps[walk_i]
    assert "SPEC_FLEET_CLONE_TOKEN" in walk["env"]
    assert "token_mode == 'app'" in walk["env"]["SPEC_FLEET_CLONE_TOKEN"]
    assert "add-mask" in str(walk["run"])


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([str(Path(__file__))]))