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

Three misreports are guarded against here rather than left to be noticed, all
three having been observed on the hosted lane:

  * a stale anchor filed as a survivor (`survivors (a guard no named test
    depends on)` — the wrong diagnosis, and the same exit code, so only the
    report can carry the difference),
  * two batteries on one tree interleaving, each capturing its "original" from
    the other's mutant and restoring faithfully to it, so both runs' verdicts
    are worthless while every per-entry check passes,
  * a run that leaves a mutant applied, which the per-entry restores cannot see
    and which makes the NEXT run's anchors and verdicts read off a tree that is
    not the one under test.

The second and third are why a battery takes a `flock` and hashes its artifacts
before it starts; `tests/test_mutation_harness.py` drives each failure against a
synthetic repository whose outcome is known by construction, including an
injected non-restoring entry.

Kept out of the `test_*.py` namespace so pytest's collection stays about the
product; the batteries are a separate, slower, self-mutating lane.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import workflow_read

REPO = Path(__file__).resolve().parent.parent

# Hermetic: an ambient git identity or config could change how a test that
# shells out to git behaves (this bit the re-pin suite once).
ENV = dict(os.environ,
           HOME="/nonexistent-devgate-mutation",
           XDG_CONFIG_HOME="/nonexistent-devgate-mutation",
           GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")


def well_formed(path):
    """True when the mutated artifact is still readable. False means INVALID.

    All the artifact languages the batteries touch are here rather than only the
    one this file's original copy happened to need: a mutation that leaves a
    syntax error makes the test command exit non-zero for a reason that has
    nothing to do with a test catching anything, so it must be rejected before
    any verdict is read.

    "Readable" is per language and deliberately not overstated. Python is
    compiled, shell is checked by `bash -n`, JSON by `json.loads` — all real
    parsers. YAML is checked by the reader the workflow guards themselves use
    (`tests/workflow_read.py`), so what this returns for a workflow is exactly
    "the guards can still read it", which is the property that decides whether a
    mutation is evaluable at all.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            json.loads(text)
            return True
        except Exception:
            return False
    if path.suffix in (".yml", ".yaml"):
        # The same reader the workflow guards use, not PyYAML: the hosted lane
        # installs only pytest, so `import yaml` here would raise on every
        # mutation and report each one as INVALID. "Well formed" is therefore
        # stated precisely — the construct set the guards depend on is still
        # readable — rather than claimed to be a YAML parse.
        try:
            workflow_read.read_workflow(text)
            return True
        except workflow_read.WorkflowReadError:
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


class BatteryInProgress(RuntimeError):
    """Another battery holds this tree. Refused, not queued."""


@contextlib.contextmanager
def battery_lock(root):
    """One battery per tree at a time, across processes.

    A battery mutates tracked files in place, so two concurrent runs each
    capture their "original" from whatever the other has already left behind —
    and each then restores faithfully to the *other's* mutant while every
    per-entry check passes. Measured: a concurrent run produced three phantom
    anchor misses and credited kills to unrelated tests, and both runs' verdicts
    were worthless. That is also the shape of this session's unexplained
    anomaly, where three mutants were found applied on disk with verdicts
    derived from the mutated tree.

    Keyed by the resolved root, so a battery against a copy of the tree is
    independent (it shares no files) while two runs against the same tree
    contend. Refusing rather than blocking: a battery takes minutes, and a
    silently serialised run is indistinguishable from a slow one.
    """
    key = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]
    path = Path(tempfile.gettempdir()) / f"devgate-mutation-{key}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BatteryInProgress(
                f"another battery is already running against {root} — refusing "
                "rather than interleaving, which would corrupt both runs' "
                "verdicts. Wait for it, or run against a copy of the tree.")
        yield
    finally:
        os.close(fd)


def artifact_hashes(root, rels):
    """sha256 of each named file, for a baseline taken before any mutation."""
    out = {}
    for rel in rels:
        path = Path(root) / rel
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest() \
            if path.is_file() else None
    return out


def verify_hashes(root, baseline):
    """The names that differ from the baseline.

    Verified against a hash taken before the battery started rather than
    against the text an entry captured as it went: an entry that captures its
    "original" from an already-mutated tree restores to that mutant and every
    per-entry check passes. Only a baseline has the vantage point to see it.
    """
    return sorted(rel for rel, want in baseline.items()
                  if artifact_hashes(root, [rel])[rel] != want)


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

    Three things are reported apart from each other because they need three
    different responses: a killed mutation is the guard holding, a *survivor*
    says a guard has no test and the test is missing, and a *stale anchor* says
    the mutation never applied at all and it is the anchor that needs re-pointing
    — filing the last two together sends the reader to write a test that answers
    a question nobody asked. All three non-zero exits are the same code; the
    distinction lives in the report, which is why it is asserted.
    """
    root = root or REPO
    artifacts = sorted({rel for _, edits, _, _ in [*mutations, *controls]
                        for rel, _, _ in edits})
    try:
        with battery_lock(root):
            return _run_battery(mutations, controls, controls_note, root, artifacts)
    except BatteryInProgress as exc:
        print(f"  REFUSED {exc}")
        return 1


def _run_battery(mutations, controls, controls_note, root, artifacts):
    baseline = artifact_hashes(root, artifacts)

    survivors, stale = [], []
    for name, edits, tests, extra_env in mutations:
        verdict = run_entry(name, edits, tests, extra_env, True, root)
        if verdict is None:
            stale.append(name)
        elif verdict is not True:
            survivors.append(name)

    controls_bad = []
    for name, edits, tests, extra_env in controls:
        if run_entry(name, edits, tests, extra_env, False, root) is not True:
            controls_bad.append(name)

    drifted = verify_hashes(root, baseline)

    print(f"\n{len(mutations) - len(survivors) - len(stale)}/{len(mutations)} "
          f"mutations killed")
    if survivors:
        print("survivors (a guard no named test depends on):")
        for s in survivors:
            print(f"  - {s}")
    if stale:
        print("stale anchors (the mutation never applied — re-point the anchor; "
              "a new test would not help):")
        for s in stale:
            print(f"  - {s}")
    print(f"{len(controls) - len(controls_bad)}/{len(controls)} "
          f"negative controls behaved ({controls_note})")
    for c in controls_bad:
        print(f"  - {c} (expected to survive and did not, or a bad anchor)")
    if drifted:
        # The harness's own failure, not a verdict about the code: every entry
        # restored what it captured, and the tree still does not match the
        # baseline it started from.
        print("HARNESS FAILURE — mutations left applied, vs the baseline taken "
              "before this battery started:")
        for rel in drifted:
            print(f"  - {rel}")
    return 1 if (survivors or stale or controls_bad or drifted) else 0
