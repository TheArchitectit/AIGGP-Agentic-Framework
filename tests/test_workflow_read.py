"""Guards for the workflow reader the publish-trigger checks rest on.

`tests/workflow_read.py` reads `.github/workflows/*.yml` structurally, without
PyYAML. That is not a stylistic preference: the hosted lane installs only pytest
(`.github/workflows/ci.yml`, "Install pytest"), so a module-level `import yaml`
anywhere in `tests/` aborts collection and takes the whole suite down with it —
which is exactly what happened on the first push of this guard, and what
`add-secret-scanning` tasks 6.3 already records as a failure mode ("a test-only
dependency that takes the whole suite down when it is missing"). The repository
owns no PyYAML dependency at all; `parse_workflow` in
`test_secret_validation_template.py` reads the same file the same way for the
same reason.

Replacing a real parser with a narrow reader is only safe if the narrow reader
is exercised, so the reader is pinned here rather than inferred from the guard
that uses it. Two properties matter, and they are different:

  * it READS what this repository actually writes — a reader that choked on the
    live ci.yml would report the publish guard as unable to run, and a reader
    that quietly returned an empty tree would make every assertion about a
    missing job look satisfied by a missing job;
  * it REJECTS what it cannot follow — the same reader backs the mutation
    harness's "did this mutation break the file" check, and a reader that
    accepted anything would report a YAML mutation that breaks parsing as a
    mutation a test killed.

Deliberately carries no `// spec:` marker: no requirement in `openspec/specs/`
is about reading workflows, and marking this against a change-package id that is
not published yet would manufacture the coverage the marker is meant to measure.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_read as wr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"

# The shapes the reader has to survive, written the way this repository writes
# them: two-space indents, a step list, `with:` scalars, an inline flow sequence,
# and a block scalar whose body is shell that looks like YAML.
SAMPLE = """
name: CI
on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      publish:
        description: "Build and push the evaluator image to GHCR"
        type: boolean
        default: false

jobs:
  container-publish:
    name: Publish evaluator image to GHCR (S4)
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch' && inputs.publish
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
        if: always()
        with:
          fetch-depth: 0
      - name: Something
        run: |
          echo "if: not a job condition"
          # a comment inside a block scalar
          for b in a b; do
            echo "$b"
          done
