"""hub.toolchain_store — recording a lane's gap report into the registry.

// spec: mon-tc-01, mon-tc-02, mon-tc-06

The write half of the runner-toolchain capability. `toolchain_requests.py` owns
the vocabulary and the *rules* (what a valid report is, what coverage means);
this module owns the act of turning an accepted report into stored rows. They are
split for the reason `scan_view.py` was split off `monitor.py`: `registry.py` is
at DevGate's own 500-line source hard limit (572 with the feature inline, 493 with
it here), and a file over that limit is a **blocking** `regression_check` failure
in CI, not a warning — the soft-limit list is long and forgiving, the hard-limit
list is one line and stops the commit. So the ~130 lines of gap-recording live
here and `Registry.record_gap_report` is a delegator.

WHY FUNCTIONS OVER DICTS AND NOT A NEW CLASS. `Registry` owns one JSON document
(`self._data`) and the lock that serialises HTTP threads against the monitor
thread; that structure is the thing that makes concurrent identical reports yield
one row, and it must stay there. What moves out is the part that is a pure
function of `(data, runner, submitted, profile_id, now)` — it needs nothing from
the Registry object but those, so it takes exactly those and stays independently
testable. A `class ToolchainStore(self._data)` would have invited a second writer
of the same document with its own idea of when to save, which is the two-owners
failure this repository keeps auditing for.

Everything mon-tc-01 says about *not storing a rejected value* applies to this
module with full force, and it is why no function here takes a message string:
`note_rejection` receives a code drawn from `toolchain_requests`' fixed set, never
the bytes that were refused. The docstring on that function records the draft that
got it wrong.
"""

from __future__ import annotations

from . import toolchain_requests


def next_request_id(data: dict) -> str:
    """tcr-NNNN, one past the highest existing number.

    Derived from the stored rows rather than from a counter field, because a
    counter that drifts from the rows produces duplicate ids on the next restart,
    and duplicate ids are exactly the failure mon-tc-02's (lane, tool) row identity
    exists to prevent. Reading `id` defensively (not every legacy row is ours)
    keeps a foreign collection from raising inside a heartbeat.
    """
    highest = 0
    for row in data.get("toolchain_requests", []):
        ident = row.get("id", "")
        if isinstance(ident, str) and ident.startswith("tcr-"):
            digits = ident[4:].lstrip("0") or "0"
            if digits.isdigit():
                highest = max(highest, int(digits))
    return f"tcr-{highest + 1:04d}"


def find_request(data: dict, lane: str, tool: str) -> dict | None:
    """The row for this (lane, tool), or None. mon-tc-02's row identity."""
    for row in data.get("toolchain_requests", []):
        if row.get("lane") == lane and row.get("tool") == tool:
            return row
    return None


def new_request_row(lane: str, tool: str, profile_id: str | None,
                    now: str, request_id: str) -> dict:
    """One freshly-opened request row, with its first history entry.

    Every terminal field starts None/empty rather than guessed: `state`, `version`
    and the opening audit row are the only facts this moment actually establishes.
    The history entry's shape is fixed by mon-tc-03 (the single-principal v1 limit
    is why `principal` and `credential_id` are None here — an opened request has no
    deciding principal, and inventing one would be the audit trail lying).
    """
    return {
        "id": request_id,
        "lane": lane,
        "tool": tool,
        "required_profile": profile_id,
        "state": "open",
        "version": 1,
        "observed_at": now,
        "last_seen": now,
        "last_reported_at": now,
        "actor": None,
        "principal": None,
        "credential_id": None,
        "decided_at": None,
        "decision_note": None,
        "nonces": [],
        "build_id": None,
        "builder_identity": None,
        "lane_image_digest": None,
        "fulfilled_at": None,
        "suppression_until": None,
        "suppressed_reports": 0,
        "history": [{"seq": 0, "at": now, "actor": None, "principal": None,
                     "credential_id": None, "event": "gap-reported", "from": None,
                     "to": "open", "version_before": None, "version_after": 1,
                     "note": None}],
    }


