# // spec: base-specs-01, rule-marker-01, spec-fmt-01, spec-fmt-02, spec-fmt-03
"""Tests for .devgate/scripts/spec_traceability.py."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "spec_traceability.py"
PYTHON = sys.executable


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPT), "--root", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
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


def test_tsx_marker_counts_as_coverage(tmp_path):
    """TSX components are the shipped enforcement surface for UI flows, so a
    // spec: <id> marker in a .tsx file must satisfy the requirement. Without
    .tsx in SCAN_EXTS the marker is invisible and the requirement reads
    UNCOVERED -- coverage that looks asserted in the source but is never counted.
    TSX uses // comments, so the marker grammar already fits; only the
    extension allowlist kept it out."""
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "src/Router.tsx",
          'export function Router() {\n'
          '  // spec: router-req-01 -- enforced by the route switch\n'
          '  return null;\n'
          '}\n')
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_hash_marker_covers_python_requirement(tmp_path):
    """H6 fix: `# spec: <id>` must count for Python/Ruby/shell sources. The
    `//`-only grammar meant a Python consumer in blocking mode could never
    reach coverage no matter how the code was annotated."""
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "router/src/loader.py",
          "# spec: router-req-01\ndef load():\n    return True\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_uppercase_ids_are_discovered_and_covered(tmp_path):
    """`add-gitlab-forge-support` writes `<!-- id: GLF-01 -->` and covers it
    with `// spec: GLF-01`. The ID classes were lowercase-only, so all seven
    of that change package's requirements were discovered as NOTHING: the
    repo's gate reported 187 requirements where the tree holds 194, and the
    seven covered ones were invisible to the ratchet — coverage that the code
    asserts but the gate can never count. Same defect class as the zig/tsx/
    .sh markers above: a marker the discovery cannot read is uncovered
    forever (or, worse here, not required at all)."""
    write(tmp_path / "openspec/changes/add-gitlab-forge-support/specs/forge-parity/spec.md",
          SPEC.replace("router-req-01", "GLF-01"))
    write(tmp_path / "hub/forge/__init__.py",
          "# // spec: GLF-01, GLF-02\n")
    write(tmp_path / "openspec/changes/add-gitlab-forge-support/specs/forge-parity/spec2.md",
          SPEC.replace("router-req-01", "GLF-02"))
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "GLF-01: covered" in result.stdout, result.stdout
    assert "GLF-02: covered" in result.stdout, result.stdout
    assert "2/2 requirements covered" in result.stdout, result.stdout


def test_case_sensitive_ids_stay_distinct(tmp_path):
    """Accepting both cases must not silently merge two IDs that differ only
    by case: comparison is exact, so a marker must spell the ID its spec
    does. Otherwise one marker would cover two requirements and the count
    would overstate coverage."""
    write(tmp_path / "openspec/specs/a/spec.md", SPEC.replace("router-req-01", "req-01"))
    write(tmp_path / "openspec/specs/b/spec.md", SPEC.replace("router-req-01", "REQ-01"))
    write(tmp_path / "src/a.rs", "// spec: req-01\n")
    result = run(tmp_path, "--report")
    assert "req-01: covered" in result.stdout, result.stdout
    assert "REQ-01: UNCOVERED" in result.stdout, result.stdout
    assert "1/2 requirements covered" in result.stdout, result.stdout


def test_module_constants_are_defined_exactly_once():
    """F2 disposition (2026-09-26): 8c7556d shipped spec_traceability.py with
    SCAN_EXTS/SCAN_SKIP/ID defined twice (the second block silently shadowing
    the first) — a duplicated constant that must be kept in sync is exactly the
    latent-bug class the author flagged and left "to keep the change
    reviewable". Collapsed to one block here. The pin is source-shape, not
    behavior: any constant redefined later in the module fails this test,
    because a shadowed definition makes an edit to the first copy a silent
    no-op — the same dead-code-lies-green shape as a gate that scans nothing.

    SGA-05 moved the constants to scripts/lib/spec_discovery.py (shared with
    the gap scanner); the pin follows them, and spec_traceability.py itself
    must hold none — a definition anywhere else re-creates the drift class."""
    lib = SCRIPT.parent / "lib" / "spec_discovery.py"
    for path, expected in ((lib, 1), (SCRIPT, 0)):
        src = path.read_text(encoding="utf-8")
        for name in ("SCAN_EXTS", "SCAN_SKIP", "ID"):
            assignments = [ln for ln in src.splitlines()
                           if ln.startswith(f"{name} = ")]
            assert len(assignments) == expected, (
                f"{name} is defined {len(assignments)} times in "
                f"{path.name} (expected {expected}): {assignments} — a second "
                "definition silently shadows the first, making an edit to "
                "either copy a silent no-op")


def test_hash_marker_blocks_clean_when_present(tmp_path):
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "openspec/gate-config.json",
          json.dumps({"default_mode": "blocking", "specs": {}}))
    write(tmp_path / "router/src/loader.py", "# spec: router-req-01\n")
    result = run(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "1/1 requirements covered" in result.stdout


def test_hash_marker_multiple_ids(tmp_path):
    for name in ("alpha-req-01", "beta-req-02"):
        write(tmp_path / f"openspec/specs/{name}/spec.md",
              SPEC.replace("router-req-01", name))
    write(tmp_path / "lib/run.py", "# spec: alpha-req-01, beta-req-02\n")
    result = run(tmp_path, "--report")
    assert "alpha-req-01: covered" in result.stdout
    assert "beta-req-02: covered" in result.stdout


def test_dash_marker_covers_sql_or_lua_requirement(tmp_path):
    """rule-marker-01: `-- spec: <id>` comment syntax counts as coverage."""
    write(tmp_path / "openspec/specs/router/spec.md", SPEC)
    write(tmp_path / "db/schema.sql", "-- spec: router-req-01\nCREATE TABLE t (id INT);\n")
    result = run(tmp_path, "--report")
    assert result.returncode == 0
    assert "router-req-01: covered" in result.stdout


def test_bundled_specs_have_traceable_ids_and_no_external_game_framework_pointer():
    """base-specs-01, spec-fmt-01..03: bundled specs have requirement IDs (no 0/0
    capabilities), active changes have proposal.md + tasks.md, AGENTS.md
    documents change-local authority, and no bundled doc directs readers to a
    separate devgate-game-framework repository."""
    repo = SCRIPT.parent.parent
    result = run(repo, "--report")
    assert result.returncode == 0, result.stdout
    assert "(0/0)" not in result.stdout, result.stdout
    readme = (repo / "scripts" / "game-framework-README.md").read_text(encoding="utf-8")
    assert "submodule add" not in readme or "devgate-game-framework" not in readme
    agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "openspec/changes" in agents and "archive" in agents
    changes_dir = repo / "openspec" / "changes"
    if changes_dir.is_dir():
        for ch in sorted(changes_dir.iterdir()):
            if not ch.is_dir() or ch.name == "archive":
                continue
            assert (ch / "proposal.md").is_file(), f"{ch.name} missing proposal.md"
            assert (ch / "tasks.md").is_file(), f"{ch.name} missing tasks.md"

