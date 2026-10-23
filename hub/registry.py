"""hub.registry — runners.json load/save on the hub volume.

The registry is INSTANCE STATE: it lives on the hub's persistent volume on
monitor-hub and is never committed (mon-registry-01). Only the schema and a redacted
example ship in-repo under hub/schema/. Saves are atomic (tmp + os.replace)
so a crash mid-write cannot corrupt the fleet registry.

// spec: mon-registry-01
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from datetime import datetime, timezone

from . import (toolchain_creds, toolchain_evidence, toolchain_requests,
               toolchain_store)
from . import tokens
from .toolchain_registry import ToolchainRegistryMixin

SCHEMA_VERSION = 1

# One consumed nonce, stored as {value, request_id, at}. Kept as records rather
# than a bare string set so a refused replay can be answered with *which* row the
# nonce was first used on — the useful operator question when two callers claim the
# same moment ("someone else decided this, or is something replaying me?"). The
# nonce value itself is a random 256-bit string (tokens.mint_token), not a secret
# an attacker chose, and it identifies a decision rather than a principal, so
# storing it is not the mon-sec-02 problem heartbeat tokens are. That is also why
# these entries are never logged or echoed: a nonce is single-use evidence, and
# publishing it would let a reader replay it against a row that has since moved.


# UNREPORTED marks a heartbeat field the body did not mention at all.
#
# Most fields here treat `None` as "no news": a heartbeat that omits `disk_ok`
# leaves the last reading in place. That rule is fine for the health booleans
# and wrong for the image, which needs a third state. A host that converged
# yesterday and lost its image today reports an explicit JSON null — and if
# null were also "no news", the hub would keep the superseded ref and the fleet
# view would show that host as ready to gate. So the image fields distinguish,
# on the way in, a body that SAYS null from a body that says nothing.
#
# "Nothing" is said by OMITTING the argument, never by passing None: for the
# image fields `None` IS the report that there is no image, and
# `heartbeat(..., image_digest=None)` therefore CLEARS a stored ref. Do not
# read that as no-news — that reading is how a converged host's digest gets
# wiped by a caller meaning to leave it alone.
#
# The distinction is invisible in the wire format — JSON has one null — so it
# has to be made here, from the presence of the key. It is worth the sentinel:
# the two cases are different facts (the host reports no image / the host has
# not told us about images) and the monitor renders them differently.
#
# Written as # comments rather than a bare string literal on purpose: a
# literal is not a docstring, so the mutation tool treats this prose as code
# and reports `bool:and->or` survivors on lines inside it (observed: five
# permanent, unkillable "survivors" in this block) — noise that trains an
# operator to ignore the report.
UNREPORTED = object()


def scan_state_unknown(runner: dict) -> bool:
    """True when this host's fleet scan state is not a usable verdict.

    Three different things land here and all three are the same answer to the
    question "may I read this host as scanned?" — never reported (the sentinel
    case: an older helper, or a host enrolled before the field existed), reported
    as absent (an explicit null: the sweep has not run, or its report is gone),
    and reported as unreadable (a report that was on disk and would not parse).

    Keyed on the state being USABLE rather than on any one of those, because the
    requirement is about the reading: a repository with no recorded scan state
    SHALL be rendered unknown, never healthy (secret-scan-07). A predicate that
    asked only "did the host report a file?" would count an unreadable report as
    a clean fleet, which is the failure the reader-side reduction exists to
    prevent and would be undone here.

    TYPE SAFETY is part of the reading, not a formality. The registry stores
    whatever a spoke posted, verbatim and unvalidated (`hub/schema/` declares the
    shape; nothing enforces it on the way in — see tests/test_hub_registry.py's
    drift test, which asserts exactly that). So `scan_state` can be a string, a
    list, a bare `{}` — a buggy or hostile spoke with a valid heartbeat token can
    put any JSON value there. A predicate that reached into it with `.get()`
    would RAISE on those, and this is the function 5.3b's fleet view keys on: the
    renderer would die on host-supplied input, which is a worse failure than the
    one the type check costs. Hence `isinstance` rather than attribute access —
    the same reason `image_missing` below only ever asks whether a value is
    truthy. Every shape that is not the declared one reads as unknown, which is
    the safe direction and the one the requirement asks for.

    The `repos` list is required for the same reason one level down. A dict with
    no `repos` (or a `repos` that is not a list) has no repositories to render,
    and "no repositories" is the sentence a dashboard shows as clean — the exact
    failure this predicate exists to prevent. Requiring the list to be there is
    what keeps `{}` and `{"repos": {}}` unknown rather than empty-and-healthy.
    The heartbeat's reader makes the same check for the same reason
    (`isinstance(repos, list)` in runner-heartbeat.sh); these two are the hub and
    spoke halves of one rule, and a test covers each.

    What this does NOT check: whether a report that IS usable is recent. A sweep
    that ran a month ago leaves a state that reads clean and is stale, and
    bounded staleness needs the sweep's cadence in hand — recorded as a residual
    rather than implied away, exactly as image_missing records its own. The
    timed-out sweep is the sharper version and is not covered by that residual:
    a host whose sweep now exceeds `TimeoutStartSec=3600` keeps whatever its last
    successful report said, and nothing here notices.
    """
    state = runner.get("scan_state")
    if not isinstance(state, dict):
        return True
    if state.get("unreadable"):
        return True
    return not isinstance(state.get("repos"), list)


def image_missing(runner: dict) -> bool:
    """True when this host has reported no image at all — unknown or faulted.

    Called by the monitor and available to any dashboard: an absent digest, no
    matter why, is not readiness (img-cycle-03). Deliberately keyed on whether
    a digest was REPORTED, and not on a reason being present — a host whose image state
    was never reported is exactly as unable to gate as one that reported a
    fault, and requiring a reason would quietly count it as ready.

    What it does NOT check, and cannot from the registry alone: whether the
    reported digest is still the PINNED one. A host that converged on pin A
    and has not ticked since the pin moved to B holds a digest that is present
    and stale, and reads here as ready. The window is bounded by the heartbeat
    interval only in the ordinary case; nothing in this check bounds the AGE of
    the reading. Catching it needs the current pin in hand, which is the
    served-vs-recorded advisory's job (Sprint 4) rather than this predicate's —
    recorded as a residual instead of implied away, because "ready to gate" is
    the reading an operator acts on.
    """
    return not runner.get("image_digest")



def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RegistryError(Exception):
    """Raised when the registry file is missing required structure."""


class Registry(ToolchainRegistryMixin):
    """In-memory view of runners.json with atomic persistence.

    // spec: mon-enroll-01
    """

    def __init__(self, path: str, auto_init: bool = True) -> None:
        """auto_init=True (the hub's startup mode) creates a fresh registry
        when the file does not exist yet; a missing file with auto_init=False
        is a configuration error and raises."""
        self.path = path
        self._data: dict = {}
        if not os.path.exists(path) and auto_init:
            self._data = {"version": SCHEMA_VERSION,
                          "token_salt": secrets.token_hex(16),
                          "enrollment_tokens": [], "runners": [],
                          "toolchain_requests": [],
                          "toolchain_credentials": [],
                          "toolchain_consumed_nonces": []}
            return
        self.load()

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fh:
            self._data = json.load(fh)
        for key in ("version", "enrollment_tokens", "runners"):
            if key not in self._data:
                raise RegistryError(f"registry missing required key: {key}")
        # Boundary: every runner must have a non-empty name; malformed
        # entries would corrupt the monitor's scan-state mappings.
        for r in self._data.get("runners", []):
            if not isinstance(r.get("name"), str) or not r.get("name"):
                raise RegistryError(f"registry boundary: runner missing 'name': {r}")
        # P3 hygiene / registry pending-commit warning (mon-enroll-01):
        # runners missing an explicit commit timestamp are deferred.
        import logging
        log = logging.getLogger("hub.registry")
        for r in self._data.get("runners", []):
            if not r.get("committed_at") and not r.get("deferred"):
                log.warning("registry pending-commit: runner %s has no committed_at (defer or resolve)", r.get("name"))
        # Per-registry salt for token hashing at rest (mon-sec-02). Generated
        # once and persisted; a volume read yields verifier hashes, not tokens.
        self._data.setdefault("token_salt", secrets.token_hex(16))
        # Migrate any legacy plaintext heartbeat tokens in memory: hash them
        # with the salt so existing enrollments keep working, and drop the
        # plaintext field. Persisted on the next save (the hub saves at
        # startup, so the upgrade lands immediately).
        for runner in self._data["runners"]:
            plain = runner.pop("heartbeat_token", None)
            if plain and not runner.get("heartbeat_token_hash"):
                runner["heartbeat_token_hash"] = self._hash_token(plain)
        # toolchain credential + nonce collections (mon-tc-03). A registry
        # written before this capability shipped has no such keys; reading them
        # as empty sets is correct (no operator credentials, no consumed nonces).
        toolchain_creds.migrate_legacy_state(self._data)

    # --- token hashing (mon-sec-02) -----------------------------------------

    def _hash_token(self, token: str) -> str:
        salt = self._data.get("token_salt") or ""
        return "sha256:" + hashlib.sha256(
            (salt + token).encode("utf-8")).hexdigest()

    def _token_matches(self, presented: str, stored_hash: str | None) -> bool:
        if not presented or not stored_hash:
            return False
        return hmac.compare_digest(self._hash_token(presented), stored_hash)

    def save(self) -> None:
        """Atomic write: tmp file in the same directory, then os.replace."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".runners-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # --- enrollment tokens (one-time) --------------------------------------

    def add_enrollment_token(self, token: str) -> None:
        if token not in self._data["enrollment_tokens"]:
            self._data["enrollment_tokens"].append(token)

    def prune_enrollment_tokens(self, keep) -> int:
        """Drop stored enrollment tokens `keep(token)` rejects; returns how
        many. Startup calls it so a placeholder a previous load let in is
        healed by the next restart instead of riding the volume forever.
        `keep` is a caller predicate because the shape policy belongs to the
        loader, not the storage."""
        stored = self._data["enrollment_tokens"]
        survivors = [t for t in stored if keep(t)]
        removed = len(stored) - len(survivors)
        if removed:
            self._data["enrollment_tokens"] = survivors
        return removed

    def consume_enrollment_token(self, presented: str) -> bool:
        """Verify AND consume a one-time enrollment token (mon-enroll-01)."""
        for candidate in list(self._data["enrollment_tokens"]):
            if tokens.verify(presented, candidate):
                self._data["enrollment_tokens"].remove(candidate)
                return True
        return False

    # --- runners ------------------------------------------------------------

    def find_runner(self, name: str) -> dict | None:
        for runner in self._data["runners"]:
            if runner.get("name") == name:
                return runner
        return None

    def enroll(self, runner_name: str, repo: str, labels: list[str],
               host_alias: str, address: str | None = None) -> tuple[dict, str]:
        """Record identity and mint the per-runner heartbeat token.

        Returns (runner_record, plaintext_token): the plaintext leaves the hub
        exactly ONCE, in the enroll response; only its salted hash is stored
        (mon-sec-02 — a registry read at rest yields no usable token).

        ``address`` is the runner's routable (tailnet) address, published by
        the spoke at enroll time and refreshed on every heartbeat. It is what
        service discovery resolves a service's ``host_alias`` against, so a
        service can move hosts without any repo or workflow change.
        """
        heartbeat_token = tokens.mint_token()
        runner = {
            "name": runner_name,
            "repo": repo,
            "labels": labels,
            "host_alias": host_alias,
            "address": address,
            "enrolled_at": _now_iso(),
            "heartbeat_token_hash": self._hash_token(heartbeat_token),
            "last_heartbeat": None,
            "last_job_seen": None,
            "disk_ok": None,
            "podman_ok": None,
            "enrolled": True,
            "image_digest": None,
            "image_reason": None,
            "image_pin_divergence": None,
            "scan_state": None,
            # mon-tc-01: the lane's *reviewed* toolchain identity. All three are
            # hub-owned and None at enroll — nobody has reviewed this lane's
            # profile yet, and "unassigned" is not the same claim as "requires
            # nothing". They are never read from a heartbeat: a spoke that could
            # set its own profile could declare itself provisioned.
            "lane_image_ref": None,
            "lane_image_digest": None,
            "toolchain_profile_id": None,
            # mon-tc-06: coverage starts at never-reported, which is derived
            # rather than stored (see toolchain_requests.effective_coverage); only
            # the two fields below are persisted.
            "last_gap_report_at": None,
            "coverage": None,
            "toolchain_rejections": [],
        }
        self._data["runners"].append(runner)
        return runner, heartbeat_token

    def heartbeat(self, runner_name: str, last_job_seen: str | None,
                  disk_ok: bool | None, podman_ok: bool | None,
                  image_digest=UNREPORTED, image_reason=UNREPORTED,
                  image_pin_divergence=UNREPORTED,
                  scan_state=UNREPORTED,
                  missing_tools=UNREPORTED,
                  probe_complete: bool | None = None,
                  address: str | None = None,
                  lane_image_digest=UNREPORTED,
                  gap_outcome: dict | None = None) -> bool:
        """Update freshness + health fields for a verified runner.

        The image fields and `scan_state` take UNREPORTED as their default, not
        None: a caller that means "the host reports no image" passes None
        explicitly and the stored ref is cleared; a caller that passes nothing
        leaves the last report alone. `image_pin_divergence` is the same
        distinction — null means the host checked and the served digest matches
        the record (or it could not check), whereas omitting it means the spoke
        has no opinion. `scan_state` is the same distinction for
        the fleet sweep's report — null is a POSITIVE report that this host has
        no scan state (which must clear a stale one to unknown), whereas
        omitting it means the spoke has no opinion (which must not).

        ``missing_tools`` reuses that three-state convention, but the third state
        is *not* "the lane is provisioned": under mon-tc-06 an absent field means
        the hub has no evidence either way, so a plain heartbeat neither records a
        gap nor clears coverage back to never-reported. Present-but-empty is the
        positive report; that distinction is the whole coverage story and is
        preserved by the caller before this method is reached (mon-tc-02).

        ``address`` (the runner's current routable address) is refreshed on
        every heartbeat when the spoke publishes one, so a host that changes
        tailnet address stays discoverable without re-enrolling.
        """
        runner = self.find_runner(runner_name)
        if runner is None or not runner.get("enrolled", False):
            return False
        runner["last_heartbeat"] = _now_iso()
        if last_job_seen is not None:
            runner["last_job_seen"] = last_job_seen
        if disk_ok is not None:
            runner["disk_ok"] = disk_ok
        if podman_ok is not None:
            runner["podman_ok"] = podman_ok
        if image_digest is not UNREPORTED:
            runner["image_digest"] = image_digest
        if image_reason is not UNREPORTED:
            runner["image_reason"] = image_reason
        if image_pin_divergence is not UNREPORTED:
            runner["image_pin_divergence"] = image_pin_divergence
        if scan_state is not UNREPORTED:
            runner["scan_state"] = scan_state
        accepted_gap = None
        if missing_tools is not UNREPORTED:
            # Presence is the signal, so this branch is entered on an accepted
            # empty list too (mon-tc-02). A refused list still counts as the lane
            # having spoken about its toolchain — it did speak, and mon-tc-06's
            # question is "has a gap field ever arrived", not "was it valid".
            self.note_gap_coverage(runner_name, probe_complete)
            touched, rejection = self.record_gap_report(
                runner_name, missing_tools, runner.get("toolchain_profile_id"))
            accepted_gap = toolchain_evidence.accepted_gap_list(
                missing_tools, rejection)
            if gap_outcome is not None:
                gap_outcome["toolchain_requests_recorded"] = touched
                gap_outcome["toolchain_rejection"] = rejection
        if gap_outcome is not None:
            # mon-tc-01, spoke side: the lane's required tools are the hub's
            # spec-governed data, so the spoke measures against THIS echo rather
            # than its own guess. It travels on every successful heartbeat — not
            # only on one carrying a gap field — so a lane whose image already
            # has everything still learns what it was supposed to have. JSON
            # cannot carry "absent because unassigned" distinct from null, so a
            # null here means exactly that, and the spoke treats it as "no
            # opinion" (send nothing) rather than as an empty requirement.
            gap_outcome["required_tools"] = toolchain_requests.required_tools(
                runner.get("toolchain_profile_id"))
        # mon-tc-05 convergence, after the gap record above so "the probe
        # passes" reads this tick. A refused gap list arrives as None: it says
        # nothing about any tool and must never converge a request (mon-tc-01).
        toolchain_evidence.note_lane_evidence(
            runner, self._data, lane_image_digest, accepted_gap, _now_iso(),
            probe_complete=probe_complete)
        if address is not None:
            runner["address"] = address
        return True

    def verify_heartbeat_token(self, runner_name: str, presented: str) -> bool:
        """True when the token matches an enrolled (non-revoked) runner.
        Compares salted hashes with a constant-time digest compare."""
        runner = self.find_runner(runner_name)
        if runner is None or not runner.get("enrolled", False):
            return False
        return self._token_matches(presented, runner.get("heartbeat_token_hash"))

    def revoke(self, runner_name: str) -> bool:
        """Mark a runner unenrolled; subsequent heartbeats must 401
        (mon-enroll-01). The stored verifier is cleared too (mon-sec-02)."""
        runner = self.find_runner(runner_name)
        if runner is None:
            return False
        runner["enrolled"] = False
        runner["heartbeat_token_hash"] = None
        return True

    def runners(self) -> list[dict]:
        return self._data["runners"]

    def record_gap_report(self, runner_name: str, submitted: object,
                          profile_id: str | None) -> tuple[int, str | None]:
        """Record one lane's gap report. Returns (rows_touched, rejection_code).

        // spec: mon-tc-01, mon-tc-02

        The rules and the writing live in `toolchain_store` (this file is at
        DevGate's 500-line source hard limit); this is the Registry seam, and the
        only thing it adds is resolution by name, which is Registry's job. See the
        module docstring and `record_gap_report`'s own for why a rejected report
        keeps its reason and loses its payload, and why the heartbeat still 200s.
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
