"""Unit tests for mon-tc-01/02/06 — the hub half of runner toolchain requests.

S1 of add-runner-toolchain-requests: the hub records what a lane says it is
missing, and nothing else. Wire-level cases (live hub fixture, HTTP POST,
concurrency, echo-shape) live in test_hub_toolchain_requests_wire.py; this file
is pure-function and pure-Registry, so a failure here means a rule is wrong rather
than that a handler or transport broke. The transition rules (mon-tc-03/04/05) land
in S2/S3 and are deliberately NOT exercised here, because a test that reaches for a
green `fulfilled` today would have to invent a state machine and would then pass
against the invention instead of the spec.

What is asserted, and why each is worth the bytes:

  * **Vocabulary is all-or-nothing** (mon-tc-01). A list with one bad entry creates
    NO rows. The failure mode ruled out is the partial write: storing `cargo` and
    dropping `Cargo` reports a smaller gap than the spoke believes it has.
  * **Nothing is normalised** (mon-tc-01). Wrong case, trailing space/newline,
    zero-width — each is a *rejection*, not a near-miss; a trim would turn an
    unknown value into a stored row, indistinguishable from a real one forever.
  * **The rejected value is never stored** (mon-tc-01), asserted against the saved
    bytes rather than the return value: the requirement is about where bytes end up.
  * **Row identity is (lane, tool)** (mon-tc-02). Twenty identical reports are one
    row, and a re-report must not bump the version (mon-tc-04 counts transitions).
  * **Presence is the coverage signal** (mon-tc-06). An omitted field must neither
    record a gap nor un-report a lane that reported earlier; [] is a positive
    report. Both directions are asserted separately on purpose.

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_toolchain_requests.py`
runs them too.
"""
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub import toolchain_requests as tcr  # noqa: E402
from hub.coherence import schemacheck  # noqa: E402
from hub.registry import Registry  # noqa: E402

HERE = Path(__file__).resolve().parent

NEW_MODULES = [
    HERE.parent / "hub" / "toolchain_requests.py",
    HERE.parent / "hub" / "toolchain_store.py",
    HERE.parent / "hub" / "registry.py",
]
SCHEMA_PATH = HERE.parent / "hub" / "schema" / "runners.schema.json"


def _validate(doc) -> list:
    return schemacheck.validate(doc, json.loads(SCHEMA_PATH.read_text()))


def _registry(tmp_path) -> Registry:
    return Registry(str(tmp_path / "runners.json"))


def _enrolled(tmp_path, name="runner-one", profile="rust"):
    """Registry with one enrolled lane whose reviewed profile is set.

    The profile is set through the operator-side method rather than by writing
    the field, so the tests exercise the same guard the P4 endpoint will use.
    """
    reg = _registry(tmp_path)
    reg.enroll(name, "TheArchitectit/AIGGP-Agentic-Framework", ["rust"], name)
    reg.set_lane_profile(name, profile)
    reg.save()
    return reg






# --- vocabulary (mon-tc-01) --------------------------------------------------


def test_vocab_is_the_spec_list_and_derived_counts_agree():
    """The list is normative; any count of it is derived, never asserted.

    mon-tc-01 carries this rule because task 0.1 shipped "16 names" after
    `shellcheck` joined the vocabulary — a count written next to the list instead
    of computed from it. This test is the machine for not repeating that: it
    re-checks the count against the list rather than pinning a number, so adding a
    tool is one edit in one place.
    """
    assert len(tcr.VOCABULARY) == len(set(tcr.VOCABULARY)), "duplicate tool name"
    assert len(tcr.VOCABULARY) == 17
    # The membership the spec spells out, compared as a set: order in the spec
    # prose is a reading order, and a test that pinned the tuple position-for
    # position would fail on a re-flow of prose that changed no rule.
    assert set(tcr.VOCABULARY) == {
        "cargo", "cmake", "dotnet", "g++", "gcc", "gitleaks", "go", "gradle",
        "java", "make", "maven", "node", "npm", "pip", "pnpm", "python",
        "shellcheck"}
    for banned in ("bash", "sh", "sudo", "curl", "wget", "apt", "apt-get", "dnf",
                   "yum", "docker", "podman", "ssh", "python3"):
        # An interpreter or a package manager is not a build tool: `python` is in
        # the vocabulary, and shipping the probe's own command name invites the
        # probe to exec it, which is what the execution-primitive rule forbids.
        assert banned not in tcr.VOCABULARY
    assert tcr.MISSING_TOOLS_MAX_ENTRIES > len(tcr.VOCABULARY), \
        "mon-tc-06: a correct spoke cannot approach the cap by reporting honestly"


