"""YAML source markers are limited to owned workflow comment preambles."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TRACE = ROOT / "scripts" / "spec_traceability.py"
GAP = ROOT / "scripts" / "spec_gap_scan.py"
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import spec_discovery  # noqa: E402


def write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def marker(rid: str) -> str:
    # Build the source annotation in pieces so this test fixture cannot itself
    # satisfy the repository's legacy Python source-marker scan.
    return "# " + "spec: " + rid


def add_requirements(root: Path, ids: list[str]) -> None:
    blocks = [
        f"### Requirement: marker {rid}\n<!-- id: {rid} -->\n"
        "The requirement SHALL be covered.\n\n"
        "#### Scenario: marker source\n- **WHEN** scanned\n- **THEN** coverage is reported\n"
        for rid in ids
    ]
    write(root, "openspec/specs/workflow/spec.md",
          "# Workflow source markers\n\n## ADDED Requirements\n\n" + "\n".join(blocks))


def run_trace(root: Path) -> tuple[set[str], set[str]]:
    result = subprocess.run(
        [sys.executable, str(TRACE), "--root", str(root), "--report"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    covered = set()
    uncovered = set()
    for rid, state in re.findall(
            r"^([A-Za-z0-9-]+): (covered|UNCOVERED)", result.stdout, re.M):
        (covered if state == "covered" else uncovered).add(rid)
    return covered, uncovered


def run_gap(root: Path, all_ids: set[str]) -> tuple[set[str], set[str]]:
    result = subprocess.run(
        [sys.executable, str(GAP), "--root", str(root), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    uncovered = {row["id"] for row in report["coverage"]["uncovered_ids"]}
    requirement_ids = report["coverage"]["requirement_ids"]
    assert requirement_ids == len(all_ids)
    return all_ids - uncovered, uncovered


def test_yaml_preamble_is_shared_and_scalar_decoys_are_not_coverage(tmp_path):
    ids = [
        "glf-template-bootstrap-01", "owned-github-01", "owned-template-github-01",
        "literal-decoy-01", "folded-decoy-01", "quoted-decoy-01",
        "root-scalar-decoy-01", "nested-decoy-01", "after-content-decoy-01",
        "malformed-suffix-decoy-01",
        "unicode-separator-decoy-01", "nbsp-content-decoy-01",
    ]
    add_requirements(tmp_path, ids)
    write(tmp_path, "src/autoload/economy_manager.gd",
          "extends Node\nvar coins = 0\nfunc add_coins(n): coins += n\n")

    # This is the real source marker/path present at the reviewed revision.
    write(tmp_path, "templates/gitlab-ci/includes/devgate-bootstrap.yml",
          marker("glf-template-bootstrap-01") + "\n.job:\n  script: echo bootstrap\n")
    write(tmp_path, ".github/workflows/build.yml",
          marker("owned-github-01") + "\nname: Build\njobs: {}\n")
    write(tmp_path, "templates/github-workflows/reusable.yaml",
          marker("owned-template-github-01") + "\nname: Reusable\njobs: {}\n")

    write(tmp_path, "templates/gitlab-ci/scalars.yml", f'''\
{marker("malformed-suffix-decoy-01")}_suffix
literal: |
  {marker("literal-decoy-01")}
folded: >
  {marker("folded-decoy-01")}
quoted: "{marker("quoted-decoy-01")}"
nested:
  value: |
    {marker("nested-decoy-01")}
''')
    # A valid root double-quoted scalar with a marker-shaped content line.
    write(tmp_path, "templates/gitlab-ci/root-scalar.yml",
          '"first line\n' + marker("root-scalar-decoy-01") + '\nlast line"\n')
    write(tmp_path, "templates/gitlab-ci/after-content.yml",
          "name: Content starts here\n" + marker("after-content-decoy-01") + "\njobs: {}\n")
    write(tmp_path, "templates/gitlab-ci/unicode-separator.yml",
          "# one YAML comment\u2028" + marker("unicode-separator-decoy-01") + "\nname: Check\n")
    write(tmp_path, "templates/gitlab-ci/nbsp-content.yml",
          "\u00a0\n" + marker("nbsp-content-decoy-01") + "\nname: Check\n")

    trace_covered, trace_uncovered = run_trace(tmp_path)
    gap_covered, gap_uncovered = run_gap(tmp_path, set(ids))
    expected_covered = {
        "glf-template-bootstrap-01", "owned-github-01", "owned-template-github-01",
    }
    expected_uncovered = set(ids) - expected_covered
    assert trace_covered == expected_covered
    assert trace_uncovered == expected_uncovered
    assert gap_covered == expected_covered
    assert gap_uncovered == expected_uncovered
    assert trace_covered == set(ids) - gap_uncovered


def test_yaml_markers_outside_owned_workflow_roots_are_ignored(tmp_path):
    ids = ["example-decoy-01", "fixture-decoy-01", "docs-decoy-01",
           "generated-decoy-01", "archive-decoy-01", "nested-fixture-decoy-01"]
    add_requirements(tmp_path, ids)
    write(tmp_path, "src/autoload/economy_manager.gd", "extends Node\nvar coins = 0\n")
    for path, rid in zip(("examples/example.yml", "tests/fixtures/fixture.yaml",
                          "docs/workflow.yml", "generated/output.yml",
                          "archive/old-workflow.yml",
                          "templates/gitlab-ci/fixtures/decoy.yml"), ids):
        write(tmp_path, path, marker(rid) + "\nname: decoy\n")

    trace_covered, trace_uncovered = run_trace(tmp_path)
    gap_covered, gap_uncovered = run_gap(tmp_path, set(ids))
    assert trace_covered == set()
    assert trace_uncovered == set(ids)
    assert gap_covered == set()
    assert gap_uncovered == set(ids)


def test_symlinked_yaml_is_ignored(tmp_path):
    rid = "symlink-decoy-01"
    add_requirements(tmp_path, [rid])
    write(tmp_path, "src/autoload/economy_manager.gd", "extends Node\nvar coins = 0\n")
    target = write(tmp_path, "outside/target.yml", marker(rid) + "\nname: target\n")
    link = tmp_path / "templates" / "gitlab-ci" / "linked.yml"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    trace_covered, trace_uncovered = run_trace(tmp_path)
    gap_covered, gap_uncovered = run_gap(tmp_path, {rid})
    assert trace_covered == set()
    assert trace_uncovered == {rid}
    assert gap_covered == set()
    assert gap_uncovered == {rid}


def test_non_yaml_source_marker_behavior_is_unchanged(tmp_path):
    rid = "python-source-01"
    add_requirements(tmp_path, [rid])
    write(tmp_path, "src/autoload/economy_manager.gd", "extends Node\nvar coins = 0\n")
    write(tmp_path, "src/loader.py", marker(rid) + "\n")
    trace_covered, trace_uncovered = run_trace(tmp_path)
    gap_covered, gap_uncovered = run_gap(tmp_path, {rid})
    assert trace_covered == {rid}
    assert trace_uncovered == set()
    assert gap_covered == {rid}
    assert gap_uncovered == set()


def test_actual_gitlab_yaml_markers_and_scanner_trace_exist(tmp_path):
    source_roots = [ROOT / ".github" / "workflows",
                    ROOT / "templates" / "github-workflows",
                    ROOT / "templates" / "gitlab-ci"]
    eligible = [path for source_root in source_roots for path in source_root.rglob("*")
                if path.is_file() and spec_discovery._is_owned_yaml_source(ROOT, path)]
    marker_lines = sum(
        len(spec_discovery._yaml_preamble_markers(path.read_text(encoding="utf-8")))
        for path in eligible
    )
    actual_root = tmp_path / "actual-source-sample"
    scanner_source = ROOT / "scripts" / "lib" / "spec_discovery.py"
    scanner_copy = actual_root / "scripts" / "lib" / "spec_discovery.py"
    scanner_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(scanner_source, scanner_copy)
    for path in eligible:
        destination = actual_root / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    markers = spec_discovery.collect_markers(actual_root)
    assert marker_lines >= 11
    assert {"GLF-01", "glf-template-bootstrap-01"} <= markers
    assert "spec-fmt-06" in markers
