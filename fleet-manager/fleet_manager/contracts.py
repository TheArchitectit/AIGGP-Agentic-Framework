# spec: repo-003-01, repo-003-02, repo-004-01, repo-004-02, repo-004-03, repo-004-04
"""Fleet Manager's side of the versioned cross-boundary contracts (v1).

Everything that crosses the open-core/commercial boundary is a document whose
shape lives under ``contracts/v1/`` and whose version is in the document
itself. There are exactly three:

- ``capacity_request``   core -> Fleet Manager  (what the job needs)
- ``capacity_decision``  Fleet Manager -> core  (assigned / queued / refused /
  unavailable, with a typed reason when it is not "assigned")
- ``operation_receipt``  Fleet Manager -> evidence plane (what was done, by
  whom, with a digest of the evidence)

Two properties are deliberate and tested:

1. **A producer here cannot emit an invalid document.** The ``build_*``
   functions validate what they built and raise rather than return it.
2. **A consumer refuses, it does not guess.** ``validate`` returns every
   violation; ``parse`` raises ``ContractInvalid`` with the same list. Nothing
   raises ``KeyError``/``TypeError`` on a hostile document, so a caller can
   turn a refusal into an explicit degraded state instead of an exception that
   reads like a crash.

Some rules cannot be expressed in the schema language the core ships
(no ``if/then``): "assignment iff assigned" and "evidence when completed" are
checked in ``_semantic_errors``. That split is stated rather than hidden —
a schema that silently under-checks is worse than one that says where its
authority ends.

The only open-core module this package imports is ``hub.coherence.schemacheck``
(a stdlib JSON-Schema subset validator). The import surface is pinned by a test
so extraction has a bounded, declared dependency rather than a discovered one
(REPO-005).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from hub.coherence import schemacheck

CONTRACT_VERSION = 1
CONTRACT_DIR = Path(__file__).resolve().parent.parent / "contracts" / "v1"

SCHEMAS = {
    "capacity_request": "capacity-request.schema.json",
    "capacity_decision": "capacity-decision.schema.json",
    "operation_receipt": "operation-receipt.schema.json",
}

TERMINAL_OUTCOMES = ("assigned", "queued", "refused", "unavailable")


class ContractError(ValueError):
    """A document crossed the boundary and was not acceptable."""


class ContractUnsupportedVersion(ContractError):
    """The document declares a contract version this build does not implement."""

    def __init__(self, found, supported=CONTRACT_VERSION):
        self.found = found
        self.supported = supported
        if found is None:
            message = (f"missing contract_version — every cross-boundary "
                       f"document carries one (this build implements {supported})")
        else:
            message = (f"contract_version {found!r} is not supported by this "
                       f"build (implements {supported})")
        super().__init__(message)


class ContractInvalid(ContractError):
    """The document is the right version but violates its contract."""

    def __init__(self, kind: str, errors):
        self.kind = kind
        self.errors = list(errors)
        super().__init__(f"{kind} rejected: " + "; ".join(self.errors))


def load_schema(kind: str) -> dict:
    """Load a frozen v1 schema by contract kind."""
    try:
        name = SCHEMAS[kind]
    except KeyError:
        raise ContractError(
            f"unknown contract kind {kind!r}; known: {sorted(SCHEMAS)}") from None
    return json.loads((CONTRACT_DIR / name).read_text(encoding="utf-8"))


def check_version(doc) -> int:
    """Return the major version, or raise if it is absent or not ours."""
    version = doc.get("contract_version") if isinstance(doc, dict) else None
    if isinstance(version, bool) or not isinstance(version, int):
        raise ContractUnsupportedVersion(version)
    if version != CONTRACT_VERSION:
        raise ContractUnsupportedVersion(version)
    return version


def _semantic_errors(kind: str, doc: dict) -> list:
    """Rules the shipped schema language cannot express (documented above)."""
    errors = []
    if kind == "capacity_decision":
        outcome = doc.get("outcome")
        if outcome == "assigned":
            if "assignment" not in doc:
                errors.append(
                    "$.assignment: required when outcome is 'assigned'")
            if "reason" in doc:
                errors.append(
                    "$.reason: not allowed when outcome is 'assigned' — a "
                    "grant and an excuse in one document cannot be acted on")
        elif outcome in TERMINAL_OUTCOMES:
            if "reason" not in doc:
                errors.append(
                    f"$.reason: required when outcome is {outcome!r} — a "
                    "decision without a reason cannot be acted on")
            if "assignment" in doc:
                errors.append(
                    f"$.assignment: not allowed when outcome is {outcome!r}")
    elif kind == "operation_receipt":
        if doc.get("outcome") == "completed" and "evidence" not in doc:
            errors.append(
                "$.evidence: required when outcome is 'completed' — a "
                "completion claim without evidence is not a receipt")
    return errors


def validate(kind: str, doc) -> list:
    """Return every violation of the contract (empty list means valid).

    Version is checked first and alone: a v2 document must be refused as a
    version problem, not reported as a pile of shape errors from a v1 schema
    that was never meant to describe it.
    """
    if kind not in SCHEMAS:
        raise ContractError(
            f"unknown contract kind {kind!r}; known: {sorted(SCHEMAS)}")
    try:
        check_version(doc)
    except ContractUnsupportedVersion as exc:
        return [f"$.contract_version: {exc}"]
    errors = list(schemacheck.validate(doc, load_schema(kind)))
    errors.extend(_semantic_errors(kind, doc))
    return errors


def parse(kind: str, doc) -> dict:
    """Validate and return the document; raise ContractInvalid if it fails."""
    errors = validate(kind, doc)
    if errors:
        raise ContractInvalid(kind, errors)
    return doc


def _utc_now() -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


def build_capacity_decision(request: dict, outcome: str, *,
                            assignment: dict | None = None,
                            reason: dict | None = None,
                            decided_at: str | None = None) -> dict:
    """Build a capacity decision for ``request``, refusing to emit garbage.

    The request is validated first: a decision that echoes a request nobody
    could have produced is not a contract test, it is a fixture that agrees
    with itself.
    """
    request = parse("capacity_request", request)
    doc = {
        "contract_version": CONTRACT_VERSION,
        "request_id": request["request_id"],
        "decided_at": decided_at or _utc_now(),
        "outcome": outcome,
    }
    if assignment is not None:
        doc["assignment"] = assignment
    if reason is not None:
        doc["reason"] = reason
    return parse("capacity_decision", doc)


def build_receipt(*, receipt_id: str, subject: dict, operation: str,
                  outcome: str, actor: dict, evidence: dict | None = None,
                  detail: str | None = None,
                  issued_at: str | None = None) -> dict:
    """Build an operation receipt, refusing to emit garbage."""
    doc = {
        "contract_version": CONTRACT_VERSION,
        "receipt_id": receipt_id,
        "issued_at": issued_at or _utc_now(),
        "subject": subject,
        "operation": operation,
        "outcome": outcome,
        "actor": actor,
    }
    if evidence is not None:
        doc["evidence"] = evidence
    if detail is not None:
        doc["detail"] = detail
    return parse("operation_receipt", doc)


def describe() -> dict:
    """The contract surface this build speaks — for humans and for evidence."""
    return {
        "contract_version": CONTRACT_VERSION,
        "kinds": {kind: str(CONTRACT_DIR / name)
                  for kind, name in sorted(SCHEMAS.items())},
        "outcomes": list(TERMINAL_OUTCOMES),
    }
