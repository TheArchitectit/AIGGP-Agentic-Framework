"""Tests for scripts/secret-scan-declared.sh — the fleet declaration generator.

The fleet sweep's first production run carried a residual that is not a
scanner problem: "a new public repository created tomorrow is not in this
declaration until someone updates the file." A hand-maintained list cannot
avoid going stale, and a stale list silently shrinks the fleet — the exact
shape of every scanner bug this repository has already met, just one layer
up.

So the declaration is generated per run from the live repo list, with the
reviewable exceptions as checked-in text files. This suite is written against
`secret-gate-rollout` SGR-08 and design D3. What it pins:

  T-09  a canned `gh repo list` JSON produces a sorted, deduped declaration
        with include/exclude applied, byte-stable across runs.
  T-10  a generator that would emit an empty declaration exits 3 and writes
        nothing — the sweep's own vacuity code, reused for the same reason:
        an empty generated list is a broken generator, never a clean fleet.

The generator is required to take a --snapshot so this suite runs without
credentials and without the network, which is also how a human can dry-run a
declaration change locally.

Dual-runnable: pytest collects test_*;
`python3 tests/test_secret_scan_declared.py` runs them too.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Requires bash: these tests shell out to things that do not exist on Windows.
# A test that cannot run must SKIP, not fail -- failing here is
# indistinguishable from real breakage.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires bash")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "secret-scan-declared.sh"
REAL_INCLUDE = REPO_ROOT / "fleet-sweep-include.txt"
REAL_EXCLUDE = REPO_ROOT / "fleet-sweep-exclude.txt"
BASH = shutil.which("bash") or "/bin/bash"

# How many URLs the shipped include file unions in. If the file changes
# deliberately, bump this constant in the same commit — a silent emptying of
# the include list is exactly the coverage gap this constant exists to catch.
REAL_INCLUDE_COUNT = 7


def repo(owner, name, *, archived=False, url=None):
    return {
        "nameWithOwner": f"{owner}/{name}",
        "isPrivate": False,
        "isArchived": archived,
        "url": url or f"https://github.com/{owner}/{name}",
    }


class Gen:
    """A generator under test, living in a throwaway layout.

    The script reads its include/exclude files from the parent of its own
    directory, so the layout has to be a miniature repo root: scripts/ for
    the generator, and the two exception files beside it. This is the shape
    the workflow ships, not a test-only convention.

    Each instance owns its own tree under tmp_path, so a test can stand up
    two generators (one for the positive run, one for the refusal) without
    the second mkdir blowing up on the first's leftover.
    """

    def __init__(self, tmp_path: Path, name: str = "layout"):
        self.root = tmp_path / name
        (self.root / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT, self.root / "scripts" / "secret-scan-declared.sh")
        self.include = self.root / "fleet-sweep-include.txt"
        self.exclude = self.root / "fleet-sweep-exclude.txt"
        self.include.write_text("# empty include\n", encoding="utf-8")
        self.exclude.write_text("# empty exclude\n", encoding="utf-8")
        self.out = tmp_path / f"{name}-declared.txt"
        self.snapshot = tmp_path / f"{name}-snapshot.json"
        self.script = self.root / "scripts" / "secret-scan-declared.sh"

    def write_snapshot(self, repos):
        self.snapshot.write_text(json.dumps(repos), encoding="utf-8")

    def run(self, *, env=None):
        cmd = [
            BASH,
            str(self.script),
            "--out",
            str(self.out),
            "--snapshot",
            str(self.snapshot),
        ]
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def lines(self):
        return self.out.read_text(encoding="utf-8").splitlines()


# --- T-09: determinism ------------------------------------------------------


def test_T09_a_canned_snapshot_produces_a_sorted_deduped_declaration(tmp_path):
    """sorted on owner/name, include unioned, exclude applied, no duplicates.

    The snapshot deliberately lists repos out of order and with an archived
    one, because a generator that sorts is a generator whose output a human
    can diff on a review. Byte-stability across two runs is the other half of
    "deterministically" — a flaky ordering is a flaky diff, and a flaky diff
    is a report no one reads.
    """
    g = Gen(tmp_path)
    g.write_snapshot(
        [
            repo("TheArchitectit", "zeta"),
            repo("TheArchitectit", "alpha"),
            repo("TheArchitectit", "beta"),
            # archived: nobody can push to it; its state is what the last
            # sweep recorded. Not ours to re-litigate nightly.
            repo("TheArchitectit", "old-thing", archived=True),
            # duplicate of alpha under a trailing-slash spelling — the
            # declaration is one URL per repo.
            repo("TheArchitectit", "alpha", url="https://github.com/TheArchitectit/alpha/"),
        ]
    )
    g.include.write_text(
        "# comment\n"
        "\n"
        "https://github.com/drwhofan2k18-pixel/alpha\n"  # not in the owner scope
        "\n",
        encoding="utf-8",
    )
    g.exclude.write_text("TheArchitectit/zeta  # out of scope this week\n", encoding="utf-8")

    res = g.run()
    assert res.returncode == 0, res.stderr
    got = g.lines()
    # Owner/name sorts case-insensitively, so the drw fork sorts up next to
    # TheArchitectit/alpha rather than after the empty-line-excluded zeta.
    assert got == [
        "https://github.com/drwhofan2k18-pixel/alpha",
        "https://github.com/TheArchitectit/alpha",
        "https://github.com/TheArchitectit/beta",
    ], got

    again = g.run()
    assert again.returncode == 0, again.stderr
    assert g.lines() == got, "two runs over the same snapshot disagree"


def test_T09_real_include_file_unions_the_two_owner_repos(tmp_path):
    """The shipped fleet-sweep-include.txt is the SGR-08 scenario itself:
    `llama.cpp` is absent (excluded), the drwhofan2k18-pixel forks are
    present. Asserting on the real file means an edit that empties the
    include list, or that drops a reason from an exclusion, fails here rather
    than in a week's nightly run.
    """
    assert REAL_INCLUDE.exists(), "fleet-sweep-include.txt is missing"
    assert REAL_EXCLUDE.exists(), "fleet-sweep-exclude.txt is missing"

    g = Gen(tmp_path)
    g.include.write_text(REAL_INCLUDE.read_text(encoding="utf-8"), encoding="utf-8")
    g.exclude.write_text(REAL_EXCLUDE.read_text(encoding="utf-8"), encoding="utf-8")
    g.write_snapshot(
        [
            repo("TheArchitectit", "AIGGP-Agentic-Framework"),
            repo("TheArchitectit", "llama.cpp"),
            repo("TheArchitectit", "awesome-cline-skills"),
            repo("TheArchitectit", "plexus-debug-ui"),
        ]
    )

    res = g.run()
    assert res.returncode == 0, res.stderr
    got = g.lines()
    assert "https://github.com/TheArchitectit/AIGGP-Agentic-Framework" in got
    assert "https://github.com/TheArchitectit/plexus-debug-ui" in got
    assert not any(u.rstrip("/").endswith("/llama.cpp") for u in got), (
        f"excluded upstream fork reached the declaration: {got}"
    )
    assert not any("awesome-cline-skills" in u for u in got), got
    included = [u for u in got if "drwhofan2k18-pixel/" in u]
    assert len(included) == REAL_INCLUDE_COUNT, (
        f"the include file is expected to carry {REAL_INCLUDE_COUNT} URLs, "
        f"the generator unioned {len(included)}: {included}"
    )


# --- T-10: vacuity is not cleanliness ---------------------------------------


def test_T10_an_empty_result_exits_3_and_writes_nothing(tmp_path):
    """Every candidate excluded (or the snapshot empty) means the generator
    produced nothing. Writing an empty file and exiting 0 would hand the
    sweep a declaration it then rejects — the failure would surface one layer
    down, named after the wrong tool. Exit 3 is the sweep's vacuity code and
    it is reused here for the same reason: an empty generated list is a
    broken generator, never a clean fleet.
    """
    g = Gen(tmp_path, "empty")
    g.write_snapshot([])
    res = g.run()
    assert res.returncode == 3, res.returncode
    assert not g.out.exists(), "the generator wrote a file after refusing"

    g2 = Gen(tmp_path, "all-excluded")
    g2.write_snapshot([repo("TheArchitectit", "only")])
    g2.exclude.write_text("only  # excluded\n", encoding="utf-8")
    res2 = g2.run()
    assert res2.returncode == 3, res2.returncode
    assert not g2.out.exists(), "the generator wrote a file after refusing"


def test_an_absent_snapshot_is_a_broken_generator_not_an_empty_fleet(tmp_path):
    """--snapshot names a file that is not there: refuse, do not fall back to
    a live `gh` call (which is what silently turns a unit test into a
    credentialed network sweep) and do not write an empty declaration.
    """
    g = Gen(tmp_path)
    cmd = [
        BASH,
        str(g.script),
        "--out",
        str(g.out),
        "--snapshot",
        str(tmp_path / "definitely-not-here.json"),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 3, (res.returncode, res.stdout, res.stderr)
    assert not g.out.exists()


# --- the snapshot path is the no-network path -------------------------------


def test_the_snapshot_path_never_invokes_gh(tmp_path):
    """T-09's real assertion is "byte-stable" and "no credentials". Both
    break the moment the generator reaches for `gh` even under --snapshot.
    Put a stub `gh` first on PATH that would crash if called.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    stub = fake_bin / "gh"
    stub.write_text(
        '#!/usr/bin/env bash\necho "gh must not run under --snapshot" >&2\nexit 99\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)

    g = Gen(tmp_path)
    g.write_snapshot([repo("TheArchitectit", "alpha")])
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
    res = g.run(env=env)
    assert res.returncode == 0, res.stderr
    assert "must not run" not in res.stderr, res.stderr
    assert g.lines() == ["https://github.com/TheArchitectit/alpha"]


def test_a_live_run_without_gh_exits_2_not_3(tmp_path):
    """Exit 2 is the sweep code for "scanner unusable" — nothing about any
    repository can be claimed — and the generator reuses it for "gh is not
    here and I was asked for a live listing". Distinguishing it from exit 3
    (bad invocation) is what tells an operator whether to fix their PATH or
    their argv.
    """
    g = Gen(tmp_path)
    g.snapshot.write_text("[]", encoding="utf-8")
    # Empty PATH: gh cannot be found. Ask for a live run by dropping --snapshot
    # and pointing --out at the layout as the sweep would.
    fake_bin = tmp_path / "empty-bin"
    fake_bin.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(fake_bin)
    cmd = [BASH, str(g.script), "--out", str(g.out)]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert res.returncode == 2, (res.returncode, res.stdout, res.stderr)
    assert "gh" in res.stderr.lower(), res.stderr


# --- exclusion matching is what keeps the file reviewable --------------------


def test_exclusions_match_by_url_owner_name_and_bare_name(tmp_path):
    g = Gen(tmp_path)
    g.write_snapshot(
        [
            repo("TheArchitectit", "llama.cpp"),
            repo("TheArchitectit", "awesome-cline-skills"),
            repo("TheArchitectit", "TheArchitectit"),
            repo("TheArchitectit", "keeper"),
        ]
    )
    g.exclude.write_text(
        "https://github.com/TheArchitectit/llama.cpp  # by URL\n"
        "TheArchitectit/awesome-cline-skills  # by owner/name\n"
        "TheArchitectit  # bare name; also matches the profile repo\n",
        encoding="utf-8",
    )
    res = g.run()
    assert res.returncode == 0, res.stderr
    assert g.lines() == ["https://github.com/TheArchitectit/keeper"], g.lines()


def test_a_reason_less_exclusion_warns_but_still_works(tmp_path):
    """The reason is what the next auditor reads; the generator warns when it
    is missing rather than letting the entry look deliberate. Failing on it
    would let a typo file one night into a red nightly nobody can distinguish
    from a leak. Warn, apply the exclusion anyway, and leave the warning on
    stderr where the log carries it.
    """
    g = Gen(tmp_path)
    g.write_snapshot([repo("TheArchitectit", "messy"), repo("TheArchitectit", "ok")])
    g.exclude.write_text("messy\n", encoding="utf-8")
    res = g.run()
    assert res.returncode == 0, res.stderr
    assert g.lines() == ["https://github.com/TheArchitectit/ok"]
    assert "reason" in res.stderr.lower(), res.stderr
    assert "messy" in res.stderr, res.stderr


# --- option-injection guard -------------------------------------------------


def test_a_line_starting_with_a_dash_is_refused_not_emitted(tmp_path):
    """The sweep script refuses a declaration URL that starts with '-' so a
    crafted line cannot smuggle an option into its argv. The generator is the
    thing that writes the declaration, so it refuses the same shape before it
    writes anything — catching it here names the cause, not the consumer.
    """
    for where in ("include", "exclude"):
        g = Gen(tmp_path, f"inject-{where}")
        g.write_snapshot([repo("TheArchitectit", "alpha")])
        (g.include if where == "include" else g.exclude).write_text(
            f"-e helloworld  # {where} injection\n", encoding="utf-8"
        )
        res = g.run()
        assert res.returncode == 3, (where, res.returncode, res.stderr)
        assert not g.out.exists(), f"{where}: the generator wrote a file after refusing"
        assert "refused" in res.stderr or "injection" in res.stderr or "-" in res.stderr, (
            where,
            res.stderr,
        )


# --- invocation hygiene ----------------------------------------------------


def test_missing_out_is_a_bad_invocation(tmp_path):
    g = Gen(tmp_path)
    g.write_snapshot([repo("TheArchitectit", "alpha")])
    cmd = [BASH, str(g.script), "--snapshot", str(g.snapshot)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 3, res.returncode
    assert "out" in res.stderr.lower(), res.stderr


def test_unrecognised_arguments_are_refused(tmp_path):
    g = Gen(tmp_path)
    g.write_snapshot([repo("TheArchitectit", "alpha")])
    cmd = [BASH, str(g.script), "--out", str(g.out), "--wat"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 3, res.returncode
    assert not g.out.exists()


def test_case_differing_urls_collapse_and_order_is_canonical(tmp_path):
    """GitHub paths are case-insensitive, so `.../Alpha` and `.../alpha` are
    one repository and the declaration may not list both. The surviving
    spelling is the first one the snapshot carried, and the residual order is
    a pure function of the lowercased URL — so two runs cannot disagree about
    which letters landed on the disk.
    """
    g = Gen(tmp_path)
    g.write_snapshot(
        [
            repo("TheArchitectit", "beta"),
            repo("TheArchitectit", "Alpha"),
            repo("TheArchitectit", "alpha"),
            repo("TheArchitectit", "gamma"),
        ]
    )
    res = g.run()
    assert res.returncode == 0, res.stderr
    assert g.lines() == [
        "https://github.com/TheArchitectit/Alpha",
        "https://github.com/TheArchitectit/beta",
        "https://github.com/TheArchitectit/gamma",
    ], g.lines()

    # And the do-over stays put: same snapshot, same bytes.
    assert g.run().returncode == 0
    assert g.lines() == [
        "https://github.com/TheArchitectit/Alpha",
        "https://github.com/TheArchitectit/beta",
        "https://github.com/TheArchitectit/gamma",
    ]


if __name__ == "__main__":
    import pytest as _pytest

    sys.exit(_pytest.main([__file__, "-q"]))