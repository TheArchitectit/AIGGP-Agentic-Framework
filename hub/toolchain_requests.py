"""hub.toolchain_requests — the vocabulary, the bounds, and gap validation.

// spec: mon-tc-01, mon-tc-02, mon-tc-06

mon-tc-01 makes the tool vocabulary *spec-governed data*: a name joins it by a
reviewed change to this capability, never by a config edit and never by
something a spoke sends. So the vocabulary lives here as a tuple of literals and
nothing in the hub derives a name, sorts one into a shell word, or counts one
out of a live report.

The whole module is inert data plus pure functions, on purpose. mon-tc-05
forbids any code path in this capability from executing a package manager or
otherwise installing software on a running runner, and the cheapest way to keep
that promise is for the module that owns the tool *names* to have no way to run
a thing. `tests/test_hub_toolchain_requests.py` walks this file's syntax tree
and fails if an execution primitive appears (task 1.7). The scan targets
*execution* rather than the forbidden-looking strings `pip` and `npm`, because
those two are mandated members of the vocabulary above: a scan for the strings
would fail the spec it was written to protect. See the note in tasks.md 1.7.

A rejected report keeps its reason and loses its payload (mon-tc-01: "no byte of
the submitted value appears in any stored field or log line"), so nothing here
formats a submitted value into a message. The codes below are a fixed vocabulary
for the same reason: an operator must be able to tell a typo from an attack from
a broken spoke without reading a value they are not supposed to have.
"""

from __future__ import annotations

# // spec: mon-tc-01
# The vocabulary, as 17 literal names. The count is a comment, never a
# constraint: mon-tc-01 makes the *list* normative and states that where a
# count elsewhere in the package disagrees with the list, the list is right.
# (tasks.md 0.1 asserted "16 names", a value written before `shellcheck` joined
# the list.) An implementation that asserts len() == 16 is a trap that fires on
# the next legitimate addition; a test that the count matches the list is the
# thing that would have caught the original drift, so that test lives in
# tests/, not here.
VOCABULARY: tuple[str, ...] = (
    "cargo",
    "cmake",
    "dotnet",
    "gcc",
    "g++",
    "gitleaks",
    "go",
    "gradle",
    "java",
    "make",
    "maven",
    "node",
    "npm",
    "pnpm",
    "pip",
    "python",
    "shellcheck",
)

# // spec: mon-tc-01
# Profiles are spec-governed data too, and each is a subset of VOCABULARY — the
# test suite asserts that, because a profile naming a non-member would make that
# lane permanently, silently gapful. `rust` names gcc and make because a cargo
# build needs a linker and build.rs scripts need make: the probe checks the
# cargo binary only, so the profile is what makes the compiler a lane
# requirement.
PROFILES: dict[str, tuple[str, ...]] = {
    "none": (),
    "base": ("gcc", "make", "python", "pip"),
    "rust": ("cargo", "gcc", "make"),
    "node": ("node", "npm"),
    "go": ("go",),
    "jvm": ("java", "maven", "gradle"),
    "dotnet": ("dotnet",),
    "web-js": ("node", "npm", "pnpm"),
    "ci-hygiene": ("shellcheck", "gitleaks"),
}

# // spec: mon-tc-01
# The profile's tool list, resolved. A spoke never reads the hub's profile table
# from source, and never guesses its own lane's assignment either: the hub echoes
# THIS list (the tools its own record of the lane requires) on the /heartbeat
# response, and the spoke probes exactly those. Echoing resolved names rather
# than a profile id is what keeps the spoke from owning profile semantics — it
# cannot widen a profile, only measure against what the hub stated. None means
# no reviewed assignment exists (the lane is `profile-unassigned`, and an
# unassigned lane must not be told it requires nothing), () means the reviewed
# answer `none`, which really is nothing.
def required_tools(profile_id: str | None) -> list[str] | None:
    """Tools the lane's profile requires, or None when it has no assignment."""
    if profile_id is None:
        return None
    tools = PROFILES.get(profile_id)
    if tools is None:
        # An id outside the table is refused, never treated as empty (mon-tc-01).
        # Reaching here means stored data drifted from the table; saying "nothing
        # is required" would be the silent-clean answer the spec forbids, so the
        # echo degrades to "no opinion" (absent field) instead.
        return None
    return sorted(tools)


# // spec: mon-tc-01
# The numeric bounds, exactly as mon-tc-01 and mon-tc-06 state them. These are
# spec values: changing one is a change to the capability. A bound an operator
# can dial is a bound nobody gets measured against, which is why the spec fixes
# them rather than reading them from config.
TOOL_PROBE_TIMEOUT_S = 10
MISSING_TOOLS_MAX_ENTRIES = 32
TOOL_REQUEST_STALE_AFTER_S = 900
TOOL_REQUEST_FULFILL_WINDOW_S = 86400
TOOL_REQUEST_SUPPRESSION_DAYS = 14
DECISION_NOTE_MAX_CHARS = 512

