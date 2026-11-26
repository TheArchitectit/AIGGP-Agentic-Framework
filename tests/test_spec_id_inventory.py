"""Behavioral controls for requirement identity inventory validation."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/spec_id_inventory.py"
spec = importlib.util.spec_from_file_location("spec_id_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def write_spec(root: Path, blocks: str) -> None:
    path = root / "openspec/specs/demo/spec.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# demo\n## Requirements\n" + blocks, encoding="utf-8")


def check(root: Path, cli_names: list[str]) -> list[str]:
    local, errors = inventory.canonical_inventory(root)
    return inventory.validate(local, {"demo": cli_names}, errors)


def test_inventory_matches_cli_and_has_unique_ids(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n"
               "### Requirement: second\n<!-- id: demo-02 -->\n")
    assert check(tmp_path, ["first", "second"]) == []


def test_missing_id_fails_with_heading(tmp_path):
    write_spec(tmp_path, "### Requirement: first\nNo ID\n")
    errors = check(tmp_path, ["first"])
    assert any("demo: first" in error and "missing ID marker" in error for error in errors)


def test_malformed_placeholder_fails_with_heading(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: ... -->\n")
    errors = check(tmp_path, ["first"])
    assert any("demo: first" in error and "malformed" in error for error in errors)


def test_duplicate_id_fails_with_both_headings(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n"
               "### Requirement: second\n<!-- id: demo-01 -->\n")
    errors = check(tmp_path, ["first", "second"])
    assert any("duplicate ID 'demo-01'" in error and "demo: first" in error for error in errors)


def test_extra_id_fails_with_inventory_mismatch(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n<!-- id: stray-01 -->\n")
    errors = check(tmp_path, ["first"])
    assert any(error == "demo: extra ID marker outside a requirement heading" for error in errors)


def test_second_marker_is_reported_as_extra(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n<!-- id: stray-01 -->\n")
    errors = check(tmp_path, ["first"])
    assert any("extra ID marker outside a requirement heading" in error for error in errors)


def test_misplaced_marker_does_not_satisfy_heading(tmp_path):
    write_spec(tmp_path, "### Requirement: first\nProse before the marker.\n<!-- id: demo-01 -->\n")
    errors = check(tmp_path, ["first"])
    assert any("immediately below" in error for error in errors)
    assert any("extra ID marker" in error for error in errors)


def test_fenced_literal_id_example_is_ignored(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n"
               "```markdown\n<!-- id: ... -->\n```\n")
    assert check(tmp_path, ["first"]) == []


def test_valid_fenced_marker_disagrees_with_shared_parser(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n"
               "```markdown\n<!-- id: example-01 -->\n```\n")
    errors = check(tmp_path, ["first"])
    assert any("shared parser IDs ['demo-01', 'example-01']" in error for error in errors)


def test_unclosed_marker_is_reported_as_malformed(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01\n")
    errors = check(tmp_path, ["first"])
    assert any("unclosed ID marker" in error for error in errors)


def test_unclosed_standalone_marker_outside_requirement_fails(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n\n<!-- id: stray-01\n")
    errors = check(tmp_path, ["first"])
    assert any("unclosed extra ID marker" in error for error in errors)


def test_draft_requirement_is_excluded_from_shared_comparison(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n"
               "<!-- draft: unreviewed -->\nDraft text.\n")
    assert check(tmp_path, ["first"]) == []


def test_cli_heading_mismatch_fails_with_capability(tmp_path):
    write_spec(tmp_path, "### Requirement: first\n<!-- id: demo-01 -->\n")
    errors = check(tmp_path, ["different"])
    assert any("demo: CLI headings" in error for error in errors)
