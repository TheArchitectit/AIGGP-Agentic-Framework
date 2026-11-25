"""Hermetic consumer tests for the three GitHub workflow DevGate bootstraps."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = {
    "drift-scan.yml": (
        "Bootstrap pinned DevGate for target detection",
        "Bootstrap pinned DevGate",
    ),
    "specs.yml": ("Bootstrap pinned DevGate",),
    "text-integrity.yml": ("Bootstrap pinned DevGate",),
}


def _step_run(text: str, name_contains: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == f"- name: {name_contains}":
            for run_index in range(index, len(lines)):
                if lines[run_index].strip() == "run: |":
                    indent = len(lines[run_index]) - len(lines[run_index].lstrip()) + 2
                    body = []
                    for raw in lines[run_index + 1 :]:
                        if raw.strip() and len(raw) - len(raw.lstrip()) < indent:
                            break
                        body.append(raw[indent:] if raw.strip() else "")
                    return "\n".join(body)
            break
    raise AssertionError(f"no run block for step {name_contains!r}")


def _bootstrap(workflow: str, step: str) -> tuple[str, tuple[str, ...]]:
    text = (REPO / "templates" / "github-workflows" / workflow).read_text(encoding="utf-8")
    body = _step_run(text, step)
    end = body.find('echo "DevGate ready at $DEVGATE_SHA under .devgate/"')
    assert end >= 0, f"{workflow} bootstrap completion marker is absent"
    body = body[:end]
    required_match = re.search(r"for required in (.+); do", body)
    assert required_match, f"{workflow} has no required-path preflight"
    required = tuple(required_match.group(1).split())
    assert required, f"{workflow} has an empty required-path list"
    return body, required


BOOTSTRAPS = {
    (workflow, step): _bootstrap(workflow, step)
    for workflow, steps in WORKFLOWS.items()
    for step in steps
}


def _git(cwd: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0"})
    result = subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def _make_bare_source(tmp_path: Path, omit: str | None = None) -> tuple[str, str, set[str]]:
    source = tmp_path / "approved-source"
    bare = tmp_path / "approved-source.git"
    source.mkdir()
    bare.mkdir()
    _git(source, "init", "--quiet", "--initial-branch=main")
    _git(bare, "init", "--quiet", "--bare", "--initial-branch=main")
    _git(source, "config", "user.name", "Synthetic Fixture")
    _git(source, "config", "user.email", "fixture@example.invalid")
    required = {path for _body, paths in BOOTSTRAPS.values() for path in paths}
    if omit:
        required.discard(omit)
    for relative in required:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    _git(source, "add", "--all")
    _git(source, "commit", "--quiet", "-m", "synthetic approved DevGate source")
    pin = _git(source, "rev-parse", "HEAD")
    _git(source, "push", "--quiet", str(bare), "HEAD:main")
    return bare.as_uri(), pin, required


def _consumer_root(path: Path) -> None:
    path.mkdir()
    _git(path, "init", "--quiet", "--initial-branch=main")
    _git(path, "config", "user.name", "Synthetic Consumer")
    _git(path, "config", "user.email", "consumer@example.invalid")
    (path / ".gitignore").write_text(".devgate/\n", encoding="utf-8")
    _git(path, "add", ".gitignore")
    _git(path, "commit", "--quiet", "-m", "synthetic consumer")
    assert not (path / ".gitmodules").exists()


def _run(
    project: Path, source_url: str, pin: str, block: str,
    path_prefix: Path | None = None,
    global_config: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    from tests.platform_caps import require_bash

    require_bash("GitHub workflow bootstrap behavior executes a shell block")
    env = os.environ.copy()
    env.update({"DEVGATE_SOURCE_URL": source_url, "DEVGATE_SHA": pin,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": str(global_config) if global_config else os.devnull,
                "GIT_TERMINAL_PROMPT": "0"})
    if path_prefix is not None:
        env["PATH"] = str(path_prefix) + os.pathsep + env.get("PATH", "")
    return subprocess.run(["bash", "-c", block],
                         cwd=project, env=env, capture_output=True, text=True, timeout=30)


def _assert_fail_closed(project: Path, result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, result.stdout + result.stderr
    assert "DevGate bootstrap:" in result.stdout + result.stderr
    assert not (project / "gate.green").exists()


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_each_copy_in_workflow_bootstraps_exact_ignored_pin_offline(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)

    body, declared = BOOTSTRAPS[(workflow, step)]
    assert set(declared).issubset(required)
    for path in declared:
        assert (REPO / path).is_file(), f"{workflow} declares absent DevGate input {path}"
    result = _run(project, source_url, pin, body)
    if result.returncode == 0:
        (project / "gate.green").write_text("gate may now run\n", encoding="utf-8")

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (project / ".gitmodules").exists()
    assert (project / "gate.green").is_file()
    assert _git(project / ".devgate", "rev-parse", "HEAD") == pin
    assert _git(project / ".devgate", "rev-parse", "--show-toplevel") == str(project / ".devgate")
    assert _git(project, "check-ignore", "--quiet", "--no-index", ".devgate/") == ""


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_fresh_checkout_ignores_global_autocrlf_conversion(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")

    result = _run(project, source_url, pin, BOOTSTRAPS[(workflow, step)][0],
                  global_config=global_config)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _git(project / ".devgate", "rev-parse", "HEAD") == pin
    assert "content does not match DEVGATE_SHA" not in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_malformed_pin_fails_before_gate_for_each_workflow(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, _pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    result = _run(project, source_url, "not-a-full-sha", BOOTSTRAPS[(workflow, step)][0])
    _assert_fail_closed(project, result)
    assert "full lowercase commit SHA" in result.stdout + result.stderr
    assert "workflow-level DEVGATE_SHA placeholder" in result.stdout + result.stderr
    assert not (project / ".devgate").exists()


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_failed_git_inspection_is_not_treated_as_empty_state(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    git = fake_bin / "git"
    git.write_text("#!/bin/sh\nexit 42\n", encoding="utf-8")
    git.chmod(0o755)
    result = _run(project, source_url, pin, BOOTSTRAPS[(workflow, step)][0], fake_bin)
    _assert_fail_closed(project, result)
    assert "cannot resolve the consumer Git root" in result.stdout + result.stderr
    assert not (project / ".devgate").exists()


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_wrong_commit_reuse_fails_closed(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    body = BOOTSTRAPS[(workflow, step)][0]
    assert _run(project, source_url, pin, body).returncode == 0
    _git(project / ".devgate", "config", "user.name", "Synthetic Wrong Pin")
    _git(project / ".devgate", "config", "user.email", "wrong-pin@example.invalid")
    wrong_file = project / ".devgate" / "scripts" / "synthetic-wrong-pin.txt"
    wrong_file.write_text("wrong commit\n", encoding="utf-8")
    _git(project / ".devgate", "add", "scripts/synthetic-wrong-pin.txt")
    _git(project / ".devgate", "commit", "--quiet", "-m", "synthetic wrong pin")
    result = _run(project, source_url, pin, body)
    _assert_fail_closed(project, result)
    assert "not at DEVGATE_SHA" in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_incomplete_existing_checkout_fails_closed(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    body = BOOTSTRAPS[(workflow, step)][0]
    (project / ".devgate").mkdir()
    _git(project, "init", "--quiet", ".devgate")
    result = _run(project, source_url, pin, body)
    _assert_fail_closed(project, result)
    assert "no checked-out commit" in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_wrong_dev_gate_root_fails_before_gate(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    nested = project / ".devgate" / "nested"
    nested.mkdir(parents=True)
    _git(project, "init", "--quiet", ".devgate/nested")
    result = _run(project, source_url, pin, BOOTSTRAPS[(workflow, step)][0])
    _assert_fail_closed(project, result)
    assert "not a checkout rooted at .devgate" in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_missing_required_source_file_fails_closed(
    tmp_path: Path, workflow: str, step: str
) -> None:
    body, required = BOOTSTRAPS[(workflow, step)]
    source_url, pin, _files = _make_bare_source(tmp_path, omit=required[0])
    project = tmp_path / "consumer"
    _consumer_root(project)
    result = _run(project, source_url, pin, body)
    _assert_fail_closed(project, result)
    assert required[0] in result.stdout + result.stderr


def test_drift_scan_job_fails_closed_when_silent_success_rules_are_missing(
    tmp_path: Path,
) -> None:
    workflow = "drift-scan.yml"
    step = "Bootstrap pinned DevGate"
    missing = ".guardrails/prevention-rules/silent-success-rules.json"
    body, required = BOOTSTRAPS[(workflow, step)]
    assert missing in required
    source_url, pin, _files = _make_bare_source(tmp_path, omit=missing)
    project = tmp_path / "consumer"
    _consumer_root(project)

    result = _run(project, source_url, pin, body)

    _assert_fail_closed(project, result)
    assert missing in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_assume_unchanged_required_file_drift_fails_closed(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    body, required = BOOTSTRAPS[(workflow, step)]
    project = tmp_path / "consumer"
    _consumer_root(project)
    assert _run(project, source_url, pin, body).returncode == 0

    # Git status can hide assume-unchanged files; compare the checkout's raw
    # bytes to the pinned commit blob before allowing the gate to start.
    relative = next((path for path in required if path.endswith((".py", ".sh"))), required[0])
    devgate_file = project / ".devgate" / relative
    _git(project / ".devgate", "update-index", "--assume-unchanged", "--", relative)
    devgate_file.write_text(
        devgate_file.read_text(encoding="utf-8") + "\n# harmless local comment drift\n",
        encoding="utf-8",
    )

    result = _run(project, source_url, pin, body)

    _assert_fail_closed(project, result)
    assert "required DevGate file content does not match DEVGATE_SHA" in result.stdout + result.stderr
    assert relative in result.stdout + result.stderr


@pytest.mark.parametrize("workflow,step", BOOTSTRAPS)
def test_tracked_and_dirty_dev_gate_paths_fail_closed(
    tmp_path: Path, workflow: str, step: str
) -> None:
    source_url, pin, _required = _make_bare_source(tmp_path)
    body = BOOTSTRAPS[(workflow, step)][0]
    project = tmp_path / "consumer"
    _consumer_root(project)
    tracked = project / ".devgate" / "tracked.txt"
    tracked.parent.mkdir()
    tracked.write_text("consumer data\n", encoding="utf-8")
    _git(project, "add", "-f", ".devgate/tracked.txt")
    _git(project, "commit", "--quiet", "-m", "tracked path control")
    result = _run(project, source_url, pin, body)
    _assert_fail_closed(project, result)
    assert "must not be tracked" in result.stdout + result.stderr

    dirty_project = tmp_path / "dirty-consumer"
    _consumer_root(dirty_project)
    assert _run(dirty_project, source_url, pin, body).returncode == 0
    (dirty_project / ".devgate" / "untracked-control.txt").write_text("dirty\n", encoding="utf-8")
    result = _run(dirty_project, source_url, pin, body)
    _assert_fail_closed(dirty_project, result)
    assert "is dirty" in result.stdout + result.stderr