# // spec: mon-tc-01
# Rejection reasons. Fixed strings, never a format of the rejected value.
REJECT_NOT_A_LIST = "missing_tools_not_a_list"
REJECT_EMPTY_NOT_ALLOWED = "missing_tools_wrong_type"
REJECT_TOO_MANY = "missing_tools_too_many_entries"
REJECT_NOT_A_STRING = "missing_tools_entry_not_a_string"
REJECT_OUTSIDE_VOCABULARY = "missing_tools_outside_vocabulary"
REJECT_UNKNOWN_PROFILE = "toolchain_profile_unknown"

# // spec: mon-tc-06
# The four coverage states. `probe-failed` is declared now and is not reachable
# until the spoke reports per-tool probe outcomes (S4): a hub cannot tell an
# incomplete probe run from a complete one that found everything, and inventing
# the state early would be exactly the "absence reported as health" error this
# requirement exists to prevent. `stale` is likewise not stored — see
# effective_coverage().
COVERAGE_STATES = ("reported", "never-reported", "stale", "probe-failed")
COVERAGE_UNASSIGNED = "profile-unassigned"


def is_known_profile(profile_id: str | None) -> bool:
    """True when profile_id is a reviewed profile (or the explicit absence of one).

    A lane with no reviewed assignment is `None`, which is a different answer
    from `"none"`: one means the lane requires nothing, the other means nobody
    has decided what it requires. mon-tc-01 requires that the two not render the
    same way, so they are not the same value here either.
    """
    return profile_id is None or profile_id in PROFILES


def validate_missing_tools(submitted: object) -> tuple[list[str], str | None]:
    """All-or-nothing gap validation (mon-tc-01).

    Returns ``(accepted_tools, rejection_code)``. On rejection the tool list is
    empty and no caller may create or update a request; on success the code is
    None. There is no third outcome — a partially-valid list is a rejected list,
    because a spoke that sends one tool it has and one it invented is a spoke
    whose whole report is untrustworthy, and silently dropping the invented half
    would report a smaller gap than the spoke actually believes it has.

    Matching is exact byte comparison, case-sensitive, with no trimming and no
    Unicode normalization. `"cargo "` (trailing space), `"Cargo"` (wrong case)
    and a zero-width character are all rejections rather than near-misses:
    mon-tc-01 spells out that trimming and normalization are the things that
    must not happen, and each one would silently convert an unknown value into a
    stored request.

    The rejected value is never returned and never formatted. It must not reach
    a stored field, a log line, or an audit row, and a function that hands the
    caller back the bad bytes makes that a promise about the caller's hygiene
    rather than about this code.
    """
    if not isinstance(submitted, list):
        return [], REJECT_NOT_A_LIST
    if len(submitted) > MISSING_TOOLS_MAX_ENTRIES:
        # Length first: a 10 MB list of valid names is still a rejected list, and
        # rejecting it should not require validating 10 MB of entries first.
        return [], REJECT_TOO_MANY
    for entry in submitted:
        # bool is an int and an int is not a str; an entry of True must reject as
        # not-a-string, not slip through as a weird member.
        if not isinstance(entry, str):
            return [], REJECT_NOT_A_STRING
        # Membership, not equality-then-normalize. `in` over the tuple is exact
        # byte comparison, which is what the spec asks for; anything that looks
        # like `entry.strip() in VOCABULARY` would violate it.
        if entry not in VOCABULARY:
            return [], REJECT_OUTSIDE_VOCABULARY
    # Accepted: a copy, so a caller mutating its own list cannot reach the
    # registry through the alias. Duplicates are kept here and collapsed at
    # record time (dedupe) rather than silently here, because a list that names
    # `cargo` twice is a different observation from one that names it once — it
    # says the spoke's own probe ran twice — and the validator's job is to say
    # whether the report is trustworthy, not what it means.
    return list(submitted), None


def dedupe(tools: list[str]) -> list[str]:
    """First-occurrence order-preserving de-duplication.

    mon-tc-02 makes a row's identity (lane, tool), so a repeated tool in one
    report must not create a second row: a hub that appended per entry would turn
    a buggy spoke into a backlog of identical requests, each of which an operator
    would have to decide one at a time. Order is preserved so the recorded set is
    byte-stable across re-reports and a diff of two heartbeats shows a real change
    rather than a shuffle.
    """
    seen: set[str] = set()
    out: list[str] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            out.append(tool)
    return out


def gap_for_profile(
    profile_id: str | None, observed_present: list[str] | None
) -> list[str]:
    """Required-minus-observed, the spoke-side rule, exposed for testability.

    // spec: mon-tc-01

    The spoke computes the gap (task 4.1) and the hub only validates what
    arrives; this helper exists so the *rule* is spec-side and testable without a
    runner image, and so the F4 defect — diffing against the whole vocabulary and
    reporting a permanent gap on every stock lane — cannot be reintroduced by an
    operator-side script copying from the spec.

    An unknown observed state is not `absent` and not `present` (mon-tc-01): a
    probe that could not complete does not create a request, so an `unknown`
    entry is absent from ``observed_present`` and also from the gap. Pass the
    probe's `present` set only.
    """
    if observed_present is None:
        return []
    required = PROFILES.get(profile_id or "", ())
    present = set(observed_present)
    return [tool for tool in required if tool not in present]


