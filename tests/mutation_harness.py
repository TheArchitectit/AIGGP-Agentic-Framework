"""The machinery the mutation batteries run on — one copy, not three.

A battery asserts something the ritual depends on: that each guard is killable
by exactly one named test, and that the program actually consumes what the test
asserts. It does that by mutating a tracked file, running a named test, and
reading the verdict off the exit status — which means the harness is the
evaluator, and an evaluator that misreports makes every battery green while
proving nothing. `scripts/mutation_check.py` states the rule for its own tool:
"a mutation tool that silently misreports is itself an evaluator integrity
failure." Its guard is a `--self-check`; this harness's is
`tests/test_mutation_harness.py`, which drives the functions below against a
synthetic repository whose outcomes are known by construction.

Task #14: the three batteries each carried a private copy of this. Two were
byte-identical; the third, `_well_formed`, understood only Python and would have
called a broken shell unit file valid. Consolidating also found that nothing ran
the batteries at all — pytest does not collect `mutation_battery_*.py`, so a
survivor was visible only to whoever remembered to look. CI runs them by name
now, and `test_every_battery_runs_in_the_suite` keeps a fourth from being added
unrun.

Kept out of the `test_*.py` namespace so pytest's collection stays about the
product; the batteries are a separate, slower, self-mutating lane.
"""
import json
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


def well_formed(path):
    """True when the mutated artifact still parses. False means INVALID.

    All three artifact languages are here rather than only the one this file's
    original copy happened to need: a mutation that leaves a syntax error makes
    the test command exit non-zero for a reason that has nothing to do with a
    test catching anything, so it must be rejected before any verdict is read.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            json.loads(text)
            return True
        except Exception:
            return False
    if path.suffix in (".yml", ".yaml"):
        try:
            import yaml
            yaml.safe_load(text)
            return True
        except Exception:
            return False
    if path.suffix == ".sh":
        return subprocess.run(["bash", "-n", str(path)],
                              capture_output=True, text=True).returncode == 0
    if path.suffix == ".py":
        try:
            compile(text, str(path), "exec")
            return True
        except SyntaxError:
            return False
    return True


def clear_bytecode(root=None):
    """Drop __pycache__ before each run.

    Restoring a mutated .py can leave the same size and an mtime inside the
    filesystem's resolution, so CPython keeps the MUTATED bytecode cached and
    the next run imports it. Observed once: a restore-then-verify step reported
    the mutation's error against a file that was already correct.
    """
    for d in (root or REPO).rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run_tests(files, extra_env=None, root=None):
    clear_bytecode(root)
    env = dict(ENV)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "pytest", *files, "-q",
                           "-p", "no:cacheprovider"],
                          capture_output=True, text=True,
                          cwd=str(root or REPO), env=env)


def run_entry(name, edits, tests, extra_env, expect_kill, root=None):
    """Apply edits, run the named tests, restore.

    Returns True when the outcome matched `expect_kill`, False when it did not
    or the mutant could not be evaluated, and None when an anchor did not apply
    — a distinction the caller needs: a stale anchor means the mutation was
    never applied, and reporting that as a kill would let a battery pass by
    never having run anything (which is what a moved file produces).
    """
    root = root or REPO
    originals = {}
    for rel, old, new in edits:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(
                f"{root} does not contain {rel} — this root is not the tree "
                "under test (a misresolved root, not a stale anchor)")
        originals.setdefault(rel, path.read_text(encoding="utf-8"))
        count = originals[rel].count(old)
        if count != 1:
            print(f"  ANCHOR  {name}: {rel} anchor appears {count} times, not 1")
            return None
    for rel, old, new in edits:
        (root / rel).write_text(originals[rel].replace(old, new),
                                encoding="utf-8")
    try:
        if not all(well_formed(root / rel) for rel, _, _ in edits):
            print(f"  INVALID {name}: the mutation does not parse — not a kill")
            return False
        res = run_tests(tests, extra_env, root)
        killed = res.returncode != 0
        if killed:
            tail = [l for l in res.stdout.splitlines() if l.startswith("FAILED")]
            print(f"  killed  {name}\n            by {tail[0][7:] if tail else '(?)'}")
        else:
            print(f"  SURVIVED {name}")
        return killed == expect_kill
    finally:
        for rel, text in originals.items():
            (root / rel).write_text(text, encoding="utf-8")


def main(mutations, controls, controls_note, root=None):
    """Run a battery. Returns the process exit code: non-zero when any mutation
    survived, or any negative control died.

    A negative control that dies means the property a fixture was built to have
    is not the property it has — a battery that reported that as fine would be
    reporting on a fixture it does not understand. `controls_note` says what
    that particular battery's controls pin, which differs between them, so it is
    the caller's words rather than a generic line.
    """
    survivors = []
    for name, edits, tests, extra_env in mutations:
        if run_entry(name, edits, tests, extra_env, True, root) is not True:
            survivors.append(name)

    controls_bad = []
    for name, edits, tests, extra_env in controls:
        if run_entry(name, edits, tests, extra_env, False, root) is not True:
            controls_bad.append(name)

    print(f"\n{len(mutations) - len(survivors)}/{len(mutations)} mutations killed")
    if survivors:
        print("survivors (a guard no named test depends on):")
        for s in survivors:
            print(f"  - {s}")
    print(f"{len(controls) - len(controls_bad)}/{len(controls)} "
          f"negative controls behaved ({controls_note})")
    for c in controls_bad:
        print(f"  - {c} (expected to survive and did not, or a bad anchor)")
    return 1 if (survivors or controls_bad) else 0
