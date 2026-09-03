"""Tests for .devgate/scripts/spec_traceability.py."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "spec_traceability.py"
PYTHON = sys.executable


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPT), "--root", str(root), *args],
        capture_output=True, text=True,
    )


SPEC = """\
## ADDED Requirements
### Requirement: Router resolves config
<!-- id: router-req-01 -->
The router shall load config at startup.

#### Scenario: cold start
- **WHEN** the router starts with a valid config file
- **THEN** it binds the configured port
"""


def test_parses_requirement_ids(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01" in result.stdout


def test_marker_satisfies_requirement(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "router/src/lib.rs", "// spec: router-req-01\nfn x() {}\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_blocking_fails_on_uncovered(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    cfg = {"default_mode": "blocking", "specs": {}}
    write(tmp_path / "openspec/gate-config.json", json.dumps(cfg))
    result = run(tmp_path)
    assert result.returncode == 1
    assert "router-req-01" in result.stdout


def test_per_spec_blocking(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    cfg = {"default_mode": "advisory", "specs": {"router": "blocking"}}
    write(tmp_path / "openspec/gate-config.json", json.dumps(cfg))
    result = run(tmp_path)
    assert result.returncode == 1


def test_advisory_passes_on_uncovered(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    result = run(tmp_path)
    assert result.returncode == 0
    assert "uncovered" in result.stdout.lower()


def test_missing_spec_file_is_error(tmp_path):
    result = run(tmp_path, "--report")
    assert result.returncode == 2
