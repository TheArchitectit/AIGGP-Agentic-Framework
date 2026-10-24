# spec: repo-003-01
"""Fleet Manager package (product-tiers boundary root, REPO-002).

Everything here is inside the `fleet-manager/` boundary declared by
`fleet-manager/manifest.json`. Open-core code must not import this package; the
direction is one-way and `scripts/check_boundary.py` enforces it in CI.
"""

from .contracts import (  # noqa: F401
    CONTRACT_VERSION,
    ContractError,
    ContractInvalid,
    ContractUnsupportedVersion,
    build_capacity_decision,
    build_receipt,
    check_version,
    describe,
    load_schema,
    parse,
    validate,
)

__all__ = [
    "CONTRACT_VERSION",
    "ContractError",
    "ContractInvalid",
    "ContractUnsupportedVersion",
    "build_capacity_decision",
    "build_receipt",
    "check_version",
    "describe",
    "load_schema",
    "parse",
    "validate",
]
