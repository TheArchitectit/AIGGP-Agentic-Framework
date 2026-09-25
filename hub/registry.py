"""hub.registry — runners.json load/save on the hub volume.

The registry is INSTANCE STATE: it lives on the hub's persistent volume on
monitor-hub and is never committed (mon-registry-01). Only the schema and a redacted
example ship in-repo under hub/schema/. Saves are atomic (tmp + os.replace)
so a crash mid-write cannot corrupt the fleet registry.

// spec: mon-registry-01
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

from . import tokens

SCHEMA_VERSION = 1

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


class Registry:
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
            self._data = {"version": SCHEMA_VERSION, "enrollment_tokens": [], "runners": []}
            return
        self.load()

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fh:
            self._data = json.load(fh)
        for key in ("version", "enrollment_tokens", "runners"):
            if key not in self._data:
                raise RegistryError(f"registry missing required key: {key}")

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

    def enroll(self, runner_name: str, repo: str, labels: list[str], host_alias: str) -> dict:
        """Record identity and mint the per-runner heartbeat token."""
        runner = {
            "name": runner_name,
            "repo": repo,
            "labels": labels,
            "host_alias": host_alias,
            "enrolled_at": _now_iso(),
            "heartbeat_token": tokens.mint_token(),
            "last_heartbeat": None,
            "last_job_seen": None,
            "disk_ok": None,
            "podman_ok": None,
            # Null until a heartbeat reports one: a freshly enrolled host has
            # no image state yet, and null must never read as healthy.
            "image_digest": None,
            "image_reason": None,
            "enrolled": True,
        }
        self._data["runners"].append(runner)
        return runner

    def heartbeat(self, runner_name: str, last_job_seen: str | None,
                  disk_ok: bool | None, podman_ok: bool | None,
                  image_digest=UNREPORTED, image_reason=UNREPORTED) -> bool:
        """Update freshness + health fields for a verified runner.

        The image fields take UNREPORTED as their default, not None: see the
        sentinel above. A caller that means "the host reports no image" passes
        None explicitly and the stored ref is cleared; a caller that passes
        nothing leaves the last report alone.
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
        return True

    def verify_heartbeat_token(self, runner_name: str, presented: str) -> bool:
        """True when the token matches an enrolled (non-revoked) runner."""
        runner = self.find_runner(runner_name)
        if runner is None or not runner.get("enrolled", False):
            return False
        return tokens.verify(presented, runner.get("heartbeat_token"))

    def revoke(self, runner_name: str) -> bool:
        """Mark a runner unenrolled; subsequent heartbeats must 401 (mon-enroll-01)."""
        runner = self.find_runner(runner_name)
        if runner is None:
            return False
        runner["enrolled"] = False
        return True

    def runners(self) -> list[dict]:
        return self._data["runners"]
