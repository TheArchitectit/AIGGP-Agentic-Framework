"""Guards for the mutation harness the batteries run on.

Deliberately carries no `// spec:` marker. The convention means "this file
covers that requirement", and no requirement in `openspec/specs/` is about
mutation testing — marking it against a change-package id that is not published
yet would manufacture coverage, which is the thing the marker is supposed to
measure.

The three `mutation_battery_*.py` files each decide whether a guard is
load-bearing: mutate, run a named test, report killed or survived. Each carried
its own private copy of the machinery that reads that verdict — three places
for the same answer to be wrong, and no place that noticed if it were.

Consolidating them into `tests/mutation_harness.py` removes the copies and adds
exactly one place to be wrong — so the verdict logic is pinned here instead of
inferred from the batteries passing. A harness that read a mutant's SyntaxError
as "a test caught it", or a stale anchor as a kill, would turn every battery
green while proving nothing. `scripts/mutation_check.py` carries the same guard
for the same reason: "a mutation tool that silently misreports is itself an
evaluator integrity failure."

These drive the real harness against a synthetic repository whose outcomes are
known by construction.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mutation_harness as h  # noqa: E402

WIDGET = "def check(n):\n    return n >= 10\n"
WIDGET_TEST = "from widget import check\n\n\ndef test_boundary():\n    assert check(11) is True\n    assert check(9) is False\n"

# A mutation the fixture's test MUST catch, and one no test can see. The second
# is what a negative control looks like when it is doing its job.
KILLS = ("widget.py", "return n >= 10", "return n < 10")
BLIND = ("widget.py", "return n >= 10", "return n >= 11")
# A syntactic break: pytest fails at collection, which is a non-zero exit. A
# harness that only checks the exit code reports this as a kill.
SYNTAX = ("widget.py", "return n >= 10", "return n >= ")
# An anchor that matches nothing — a mutation that was never applied.
STALE = ("widget.py", "return n >= 12", "return n < 12")


@pytest.fixture()
def repo(tmp_path):
    """A repository whose only test catches exactly one of the mutations above."""
    (tmp_path / "widget.py").write_text(WIDGET, encoding="utf-8")
    (tmp_path / "test_widget.py").write_text(WIDGET_TEST, encoding="utf-8")
    return tmp_path


def _run(repo, edits, expect_kill, name="case"):
    return h.run_entry(name, [edits], ["test_widget.py"], {}, expect_kill,
                       root=repo)


def test_a_defect_a_named_test_catches_is_reported_as_killed(repo):
    assert _run(repo, KILLS, expect_kill=True) is True


def test_a_change_no_test_can_see_is_reported_as_survived(repo):
    """The other half of the verdict. A harness that reports everything killed
    is as useless as one that reports nothing killed, and it fails in the
    direction that looks green."""
    assert _run(repo, BLIND, expect_kill=False) is True


def test_a_survivor_where_a_kill_was_expected_is_a_failure(repo):
    """`run_entry` must return something that is not True, so `main`'s
    `is not True` collects it — a bare False would do, but so would None, and
    the distinction matters for the anchor case below."""
    assert _run(repo, BLIND, expect_kill=True) is not True


def test_an_anchor_that_matches_nothing_is_refused_not_counted(repo):
    """A mutation whose anchor does not apply was not applied. Reporting it as
    killed would make a battery pass by never having run the mutation at all —
    the failure mode a moved file produces, which is exactly what the enroll
    split triggered (four anchors, E1b/E1c/E2/E6)."""
    assert _run(repo, STALE, expect_kill=True) is None


def test_a_mutations_syntax_error_is_invalid_not_a_kill(repo):
    """Collection failure is a non-zero exit. Counting it as a kill would let a
    battery claim a guard is pinned by a test that never ran."""
    assert _run(repo, SYNTAX, expect_kill=True) is False


def test_a_mutation_that_does_not_apply_leaves_the_file_untouched(repo):
    before = (repo / "widget.py").read_text()
    _run(repo, STALE, expect_kill=True)
    assert (repo / "widget.py").read_text() == before


def test_a_killed_mutation_is_restored_too(repo):
    """The restore lives in a finally so a failing battery cannot leave a
    mutant on disk for the next run to be judged against."""
    before = (repo / "widget.py").read_text()
    _run(repo, KILLS, expect_kill=True)
    assert (repo / "widget.py").read_text() == before


def test_a_battery_whose_control_dies_exits_nonzero(repo, capsys):
    """A negative control must survive. If one dies, the battery is broken
    (or the property it pins is load-bearing after all) and CI has to go red —
    a control that fails quietly is worse than none."""
    code = h.main([("M1: the real defect", [KILLS], ["test_widget.py"], {})],
                  [("N1: supposed to survive", [KILLS], ["test_widget.py"], {})],
                  "controls note", root=repo)
    assert code == 1
    assert "N1" in capsys.readouterr().out


def test_a_battery_with_a_survivor_exits_nonzero(repo, capsys):
    code = h.main([("M1: supposed to be caught", [BLIND], ["test_widget.py"], {})],
                  [], "controls note", root=repo)
    assert code == 1
    assert "survivors" in capsys.readouterr().out


def test_a_stale_anchor_is_reported_as_a_stale_anchor_not_a_survivor(repo, capsys):
    """A stale anchor and a survivor both mean exit 1, so the exit code cannot
    carry the difference — and the two need opposite responses. A survivor says
    "write the test this guard is missing"; a stale anchor says "the mutation
    never applied, re-point it", and writing a new test would answer a question
    that was never asked.

    Measured on the hosted fw-* lane: two anchor misses (a revoke line and a
    fixture scrub line this change had moved) were printed under `survivors (a
    guard no named test depends on)`. Same exit code, wrong diagnosis.
    """
    code = h.main([("M1: the anchor is stale", [STALE], ["test_widget.py"], {})],
                  [], "controls note", root=repo)
    out = capsys.readouterr().out
    assert code == 1
    assert "stale anchor" in out, out
    assert "M1" in out.split("stale anchor", 1)[1], \
        f"the stale anchor is not listed under its own heading: {out}"
    # The misreport this pins: with no real survivor, the survivors heading and
    # its "a guard no named test depends on" promise must not appear at all.
    assert "survivors (" not in out, out


def test_a_second_battery_on_the_same_tree_refuses_rather_than_interleaving(repo, capsys):
    """Two batteries mutate the same files in place, so interleaving corrupts
    both: each captures its "original" from whatever the other left, and the
    restore put back the other's mutant. Measured — a concurrent run produced
    three phantom anchor misses and credited kills to unrelated tests, and both
    runs' verdicts were worthless.

    Refusing is the choice, not queueing: a battery is minutes long, and a
    silently serialised run looks identical to a slow one.
    """
    with h.battery_lock(repo):
        code = h.main([("M1: the real defect", [KILLS], ["test_widget.py"], {})],
                      [], "controls note", root=repo)
    out = capsys.readouterr().out
    assert code == 1, "a battery ran while another held the tree"
    assert "already running" in out or "another battery" in out, out
    # It must not have touched the tree on its way to refusing.
    assert (repo / "widget.py").read_text() == WIDGET


def test_a_file_that_does_not_match_the_battery_baseline_is_reported(tmp_path):
    """Restoring is verified against a hash taken BEFORE the battery ran, not
    against the text an entry captured as it went.

    The difference is the whole failure mode: an entry that captures a
    "original" from a tree someone else already mutated restores faithfully to
    that mutant, and every per-entry check passes while the tree is left
    changed. A baseline hash is the only vantage point from which that is
    visible.
    """
    f = tmp_path / "widget.py"
    f.write_text(WIDGET, encoding="utf-8")
    baseline = h.artifact_hashes(tmp_path, ["widget.py"])
    assert h.verify_hashes(tmp_path, baseline) == []

    f.write_text(WIDGET.replace("10", "11"), encoding="utf-8")
    assert h.verify_hashes(tmp_path, baseline) == ["widget.py"]


def test_a_mutant_left_applied_is_a_harness_failure_not_a_verdict(repo, capsys, monkeypatch):
    """That baseline check WIRED INTO `main`, not merely available to it.

    The functions above can pass while nothing calls them — the shape this
    repository keeps meeting, where a guard exists and no test depends on its
    being used. The failure is injected rather than described: an entry that
    writes its mutant and reports success, which is what the earlier anomaly
    left behind. Every per-entry restore said it had restored; only the
    baseline can see the tree is not what the battery started from, and the
    next run's anchors and verdicts would otherwise be read off it.
    """
    def leaves_it_mutated(name, edits, tests, extra_env, expect_kill, root=None):
        """Applies the edit and never restores it — the injected failure."""
        for rel, old, new in edits:
            path = Path(root) / rel
            path.write_text(path.read_text().replace(old, new), encoding="utf-8")
        return True

    monkeypatch.setattr(h, "run_entry", leaves_it_mutated)
    code = h.main([("M1: supposed to be caught", [KILLS], ["test_widget.py"], {})],
                  [], "controls note", root=repo)
    out = capsys.readouterr().out
    assert code == 1, out
    assert "HARNESS FAILURE" in out, out
    assert "widget.py" in out.split("HARNESS FAILURE")[1], out


def test_a_clean_battery_exits_zero(repo):
    assert h.main([("M1: the real defect", [KILLS], ["test_widget.py"], {})],
                  [("N1: must survive", [BLIND], ["test_widget.py"], {})],
                  "controls note", root=repo) == 0


def test_well_formed_reads_each_artifact_language(repo):
    """The batteries mutate shell scripts, the size gate's own Python, and the
    CI workflow, so a parse check that compiles only Python would call both a
    broken unit file and a broken workflow valid — and a YAML mutation that
    breaks parsing makes every test fail at collection, which a harness reading
    only the exit code reports as a kill."""
    py = repo / "w.py"
    py.write_text("def f(:\n", encoding="utf-8")
    sh = repo / "s.sh"
    sh.write_text("if true; then\n", encoding="utf-8")
    js = repo / "j.json"
    js.write_text(json.dumps({"a": 1}), encoding="utf-8")
    yml = repo / "c.yml"
    yml.write_text("jobs:\n  a: [\n", encoding="utf-8")
    assert h.well_formed(py) is False
    assert h.well_formed(sh) is False
    assert h.well_formed(yml) is False
    assert h.well_formed(js) is True
    sh.write_text("if true; then\n  echo hi\nfi\n", encoding="utf-8")
    yml.write_text("jobs:\n  a:\n    if: true\n", encoding="utf-8")
    assert h.well_formed(sh) is True
    assert h.well_formed(yml) is True


def test_clear_bytecode_removes_a_planted_cache(repo):
    """It exists because a restored file of the same size, with an mtime inside
    the filesystem's resolution, keeps its MUTATED bytecode cached — the next
    run then imports the mutation's behaviour against a file already correct."""
    cache = repo / "__pycache__"
    cache.mkdir()
    (cache / "widget.cpython-311.pyc").write_bytes(b"\x00")
    h.clear_bytecode(root=repo)
    assert not cache.exists()


