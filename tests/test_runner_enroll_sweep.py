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

  * The declaration path is expanded by SYSTEMD from the EnvironmentFile, not
    left as whatever enroll's shell held. Both halves are asserted against the
    generated UNIT. The failure is measured rather than described, because the
    first version of this paragraph described it wrong: with the escaping
    removed, an UNSET ambient variable makes enroll abort under `set -u`
    ("unbound variable") and no unit is written at all — loud, and not the
    "expands to the empty string while enrollment reports success" that was
    claimed. The silent case is an ambient variable that IS set: enroll
    succeeds and freezes that value into the unit, where the runner's env file
    can no longer reach it.

  * The timer is enabled by PROVISIONING, like the image cycle's: units land on
    disk either way, and an unprovisioned host gets no running timer. A sweep
    with no declaration exits 3 — a unit failing every tick is noise, and noise
    is how the alert that matters gets ignored.

Separate file rather than more lines in `test_runner_enroll.py`. An earlier
revision of this line said `test_runner_enroll.py` was "at the hard limit for
test files", which was wrong: test files are limited at 600 lines
(`TEST_HARD` in scripts/regression_sizes.py), so neither file was near a limit.
The split is still the right shape — one file per installed unit reads better
than one long file — but the reason is room, not a gate.

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
    expanded by enroll's own shell while the unit is being written, and what
    lands on disk is a literal path rather than the token systemd expands."""
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    service, _ = s.fleet_units("alpha")
    text = service.read_text()

    exec_lines = [l for l in text.splitlines() if l.startswith("ExecStart=")]
    assert len(exec_lines) == 1, text
    exec_line = exec_lines[0]
    assert f"${DECLARED_KEY}" in exec_line, (
        f"the declaration is not left for systemd to expand — enroll's shell "
        f"expanded it instead: {exec_line!r}")
    # The bare-path rule, pinned for the heartbeat and the cycle and (until the
    # battery's F10 existed to falsify it) only asserted here: systemd
    # substitutes $ in ExecStart against the unit's own environment before any
    # shell runs, so an inline body loses the variables the body itself defines
    # — incident #1, FAIL-6e7b6f84.
    assert "bash -c" not in exec_line, (
        f"an inline shell body loses the variables it defines itself (incident "
        f"#1): {exec_line!r}")
    assert str(s.fleet_helper()) in exec_line, exec_line


def test_an_ambient_declaration_is_not_baked_into_the_unit(tmp_path):
    """The hazard the escaping actually prevents, and the one no test covered.

    Measured, four ways, against the real enroll: with ambient UNSET an
    unescaped `$SECRET_SCAN_DECLARED` makes enroll abort (`set -u`, "unbound
    variable") and no unit is written — loud. With ambient SET it is silent and
    worse: enroll succeeds and the ambient path is frozen into the unit as a
    literal, where no later edit to the runner's env file can reach it, so the
    sweep runs against whatever path the operator's shell happened to carry at
    enrollment time. On a host where that path exists, the sweep that runs is
    not the one the env file declares — and nothing reports it.

    That is why the escape is the guard and `bash -c` is not: an inline body
    (incident #1) loses its own variables, and this loses the host's.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    ambient = tmp_path / "ambient-declared.txt"
    ambient.write_text("https://example.test/ambient/repo.git\n")
    s.env[DECLARED_KEY] = str(ambient)

    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    service, _ = s.fleet_units("alpha")
    exec_line = next(l for l in service.read_text().splitlines()
                     if l.startswith("ExecStart="))
    assert str(ambient) not in exec_line, (
        "the ambient declaration was baked into the unit at write time, where "
        f"the runner's env file can no longer change it: {exec_line!r}")
    assert f"${DECLARED_KEY}" in exec_line, (
        f"the unit does not defer the declaration to systemd: {exec_line!r}")

    # Non-vacuity, and the second half of the property: an ambient variable is
    # not provisioning. The key is read from the runner's env file, which has
    # none — so a host that merely exports it must still get no running timer.
    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
    assert "secretscan" not in " ".join(s.systemctl_calls()), \
        "an ambient variable was read as provisioning and enabled the sweep"


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


def test_the_gate_is_on_the_declaration_being_usable_not_on_the_key_existing(tmp_path):
    """One property, two operator mistakes that must reach the same verdict: a
    key naming a file that has since been deleted, and a key left with no value
    at all. The variable being set is not the same as the sweep being able to
    run, so the gate tests the FILE (`-s`) rather than the key's presence — and
    the mutant that swaps one for the other is separated by the missing-file
    case, not by the empty one.

    They are one test because they are one branch, `[[ ! -s "$declared" ]]`.
    Kept apart, the second asserted nothing the first did not — the same
    unkillable-second-guard shape the shell comment next to that condition
    records deleting, one slice earlier.
    """
    for case, value in (("deleted", str(tmp_path / "gone.txt")), ("blank", "")):
        (tmp_path / case).mkdir()          # Spoke homes are made without parents
        s = Spoke(tmp_path / case)
        assert s.enroll("alpha").returncode == 0

        res = _provision(s, "alpha", value)
        assert res.returncode == 0, res.stderr
        # Non-vacuity: without this, "no secretscan in the systemctl calls" is
        # also true of a host where the sweep was never installed at all.
        assert s.fleet_units("alpha")[1].is_file(), \
            "the timer unit is absent, so 'it was not enabled' proves nothing"

        calls = " ".join(s.systemctl_calls())
        assert "secretscan" not in calls, \
            f"the sweep was enabled with a {case} declaration: {calls}"
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


def test_a_declaration_naming_no_repository_does_not_enable_the_timer(tmp_path):
    """The third way a declaration can be unusable, and the one that used to
    pass: a file that exists, is non-empty, and names nothing — every line
    blank or a `#` comment.

    It has to be refused here rather than left to the sweep, because the sweep
    exits 3 on it: enabling the timer buys a unit that fails on every tick, and
    on a dashboard that is indistinguishable from a sweep that ran and found
    nothing. The two readers must agree on this file, so the scope of the check
    is exactly the sweep's own rule (strip at the first `#`, drop whitespace,
    skip if nothing is left) and no further.
    """
    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0

    empty_of_repos = tmp_path / "declared.txt"
    empty_of_repos.write_text("# the fleet, to be filled in\n\n   \n# TODO\n")
    res = _provision(s, "alpha", str(empty_of_repos))
    assert res.returncode == 0, res.stderr

    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
    assert "secretscan" not in " ".join(s.systemctl_calls()), (
        "a declaration naming no repository was read as provisioning, so the "
        f"sweep was enabled to exit 3 on every tick:\n{empty_of_repos.read_text()}")
    assert "NOT enabled" in res.stdout, res.stdout


def test_an_indented_url_is_read_as_the_sweep_reads_it(tmp_path):
    """The two readers of the declaration file must agree, in BOTH directions.

    `secret-scan-fleet.sh` strips each line at its first `#` and then removes
    every whitespace character, so `  https://…  ` is a repository to it. A
    check here written as `^[^#[:space:]]` — the obvious shorter form, and the
    one a review proposed — would refuse that line, and enroll would report a
    provisioned sweep as NOT enabled while the sweep itself would have scanned
    the fleet: the same false negative the quoted-path strip exists to prevent,
    in the other direction.

    Asserted by asking BOTH readers about the same file: enroll must enable the
    timer, and the installed sweep must accept the declaration and exit 0.
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
    declared.write_text(f"   file://{origin}   # indented, with a trailing note\n")

    res = _provision(s, "alpha", str(declared))
    assert res.returncode == 0, res.stderr
    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
    assert "secretscan" in " ".join(s.systemctl_calls()), (
        "enroll refused a declaration the sweep reads as one repository — the "
        f"two readers disagree:\n{declared.read_text()}")

    # The other reader, on the same file.
    work = tmp_path / "work"
    work.mkdir()
    swept = s.run_fleet_helper("alpha", declared, "--work", str(work))
    assert swept.returncode == 0, (
        f"the sweep refused the declaration enroll accepted (rc={swept.returncode}):\n"
        f"{swept.stdout}\n{swept.stderr}")


def test_a_quoted_declaration_path_is_read_as_systemd_reads_it(tmp_path):
    """enroll parses the EnvironmentFile itself, so its reader is a second
    reader of a file systemd also reads — and where they diverge, a provisioned
    sweep is silently left disabled.

    Measured divergence: systemd unquotes a value, so
    `SECRET_SCAN_DECLARED="/tmp/a b/declared.txt"` is a line it reads and runs
    perfectly. enroll resolved the literal string including the quotes, found no
    such file, and left the timer off on a host whose operator had provisioned
    it — defeating, one step earlier, exactly the whitespace case the ExecStart's
    own quoting exists to defend.

    The boundary is asserted too: this is one matching pair of quotes, not an
    EnvironmentFile parser. A trailing comment is not emulated, and the message
    prints the value it read, which is where the operator can see it.
    """
    spaced = tmp_path / "with space"
    spaced.mkdir()
    declared = spaced / "declared.txt"
    declared.write_text("https://example.test/owner/repo.git\n")

    s = Spoke(tmp_path)
    assert s.enroll("alpha").returncode == 0
    env = s.env_file("alpha")
    env.write_text(env.read_text()
                   + f'{DECLARED_KEY}="{declared}"\n')
    res = s.enroll("alpha")
    assert res.returncode == 0, res.stderr

    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
    assert "secretscan" in " ".join(s.systemctl_calls()), (
        "a quoted declaration path containing a space was read with its quotes "
        "still on it, so enroll saw a file that does not exist and left the "
        f"sweep disabled — while systemd reads that line fine:\n{env.read_text()}")


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
    # Non-vacuity, as in the two tests above: without this, "no secretscan in
    # the systemctl calls" is equally true of a host where the sweep does not
    # exist — this was the only test in the file that survived deleting it.
    assert s.fleet_units("alpha")[1].is_file(), \
        "the timer unit is absent, so 'it was not enabled' proves nothing"
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
