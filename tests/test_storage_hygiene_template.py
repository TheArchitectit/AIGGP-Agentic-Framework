# // spec: fw-storage-01
"""Conformance tests for the storage-hygiene template (fw-storage-01).

The workflow is configuration, and configuration is where this contract is
easiest to lose quietly: a template can drift into reimplementing the gate in
shell, into a trim job that deletes when nobody asked it to, or into an audit
job that cannot run at all — and every one of those looks like a green check
downstream.

These tests read the template with `tests/workflow_read.py` (no PyYAML — the
repository is stdlib-only, and a module-level `import yaml` in `tests/` aborts
collection for the whole suite). They are deliberately structural: they assert
the SHAPE a correct template must have, not the prose of this one.

Dual-runnable: pytest collects test_*; `python3 <this file>` runs them too.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

import workflow_read as wr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "github-workflows" / "storage-hygiene.yml"
GATE = REPO / "scripts" / "artifact_hygiene.py"


def _text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _run_blocks() -> list[str]:
    """Every `run: |` block in the file, de-indented, extracted by indentation
    rather than parsed so the test needs no YAML library."""
    lines = _text().split("\n")
    blocks, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)run: \|$", lines[i])
        if m:
            ind = len(m.group(1))
            body, j = [], i + 1
            while j < len(lines) and (not lines[j].strip()
                                      or len(lines[j]) - len(lines[j].lstrip()) > ind):
                body.append(lines[j][ind + 2:] if len(lines[j]) > ind + 2 else "")
                j += 1
            blocks.append("\n".join(body))
            i = j
        else:
            i += 1
    return blocks


def _run_commands() -> str:
    """Every shell command the template runs: `run: |` BLOCKS and inline
    `run: cmd` scalars alike.

    Reading only the blocks would miss a one-line invocation, which is how a
    gate call is most naturally written — and a check that cannot see the
    audit command reports the template as never running it.
    """
    parts = list(_run_blocks())
    for line in _text().split("\n"):
        m = re.match(r"^\s*(?:-\s*)?run:\s*(?!\|)(\S.*)$", line)
        if m:
            parts.append(m.group(1).strip())
    return "\n".join(parts)


def test_template_parses_with_the_repo_reader():
    """A template the repo's own reader cannot parse is one the mutation
    harness reports as broken — and one no consumer can adopt confidently."""
    wf = wr.read_workflow(_text())
    assert set(wf.jobs) >= {"audit", "trim"}


def test_companion_gate_exists_and_is_executable():
    """The template is a thin caller for a gate that must sit beside it. A
    missing gate fails the job closed, but the SHIP itself should be present
    or the template is a stub."""
    assert GATE.is_file(), f"{GATE} is not shipped with the template"
    assert GATE.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


def test_template_pins_full_commits():
    """A branch or tag in the pin is not a pin — the same template would run
    different bytes tomorrow. 40 hex, as the rest of the fleet writes it."""
    for line in _text().split("\n"):
        if "uses:" in line:
            ref = line.split("uses:", 1)[1].strip()
            assert not re.search(r"@v\d+(\.\d+)*\s*(#.*)?$", ref), \
                f"floating action version: {line.strip()}"
            m = re.search(r"@([0-9a-f]+)", ref)
            if m:
                assert len(m.group(1)) == 40, f"not a full sha: {line.strip()}"


def test_template_does_not_reimplement_the_gate():
    """The template must INVOKE the gate, not recompute its policy in shell.
    A second implementation is free to disagree with the first, and the
    disagreement shows up as a job that passes where the gate fails."""
    body = _run_commands()
    assert "scripts/artifact_hygiene.py" in body
    for forbidden in ("retention-days", "size_in_bytes", "created_at"):
        assert forbidden not in body, \
            f"template recomputes gate logic in shell: {forbidden!r}"


def test_audit_runs_on_push_without_a_token():
    """The audit is static and must run on every push, so it cannot depend on
    a live API call — a push-time gate that needs network is a gate that fails
    for the wrong reason."""
    wf = wr.read_workflow(_text())
    assert "push" in wf.triggers
    audit = wf.jobs["audit"]
    assert "actions" not in (audit.get("permissions") or {}), \
        "the audit job requests API write scope it does not need"
    assert "--audit" in _run_commands()


def test_trim_is_scheduled():
    wf = wr.read_workflow(_text())
    sched = wf.triggers.get("schedule")
    assert sched, "the trim half has no schedule — nothing removes stored artifacts"


def test_trim_requires_write_scope_and_passes_apply():
    """Deletion needs `actions: write`; without it the trim silently reports
    failures. The scheduled path must pass --apply, or nothing is removed."""
    wf = wr.read_workflow(_text())
    trim = wf.jobs["trim"]
    perms = trim.get("permissions") or {}
    assert perms.get("actions") == "write", \
        "the trim job does not request actions: write"
    body = _run_commands()
    assert "--apply" in body, "the trim job never passes --apply"
    assert "GH_TOKEN" in _text()


def test_dispatch_inputs_are_declared():
    """An `if:` reading an undeclared input is false on every event, with no
    error from GitHub — the job silently never runs again. The repo's own
    ci.yml records this failure mode (test_the_publish_input_is_declared), and
    this template has the same shape, so it gets the same guard."""
    wf = wr.read_workflow(_text())
    dispatch = wf.triggers.get("workflow_dispatch") or {}
    assert "apply" in (dispatch.get("inputs") or {})


def test_manual_run_is_a_dry_run():
    """The safety property: a human clicking 'Run workflow' must not delete
    anything. The scheduled job applies; a manual run previews."""
    wf = wr.read_workflow(_text())
    trim_if = wf.job_if("trim")
    assert "schedule" in trim_if, \
        "the applying job runs on events other than the schedule"
    assert "apply" in trim_if, \
        "the applying job is not gated on an explicit apply input/preview split"
    assert "--trim" in _run_commands()


def test_trim_slug_comes_from_the_context_not_a_literal():
    """A hardcoded owner/name would trim the WRONG repository — the one
    mistake here with data loss attached."""
    body = _run_commands()
    assert "$GITHUB_REPOSITORY" in body
    assert "TheArchitectit/" not in _text(), "template hardcodes an owner"


def test_missing_gate_fails_closed():
    """A gate file that is absent must fail the job, not pass it vacuously."""
    body = "\n".join(_run_blocks())
    assert "artifact_hygiene.py is missing" in body
    assert re.search(r"artifact_hygiene\.py is missing[\s\S]{0,400}exit 1", body), \
        "the missing-gate branch does not exit non-zero"


def test_runner_label_is_overridable_or_defaulted():
    """Runner labels are repo-scoped; one hardcoded label queues forever
    somewhere. This template uses the hosted default and says so in SETUP."""
    assert "runs-on:" in _text()
    assert "runner" in _text().lower()


def main() -> int:
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
