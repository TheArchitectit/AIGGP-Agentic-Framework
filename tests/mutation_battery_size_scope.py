#!/usr/bin/env python3
"""Mutation battery for the file-size gate's SCOPE (task #13, FAIL-8f9249ca).

The gate sized sixteen languages and not the one this repository's fleet-side
scripts are written in, so `scripts/runner-enroll.sh` reached 589 lines against
a 500-line limit with the FILE-SIZE CHECK reporting nothing. That is the same
shape as FAIL-f6228dda: a SCOPE declaration drifting from its intent, green
because it never looked.

The subject here is therefore scope, not arithmetic. Every mutation removes one
declaration and asks whether a named test notices:
  * the extension list,
  * the test-file prefix convention,
  * the directory list the walk enters.

Two properties this battery asserts about itself, inherited from the sibling
batteries:

  * A mutation that merely BREAKS THE PARSER kills every test at once, which
    looks identical to a clean behavioural kill. Each mutated artifact is
    checked for well-formedness first and reported INVALID rather than killed.
  * The count of the anchor text is asserted before the edit, and a mutation
    whose anchor has drifted is reported rather than silently skipped.

Run it from the repository root: it rewrites files in place and restores them.
It lives in the repository (rather than in /tmp) so that "no survivors" can be
re-checked by whoever reads the ledger next.

Third copy of this harness. `mutation_battery_image_cycle.py` and
`mutation_battery_image_state.py` carry their own; consolidating all three into
one tests/mutation_harness.py is task #14, and is deliberately NOT done here —
this battery exists so that the scope guard is reproducible, and folding two
other batteries in at the same time would put that reproduction at risk.

Negative controls: this battery has ONE, and it is a different kind from the
image batteries'. Those mutate shipped code together with the fixture that
models it, so the two agree with each other and the suite cannot see the
defect — proving a fixture property is load-bearing. There is no such pair
here: every mutation below removes a literal that the named test reads
directly, and the fixture is arithmetic (a line count) with no second half to
co-mutate. What this battery CAN be wrong about is its own kill detection — a
harness that reported every mutation as killed would make the whole file
decoration, and no mutation below would notice. The control pins exactly that.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Hermetic: an ambient git identity or config could change how a test that
# shells out to git behaves (this bit the re-pin suite once).
ENV = dict(os.environ,
           HOME="/nonexistent-devgate-mutation",
           XDG_CONFIG_HOME="/nonexistent-devgate-mutation",
           GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")

SIZES = "scripts/regression_sizes.py"
CHECK = "scripts/regression_check.py"
T_SIZES = "tests/test_regression_sizes.py"

EXTENSIONS_WITH_SH = '''                     ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs",
                     ".sh")'''
EXTENSIONS_WITHOUT_SH = '''                     ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs")'''

TEST_PREFIX_WITH_SH = 'TEST_PREFIX_EXTENSIONS = (".py", ".sh")'
TEST_PREFIX_WITHOUT_SH = 'TEST_PREFIX_EXTENSIONS = (".py",)'

DIRS_WITH_SCRIPTS = 'SOURCE_DIRS = []\nfor candidate in ["src", "lib", "app", "extensions", "scripts", "internal", "pkg", "cmd", "game",'
DIRS_WITHOUT_SCRIPTS = 'SOURCE_DIRS = []\nfor candidate in ["src", "lib", "app", "extensions", "internal", "pkg", "cmd", "game",'

MUTATIONS = [
    # S1 — the extension list. Killed by the MUST-flag test; the
    # classification test dies with it, because an unsized file is also an
    # unclassified one.
    ("S1: `.sh` dropped from SOURCE_EXTENSIONS — shell scripts sized again by nobody",
     [(SIZES, EXTENSIONS_WITH_SH, EXTENSIONS_WITHOUT_SH)],
     [T_SIZES], {}),

    # S2 — the test-file prefix convention. Killed by the classification test
    # ALONE: `tests/test_giant.sh` is still flagged as source (601 > 500), so
    # only the assertion that it was judged at TEST_HARD can see this.
    ("S2: `.sh` dropped from TEST_PREFIX_EXTENSIONS — shell tests judged at SRC_HARD",
     [(SIZES, TEST_PREFIX_WITH_SH, TEST_PREFIX_WITHOUT_SH)],
     [T_SIZES], {}),

    # S3 — the directory list. `.sh` in the extension list is inert unless the
    # walk enters scripts/, which is where every shell script here lives. This
    # mutation is what found the missing assertion.
    ("S3: `scripts` dropped from the SOURCE_DIRS candidates — the walk never enters it",
     [(CHECK, DIRS_WITH_SCRIPTS, DIRS_WITHOUT_SCRIPTS)],
     [T_SIZES], {}),
]

# Must SURVIVE. See the docstring: this pins the harness's own kill detection,
# not a fixture property.
NEGATIVE_CONTROLS = [
    ("N1: an extension nothing in the tree uses — must change no outcome",
     [(SIZES, EXTENSIONS_WITH_SH, EXTENSIONS_WITH_SH.replace('".sh")', '".sh", ".bak")'))],
     [T_SIZES], {}),
]


def _clear_bytecode():
    """Drop __pycache__ before each run.

    Restoring a mutated .py can leave the same size and an mtime inside the
    filesystem's resolution, so CPython keeps the MUTATED bytecode cached and
    the next run imports it. Observed once in a sibling battery: a
    restore-then-verify step reported the mutation's error against a file that
    was already correct.
    """
    for d in REPO.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def _well_formed(path):
    """True when the mutated artifact still parses. False means INVALID."""
    try:
        compile(path.read_text(), str(path), "exec")
        return True
    except SyntaxError:
        return False


def run_tests(files, extra_env=None):
    _clear_bytecode()
    env = dict(ENV)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "pytest", *files, "-q",
                           "-p", "no:cacheprovider"],
                          capture_output=True, text=True, cwd=str(REPO), env=env)


def _run_entry(name, edits, tests, extra_env, expect_kill):
    """Apply edits, run the named tests, restore. Returns True when the
    outcome matched the expectation (killed, or survived)."""
    originals = {}
    for rel, old, new in edits:
        path = REPO / rel
        originals.setdefault(rel, path.read_text())
        count = originals[rel].count(old)
        if count != 1:
            print(f"  ANCHOR  {name}: {rel} anchor appears {count} times, not 1")
            return None
    for rel, old, new in edits:
        (REPO / rel).write_text(originals[rel].replace(old, new))
    well_formed = all(_well_formed(REPO / rel) for rel, _, _ in edits)
    try:
        res = run_tests(tests, extra_env)
        killed = res.returncode != 0
    finally:
        for rel, text in originals.items():
            (REPO / rel).write_text(text)

    if not well_formed:
        print(f"  INVALID {name}: the mutation does not parse — not a kill")
        return False
    if killed:
        tail = [l for l in res.stdout.splitlines() if l.startswith("FAILED")]
        print(f"  killed  {name}\n            by {tail[0][7:] if tail else '(?)'}")
    else:
        print(f"  SURVIVED {name}")
    return killed == expect_kill


def main():
    survivors = []
    for name, edits, tests, extra_env in MUTATIONS:
        if _run_entry(name, edits, tests, extra_env, expect_kill=True) is not True:
            survivors.append(name)

    controls_bad = []
    for name, edits, tests, extra_env in NEGATIVE_CONTROLS:
        if _run_entry(name, edits, tests, extra_env, expect_kill=False) is not True:
            controls_bad.append(name)

    print(f"\n{len(MUTATIONS) - len(survivors)}/{len(MUTATIONS)} mutations killed")
    if survivors:
        print("survivors (a guard no named test depends on):")
        for s in survivors:
            print(f"  - {s}")
    print(f"{len(NEGATIVE_CONTROLS) - len(controls_bad)}/{len(NEGATIVE_CONTROLS)} "
          "negative controls behaved (this one MUST survive — it pins the "
          "battery's own kill detection)")
    for c in controls_bad:
        print(f"  - {c} (expected to survive and did not, or a bad anchor)")
    return 1 if (survivors or controls_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