def effective_coverage(runner: dict) -> str:
    """The lane's coverage state, computed rather than stored (mon-tc-06).

    // spec: mon-tc-06

    `stale` is deliberately *derived at read time*. A stored `stale` is a lie the
    moment the next heartbeat arrives but before anyone re-renders the field, and
    a lane whose spoke died would read as reported for exactly as long as nobody
    looked. Deriving it makes "when did this lane last speak?" un-rottable.

    `probe-failed` is returned only if something stored it; until the spoke
    reports probe outcomes (S4) nothing writes it, and this function does not
    invent it from a missing field — that would be absence read as a verdict.
    """
    stored = runner.get("coverage")
    if stored == "probe-failed":
        return "probe-failed"
    if stored != "reported":
        return "never-reported"
    last = runner.get("last_gap_report_at")
    if _age_seconds(last) > TOOL_REQUEST_STALE_AFTER_S:
        return "stale"
    return "reported"


def outstanding_reason(request: dict) -> str | None:
    """Why this request is OVERDUE, or None when nothing is overdue.

    // spec: mon-tc-06

    One question, because the spec makes two and conflating them is how a queue
    becomes unreadable:

      * **visible** — mon-tc-06's "SHALL remain visible in the request set until
        it reaches `fulfilled` or `denied`". That is `is_visible(request)` below:
        `open`, `approved` and `built` are all visible.
      * **overdue** — mon-tc-06's "An `approved` request not built within the
        fulfillment window SHALL be reported as outstanding with its age". Only
        that case, plus the `built` analogue, is overdue.

    An `open` request is visible and NOT overdue: nobody has decided anything yet,
    so there is no commitment to miss. Returning a reason for it would make every
    freshly-reported gap look stuck, and an operator who has seen a hundred false
    alarms stops reading the queue — which is the same failure as hiding it, wearing
    an alert.

    Approval alone is never progress: mon-tc-05 requires build evidence and a later
    converging heartbeat, so `approved` and `built` are reported as distinct states
    and never collapsed into one "in flight" word.
    """
    state = request.get("state")
    window_h = TOOL_REQUEST_FULFILL_WINDOW_S / 3600.0
    if state == "approved":
        decided_at = request.get("decided_at")
        if _age_seconds(decided_at) == float("inf"):
            # An approved row with no readable decision time is not "approved a
            # moment ago" and it is not settled. Formatting `inf h ago` would put a
            # fake number in an operator's sentence, and a row that unreadable is
            # more likely a broken transition than a stuck build — so the sentence
            # names the missing field instead of guessing a duration from it.
            return ("approved, decision timestamp missing or unparseable; cannot "
                    f"age it against the {window_h:.0f}h fulfillment window")
        age_h = _age_seconds(decided_at) / 3600.0
        if age_h > window_h:
            return (f"approved {age_h:.1f}h ago, no build report "
                    f"(window {window_h:.0f}h)")
        return None
    if state == "built":
        if _age_seconds(request.get("last_seen")) == float("inf"):
            return ("built, last-seen timestamp missing or unparseable; cannot say "
                    "how long the converging heartbeat has been outstanding")
        age_h = _age_seconds(request.get("last_seen")) / 3600.0
        if age_h > window_h:
            return (f"built {age_h:.1f}h ago, no converging heartbeat "
                    f"(window {window_h:.0f}h)")
        return None
    if state in ("open", "fulfilled", "denied"):
        # open: visible, not overdue. fulfilled/denied: settled, per the spec's
        # own words about what ends visibility.
        return None
    # Anything else — a misspelled state, a state a future transition invents —
    # is overdue by default. Saying None would make an unrecognised state read as
    # settled, and "settled" is the one word that takes a request off a screen.
    return f"state {state!r} is not a state this capability defines"


def is_visible(request: dict) -> bool:
    """Whether this request belongs in the operator's set (mon-tc-06).

    Separate from `outstanding_reason` on purpose: `open` is visible without being
    overdue, and a denied request stays visible while its suppression window runs
    (mon-tc-04 reopens it after the window, and an operator has to be able to see
    the reopen happen). Writing one predicate for both questions is how a queue
    either hides fresh gaps or cries wolf about them.
    """
    return request.get("state") in ("open", "approved", "built", "denied")


def _age_seconds(iso: str | None) -> float:
    """Seconds since an ISO-8601 UTC stamp; unknown stamps are infinitely old.

    A missing or unparseable stamp returns infinity rather than 0. Reading a
    corrupt timestamp as "just now" makes a dead lane look fresh, which is the
    failure mode mon-tc-06 exists to prevent; reading it as ancient is the
    conservative direction and is visible as such.
    """
    if not isinstance(iso, str) or not iso:
        return float("inf")
    from datetime import datetime, timezone

    text = iso.rstrip("Z") + "+00:00" if iso.endswith("Z") else iso
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return float("inf")
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds())
