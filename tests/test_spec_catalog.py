"""The generated OpenSpec index catalogs every capability and change."""
from pathlib import Path

from scripts import spec_index
import spec_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_generated_catalog_lists_every_published_capability_and_requirement():
    rendered = spec_index.render(
        ROOT, ROOT / "openspec/state-ledger.jsonl",
        ROOT / "openspec/state-unproven.jsonl")
    spec_paths = sorted((ROOT / "openspec/specs").glob("*/spec.md"))

    assert "## Capability catalog" in rendered
    assert "## Supporting materials" in rendered
    assert "[project.md](project.md)" in rendered
    assert "[audits/](audits/)" in rendered
    assert "[evidence/](evidence/)" in rendered
    assert "[aiggp-source/](aiggp-source/)" in rendered
    assert "[state-ledger.jsonl](state-ledger.jsonl)" in rendered
    assert "[AIGGP-DISPOSITION-2026-10-03.md](changes/AIGGP-DISPOSITION-2026-10-03.md)" in rendered
    assert f"**{len(spec_paths)} specs**" in rendered
    for path in spec_paths:
        capability = path.parent.name
        assert f"(`{capability}`)" in rendered
        _, _, _, reqs = spec_index.read_spec(path)
        for req_id in reqs:
            assert f"[`{req_id}`](specs/{capability}/spec.md#" in rendered


def test_generated_catalog_lists_every_active_and_archived_change():
    rendered = spec_index.render(
        ROOT, ROOT / "openspec/state-ledger.jsonl",
        ROOT / "openspec/state-unproven.jsonl")
    changes = ROOT / "openspec/changes"
    active = [p for p in changes.iterdir() if p.is_dir() and p.name != "archive"]
    archived = [p for p in (changes / "archive").iterdir() if p.is_dir()]

    assert f"{len(active)} active changes are cataloged" in rendered
    assert f"{len(archived)} archived changes are cataloged" in rendered
    for path in active + archived:
        assert f"(`{path.name}`)" in rendered
        rel = path.relative_to(changes).as_posix()
        assert f"](changes/{rel}/" in rendered or f"](changes/{rel}." in rendered


def test_review_batches_have_navigable_catalog_links():
    change = ROOT / "openspec/changes/dg-02-evidence-ledger-reconciliation"
    if not change.is_dir():
        return
    rendered = spec_index.render(
        ROOT, ROOT / "openspec/state-ledger.jsonl",
        ROOT / "openspec/state-unproven.jsonl")
    for batch in sorted((change / "batches").glob("batch-*")):
        if batch.is_dir():
            assert f"changes/dg-02-evidence-ledger-reconciliation/batches/{batch.name}/" in rendered


def test_temporary_catalog_covers_legacy_deltas_batches_and_dynamic_changes(tmp_path):
    root = tmp_path
    specs = root / "openspec/specs/demo"
    specs.mkdir(parents=True)
    spec = specs / "spec.md"
    spec.write_text(
        "# Demo\n\n## Requirements\n\n"
        "### Requirement: Punctuation in a name?!\n<!-- id: demo-01 -->\n"
        "Text.\n\n### Requirement: Punctuation in a name?!\n"
        "<!-- id: demo-02 -->\nText.\n", encoding="utf-8")
    capability = ("demo", "Demo", ["demo-01", "demo-02"], "OPEN")

    active = root / "openspec/changes/legacy-without-proposal"
    (active / "specs/nested-capability").mkdir(parents=True)
    (active / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (active / "specs/flat-delta.md").write_text("# Flat delta\n", encoding="utf-8")
    (active / "specs/nested-capability/spec.md").write_text(
        "# Nested delta\n", encoding="utf-8")
    batch = active / "batches/batch-012"
    batch.mkdir(parents=True)
    (batch / "README.md").write_text("# Review batch\n", encoding="utf-8")

    archived = root / "openspec/changes/archive/2026-legacy-record"
    archived.mkdir(parents=True)
    (archived / ".openspec.yaml").write_text("schema: openspec\n", encoding="utf-8")
    empty_legacy = root / "openspec/changes/archive/empty-legacy-record"
    empty_legacy.mkdir(parents=True)

    rendered = spec_catalog.render(root, [capability])
    assert "specs/demo/spec.md#requirement-punctuation-in-a-name" in rendered
    assert "specs/demo/spec.md#requirement-punctuation-in-a-name-1" in rendered
    assert "changes/legacy-without-proposal/tasks.md" in rendered
    assert "changes/legacy-without-proposal/specs/flat-delta.md" in rendered
    assert "changes/legacy-without-proposal/specs/nested-capability/spec.md" in rendered
    assert "changes/legacy-without-proposal/batches/batch-012/README.md" in rendered
    assert "changes/archive/2026-legacy-record/.openspec.yaml" in rendered
    assert "changes/archive/empty-legacy-record/" in rendered

    added = root / "openspec/changes/new-package"
    added.mkdir()
    first = spec_catalog.render(root, [capability])
    assert "(`new-package`)" in first
    (added / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    second = spec_catalog.render(root, [capability])
    assert "changes/new-package/tasks.md" in second
    import shutil
    shutil.rmtree(added)
    third = spec_catalog.render(root, [capability])
    assert "(`new-package`)" not in third


def test_specs_only_repository_without_changes_directory_renders(tmp_path):
    (tmp_path / "openspec/specs").mkdir(parents=True)
    rendered = spec_catalog.render(tmp_path, [])
    assert "## Capability catalog" in rendered
    assert "## Active changes" in rendered
    assert "0 active changes are cataloged" in rendered
    assert "## Archived changes" in rendered
    assert "0 archived changes are cataloged" in rendered
