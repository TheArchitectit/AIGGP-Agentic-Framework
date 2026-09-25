"""The fleet secret sweep's place on a runner host (Sprint 5.2).

`runner-enroll.sh` already installs two helpers and two timers per runner: the
heartbeat, and the evaluator-image cycle. This is the third — the periodic
sweep that answers "is there a credential in a repository we own that nobody
has pushed to in months" — and it is installed the same way, for the same
reason: the sweep has to run on a host that is up, not on the developer's
laptop.

Three properties are load bearing, and the first two are why this file exists
rather than a line in the enroll suite:

  * BOTH scripts are copied, not just the sweep. `secret-scan-fleet.sh` locates
    the gate as `dirname $0/secret-scan.sh` — a checkout copy of the sweep with
    no gate beside it dies at its own precondition on every tick, which is a
    host that looks enrolled and sweeps nothing.

  * The declaration path is expanded by SYSTEMD from the EnvironmentFile, not by
    enroll's shell. This is the same family as incident #1 (the inline `bash -c`
    ExecStart) and it fails the same silent way: an unescaped `$SECRET_SCAN_
    DECLARED` in the heredoc expands to the empty string at write time, the unit
    runs `--declared` with no argument, and every tick exits 3 while enrollment
    reports success. It is asserted against the generated UNIT, not described.

  * The timer is enabled by PROVISIONING, like the image cycle's: units land on
    disk either way, and an unprovisioned host gets no running timer. A sweep
    with no declaration exits 3 — a unit failing every tick is noise, and noise
    is how the alert that matters gets ignored.

Separate file rather than more lines in `test_runner_enroll.py`, which is at
the hard limit for test files; the honest response to that gate is to stop
growing the file rather than to move the limit.

Dual-runnable: pytest collects test_*; `python3 tests/test_runner_enroll_sweep.py`
runs them too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.runner_spoke import Spoke, slug  # noqa: E402

DECLARED_KEY = "SECRET_SCAN_DECLARED"


def _provision(s, runner, declared):
    """Add the declaration to the runner's env file the way an operator does,
    then re-enroll. The key is not one enroll owns, so it survives — which is
    the contract `test_reenroll_preserves_hand_added_provisioning_lines` pins
    for the image cycle's variables."""
    env = s.env_file(runner)
    assert env.exists(), "the env file must exist before it can be provisioned"
    env.write_text(env.read_text() + f"{DECLARED_KEY}={declared}\n")
    return s.enroll(runner)


# --- both helpers are installed ---------------------------------------------

def test_the_sweep_and_the_gate_it_needs_are_both_installed(tmp_path):
    """The sweep resolves the gate as `dirname $0/secret-scan.sh`. Copying only
    the sweep installs a helper that dies at its own precondition every tick."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    fleet, gate = s.fleet_helper(), s.gate_helper()
    assert fleet.is_file(), f"the sweep helper was not installed: {fleet}"
    assert gate.is_file(), (
        "the gate the sweep resolves as a sibling was not installed — the "
        "helper would die with 'the gate script is not beside this one'")
    assert fleet.parent == gate.parent, "the two are not beside each other"


def test_the_installed_helpers_are_the_repository_scripts(tmp_path):
    """Copied, not referenced in place: an ExecStart pointing into the checkout
    is the shape that broke when the checkout moved, and the shape that cannot
    be fixed on the host without a re-enroll."""
    from tests.fixtures.runner_spoke import REPO_ROOT

    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    for installed, source in (
        (s.fleet_helper(), REPO_ROOT / "scripts" / "secret-scan-fleet.sh"),
        (s.gate_helper(), REPO_ROOT / "scripts" / "secret-scan.sh"),
    ):
        assert installed.read_bytes() == source.read_bytes(), \
            f"{installed} is not a copy of {source}"


def test_the_installed_sweep_can_actually_run(tmp_path):
    """The end-to-end check, and the one that is not a file comparison.

    It exists because a test that compared the two installed files' presence,
    parent directory and BYTES passed while the sweep died on every tick: the
    sweep resolves its gate as `$(dirname $0)/secret-scan.sh`, and enroll was
    installing it under a different name. Co-located, byte-identical, and
    unreachable — which is why this runs the installed helper over a real
    repository instead of reading it.
    """
    import subprocess

    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    s.stub_gitleaks()

    origin = tmp_path / "origin"
    origin.mkdir()
    git = ["git", "-c", "user.email=a@b", "-c", "user.name=a"]
    subprocess.run([*git, "init", "-q", "."], cwd=origin, check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"],
                   cwd=origin, check=True)

    declared = tmp_path / "declared.txt"
    declared.write_text(f"file://{origin}\n")
    work = tmp_path / "work"
    work.mkdir()
    res = s.run_fleet_helper("alpha", declared, "--work", str(work))

    assert "is not beside this one" not in res.stdout + res.stderr, (
        "the sweep could not find the gate beside itself — the helper is "
        f"installed under the wrong name:\n{res.stdout}\n{res.stderr}")
    assert res.returncode == 0, (
        f"the installed sweep did not run to completion (rc={res.returncode}):\n"
        f"{res.stdout}\n{res.stderr}")


# --- the units ---------------------------------------------------------------

def test_the_sweep_units_are_named_for_the_runner(tmp_path):
    """Two runners on one host must not share a sweep, for the same reason they
    do not share a heartbeat: one declaration, one token file, one host that
    reports as the other."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    assert s.enroll("beta").returncode == 0

    for runner in ("alpha", "beta"):
        service, timer = s.fleet_units(runner)
        assert service.is_file(), f"no sweep service for {runner}: {service}"
        assert timer.is_file(), f"no sweep timer for {runner}: {timer}"
        assert slug(runner) in service.name and slug(runner) in timer.name


