# // spec: coh-int-07 — the runbook layer is part of the S6 operational
# closure this line demanded ("migration guide + operator runbook"); this
# file is what keeps its claims from rotting into prose.
"""Runbook claim-pinning: the docs under `docs/runbooks/` are operational
promises, so the parts of them a test can check get checked.

Three claim classes, chosen because each has already rotted somewhere in
this repo's history (a runbook citing a dead exit code is worse than none):

1. **Behavior coverage.** The S6 line names four behaviors — outage,
   mirror (pinned image), cached-attestation, protocol-mismatch — and
   each must have a NAMED HOME: a runbook file containing anchor strings
   only that behavior's docs should carry. An anchor list is written OUT
   here (importing it from anywhere would let it shrink in silence).
2. **Exit-code truth.** Every coherence exit code cited in a runbook
   (`exit 3x`/`exit 40`/`exit 20`/`exit 10` — the watchdog's 0/1 are
   spoke-script codes, not coherence codes, so the range separates them
   cleanly) must equal the constant `hub/coherence/result.py` defines,
   read live from the module rather than transcribed.
3. **Migration anchors + index integrity.** The migration guide's named
   units, paths, and function must exist verbatim in the scripts it
   points at, and README.md's table must index exactly the runbook files
   on disk, each with a non-empty scenario column.

Dual-runnable: pytest collects test_*; `python3 tests/test_runbook_claims.py`
runs them too.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNBOOKS = REPO / "docs" / "runbooks"
sys.path.insert(0, str(REPO))

from hub.coherence import result as coh_result  # noqa: E402

# S6's four behaviors -> (file, anchors). Each anchor must appear verbatim
# in that file. Written out deliberately: if a runbook is deleted or its
# behavior section renamed, the named file/string fails the test by name.
BEHAVIOR_HOMES = {
    "outage": ("hub-outage.md",
               ["HUB UNREACHABLE", "polling_enabled", "watchdog-dead-hub-exit-1"]),
    "mirror": ("image-pin-and-protocol.md",
               ["image drift", "digest**, not the tag", "Pinned by"]),
    "cached-attestation": ("evidence-and-attestation.md",
                           ["decision_cache_key", "cache_entry_valid",
                            "TTL **and** retention"]),
    "protocol-mismatch": ("image-pin-and-protocol.md",
                          ['error.class: "protocol"', "exit 40", "SUPPORTED_API"]),
}

# Codes result.py exports, as cited prose must match them exactly.
CITED = {10: "EXIT_ADVISORY", 20: "EXIT_FAIL", 30: "EXIT_INVALID_INPUT",
         31: "EXIT_POLICY", 32: "EXIT_EXECUTION", 33: "EXIT_EVIDENCE",
         40: "EXIT_PROTOCOL"}

MIGRATION_FILE = "migration-fixed-name-to-per-runner-units.md"
MIGRATION_ANCHORS = {
    "scripts/lib/runner-units.sh": [
        "remove_legacy_units",
        "devgate-heartbeat.service",
        "devgate-heartbeat.timer",
        "devgate-hub-watchdog.service",
        "devgate-hub-watchdog.timer",
        "devgate-hb-",
        "devgate-watchdog-",
        "devgate-imgcycle-",
        "devgate-secretscan-",
        "$HOME/.devgate-heartbeat.env",
        "RUNNER_NAME=",
        "timers.target.wants",
    ],
    "scripts/runner-enroll.sh": [
        "remove_legacy_units",
        "--revoke",
        "--runner-name",
    ],
}


def _runbook_texts():
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(RUNBOOKS.glob("*.md"))}


def test_each_s6_behavior_has_a_named_runbook_home():
    texts = _runbook_texts()
    assert texts, f"no runbooks found under {RUNBOOKS}"
    for behavior, (fname, anchors) in BEHAVIOR_HOMES.items():
        assert fname in texts, \
            f"behavior {behavior!r} names {fname}, which is not on disk"
        for anchor in anchors:
            assert anchor in texts[fname], \
                f"{fname} lost the anchor {anchor!r} that documents " \
                f"behavior {behavior!r}"


def test_cited_coherence_exit_codes_match_result_constants():
    """Any 'exit NN' in a runbook that is in the coherence code range must
    equal result.py's constant — the table is read live, not transcribed.
    Watchdog codes 0/1 are outside the cited set on purpose: they are the
    spoke script's, not the evaluator's."""
    texts = _runbook_texts()
    checked = 0
    for name, text in texts.items():
        if name == "README.md":
            continue
        for m in re.finditer(r"exit (10|20|3[0-3]|40)\b", text):
            code = int(m.group(1))
            actual = getattr(coh_result, CITED[code])
            assert actual == code, \
                f"{name} cites exit {code} but result.{CITED[code]} is " \
                f"{actual} — docs and code disagree"
            checked += 1
    assert checked >= 2, \
        f"only {checked} coherence exit citations across all runbooks — " \
        "the gate would pass vacuously; docs dropped their codes or the " \
        "pattern no longer matches them"


def test_migration_guide_anchors_exist_in_the_scripts():
    assert (RUNBOOKS / MIGRATION_FILE).is_file(), \
        f"the S6 migration guide ({MIGRATION_FILE}) is missing entirely"
    for script, anchors in MIGRATION_ANCHORS.items():
        text = (REPO / script).read_text(encoding="utf-8")
        for anchor in anchors:
            assert anchor in text, \
                f"{MIGRATION_FILE} names '{anchor}' (per {script}) but " \
                f"{script} no longer contains it — the guide is stale"


def test_readme_indexes_every_runbook_with_a_scenario():
    """A runbook that exists but is not indexed is undiscoverable; an
    indexed file that does not exist is a broken operator path. Both
    directions, plus scenario-column non-emptiness."""
    readme = (RUNBOOKS / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\|\s*\[[^\]]+\.md\]\(\./([^)]+)\)\s*\|\s*([^|]+)\|",
                      readme, re.MULTILINE)
    assert rows, "README has no runbook table rows to check"
    indexed = {link for link, _scenario in rows}
    on_disk = {p.name for p in RUNBOOKS.glob("*.md")} - {"README.md"}
    assert indexed == on_disk, \
        f"README index and disk disagree: only-indexed={indexed - on_disk} " \
        f"only-on-disk={on_disk - indexed}"
    for link, scenario in rows:
        assert scenario.strip(), f"{link} is indexed with an empty scenario"


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))


if __name__ == "__main__":
    main()