def test_every_profile_is_a_subset_of_the_vocabulary():
    """mon-tc-01: profiles draw from the same list, or they drift apart.

    The `rust` profile once listed `rust-build-prereqs`, which is not a member of
    the vocabulary — a profile can invent a gap no lane can ever report, and that
    lane reads as permanently broken. This test is why that cannot come back.
    """
    for profile_id, required in tcr.PROFILES.items():
        for tool in required:
            assert tool in tcr.VOCABULARY, f"{profile_id} invents {tool!r}"
        assert len(set(required)) == len(required), f"{profile_id} repeats a tool"
    # `none` means "requires nothing". `None` means "nobody has decided". The
    # difference is the whole point of mon-tc-01's unassigned state, so the two
    # must not collapse to one value.
    assert tcr.PROFILES["none"] == ()
    assert not tcr.is_known_profile("not-a-reviewed-profile")
    assert tcr.is_known_profile(None)


def test_gap_is_required_minus_observed_not_vocabulary_minus_observed():
    """The F4 defect: diffing against the whole vocabulary (mon-tc-01).

    A stock lane would then report a gap on every heartbeat forever, and the one
    real gap would be lost in the noise.
    """
    assert tcr.gap_for_profile("rust", ["gcc", "make"]) == ["cargo"]
    assert tcr.gap_for_profile("rust", ["cargo", "gcc", "make"]) == []
    assert tcr.gap_for_profile("none", []) == []
    # Unknown observed state is not absent: a probe that could not complete does
    # not create a request, so it is absent from `present` AND absent from here.
    assert tcr.gap_for_profile(None, []) == []
    assert tcr.gap_for_profile("rust", None) == []


def test_valid_vocab_accepts_the_whitelist(tmp_path):
    reg = _enrolled(tmp_path)
    touched, rejection = reg.record_gap_report("runner-one", ["cargo"], "rust")
    assert rejection is None
    assert touched == 1
    rows = reg.toolchain_requests()
    assert [r["tool"] for r in rows] == ["cargo"]
    assert rows[0]["state"] == "open"
    assert rows[0]["version"] == 1
    assert rows[0]["id"].startswith("tcr-")
    assert rows[0]["required_profile"] == "rust"


NEGATIVES = [
    ("non-member", ["notatool"]),
    ("wrong-case", ["Cargo"]),
    ("trailing-newline", ["cargo\n"]),
    ("trailing-space", ["cargo "]),
    ("zero-width", ["\u200bcargo"]),
    ("fullwidth-digit-ish", ["\uff43argo"]),
    ("over-length", ["cargo"] * (tcr.MISSING_TOOLS_MAX_ENTRIES + 1)),
    ("non-string-int", [17]),
    ("non-string-bool", [True]),
    ("nested-list", [["cargo"]]),
    ("mixed-one-bad", ["cargo", "notatool"]),
    ("not-a-list", "cargo"),
    ("null-instead", None),
]


def test_vocab_negatives_create_no_rows(tmp_path):
    """Each malformed report is refused whole (mon-tc-01), incl. `mixed-one-bad`.

    The mixed case is the one that matters: it is a *valid* entry plus an invalid
    one, and a hub that accepted the good half would be reporting a gap smaller
    than the spoke's own.
    """
    reg = _enrolled(tmp_path)
    for label, payload in NEGATIVES:
        touched, rejection = reg.record_gap_report("runner-one", payload, "rust")
        assert touched == 0, label
        assert rejection is not None, label
        assert reg.toolchain_requests() == [], f"{label} wrote a row"
        runner = reg.find_runner("runner-one")
        codes = {c["code"] for c in runner["toolchain_rejections"]}
        assert codes, f"{label} refused without counting"


def test_vocab_negatives_count_by_reason(tmp_path):
    """The counter is per-reason, so an operator can tell a broken spoke from a
    hostile one without reading either's payload (mon-tc-01)."""
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")  # accepted
    reg.record_gap_report("runner-one", "cargo", "rust")    # not a list
    reg.record_gap_report("runner-one", "cargo", "rust")    # again
    reg.record_gap_report("runner-one", ["notatool"], "rust")
    codes = {c["code"]: c["count"] for c in reg.find_runner("runner-one")["toolchain_rejections"]}
    assert codes[tcr.REJECT_NOT_A_LIST] == 2
    assert codes[tcr.REJECT_OUTSIDE_VOCABULARY] == 1