def test_the_declaration_path_is_expanded_by_systemd_not_by_enroll(tmp_path):
    """The heredoc is unquoted, so an unescaped `$SECRET_SCAN_DECLARED` is
    expanded by enroll's shell — where it is unset — and the unit is written
    with `--declared` and no argument. Every tick then exits 3 (bad invocation)
    while enrollment reports success, which is incident #1's shape exactly."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    service, _ = s.fleet_units("alpha")
    text = service.read_text()

    exec_lines = [l for l in text.splitlines() if l.startswith("ExecStart=")]
    assert len(exec_lines) == 1, text
    exec_line = exec_lines[0]
    assert f"${DECLARED_KEY}" in exec_line, (
        f"the declaration is not left for systemd to expand — enroll's shell "
        f"expanded it to nothing instead: {exec_line!r}")
    assert "bash -c" not in exec_line, (
        "an inline shell body loses the variables it defines itself (incident "
        f"#1): {exec_line!r}")
    assert str(s.fleet_helper()) in exec_line, exec_line


def test_the_sweep_reads_the_runner_s_own_environment_file(tmp_path):
    """One EnvironmentFile per runner (design D3.1): the declaration lives
    beside the token, so it is that runner's declaration and not the host's."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    service, _ = s.fleet_units("alpha")
    text = service.read_text()
    assert f"EnvironmentFile={s.env_file('alpha')}" in text, text


# --- enabled by provisioning, not by enrollment ------------------------------

def test_the_sweep_is_not_enabled_without_a_declaration(tmp_path):
    """A sweep with no declaration exits 3 by design. Enabling its timer anyway
    would put a failing unit on every host that has never been provisioned."""
    s = Spoke(tmp_path)
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    service, timer = s.fleet_units("alpha")
    assert service.is_file() and timer.is_file(), \
        "the units should be on disk even when the sweep is not enabled"

    calls = " ".join(s.systemctl_calls())
    assert "secretscan" not in calls, \
        f"an unprovisioned host started the sweep timer: {calls}"
    assert "NOT enabled" in res.stdout, (
        "enrollment did not say the sweep was left disabled, so an operator "
        f"has no signal that it is not running:\n{res.stdout}")

    # The unit file IS the artifact here: `systemctl --user enable` on a timer
    # with no [Install] section is an error, and the systemctl stub exits 0 for
    # everything, so only reading the file pins it.
    assert "[Install]" in timer.read_text() and \
        "WantedBy=timers.target" in timer.read_text(), timer.read_text()


def test_the_sweep_is_enabled_once_a_declaration_is_provisioned(tmp_path):
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    declared = tmp_path / "declared.txt"
    declared.write_text("https://example.test/owner/repo.git\n")
    res = _provision(s, "alpha", str(declared))
    assert res.returncode == 0, res.stderr

    calls = " ".join(s.systemctl_calls())
    timer = s.fleet_units("alpha")[1].name
    assert f"enable {timer}" in calls, f"the sweep timer was not enabled: {calls}"
    assert f"start {timer}" in calls, f"the sweep timer was not started: {calls}"


