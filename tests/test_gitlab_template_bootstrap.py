"""Hermetic checks for GitLab mirror bootstrap; no live GitLab or network."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MIRRORS = REPO / "templates" / "gitlab-ci"
BOOTSTRAP_INCLUDE = MIRRORS / "includes" / "devgate-bootstrap.yml"
sys.path.insert(0, str(REPO))
from hub.forge.instance import verify_gitlab_ci_template_mirrors  # noqa: E402


REQUIRED_BY_MIRROR = {
    "bundle-size-check.gitlab-ci.yml": "scripts/bundle-size-check.mjs",
    "drift-scan.gitlab-ci.yml": (
        ".guardrails/failure-registry.jsonl "
        ".guardrails/prevention-rules/pattern-rules.json "
        ".guardrails/prevention-rules/semantic-rules.json "
        "scripts/guardrails-scan.mjs scripts/regression_check.py "
        "scripts/semantic-scan.mjs scripts/silent-success-scan.sh"
    ),
    "file-size-check.gitlab-ci.yml": "scripts/regression_check.py",
    "guardrails-compliance.gitlab-ci.yml": (
        ".guardrails/failure-registry.jsonl "
        ".guardrails/prevention-rules/pattern-rules.json "
        ".guardrails/prevention-rules/semantic-rules.json "
        "scripts/check_charset.py scripts/check_corruption.py "
        "scripts/check_encoding.py scripts/regression_check.py "
        "scripts/secret-scan.sh scripts/spec_traceability.py"
    ),
    "secret-validation.gitlab-ci.yml": "scripts/secret-scan.sh",
    "smoke-gate.gitlab-ci.yml": "scripts/game_regression.py scripts/scene_inventory.py",
    "spec-coherence.gitlab-ci.yml": "hub/coherence/__init__.py hub/coherence/__main__.py",
    "specs.gitlab-ci.yml": (
        "scripts/spec_traceability.py scripts/spec_gap_scan.py "
        "scripts/specs-validate-negative-control.sh"
    ),
    "storage-hygiene.gitlab-ci.yml": "scripts/artifact_hygiene.py",
    "text-integrity.gitlab-ci.yml": (
        "scripts/check_charset.py scripts/check_corruption.py "
        "scripts/check_encoding.py"
    ),
}


JOB_BY_MIRROR = {name: name.removesuffix(".gitlab-ci.yml") for name in REQUIRED_BY_MIRROR}


def _job_section(text: str, job_name: str) -> str:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"{job_name}:"), None)
    assert start is not None, f"job {job_name} is absent"
    end = next(
        (i for i in range(start + 1, len(lines))
         if lines[i].strip() and not lines[i].startswith((" ", "#"))),
        len(lines),
    )
    return "\n".join(lines[start + 1:end])


def _bootstrap_block() -> str:
    lines = BOOTSTRAP_INCLUDE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line == ".devgate-bootstrap:"), None)
    assert start is not None, "shared hidden bootstrap job is absent"
    item = next(
        (i for i in range(start + 1, len(lines)) if lines[i] == "    - |"),
        None,
    )
    assert item is not None, "shared before_script block is absent"
    body = []
    for line in lines[item + 1:]:
        if line.strip() and len(line) - len(line.lstrip(" ")) <= 4:
            break
        body.append(line[6:] if line.startswith("      ") else "")
    command = "\n".join(body).rstrip()
    assert command.startswith("(") and command.endswith(")")
    return command


def test_all_ten_mirrors_include_bootstrap_and_declare_their_actual_inputs() -> None:
    files = sorted(MIRRORS.glob("*.gitlab-ci.yml"))
    assert {path.name for path in files} == set(REQUIRED_BY_MIRROR)
    assert len(verify_gitlab_ci_template_mirrors(REPO)) == 10
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "  - local: '/templates/gitlab-ci/includes/devgate-bootstrap.yml'" in text
        section = _job_section(text, JOB_BY_MIRROR[path.name])
        assert "  extends: .devgate-bootstrap" in section
        required_match = re.search(r'^    DEVGATE_REQUIRED_PATHS: "([^"]+)"$', section, re.M)
        assert required_match
        declared_paths = required_match.group(1)
        assert declared_paths == REQUIRED_BY_MIRROR[path.name]
        for required in REQUIRED_BY_MIRROR[path.name].split():
            assert (REPO / required).is_file(), f"{path.name} requires absent source file {required}"
        script_start = section.find("  script:")
        assert script_start >= 0
        script = section[script_start:]
        commands = re.findall(r"^    - (.+)$", script, re.M)
        assert commands
        required_paths = set(REQUIRED_BY_MIRROR[path.name].split())
        for command in commands:
            for reference in re.findall(r"\$\{DEVGATE_DIR:-\.devgate\}/([^\" ]+)", command):
                if reference == ".guardrails":
                    assert {
                        ".guardrails/prevention-rules/pattern-rules.json",
                        ".guardrails/prevention-rules/semantic-rules.json",
                    }.issubset(required_paths)
                else:
                    assert reference in required_paths, f"{path.name} invokes undeclared input {reference}"

    for name in ("drift-scan.gitlab-ci.yml", "guardrails-compliance.gitlab-ci.yml"):
        section = _job_section((MIRRORS / name).read_text(encoding="utf-8"), JOB_BY_MIRROR[name])
        script = section[section.find("  script:"):]
        regression_commands = [line for line in re.findall(r"^    - (.+)$", script, re.M)
                               if "regression_check.py" in line]
        assert regression_commands
        assert all('--rules "${DEVGATE_DIR:-.devgate}/.guardrails"' in line
                   for line in regression_commands)
        assert all("rules.json" not in line for line in regression_commands)


def _git(cwd: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_bare_source(tmp_path: Path, omit: str | None = None) -> tuple[str, str, dict[str, str]]:
    source = tmp_path / "approved-source"
    bare = tmp_path / "approved-source.git"
    source.mkdir()
    bare.mkdir()
    _git(source, "init", "--quiet", "--initial-branch=main")
    _git(bare, "init", "--quiet", "--bare", "--initial-branch=main")
    _git(source, "config", "user.name", "Synthetic Fixture")
    _git(source, "config", "user.email", "fixture@example.invalid")
    files = {
        ".guardrails/failure-registry.jsonl": "",
        ".guardrails/prevention-rules/pattern-rules.json": "{}\n",
        ".guardrails/prevention-rules/semantic-rules.json": "{}\n",
        "scripts/guardrails-scan.mjs": "process.exit(0);\n",
        "scripts/regression_check.py": "raise SystemExit(0)\n",
        "scripts/semantic-scan.mjs": "process.exit(0);\n",
        "scripts/silent-success-scan.sh": "#!/bin/sh\nexit 0\n",
    }
    if omit is not None:
        files.pop(omit, None)
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(source, "add", "--all")
    _git(source, "commit", "--quiet", "-m", "synthetic approved DevGate source")
    pin = _git(source, "rev-parse", "HEAD")
    _git(source, "push", "--quiet", str(bare), "HEAD:main")
    return bare.as_uri(), pin, files


def _consumer_root(path: Path) -> None:
    path.mkdir()
    _git(path, "init", "--quiet", "--initial-branch=main")
    _git(path, "config", "user.name", "Synthetic Consumer")
    _git(path, "config", "user.email", "consumer@example.invalid")
    (path / ".gitignore").write_text(".devgate/\n", encoding="utf-8")
    _git(path, "add", ".gitignore")
    _git(path, "commit", "--quiet", "-m", "synthetic consumer")
    assert not (path / ".gitmodules").exists()


def _run_bootstrap(
    project: Path,
    source_url: str,
    pin: str,
    required: str,
    devgate_dir: str | None = None,
    git_token: str | None = None,
    temp_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(project),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "CI_PROJECT_DIR": str(project),
        "DEVGATE_SOURCE_URL": source_url,
        "DEVGATE_SHA": pin,
        "DEVGATE_REQUIRED_PATHS": required,
        "GIT_TERMINAL_PROMPT": "synthetic-parent-value",
        "GIT_ASKPASS": "synthetic-parent-askpass",
    }
    if temp_dir is not None:
        env["TMPDIR"] = str(temp_dir)
    if devgate_dir is not None:
        env["DEVGATE_DIR"] = devgate_dir
    if git_token is not None:
        env["DEVGATE_GIT_TOKEN"] = git_token
    if sys.platform == "win32":
        pytest.skip(
            "GitLab bootstrap integration exercises Linux Bash semantics; "
            "Windows bash.exe may be only a WSL shim"
        )
    from tests.platform_caps import require_bash

    require_bash("GitLab bootstrap behavior executes a shell block")
    block = _bootstrap_block()
    wrapped = "set +e; set +u; set +f; before_options=$(set +o); before_prompt=${GIT_TERMINAL_PROMPT:-}; before_askpass=${GIT_ASKPASS:-};\n" + block + "\nbootstrap_status=$?; after_options=$(set +o); [ \"$before_options\" = \"$after_options\" ] || exit 91; [ \"$before_prompt\" = \"${GIT_TERMINAL_PROMPT:-}\" ] || exit 92; [ \"$before_askpass\" = \"${GIT_ASKPASS:-}\" ] || exit 93; exit \"$bootstrap_status\""
    return subprocess.run(
        ["bash", "-c", wrapped],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _gate_marker_if_preflight_passes(project: Path, result: subprocess.CompletedProcess[str]) -> None:
    """Model GitLab's before_script boundary: a failed setup never runs script."""
    if result.returncode == 0:
        (project / "gate.green").write_text("gate ran\n", encoding="utf-8")


