#!/usr/bin/env python3
"""Tests for scripts/spec_gap_scan.py — the mechanical gap scanner.

The honesty rails (SGA-01/03/04/06/07) are what this suite exists to
lock: a row without an evidence pointer must not appear; CLAIMED-BUT-ABSENT
must never fail the gate or read as a requirement; an empty anchor set is
"unknown scope", not a pass; and the scanner must NOT soften
spec_traceability's exit-2 refusal. Fixtures are planted so each claim is
checkable against the file it points at, exactly as the scanner promises.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCANNER = HERE.parent / "scripts" / "spec_gap_scan.py"
TRACE = HERE.parent / "scripts" / "spec_traceability.py"


def run(args, root=None):
    cmd = [sys.executable, str(SCANNER), "--root", str(root)] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def gd(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_repo(tmp: Path) -> Path:
    """A minimal game-shaped repo with one capability anchor in src/."""
    gd(tmp / "src/autoload/economy_manager.gd",
       "extends Node\nvar coins = 0\nfunc add_coins(n): coins += n\n")
    return tmp


# --- SGA-04: exits and honest empties -------------------------------------

def test_unreadable_root_exits_2(tmp_path):
    r = run([], root=tmp_path / "does-not-exist")
    assert r.returncode == 2
    assert "not a directory" in r.stderr


def test_empty_anchor_set_is_unknown_scope_not_a_pass(tmp_path):
    # src/ exists but has no capability anchors at all.
    (tmp_path / "src").mkdir()
    r = run([], root=tmp_path)
    assert r.returncode == 2
    assert "unknown scope (no anchors found)" in r.stderr


def test_looked_wording_names_the_searched_roots(tmp_path):
    (tmp_path / "src").mkdir()
    r = run([], root=tmp_path)
    assert "src/autoload" in r.stderr  # states WHAT it looked at


# --- SGA-01: every row carries a file:line evidence pointer ----------------

def test_inventory_rows_all_have_evidence(tmp_path):
    make_repo(tmp_path)
    r = run(["--json"], root=tmp_path)
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout)
    for row in report["inventory"]["unspaced"]:
        assert "economy-manager" == row["capability"]
        # anchor = first GD_CODE_START line (the `var coins` line)
        assert row["evidence"].startswith("src/autoload/economy_manager.gd:2")


def test_evidence_line_points_at_real_source(tmp_path):
    make_repo(tmp_path)
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    row = report["inventory"]["unspaced"][0]
    path, rng = row["evidence"].split(":")
    start = int(rng.split("-")[0])
    text = (tmp_path / path).read_text().splitlines()
    # the anchor must be a code line, matching the scanner's own rule
    assert text[start - 1].startswith("var ")


# --- gap categories --------------------------------------------------------

def test_spaced_capability_is_not_listed_as_gap(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "openspec/specs/economy-manager/spec.md",
       "# economy-manager\n\n## ADDED Requirements\n\n### Requirement: x "
       "<!-- id: eco-01 -->\nSHALL.\n\n#### Scenario: y\nGIVEN/WHEN/THEN.\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    assert report["summary"]["unspaced"] == 0
    assert report["coverage"]["requirement_ids"] == 1
    assert report["coverage"]["uncovered_ids"][0]["id"] == "eco-01"


def test_uncovered_id_marked_covered_disappears(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "openspec/specs/economy-manager/spec.md",
       "### Requirement: x <!-- id: eco-01 -->\n")
    gd(tmp_path / "src/autoload/economy_manager.gd",
       "# spec: eco-01\nextends Node\nvar coins = 0\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    assert report["summary"]["uncovered_ids"] == 0


# --- SGA-03: CLAIMED-BUT-ABSENT is a lead, never a requirement ------------

def test_dead_const_is_claimed_not_a_requirement(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "src/autoload/hero_manager.gd",
       "extends Node\nconst HERO_UNUSED: int = 1\nvar x = 2\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    cba = report["claimed_but_absent"]
    assert any(r["kind"] == "const-dead" and r["claim"] == "HERO_UNUSED"
               for r in cba)
    # rail 3: it is NOT in the coverage requirement set
    assert "HERO_UNUSED" not in json.dumps(report["coverage"])


def test_unspaced_gap_fails_the_gate_while_cba_is_separate(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "src/autoload/dead_manager.gd",
       "extends Node\nconst DEAD: int = 1\nvar q = 2\n")
    r = run(["--fail-on-gaps"], root=tmp_path)
    assert r.returncode == 1  # unspaced capabilities DO fail
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    assert report["summary"]["unspaced"] == 2  # economy-manager, dead-manager
    assert report["summary"]["claimed_but_absent"] >= 1  # DEAD, separate


def test_pure_claim_no_gaps_exits_0(tmp_path):
    make_repo(tmp_path)
    # space the only capability, and plant a dead const in an already-spaced file
    gd(tmp_path / "openspec/specs/economy-manager/spec.md",
       "### Requirement: x <!-- id: eco-01 -->\n")
    gd(tmp_path / "src/autoload/economy_manager.gd",
       "# spec: eco-01\nextends Node\nconst HERO_ENERGY_SURCHARGE: int = 12\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    assert report["summary"]["claimed_but_absent"] >= 1  # HERO_ENERGY_SURCHARGE
    assert report["summary"]["unspaced"] == 0
    r = run(["--fail-on-gaps"], root=tmp_path)
    assert r.returncode == 0  # CBA alone never reddens


# --- worst-tracked-first ordering -----------------------------------------

def test_unspaced_ordered_by_surface_size(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "src/autoload/tiny_manager.gd", "extends Node\nvar a = 1\n")
    big = "extends Node\n" + "\n".join(f"func f{i}():\n\treturn {i}"
                                       for i in range(30))
    gd(tmp_path / "src/autoload/big_manager.gd", big)
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    caps = [c["capability"] for c in report["inventory"]["unspaced"]]
    assert caps.index("big-manager") < caps.index("tiny-manager")


# --- SGA-06: additive to the traceability refusal --------------------------

def test_scanner_does_not_soften_traceability_refusal(tmp_path):
    make_repo(tmp_path)  # src/ present, no openspec/ at all
    tr = subprocess.run([sys.executable, str(TRACE), "--root", str(tmp_path)],
                        capture_output=True, text=True)
    assert tr.returncode == 2  # config refusal stands
    assert run(["--json"], root=tmp_path).returncode == 0  # scanner runs beside it


def test_scaffold_does_not_change_traceability_verdict(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "openspec/specs/economy-manager/spec.md",
       "### Requirement: x <!-- id: eco-01 -->\n")
    gd(tmp_path / "src/autoload/economy_manager.gd",
       "# spec: eco-01\nextends Node\n")
    r = subprocess.run([sys.executable, str(SCANNER), "--root", str(tmp_path),
                        "--scaffold"], capture_output=True, text=True)
    # scaffold is a no-op in scan mode today (task 1.4) — must NOT fabricate specs
    assert r.returncode in (0, 2)
    still = subprocess.run([sys.executable, str(TRACE), "--root", str(tmp_path)],
                           capture_output=True, text=True)
    assert "0/0" not in still.stdout  # no drafted spec silently counted


# --- SGA-05: shared discovery agreement ------------------------------------

def test_scanner_and_traceability_agree_on_coverage(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "openspec/specs/economy-manager/spec.md",
       "### Requirement: x <!-- id: eco-01 -->\n")
    gd(tmp_path / "src/autoload/economy_manager.gd",
       "# spec: eco-01\nextends Node\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    tr = subprocess.run([sys.executable, str(TRACE), "--root", str(tmp_path)],
                        capture_output=True, text=True)
    assert report["coverage"]["uncovered_ids"] == []  # eco-01 covered
    assert "1/1 requirements covered" in tr.stdout


# --- scratch files are not claim surfaces ----------------------------------

def test_parked_scratch_file_emits_no_claims(tmp_path):
    make_repo(tmp_path)
    gd(tmp_path / "src/_scratch_old_manager.gd",
       "extends Node\nconst DEADTH: int = 1\nsignal orphaned\n")
    report = json.loads(run(["--json"], root=tmp_path).stdout)
    claims = [r["claim"] for r in report["claimed_but_absent"]]
    assert "DEADTH" not in claims