def test_a_declaration_naming_a_missing_file_does_not_enable_the_timer(tmp_path):
    """The variable being set is not the same as the sweep being able to run.
    Enabling here produces a unit that exits 3 on every tick, which reads on a
    dashboard exactly like a sweep that found nothing."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    res = _provision(s, "alpha", str(tmp_path / "gone.txt"))
    assert res.returncode == 0, res.stderr
    # Non-vacuity: without this, "no secretscan in the systemctl calls" is also
    # true of a host where the sweep was never installed at all.
    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"

    calls = " ".join(s.systemctl_calls())
    assert "secretscan" not in calls, \
        f"the sweep was enabled with a declaration that does not exist: {calls}"
    assert "NOT enabled" in res.stdout, res.stdout


def test_an_empty_declaration_does_not_enable_the_timer(tmp_path):
    """`SECRET_SCAN_DECLARED=` is a key with no value — the operator edited the
    file and left it blank, or a provisioning step failed halfway."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    res = _provision(s, "alpha", "")
    assert res.returncode == 0, res.stderr
    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
    assert "secretscan" not in " ".join(s.systemctl_calls()), s.systemctl_calls()
    assert "NOT enabled" in res.stdout, res.stdout


def test_a_duplicated_declaration_resolves_to_the_last_one(tmp_path):
    """systemd's EnvironmentFile is last-assignment-wins, so a host where the
    operator appended a corrected line must be judged on the corrected line —
    reading the first would refuse to enable a sweep that systemd would run
    perfectly, and (read the other way) enable one pointing at a dead path."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    good = tmp_path / "declared.txt"
    good.write_text("https://example.test/owner/repo.git\n")
    env = s.env_file("alpha")
    # The stale line first, the corrected one second — systemd's order.
    env.write_text(env.read_text()
                   + f"{DECLARED_KEY}={tmp_path / 'gone.txt'}\n"
                   + f"{DECLARED_KEY}={good}\n")
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    assert "secretscan" in " ".join(s.systemctl_calls()), (
        "the sweep was judged on the stale first line while systemd would "
        f"have used the corrected last one:\n{env.read_text()}")


def test_a_commented_out_declaration_does_not_enable_the_timer(tmp_path):
    """`#SECRET_SCAN_DECLARED=/path` is how an operator turns the sweep off
    without losing the path. systemd ignores it, so enroll must too — a grep
    that is not anchored to the start of the line would read it as a live
    declaration and enable a sweep the operator just disabled."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    good = tmp_path / "declared.txt"
    good.write_text("https://example.test/owner/repo.git\n")
    env = s.env_file("alpha")
    env.write_text(env.read_text() + f"#{DECLARED_KEY}={good}\n")
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    assert "secretscan" not in " ".join(s.systemctl_calls()), (
        "a commented-out declaration was read as a live one and enabled the "
        f"sweep the operator had just turned off:\n{env.read_text()}")


def test_provisioning_the_sweep_survives_a_reenroll(tmp_path):
    """The declaration is an operator's, not enroll's — a routine re-enroll over
    a working host must not disable the sweep it was running."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    declared = tmp_path / "declared.txt"
    declared.write_text("https://example.test/owner/repo.git\n")
    assert _provision(s, "alpha", str(declared)).returncode == 0

    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr
    env = s.env_file("alpha").read_text()
    assert f"{DECLARED_KEY}={declared}" in env, (
        "re-enrolling dropped the declaration, so the next tick's timer would "
        f"be left enabled with nothing to sweep:\n{env}")
    assert "secretscan" in " ".join(s.systemctl_calls()), \
        "the sweep was not re-enabled after a re-enroll of a provisioned host"


def test_the_sweep_units_are_not_left_behind_by_revoke(tmp_path):
    """Revoke removes the units it owns. A leftover sweep timer on a revoked
    runner keeps scanning with a declaration the operator believes is gone."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    service, timer = s.fleet_units("alpha")
    assert service.is_file() and timer.is_file()

    res = s.revoke("alpha")
    assert res.returncode == 0, res.stderr
    assert not service.exists(), f"revoke left the sweep service behind: {service}"
    assert not timer.exists(), f"revoke left the sweep timer behind: {timer}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