def test_valid_pin_bootstraps_exact_ignored_checkout_before_the_gate(tmp_path: Path) -> None:
    source_url, pin, files = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)

    result = _run_bootstrap(project, source_url, pin, REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"])
    _gate_marker_if_preflight_passes(project, result)

    assert result.returncode == 0, result.stderr
    assert not (project / ".gitmodules").exists()
    assert (project / "gate.green").is_file()
    assert _git(project / ".devgate", "rev-parse", "HEAD") == pin
    assert _git(project / ".devgate", "rev-parse", "--show-toplevel") == str(project / ".devgate")
    assert _git(project, "check-ignore", "--quiet", "--no-index", ".devgate/") == ""
    for relative in files:
        assert (project / ".devgate" / relative).is_file()


def test_malformed_pin_fails_before_creating_checkout_or_running_gate(tmp_path: Path) -> None:
    source_url, pin, _ = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)

    result = _run_bootstrap(project, source_url, "not-a-full-sha", REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"])
    _gate_marker_if_preflight_passes(project, result)

    assert result.returncode != 0
    assert "full lowercase commit SHA" in result.stderr
    assert not (project / ".devgate").exists()
    assert not (project / "gate.green").exists()


def test_failed_fetch_leaves_a_partial_root_that_is_rejected_on_retry(tmp_path: Path) -> None:
    source_url, pin, _ = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    missing_source = (tmp_path / "missing.git").as_uri()
    synthetic_token = "synthetic-test-only-not-a-token"

    first = _run_bootstrap(
        project,
        missing_source,
        pin,
        REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"],
        git_token=synthetic_token,
        temp_dir=tmp_path,
    )
    _gate_marker_if_preflight_passes(project, first)
    retry = _run_bootstrap(project, source_url, pin, REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"])
    _gate_marker_if_preflight_passes(project, retry)

    assert first.returncode != 0
    assert retry.returncode != 0
    assert "no checked-out commit" in retry.stderr
    assert not (project / "gate.green").exists()
    assert "missing.git" not in first.stderr
    assert synthetic_token not in first.stdout + first.stderr
    assert not list(tmp_path.glob("devgate-askpass.*"))


@pytest.mark.parametrize(
    "missing_path",
    [
        "scripts/guardrails-scan.mjs",
        ".guardrails/prevention-rules/pattern-rules.json",
        ".guardrails/prevention-rules/semantic-rules.json",
    ],
)
def test_missing_required_script_or_rule_file_fails_before_gate(
    tmp_path: Path, missing_path: str
) -> None:
    source_url, pin, _ = _make_bare_source(tmp_path, omit=missing_path)
    project = tmp_path / "consumer"
    _consumer_root(project)

    result = _run_bootstrap(project, source_url, pin, REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"])
    _gate_marker_if_preflight_passes(project, result)

    assert result.returncode != 0
    assert "required DevGate file is missing" in result.stderr
    assert not (project / "gate.green").exists()


def test_wrong_dev_gate_root_is_rejected_before_fetch(tmp_path: Path) -> None:
    source_url, pin, _ = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)

    result = _run_bootstrap(
        project,
        source_url,
        pin,
        REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"],
        devgate_dir="vendor/.devgate",
    )
    _gate_marker_if_preflight_passes(project, result)

    assert result.returncode != 0
    assert "root must be .devgate" in result.stderr
    assert not (project / ".devgate").exists()
    assert not (project / "gate.green").exists()


def test_tracked_devgate_path_is_rejected_without_modifying_consumer_files(tmp_path: Path) -> None:
    source_url, pin, _ = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    tracked_file = project / ".devgate" / "existing.txt"
    tracked_file.parent.mkdir()
    tracked_file.write_text("consumer-owned tracked data\n", encoding="utf-8")
    _git(project, "add", "-f", ".devgate/existing.txt")
    _git(project, "commit", "--quiet", "-m", "tracked DevGate path control")

    result = _run_bootstrap(project, source_url, pin, REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"])
    _gate_marker_if_preflight_passes(project, result)

    assert result.returncode != 0
    assert "must not be tracked" in result.stderr
    assert tracked_file.read_text(encoding="utf-8") == "consumer-owned tracked data\n"
    assert not (project / "gate.green").exists()


def test_dirty_or_untracked_reused_checkout_is_rejected_without_repair(tmp_path: Path) -> None:
    source_url, pin, files = _make_bare_source(tmp_path)
    project = tmp_path / "consumer"
    _consumer_root(project)
    required = REQUIRED_BY_MIRROR["drift-scan.gitlab-ci.yml"]

    clean = _run_bootstrap(project, source_url, pin, required)
    _gate_marker_if_preflight_passes(project, clean)
    assert clean.returncode == 0, clean.stderr
    (project / "gate.green").unlink()

    tracked_file = project / ".devgate" / "scripts" / "guardrails-scan.mjs"
    dirty_contents = "synthetic dirty reuse control\n"
    tracked_file.write_text(dirty_contents, encoding="utf-8")
    dirty = _run_bootstrap(project, source_url, pin, required)
    _gate_marker_if_preflight_passes(project, dirty)
    assert dirty.returncode != 0
    assert "worktree is not clean" in dirty.stderr
    assert tracked_file.read_text(encoding="utf-8") == dirty_contents
    assert not (project / "gate.green").exists()

    tracked_file.write_text(files["scripts/guardrails-scan.mjs"], encoding="utf-8")
    untracked = project / ".devgate" / "scripts" / "untracked-required.sh"
    untracked.write_text("exit 0\n", encoding="utf-8")
    required += " scripts/untracked-required.sh"
    untracked_result = _run_bootstrap(project, source_url, pin, required)
    _gate_marker_if_preflight_passes(project, untracked_result)
    assert untracked_result.returncode != 0
    assert "worktree is not clean" in untracked_result.stderr
    assert untracked.read_text(encoding="utf-8") == "exit 0\n"
    assert not (project / "gate.green").exists()
