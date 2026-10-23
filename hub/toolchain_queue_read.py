"""hub.toolchain_queue_read — the request set as a queue consumes it.

// spec: mon-tc-02

mon-tc-02 says the hub SHALL expose the request set, and forbids Mission Control
from keeping a copy to join against. Put those two sentences together and they
decide this module's shape: a row's identity is not enough, because the consumer
has nowhere else to ask what the lane *is*. `repo` and `host_alias` live on the
hub's runner record, and `coverage` is derived at read time by mon-tc-06 —
neither can be reconstructed by a process that may not store either.

So this is a read-time projection, and the word that matters is **read-time**.
Nothing here is written to a row. The row remains the only stored record of the
request, and the annotations exist only in the response. Had they been copied
onto the row, the hub would have become the thing mon-tc-02 forbids everyone
else: a second copy that can disagree with the runner record after a re-enroll.

`_unknown` names what the hub genuinely does not know, and it is `None` rather
than `""` or `"never-reported"` on purpose. An empty repository renders as a
blank cell that looks like a lane with no repository; a defaulted coverage state
asserts the lane never reported when the truth is that the hub has no runner
record for it at all. Absence and a negative verdict are different facts, and
mon-tc-06 built its whole vocabulary on keeping them apart.

A row whose lane has no runner record is handled and *is* still exposed: the
request happened, and a queue that drops rows it cannot decorate loses the rows
an operator most needs to see. Reaching that state needs an unusual registry —
today the hub never removes a runner record (`revoke` marks `enrolled=False` and
clears the verifier, `hub/registry.py:417-425`), so it arrives via a registry
restored from a partial backup or a future revoke that truly drops — which is
exactly the kind of defensive branch that rots into a lie if it is described as
a live path. It is described here as a robustness case, and the unit test says
the same thing the code can prove.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import toolchain_requests

if TYPE_CHECKING:
    from .registry import Registry

#: Every field a queue needs to render a row and act on it, over and above the
#: row's own keys. Listed as data so the contract is one visible list rather than
#: a shape inferable only by reading a loop body — and so a test can assert the
#: whole list against a live read instead of spot-checking two fields.
QUEUE_FIELDS = ("repository", "host_alias", "coverage_state")


def annotate_requests(rows: list[dict], registry: "Registry") -> list[dict]:
    """Copy `rows` and add `QUEUE_FIELDS`, resolved against the lane's runner.

    Returns new dicts. The rows in the registry are never mutated: this runs
    under the caller's lock in the HTTP layer, and a mutation there would turn a
    read into a write, which mon-tc-04's audit-only view of the request set is
    written to prevent.
    """
    # One pass over the runners rather than a lookup per row: a fleet with a
    # hundred lanes and a stale row for each would otherwise scan the runner
    # list a hundred times to answer one read.
    by_name = {runner.get("name"): runner for runner in registry.runners()}
    annotated = []
    for row in rows:
        runner = by_name.get(row.get("lane"))
        out = dict(row)
        out["repository"] = (runner or {}).get("repo") or None
        out["host_alias"] = (runner or {}).get("host_alias") or None
        out["coverage_state"] = (
            toolchain_requests.effective_coverage(runner) if runner else None)
        annotated.append(out)
    return annotated
