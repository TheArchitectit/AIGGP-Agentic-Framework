"""hub.services — services.json load/save on the hub volume.

The service registry is DISCOVERY METADATA: it maps a stable service *name*
(e.g. ``ci-postgres``, ``llama``) to the *host_alias* of the enrolled runner
that provides it plus a port. CI resolves ``host:port`` from the hub at run
time instead of baking a literal IP into a repository variable — the whole
point of the redesign (no repo var or workflow may contain a host/IP).

Like runners.json (hub/registry.py) this file is INSTANCE STATE: it lives on
the hub's persistent volume and is never committed; only the schema and a
redacted example ship in-repo under hub/schema/. Saves use the same atomic
tmp + os.replace pattern so a crash mid-write cannot corrupt the map.

Resolution model
----------------
The runner registry stores a ``host_alias`` (a stable fleet alias), not a
routable address. ``resolve()`` therefore reports:

  * ``resolved`` — True when a runner with the service's ``host_alias`` is
    currently enrolled (a runner record whose ``enrolled`` flag is true).
  * ``host``     — the enrolled runner's ``address`` **when that record
    carries one**, else null. The framework never synthesizes an IP from an
    alias: if the fleet has not published an address, ``host`` stays null and
    the consumer fails closed.

// spec: mon-svcdisco-01
"""

from __future__ import annotations

import json
import os
import tempfile

SCHEMA_VERSION = 1

# Protocol values the schema accepts. Kept narrow on purpose: a discovery
# contract that admits arbitrary strings cannot be validated.
_PROTOCOLS = ("tcp", "http")


class ServicesError(Exception):
    """Raised when services.json is missing required structure."""


class Services:
    """In-memory view of services.json with atomic persistence.

    // spec: mon-svcdisco-01
    """

    def __init__(self, path: str, registry=None, auto_init: bool = True) -> None:
        """auto_init=True (the hub's startup mode) starts an empty map when the
        file does not exist yet; a missing file with auto_init=False is a
        configuration error and raises. ``registry`` (a hub.registry.Registry)
        is consulted by resolve() for enrollment state; it may be None, in
        which case resolve() can never report a service as resolved."""
        self.path = path
        self.registry = registry
        self._data: dict = {}
        if not os.path.exists(path) and auto_init:
            self._data = {"version": SCHEMA_VERSION, "services": {}}
            return
        self.load()

    # --- persistence ------------------------------------------------------

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fh:
            self._data = json.load(fh)
        for key in ("version", "services"):
            if key not in self._data:
                raise ServicesError(f"services missing required key: {key}")
        if not isinstance(self._data["services"], dict):
            raise ServicesError("services must be an object keyed by service name")

    def save(self) -> None:
        """Atomic write: tmp file in the same directory, then os.replace."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".services-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    # --- mutation ----------------------------------------------------------

    def add(self, name: str, host_alias: str, port: int, protocol: str = "tcp",
            description: str = "") -> dict:
        """Register (or replace) a service entry."""
        if not name:
            raise ServicesError("service name is required")
        if protocol not in _PROTOCOLS:
            raise ServicesError(
                f"protocol must be one of {_PROTOCOLS}, got {protocol!r}")
        entry = {
            "host_alias": host_alias,
            "port": int(port),
            "protocol": protocol,
            "description": description,
        }
        self._data["services"][name] = entry
        return entry

    # --- read --------------------------------------------------------------

    def all(self) -> dict:
        """The raw name -> entry map (as stored in services.json)."""
        return self._data["services"]

    def resolve(self, name: str) -> dict | None:
        """Resolve a service name to a routable-enough descriptor.

        Returns None when the name is unknown. Otherwise a dict with
        ``name``, ``host_alias``, ``host`` (nullable), ``port``, ``protocol``
        and ``resolved`` (bool). ``host`` is only non-null when an enrolled
        runner for the alias publishes an ``address`` — no IP is ever
        invented from an alias alone.
        """
        entry = self._data["services"].get(name)
        if entry is None:
            return None

        host_alias = entry.get("host_alias")
        runner = self._enrolled_runner_for(host_alias)
        resolved = runner is not None
        host = None
        if runner is not None:
            # The runner may publish an explicit address; if it does not,
            # host stays null rather than being guessed from the alias.
            address = runner.get("address")
            if isinstance(address, str) and address:
                host = address

        return {
            "name": name,
            "host_alias": host_alias,
            "host": host,
            "port": entry.get("port"),
            "protocol": entry.get("protocol", "tcp"),
            "resolved": resolved,
        }

    def _enrolled_runner_for(self, host_alias: str) -> dict | None:
        """Return the best enrolled runner providing ``host_alias``.

        Several runners can share one host_alias (many repos on one host).
        Prefer an enrolled runner that publishes an ``address`` — a usable
        provider — and only fall back to an address-less enrolled runner so
        ``resolved`` still reflects enrollment when no address is known yet.
        Without this, resolution would depend on runners.json order and could
        report host=null even when a sibling runner on the same host publishes
        an address.
        """
        if self.registry is None or not host_alias:
            return None
        fallback = None
        for runner in self.registry.runners():
            if runner.get("host_alias") == host_alias and runner.get("enrolled", False):
                address = runner.get("address")
                if isinstance(address, str) and address:
                    return runner
                if fallback is None:
                    fallback = runner
        return fallback