def record_gap_report(data: dict, runner: dict, submitted: object,
                      profile_id: str | None, now: str) -> tuple[int, str | None]:
    """Record one lane's gap report into `data`. Returns (rows_touched, rejection).

    // spec: mon-tc-01, mon-tc-02

    Validation is all-or-nothing before anything is written, so a partially-valid
    list cannot leave a partial request behind — mon-tc-01 forbids creating or
    updating *any* request once the list is rejected. On rejection the counter for
    that reason advances and nothing else about the submission survives: not the
    bad value, not a prefix of it, not a copy in the audit trail. The heartbeat
    still succeeds (a malformed gap report is a broken gap report, not a dead
    runner — trading a visible health reading for an error would swap a known
    problem for an unknown one), which is why the caller sees a 200 and zero rows.

    ``profile_id`` is the hub's own reviewed assignment for the lane, never a value
    read out of the heartbeat body: mon-tc-01 requires the required profile be
    trusted input. An unreviewed profile id is refused the way a bad tool is,
    because treating "a profile nobody reviewed" as "requires nothing" would report
    a clean lane and hide the gap by construction.

    A report naming a tool the lane's profile does not require is still recorded:
    the lane is reporting a fact about its own image, and a lane whose profile is
    stale or whose image has drifted is worth seeing. Whether it *should* have
    wanted that tool is the operator's call (mon-tc-04), not a reason to discard an
    observation.
    """
    tools, rejection = toolchain_requests.validate_missing_tools(submitted)
    if rejection is not None:
        note_rejection(runner, rejection)
        return 0, rejection
    if not toolchain_requests.is_known_profile(profile_id) or \
            (profile_id is not None and profile_id not in toolchain_requests.PROFILES):
        note_rejection(runner, toolchain_requests.REJECT_UNKNOWN_PROFILE)
        return 0, toolchain_requests.REJECT_UNKNOWN_PROFILE

    collection = data.setdefault("toolchain_requests", [])
    touched = 0
    for tool in toolchain_requests.dedupe(tools):
        row = find_request(data, runner["name"], tool)
        if row is not None:
            # mon-tc-02: a lane whose image never gains the tool re-reports every
            # 300s. The row is not duplicated; last_seen advances and the version
            # stays put, because a re-report is not a transition and mon-tc-04
            # increments the version only on one.
            row["last_seen"] = now
            row["last_reported_at"] = now
            touched += 1
            continue
        collection.append(new_request_row(runner["name"], tool, profile_id, now,
                                          next_request_id(data)))
        touched += 1
    return touched, None


def note_rejection(runner: dict, code: str) -> None:
    """Count a refused gap report by reason, storing nothing else (mon-tc-01).

    The rejected value must not reach a field, a log line, or an audit row. That is
    why this takes only a code: the caller holds the bad bytes and hands over a
    string drawn from a fixed set, so the untrusted value cannot ride in on a
    message. An earlier draft of this helper logged the offending entry "for
    operator triage", which would have written a hostile value into the hub log and
    broken the requirement outright — the reason this function's signature is the
    whole security argument, and why it does not grow a `detail` parameter later.
    """
    counters = runner.setdefault("toolchain_rejections", [])
    for entry in counters:
        if entry.get("code") == code:
            entry["count"] = int(entry.get("count", 0)) + 1
            return
    counters.append({"code": code, "count": 1})


def set_lane_profile(runner: dict, profile_id: str | None,
                     image_ref: str | None = None,
                     image_digest: str | None = None) -> bool:
    """Record the hub's reviewed toolchain assignment for one lane.

    // spec: mon-tc-01

    Operator-only on purpose (P4 exposes it behind the `operator` credential, never
    over the heartbeat channel): the required profile is trusted input, so the spoke
    reporting its gap must not be the thing that chooses it. A lane nobody has
    reviewed stays None, which renders as `profile-unassigned` — a visible question
    rather than a silent "requires nothing", the difference mon-tc-01 insists on.

    An id outside PROFILES is refused rather than stored: a typo would give a lane
    an empty required set, i.e. a permanently clean lane, which is precisely how a
    gap becomes invisible. `image_ref`/`image_digest` are the LANE's toolchain image
    and are distinct from the evaluator `image_digest` on the same runner record;
    two things that would merge into one field if anyone got careless, hence the
    separate names and the separate isolation test.
    """
    if not toolchain_requests.is_known_profile(profile_id) or \
            (profile_id is not None and profile_id not in toolchain_requests.PROFILES):
        return False
    runner["toolchain_profile_id"] = profile_id
    if image_ref is not None:
        runner["lane_image_ref"] = image_ref
    if image_digest is not None:
        runner["lane_image_digest"] = image_digest
    return True


def note_gap_coverage(runner: dict, now: str, probe_complete: bool = True) -> None:
    """Mark that this lane has now spoken about its toolchain (mon-tc-06).

    Called only when a gap field actually arrived — including an accepted empty
    list, which is the positive report "my image has everything this lane requires".
    A heartbeat that OMITS the field must never call this, and it must never clear
    it either: mon-tc-06 asks whether the spoke has *ever* sent a gap field, so a
    later plain heartbeat cannot un-report a lane that reported yesterday. That is
    the reading task 1.5's "byte-identical" clause has to take, and its test asserts
    the direction both ways. `coverage` is stored as `reported` and the `stale`
    overlay is derived at read time by `toolchain_requests.effective_coverage`,
    never written here — a stored `stale` would be stale the instant it was saved.

    ``probe_complete`` is how the runner reaches mon-tc-06's third storable
    state: the requirement defines `probe-failed` by "whether the last probe
    run was incomplete", and its scenario says an incomplete last run makes
    coverage `probe-failed` so the toolchain "is not represented as healthy".
    This parameter is the only way that state can ever be written — the hub
    cannot tell an incomplete probe run from a complete one that found
    everything by counting the list it is sent, so storing `reported` on an
    incomplete run would be absence reported as health wearing health's
    clothes. A spoke predating the probe-outcome channel omits the flag and is
    believed (an old helper is not a failed probe); a spoke with the channel
    sends it whenever it sends the list.
    """
    runner["coverage"] = "reported" if probe_complete else "probe-failed"
    runner["last_gap_report_at"] = now