"""


def _sample():
    return wr.read_workflow(SAMPLE)


# --- it reads what the repository writes ------------------------------------

def test_the_reader_reads_the_live_workflow():
    """Non-vacuity: every other guard here uses a sample, so if the reader
    cannot read the real file the guard on the real file is untested."""
    text = CI.read_text(encoding="utf-8")
    assert wr.read_workflow(text).job_if("container-publish")


def test_the_live_workflow_still_declares_the_things_the_guard_names():
    text = CI.read_text(encoding="utf-8")
    wf = wr.read_workflow(text)
    assert wf.dispatch_input("publish")["type"] == "boolean"
    assert "workflow_dispatch" in wf.triggers


def test_a_job_condition_is_the_jobs_own_not_a_steps():
    """`if:` appears at three indents in this file — job, step, and inside block
    scalars. Only one of them is the condition that decides whether the publish
    job runs, and reading a step's would make the guard pass on the wrong
    string."""
    assert _sample().job_if("container-publish") == \
        "github.event_name == 'workflow_dispatch' && inputs.publish"


def test_the_reader_reads_the_dispatch_input_and_its_fields():
    spec = _sample().dispatch_input("publish")
    assert spec["type"] == "boolean"
    assert spec["default"] == "false"
    assert "GHCR" in spec["description"]


def test_the_key_on_is_not_coerced_to_a_boolean():
    """A YAML 1.1 parser reads a bare `on:` as the boolean True, which is why
    the fixtures that used one had to accept both spellings. This reader works
    from the file's text and has no such opinion, so the key is `on` — and this
    guard is what says so, rather than a comment claiming it."""
    assert "on" in _sample().tree
    assert True not in _sample().tree


def test_an_inline_flow_sequence_on_one_line_is_readable():
    assert _sample().triggers["push"]["branches"] == "[main]"


def test_a_trailing_comment_is_not_part_of_the_value():
    """Every action reference in this repository is written `uses: x@sha # v5`.
    A reader that kept the comment would compare a value nothing else matches."""
    wf = wr.read_workflow(SAMPLE)
    assert wf.jobs["container-publish"]["steps"][0]["uses"] == \
        "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"


def test_a_hash_inside_quotes_is_kept():
    wf = wr.read_workflow('jobs:\n  j:\n    if: a == "#b"\n')
    assert wf.job_if("j") == 'a == "#b"'
    assert _sample().dispatch_input("publish")["description"] == \
        "Build and push the evaluator image to GHCR"


def test_a_block_scalar_body_is_not_parsed_as_structure():
    """The body below `run: |` is shell. Parsing it as YAML would invent jobs
    and conditions that no runner would ever evaluate."""
    wf = _sample()
    body = wf.jobs["container-publish"]["steps"][1]["run"]
    assert "not a job condition" in body
    assert wf.jobs["container-publish"]["steps"][1]["name"] == "Something"


# --- it rejects what it cannot follow ---------------------------------------

def test_an_absent_job_raises_rather_than_returning_nothing():
    """The failure this file exists to distinguish: a guard reading a missing
    condition as an empty string would evaluate `''` as false and report that
    the publish job is delightfully deliberate."""
    with pytest.raises(wr.WorkflowReadError, match="container-publish"):
        _sample().job_if("container-publish-renamed")


def test_a_job_with_no_condition_raises():
    with pytest.raises(wr.WorkflowReadError, match="no `if:`"):
        wr.read_workflow("jobs:\n  j:\n    runs-on: ubuntu-latest\n").job_if("j")


def test_an_absent_input_raises():
    with pytest.raises(wr.WorkflowReadError, match="publish"):
        wr.read_workflow("on:\n  workflow_dispatch:\n").dispatch_input("publish")


def test_tab_indentation_is_refused():
    """Tabs are not indentation in YAML. Accepting them would let the reader
    invent a nesting that no parser agrees with."""
    with pytest.raises(wr.WorkflowReadError, match="tab"):
        wr.read_workflow("jobs:\n\ta:\n")


def test_an_unbalanced_flow_bracket_is_refused():
    """This is the shape the mutation harness's well-formedness check is asked
    about, and the one that must not read as "still parses"."""
    with pytest.raises(wr.WorkflowReadError, match="flow"):
        wr.read_workflow("jobs:\n  a: [\n")


def test_a_line_that_is_not_a_key_or_an_item_is_refused():
    with pytest.raises(wr.WorkflowReadError):
        wr.read_workflow("jobs:\n  a: 1\n  not a key at all\n")


def test_a_block_scalar_as_a_condition_is_refused_not_folded():
    """A folded condition is a different string from the one written, and this
    reader does not fold. Refusing is the honest answer; folding would hand the
    guard a condition the file does not contain."""
    with pytest.raises(wr.WorkflowReadError, match="block scalar"):
        wr.read_workflow("jobs:\n  j:\n    if: |\n      a && b\n").job_if("j")


# --- the two consumers agree ------------------------------------------------

def test_the_harness_and_the_guard_read_the_same_file_the_same_way(tmp_path):
    """`mutation_harness.well_formed` calls this reader to decide whether a
    mutation left the workflow readable. If the two disagreed about what
    "readable" means, a mutation could be judged INVALID by the harness while
    the guard happily read it — or the reverse, which reads as a killed
    mutation."""
    import mutation_harness as h

    good = tmp_path / "good.yml"
    good.write_text(CI.read_text(encoding="utf-8"), encoding="utf-8")
    assert h.well_formed(good) is True

    bad = tmp_path / "bad.yml"
    bad.write_text("jobs:\n  a: [\n", encoding="utf-8")
    assert h.well_formed(bad) is False
