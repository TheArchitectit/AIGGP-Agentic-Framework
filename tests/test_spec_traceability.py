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


def test_change_package_layout_is_discovered(tmp_path):
    """openspec/changes/<change>/specs/<cap>/spec.md is a standard OpenSpec
    layout; the gate used to miss it entirely and exit 2 with 'no specs found'
    (zombie-hero-match audit F5)."""
    write(tmp_path / "openspec/changes/zombie-hero-match/specs/match3-combat/spec.md", SPEC)
    write(tmp_path / "game/match.js", "// spec: router-req-01\nswap();\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_archived_changes_are_skipped(tmp_path):
    write(tmp_path / "openspec/changes/archive/2026-01-01-old/specs/old/spec.md", SPEC)
    result = run(tmp_path, "--report")
    assert result.returncode == 2
    assert "0 requirement IDs" not in result.stdout  # archived specs don't count as found
    assert "no spec files found" in result.stdout


def test_specs_without_id_markers_get_honest_diagnostic(tmp_path):
    """Heading-style specs (### R1:) exist but carry no <!-- id: --> markers:
    say exactly that, never 'no specs found'."""
    write(tmp_path / "openspec/changes/x/specs/cap/spec.md",
          "### R1: Swap validation\nThe game SHALL revert invalid swaps.\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 2
    assert "0 requirement IDs" in result.stdout
    assert "no spec files found" not in result.stdout


def test_comma_separated_marker_covers_every_id(tmp_path):
    """A single marker line may list several IDs: `// spec: a-01, b-02`.
    The regex used to capture only the first, so hub/monitor.py's five-ID
    marker silently covered one requirement and four read as UNCOVERED."""
    for name in ("alpha-req-01", "beta-req-02", "gamma-req-03"):
        write(tmp_path / f"openspec/specs/{name}/spec.md",
              SPEC.replace("router-req-01", name))
    write(tmp_path / "game/match.js",
          "// spec: alpha-req-01, beta-req-02, gamma-req-03\nswap();\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    for name in ("alpha-req-01", "beta-req-02", "gamma-req-03"):
        assert f"{name}: covered" in result.stdout
    assert "3/3 requirements covered" in result.stdout


def test_shell_script_marker_counts_as_coverage(tmp_path):
    """Shell scripts are part of the shipped gate surface (the specs
    negative control lives at scripts/specs-validate-negative-control.sh),
    so a `# // spec: <id>` marker in a .sh file must satisfy the requirement.
    Without .sh in SCAN_EXTS the marker is invisible and the requirement reads
    UNCOVERED — coverage that looks asserted in the source but isn't."""
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "scripts/check.sh", "#!/usr/bin/env bash\n# // spec: router-req-01\ntrue\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_both_layouts_merge(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "openspec/changes/ch1/specs/net/spec.md",
          SPEC.replace("router-req-01", "net-req-01"))
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01" in result.stdout and "net-req-01" in result.stdout
    assert "2/2 requirements covered" not in result.stdout  # nothing marked yet


def test_zig_marker_counts_as_coverage(tmp_path):
    """Zig source is the shipped gate surface for a Zig project, so a
    // spec: <id> marker in a .zig file must satisfy the requirement. Without
    .zig in SCAN_EXTS the marker is invisible and the requirement reads
    UNCOVERED -- coverage that looks asserted in the source but is never counted.
    Zig uses // comments, so the marker grammar already fits; only the
    extension allowlist kept it out."""
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "src/thing.zig",
          'const std = @import("std");\n'
          '// spec: router-req-01 -- enforced by route()\n'
          'pub fn route() void {}\n')
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout
