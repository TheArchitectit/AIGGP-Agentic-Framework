"""Execute the authored enrollment shell with inert credential fixtures."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.platform_caps import require_bash

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "fleet-app-enroll.yml"
sys_path = str(ROOT / "tests")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
import workflow_read as wr  # noqa: E402


def _workflow():
    return wr.read_workflow(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _step(name):
    steps = _workflow().jobs["enroll"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def _run_shell(script, env):
    require_bash("GitHub enrollment workflow shell blocks are bash")
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-c", str(script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _fixture_env(**extra):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("FLEET_APP_", "APP_", "EXPECTED_APP_")):
            env.pop(key, None)
    env.update(extra)
    return env


# spec: fleet-enroll-auth-01
@pytest.mark.parametrize(
    ("missing_key", "message"),
    [
        ("APP_ID", "vars.DEVGATE_SWEEP_APP_ID is missing"),
        ("APP_KEY", "secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY is missing"),
    ],
)
def test_app_pair_preflight_names_missing_half_without_values(missing_key, message):
    app_id = "fixture-app-id-42"
    app_key = "fixture-private-key-material"
    env = _fixture_env(APP_ID=app_id, APP_KEY=app_key)
    env[missing_key] = ""

    result = _run_shell(
        _step("Check the App credential pair (fail closed, named)")["run"], env
    )

    assert result.returncode == 1
    assert message in result.stdout + result.stderr
    assert app_id not in result.stdout + result.stderr
    assert app_key not in result.stdout + result.stderr


# spec: fleet-enroll-auth-01
def test_app_pair_preflight_accepts_synthetic_pair_without_logging_values():
    app_id = "fixture-app-id-43"
    app_key = "fixture-private-key-material"
    result = _run_shell(
        _step("Check the App credential pair (fail closed, named)")["run"],
        _fixture_env(APP_ID=app_id, APP_KEY=app_key),
    )

    assert result.returncode == 0
    assert app_id not in result.stdout + result.stderr
    assert app_key not in result.stdout + result.stderr


def _fake_python(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    receipt = tmp_path / "handoff.receipt"
    executable = fake_bin / "python3"
    executable.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "[ -n \"${FLEET_APP_TOKEN:-}\" ]\n"
        "[ \"$FLEET_APP_TOKEN\" = \"$EXPECTED_APP_TOKEN\" ]\n"
        "[ -n \"${FLEET_APP_PRIVATE_KEY:-}\" ]\n"
        "[ \"$FLEET_APP_PRIVATE_KEY\" = \"$EXPECTED_APP_KEY\" ]\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in *\"$FLEET_APP_TOKEN\"*) exit 31 ;; esac\n"
        "  case \"$arg\" in *\"$FLEET_APP_PRIVATE_KEY\"*) exit 32 ;; esac\n"
        "done\n"
        "# Test fixture records only verification status, never credential values.\n"
        "printf 'handoff-checked\\n' > \"$HANDOFF_RECEIPT\"\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return fake_bin, receipt


# spec: fleet-enroll-auth-01
def test_empty_minted_token_stops_before_reconciler(tmp_path):
    fake_bin, receipt = _fake_python(tmp_path)
    output_file = tmp_path / "GITHUB_OUTPUT"
    state_file = tmp_path / "GITHUB_STATE"
    report_dir = tmp_path / "runner-temp"
    report_dir.mkdir()
    output_file.touch()
    state_file.touch()
    app_key = "fixture-private-key-material"
    token = "fixture-installation-token"
    env = _fixture_env(
        PATH=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        FLEET_APP_ID="fixture-app-id-44",
        FLEET_APP_PRIVATE_KEY=app_key,
        FLEET_APP_TOKEN="",
        EXPECTED_APP_KEY=app_key,
        EXPECTED_APP_TOKEN=token,
        FLEET_OWNER="TheArchitectit",
        DRY_RUN="1",
        RUNNER_TEMP=str(report_dir),
        HANDOFF_RECEIPT=str(receipt),
        GITHUB_OUTPUT=str(output_file),
        GITHUB_STATE=str(state_file),
    )

    result = _run_shell(
        _step("Reconcile the App pair across the fleet")["run"], env
    )

    assert result.returncode == 1
    assert "installation token is missing" in result.stdout + result.stderr
    assert app_key not in result.stdout + result.stderr
    assert token not in result.stdout + result.stderr
    assert not receipt.exists()
    assert not list(report_dir.iterdir())
    assert output_file.read_bytes() == b""
    assert state_file.read_bytes() == b""


# spec: fleet-enroll-auth-02
def test_synthetic_token_reaches_reconciler_environment_only(tmp_path):
    fake_bin, receipt = _fake_python(tmp_path)
    output_file = tmp_path / "GITHUB_OUTPUT"
    state_file = tmp_path / "GITHUB_STATE"
    report_dir = tmp_path / "runner-temp"
    report_dir.mkdir()
    output_file.touch()
    state_file.touch()
    app_key = "fixture-private-key-material"
    token = "fixture-installation-token"
    env = _fixture_env(
        PATH=f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        FLEET_APP_ID="fixture-app-id-45",
        FLEET_APP_PRIVATE_KEY=app_key,
        FLEET_APP_TOKEN=token,
        EXPECTED_APP_KEY=app_key,
        EXPECTED_APP_TOKEN=token,
        FLEET_OWNER="TheArchitectit",
        DRY_RUN="1",
        RUNNER_TEMP=str(report_dir),
        HANDOFF_RECEIPT=str(receipt),
        GITHUB_OUTPUT=str(output_file),
        GITHUB_STATE=str(state_file),
    )

    result = _run_shell(
        _step("Reconcile the App pair across the fleet")["run"], env
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt.read_text(encoding="utf-8") == "handoff-checked\n"
    assert app_key not in result.stdout + result.stderr
    assert token not in result.stdout + result.stderr
    assert app_key not in receipt.read_text(encoding="utf-8")
    assert token not in receipt.read_text(encoding="utf-8")
    assert output_file.read_bytes() == b""
    assert state_file.read_bytes() == b""
    assert not list(report_dir.iterdir())


# spec: fleet-enroll-auth-01, fleet-enroll-auth-02
def test_workflow_contract_uses_pinned_app_output_directly():
    workflow = _workflow()
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    steps = workflow.jobs["enroll"]["steps"]
    by_name = {step.get("name"): step for step in steps if step.get("name")}

    assert set(workflow.triggers) == {"schedule", "workflow_dispatch"}
    assert workflow.tree["permissions"] == {"contents": "read"}
    assert "Resolve and announce the token mode" not in by_name
    assert (
        by_name["Mint the fleet App token"]["uses"]
        == "actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349"
    )
    assert "FLEET_APP_TOKEN" in by_name["Reconcile the App pair across the fleet"]["env"]
    assert (
        by_name["Reconcile the App pair across the fleet"]["env"]["FLEET_APP_TOKEN"]
        == "${{ steps.app-token.outputs.token }}"
    )
    assert "github.token" not in text
    assert "WORKFLOW_TOKEN" not in text
    assert "$GITHUB_OUTPUT" not in text
