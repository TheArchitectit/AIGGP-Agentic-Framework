# // spec: mon-tc-01, mon-tc-02, mon-tc-06
"""hub.registry_observations — the Registry's write-side observation methods.

Extracted from `hub/registry.py` for one reason and one reason only: that file
crossed DevGate's 500-line source hard limit (512 on 2026-11-08, when the
Windows-spoke enrollment landed) and the release gate refuses to ship a file
over it. This is a MOVE, not a rewrite: every method below is byte-for-byte the
text that lived in `Registry`, and `Registry` inherits this mixin first, so
`registry.note_gap_coverage(...)` and friends resolve exactly as before, with
the same MRO position relative to `ToolchainRegistryMixin`.

The seam keeps the split honest: `toolchain_store` owns the rules and the
writing, `Registry` owns resolution by name / persistence, and these methods
are the thin join between the two. `_now_iso` moved with them because every one
of them stamps a time and nothing else in `registry.py` uses it — importing it
back is cheaper than duplicating a clock.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import toolchain_store


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ObservationsMixin:
    """Gap-report, lane-profile and coverage writes, applied by runner name."""

    def record_gap_report(self, runner_name: str, submitted: object,
                          profile_id: str | None) -> tuple[int, str | None]:
        """Record one lane's gap report. Returns (rows_touched, rejection_code).

        // spec: mon-tc-01, mon-tc-02

        The rules and the writing live in `toolchain_store` (registry.py is at
        DevGate's 500-line source hard limit, which is why this method and the
        three below live in `registry_observations`); this is the Registry seam,
        and the only thing it adds is resolution by name, which is Registry's
        job. See the module docstring and `record_gap_report`'s own for why a
        rejected report keeps its reason and loses its payload, and why the
        heartbeat still 200s.
        """
        runner = self.find_runner(runner_name)
        if runner is None:
            return 0, "unknown_runner"
        return toolchain_store.record_gap_report(
            self._data, runner, submitted, profile_id, _now_iso())

    def note_rejection(self, runner_name: str, code: str) -> None:
        """Count a refused gap report by reason, storing nothing else (mon-tc-01)."""
        runner = self.find_runner(runner_name)
        if runner is not None:
            toolchain_store.note_rejection(runner, code)

    def set_lane_profile(self, runner_name: str, profile_id: str | None,
                         image_ref: str | None = None,
                         image_digest: str | None = None) -> bool:
        """Record the hub's reviewed toolchain assignment for one lane.

        // spec: mon-tc-01

        Operator-only: the required profile is trusted input, so the spoke
        reporting a gap must not choose it, and an unreviewed id is refused rather
        than stored (a typo would produce a permanently clean lane). The lane's
        toolchain image fields are distinct from the evaluator `image_digest` on the
        same record, on purpose and as a test.
        """
        runner = self.find_runner(runner_name)
        if runner is None:
            return False
        return toolchain_store.set_lane_profile(
            runner, profile_id, image_ref, image_digest)

    def note_gap_coverage(self, runner_name: str,
                          probe_complete: bool | None = None) -> None:
        """Mark that this lane has now spoken about its toolchain (mon-tc-06).

        Called only when a gap field actually arrived — an accepted empty list
        counts, it is the positive report "my image has everything this lane
        requires". A heartbeat that OMITS the field must never call this, and this
        never clears a prior report either: mon-tc-06 asks whether the spoke has
        *ever* sent a gap field, so a later plain heartbeat cannot un-report a lane
        that reported yesterday. `stale` is derived at read time, never written.

        ``probe_complete`` decides between the two storable coverage states this
        method can write: `reported` and `probe-failed`. `False` is the spoke
        saying "my probe run did not complete", which mon-tc-06 defines as
        `probe-failed` — and an incomplete run reporting nothing is precisely the
        case where storing `reported` would render absence as health. `None` is
        not "incomplete" and not "complete", it is *no opinion*: a spoke predating
        the probe-outcome field, which is not a failed probe, so it stays believed.
        """
        runner = self.find_runner(runner_name)
        if runner is not None:
            toolchain_store.note_gap_coverage(
                runner, _now_iso(),
                probe_complete if probe_complete is not None else True)