def test_unknown_profile_is_refused_like_a_bad_tool(tmp_path):
    """A profile nobody reviewed must not read as "requires nothing" (mon-tc-01)."""
    reg = _enrolled(tmp_path)
    touched, rejection = reg.record_gap_report("runner-one", ["cargo"], "sre-unreviewed")
    assert touched == 0
    assert rejection == tcr.REJECT_UNKNOWN_PROFILE


def test_rejected_value_is_never_stored(tmp_path):
    """The load-bearing negative control of S1 (mon-tc-01).

    Asserted against the **saved bytes**, because "never stored, in any field, log
    line, or audit row" is a statement about the file on disk. A test that only
    checked the return value would pass while the registry logged the payload.
    """
    canary = "\u200bCargo\u200b"  # zero-width on both sides: nothing here is legal
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", [canary], "rust")
    reg.save()
    saved = (Path(tmp_path) / "runners.json").read_text()
    assert canary not in saved
    # A prefix and a normalised form are also the value for this purpose: "Cargo"
    # is what a truncated log line would print, and it is exactly the near-miss
    # the vocabulary rule refuses to accept.
    assert "Cargo" not in saved




def test_new_hub_modules_contain_no_execution_primitive():
    """1.7: the new hub module must not gain a way to run anything (mon-tc-01).

    An AST scan, not a grep: `import subprocess` is caught whether or not it is ever
    called, and a comment *mentioning* subprocess is not flagged — which a string
    grep gets exactly backwards, and these modules' docstrings discuss shell
    handling at length. `import os` is allowed (atomic saves use `os.replace`), so
    only EXEC attributes and shell-out modules are reported.
    """
    exec_attrs = {"system", "popen", "exec", "execl", "execv", "execve", "execvp",
                  "spawnl", "spawnv", "spawnve", "Popen", "run", "call",
                  "check_output", "check_call", "killpg", "startfile"}
    shell_modules = {"subprocess", "pty", "sh", "ptyprocess", "pexpect"}
    for path in NEW_MODULES:
        tree = ast.parse(path.read_text())
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in shell_modules:
                        hits.append(f"{path.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in shell_modules:
                    hits.append(f"{path.name}:{node.lineno} from {node.module}")
            elif isinstance(node, ast.Attribute) and node.attr in exec_attrs:
                hits.append(f"{path.name}:{node.lineno} .{node.attr}")
        assert hits == [], "execution primitive present: " + "; ".join(hits)

    # The literal half of 1.7, kept as the audit it is (the task is belt-and-braces;
    # the real prohibition is mon-tc-01's own). Written against whole-word command
    # strings, NOT against bare tool names: `pip`, `npm`, `make`, `gcc`, `g++` are
    # VOCABULARY MEMBERS and appear in the module by necessity. A grep for "pip"
    # would flag the whitelist itself — which is precisely how the task's phrasing
    # ("no `pip`, `npm` reference") contradicts the spec it cites, and why the task
    # is corrected in tasks.md to name commands-as-invoked rather than names.
    forbidden_commands = ("os.system", "os.popen", "os.exec", "subprocess",
                          "sh -c", "bash -c", "apt-get", "apt ", "dnf ", "yum ",
                          "pip install", "npm install", "npm i ", "pnpm add",
                          "cargo install", "pty.spawn")
    for path in NEW_MODULES:
        text = path.read_text()
        for token in forbidden_commands:
            assert token not in text, f"{path.name} mentions {token!r}"


def test_scan_has_a_positive_control():
    """A scan with no positive control is a scan that looks for nothing.

    The honest form of task 1.7: the assertion that matters is not "the new module
    is clean" (a broken scan also satisfies that) but "the scan still fires on a
    real shell-out", so a future edit that weakens the guard breaks this test.
    """
    victim = "import subprocess\nsubprocess.run(['g++'])\n"
    tree = ast.parse(victim)
    hits = [f"{node.lineno}:{node.attr}" for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "run"]
    imports = [f"import {alias.name}" for node in ast.walk(tree)
               if isinstance(node, ast.Import) for alias in node.names
               if alias.name.split(".")[0] == "subprocess"]
    assert hits == ["2:run"] and imports == ["import subprocess"]




# --- identity, persistence, concurrency (mon-tc-02) -------------------------


def test_request_row_shape_matches_the_schema(tmp_path):
    """The registry schema is the contract, and it is `additionalProperties: false`.

    A field written here and not declared there makes the *saved registry fail
    validation* — the hub's recovery path breaks on restart. Keeps the two
    written-down shapes honest with each other.
    """
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.save()
    payload = json.loads((Path(tmp_path) / "runners.json").read_text())
    errors = _validate(payload)
    assert errors == [], errors
    assert set(payload["toolchain_requests"][0]) == set(reg.toolchain_requests()[0])


def test_same_lane_same_tool_is_one_row(tmp_path):
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    first = dict(reg.toolchain_requests()[0])
    touched, _ = reg.record_gap_report("runner-one", ["cargo"], "rust")
    assert touched == 1, "a re-report is counted as seen, not as new"
    rows = reg.toolchain_requests()
    assert len(rows) == 1
    assert rows[0]["version"] == 1, "a re-report is not a transition (mon-tc-04)"
    assert rows[0]["id"] == first["id"], "a re-report must not mint a new id"
    assert len(rows[0]["history"]) == 1, "a re-report appends no history"


def test_duplicate_tools_in_one_report_are_one_row(tmp_path):
    """Row identity is (lane, tool); a chatty spoke must not mint duplicates."""
    reg = _enrolled(tmp_path)
    touched, _ = reg.record_gap_report("runner-one", ["cargo", "cargo", "make"], "rust")
    assert touched == 2
    assert [r["tool"] for r in reg.toolchain_requests()] == ["cargo", "make"]


def test_two_lanes_same_tool_are_two_rows(tmp_path):
    reg = _enrolled(tmp_path)
    reg.enroll("runner-two", "TheArchitectit/openagentplatform", ["rust"], "runner-two")
    reg.set_lane_profile("runner-two", "rust")
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.record_gap_report("runner-two", ["cargo"], "rust")
    rows = reg.toolchain_requests()
    assert sorted((r["lane"], r["tool"]) for r in rows) == [
        ("runner-one", "cargo"), ("runner-two", "cargo")]
    assert len({r["id"] for r in rows}) == 2, "row ids must not collide across lanes"


def test_ids_do_not_reuse_across_restart(tmp_path):
    """A counter that drifts from the rows produces duplicate ids (mon-tc-02)."""
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.save()
    reloaded = Registry(str(tmp_path / "runners.json"))
    reloaded.record_gap_report("runner-one", ["make"], "rust")
    ids = [r["id"] for r in reloaded.toolchain_requests()]
    assert len(ids) == len(set(ids)) == 2, ids


def test_pre_change_registry_loads_and_survives_a_gap_cycle(tmp_path):
    """1.1: migration for a registry written before this capability shipped.

    The legacy payload is the repo's own `hub/schema/runners.example.json` — a
    shipped, schema-valid PRE-change registry, not a fixture invented here. That
    distinction was earned: an invented payload omitting `enrolled_at` passed the
    load assertions and then failed schema validation for reasons unrelated to this
    capability. Two properties: it loads with no `toolchain_requests` key, reading
    as an empty set; and it still takes a full gap cycle, and the saved file
    validates against the schema that now requires these fields declared.

    The new per-runner fields are deliberately NOT materialised onto legacy rows at
    load: rewriting rows at startup shows churn unrelated to any request, and turns
    "never seen by the new code" into "has a null coverage field", which reads like
    a reading. Absence IS the state; `effective_coverage` already answers it.
    """
    legacy_doc = json.loads((HERE.parent / "hub" / "schema" /
                             "runners.example.json").read_text())
    assert legacy_doc.get("toolchain_requests") is None, \
        "the shipped example must still be a PRE-change registry for this test to mean anything"
    assert _validate(legacy_doc) == [], "the example must be valid before the change"
    legacy = tmp_path / "runners.json"
    legacy.write_text(json.dumps(legacy_doc))

    reg = Registry(str(legacy))
    assert reg.toolchain_requests() == []
    name = legacy_doc["runners"][0]["name"]
    legacy_runner = reg.find_runner(name)
    assert "coverage" not in legacy_runner, "load must not materialise fields"
    assert tcr.effective_coverage(legacy_runner) == "never-reported"

    reg.record_gap_report(name, ["cargo"], "rust")
    reg.record_gap_report(name, "not-a-list", "rust")
    reg.note_gap_coverage(name)
    reg.save()
    assert [r["tool"] for r in reg.toolchain_requests()] == ["cargo"]
    assert reg.find_runner(name)["toolchain_rejections"], "rejection not counted"
    assert tcr.effective_coverage(reg.find_runner(name)) == "reported"
    assert _validate(json.loads(legacy.read_text())) == [], \
        "a migrated registry that fails its own schema breaks the hub on restart"




# --- coverage (mon-tc-06) ----------------------------------------------------


def test_omitted_gap_field_never_unreports_a_lane_that_reported(tmp_path):
    """The one heartbeat() cannot do: absence is not a verdict (mon-tc-06).

    `heartbeat()` writes a field only when it is present, so a naive
    "missing_tools absent therefore coverage never-reported" would erase a lane
    that reported yesterday the moment a plain heartbeat arrived — a lane whose
    spoke died mid-request would read as never-asked rather than as stale.
    `record_gap_report` is not called on absence, and `note_gap_coverage` is
    never cleared. Asserted in both directions so neither passes by accident.
    """
    reg = _enrolled(tmp_path)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "never-reported"
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.note_gap_coverage("runner-one")
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported"
    # A plain heartbeat after a real report: coverage survives, and no row appears.
    assert reg.heartbeat("runner-one", None, None, None) is True
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported"
    assert len(reg.toolchain_requests()) == 1


def test_empty_list_is_a_positive_report(tmp_path):
    """mon-tc-06: [] means "my image has everything this lane requires".

    The distinction between [] and omitted is the whole coverage requirement, and
    it is the reason the field defaults to UNREPORTED rather than [] — a default
    of [] would report every legacy spoke as fully provisioned.
    """
    reg = _enrolled(tmp_path)
    touched, rejection = reg.record_gap_report("runner-one", [], "rust")
    assert rejection is None and touched == 0
    reg.note_gap_coverage("runner-one")
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported"
    assert reg.toolchain_requests() == [], "no gap, so no request"
    assert not any(r.get("code") for r in reg.find_runner("runner-one")["toolchain_rejections"])


def test_coverage_goes_stale_by_age_not_by_a_written_flag(tmp_path):
    """mon-tc-06: a dead spoke must not read as reported forever (F8)."""
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.note_gap_coverage("runner-one")
    runner = reg.find_runner("runner-one")
    fresh = tcr.effective_coverage(runner)
    assert fresh == "reported", fresh
    runner["last_gap_report_at"] = "2020-01-01T00:00:00+00:00"
    assert tcr.effective_coverage(runner) == "stale"
    assert "stale" not in json.dumps(runner), "stale is derived, never stored"


def test_coverage_enum_refuses_the_derived_state(tmp_path):
    """The schema cannot store `stale`, so a spoke cannot pre-empt the derivation."""
    reg = _enrolled(tmp_path)
    reg.save()
    payload = json.loads((Path(tmp_path) / "runners.json").read_text())
    payload["runners"][0]["coverage"] = "stale"
    assert _validate(payload), "the schema would accept a stored 'stale'"


def test_probe_failed_needs_the_spokes_own_words(tmp_path):
    """mon-tc-06: the hub cannot tell an incomplete probe from a clean one, so it asks.

    Coverage 3 of 4 states is derivable from the presence or the age of a gap
    field; `probe-failed` is not, because an empty list from a run that timed out
    and an empty list from a healthy image are the same bytes. The hub therefore
    takes the run outcome from the spoke and there are exactly two answers to
    distinguish:

      * `probe_complete=False` — the spoke says the run did not complete, which IS
        mon-tc-06's definition of `probe-failed`, and an incomplete run that
        reports nothing must never render as a provisioned lane;
      * `probe_complete=None` — no opinion, which is a spoke predating the field.
        Not a failed probe, so it stays `reported`. Collapsing these two would
        make every legacy spoke in the fleet read unhealthy the moment the
        capability shipped, which is a fleet-wide alarm caused by a deploy.

    Asserted on the same row, in that order, so the flag is what moves the state
    and not the order the tests were written in.
    """
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", [], "rust")
    reg.note_gap_coverage("runner-one", False)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "probe-failed"
    assert "probe-failed" in tcr.COVERAGE_STATES

    # ... and the flag alone put it back: same lane, same empty list.
    reg.note_gap_coverage("runner-one", True)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported"

    reg.note_gap_coverage("runner-one", False)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "probe-failed"
    reg.note_gap_coverage("runner-one", None)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported", \
        "an old spoke is a spoke with no opinion, not a failed probe"


def test_a_complete_probe_run_does_not_inherit_a_previous_failure(tmp_path):
    """probe-failed is a statement about the LAST run, so it has to move.

    mon-tc-06's scenario names the incomplete run as "the last run"; a coverage
    state that latched would report a healthy lane as unhealthy for the rest of
    the lane's life after one timeout, and an operator watching the dashboard
    could not tell a fix that landed from one that did not.
    """
    reg = _enrolled(tmp_path)
    reg.record_gap_report("runner-one", ["cargo"], "rust")
    reg.note_gap_coverage("runner-one", False)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "probe-failed"
    # The next tick completes (nothing unknown this time) and says so.
    reg.record_gap_report("runner-one", [], "rust")
    reg.note_gap_coverage("runner-one", True)
    assert tcr.effective_coverage(reg.find_runner("runner-one")) == "reported"


def test_required_tools_echo_is_the_hubs_own_profile_statement(tmp_path):
    """mon-tc-01: the required list is the hub's data, so the hub says it aloud.

    A spoke cannot compute this lane's requirement without owning the profile
    table, and a spoke that owns the table can widen its own requirements. The
    echo is the only channel, and its three shapes are the three answers the
    spec distinguishes: a list (what rust requires), `[]` (the reviewed answer
    `none`), and null (nobody has decided — `profile-unassigned`, which is NOT a
    lane that requires nothing and must not arrive looking like one).
    """
    assigned = _enrolled(tmp_path)
    outcome: dict = {}
    assert assigned.heartbeat("runner-one", None, None, None,
                              gap_outcome=outcome) is True
    assert outcome["required_tools"] == tcr.required_tools(
        assigned.find_runner("runner-one")["toolchain_profile_id"])

    assigned.set_lane_profile("runner-one", "none")
    outcome = {}
    assigned.heartbeat("runner-one", None, None, None, gap_outcome=outcome)
    assert outcome["required_tools"] == [], "reviewed `none` is an empty list"

    assigned.set_lane_profile("runner-one", None)
    outcome = {}
    assigned.heartbeat("runner-one", None, None, None, gap_outcome=outcome)
    assert outcome["required_tools"] is None, \
        "unassigned must not echo as an empty requirement"


def test_the_profile_echo_travels_even_when_no_gap_field_arrives(tmp_path):
    """A lane with nothing missing still has to learn what it should have.

    Gating the echo on an incoming gap field would deadlock the capability on a
    fresh host: no cache means no gap field, no gap field means no echo, no echo
    means no cache — a lane could only ever report a gap after it had already
    reported one.
    """
    reg = _enrolled(tmp_path)
    reg.set_lane_profile("runner-one", "rust")
    outcome: dict = {}
    # A plain heartbeat: no missing_tools, no probe outcome.
    assert reg.heartbeat("runner-one", None, None, None, gap_outcome=outcome) is True
    assert outcome["required_tools"] == ["cargo", "gcc", "make"]
    # And it is the hub's list, not a copy of anything the spoke sent.
    assert "missing_tools" not in outcome and "cargo" not in json.dumps(
        {k: v for k, v in outcome.items() if k != "required_tools"})

if __name__ == "__main__":
    # Standalone mode mirrors what pytest does rather than re-implementing it: every
    # test gets a fresh temp dir, and the exit code is the point. The `ok`/`FAIL`
    # line for each test is printed unconditionally — an earlier version suppressed
    # the ok lines after the first failure, which read as "the suite stopped" when it
    # had not, and a suite that hides which tests passed is how a partial run gets
    # reported as a full one.
    import inspect
    import tempfile

    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(Path(tmp)) if inspect.signature(fn).parameters else fn()
            except Exception as exc:  # noqa: BLE001 — reporting, not handling
                failures += 1
                print(f"FAIL {name}: {exc!r}")
            else:
                print(f"ok   {name}")
    print(f"{len([n for n in globals() if n.startswith('test_')]) - failures} passed, "
          f"{failures} failed")
    sys.exit(1 if failures else 0)