def test_a_root_that_is_not_the_tree_under_test_refuses(tmp_path):
    """`root` is the injection seam the guards above need, which makes "root
    resolved somewhere else" a live failure mode — the same one the re-pin
    harness hit when its REPO silently became tests/. It must fail naming the
    file, not report a verdict against nothing."""
    with pytest.raises(FileNotFoundError, match="widget.py"):
        h.run_entry("case", [KILLS], ["test_widget.py"], {}, True, root=tmp_path)


def test_the_batteries_carry_no_harness_of_their_own():
    """The point of the consolidation, and the thing that decays: a battery
    that grows a private copy again is a second place for a verdict to be
    wrong. Each must import the shared harness and define neither the runner
    nor the verdict."""
    here = Path(__file__).resolve().parent
    batteries = sorted(here.glob("mutation_battery_*.py"))
    assert batteries, "no batteries found — this guard would be vacuous"
    for battery in batteries:
        text = battery.read_text(encoding="utf-8")
        assert "from mutation_harness import" in text or "import mutation_harness" in text, \
            f"{battery.name} does not use the shared harness"
        for private in ("def run_entry", "def run_tests", "def well_formed",
                        "def clear_bytecode", "def main("):
            assert private not in text, \
                f"{battery.name} has grown its own {private} again"


def test_every_battery_runs_in_the_suite():
    """Reproducibility (self-check-the-mutation-harness): the batteries are not
    test_*.py, so pytest
    does not collect them, and nothing else ran them — a survivor was visible
    only to someone who remembered to look. CI runs them by name; this pins the
    list against the directory so a fourth battery cannot be added and be
    silently unrun."""
    here = Path(__file__).resolve().parent
    lines = (here.parent / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines)
                  if l.strip().startswith("- name: mutation batteries")), None)
    assert start is not None, "the mutation-batteries step is gone from ci.yml"
    # To the next `- name:` at the same indent, so a commit elsewhere in the
    # file cannot satisfy this.
    body, indent = [], len(lines[start]) - len(lines[start].lstrip())
    for line in lines[start + 1:]:
        if line.strip().startswith("- ") and len(line) - len(line.lstrip()) == indent:
            break
        body.append(line)
    step = "\n".join(body)
    for battery in sorted(here.glob("mutation_battery_*.py")):
        assert f"tests/{battery.name}" in step, \
            f"{battery.name} is never run by CI — add it to the batteries step"
