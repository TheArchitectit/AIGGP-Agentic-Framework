"""Exercise the real pi-extension carrier, not just its presence on disk."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parent.parent


def test_pi_extension_carrier_accepts_and_refuses():
    # The other four carriers already have accept+refuse tests in
    # tests/test_game_session_start.py. Pi is TypeScript, so its real adapter
    # needs an explicit pinned runtime rather than a source-text assertion.
    tsx = os.environ.get("PI_SESSION_TSX") or shutil.which("tsx")
    if not tsx:
        candidate = REPO / "node_modules" / ".bin" / "tsx"
        tsx = str(candidate) if candidate.exists() else None
    if not tsx:
        pytest.fail("pinned tsx is missing: CI installs tsx@4.23.15; pi was not tested")
    env = dict(os.environ, AIGGP_REPO_ROOT=str(REPO))
    r = subprocess.run(
        [str(tsx), str(REPO / "tests" / "fixtures" / "pi_session_carrier.ts")],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=90,
    )
    assert r.returncode == 0, f"pi carrier failed\nstdout: {r.stdout}\nstderr: {r.stderr}"
    assert "pi-extension: accept/inject and critical refusal verified" in r.stdout
