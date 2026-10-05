#!/usr/bin/env python3
"""Mutation battery for OAP evidence acceptance (Gate 3.3, task T134).

Gate 3 exit criteria (openspec/changes/harden-oap-evidence-verification) demand
that "mutation tests kill reintroduced identity-key and duplicate-key
acceptance". This battery is that control, made operational: it reintroduces
each unsafe acceptance into the verifier/parser and asserts that the existing
OAP suite FAILS on it — a mutation that survives means no test depends on the
guard, which is the stop condition.

Two acceptance classes are deliberately reintroduced:

  * identity-key acceptance in a verifier — the identity point (`01` + 31 zero
    bytes) as A and R with S=0, plus the other small-order encodings. This is
    the forgery class Gate 1.2 exists to reject. Bypassing the strict decode
    must make `tests/test_oap_evidence_signature.py` fail.
  * duplicate-key acceptance in the parser — a second occurrence of a key at any
    object depth. `json.loads` erases duplicates, so a receiver that accepts
    them has already lost the fact; bypassing `_object_pairs_hook` must make the
    schema-fixture and loopback conformance tests fail.

The vectors themselves are unchanged; only the guard that rejects them is
removed, so a killed mutation is a test that reads the guard rather than the
reason string.

The negative control must SURVIVE: a comment reworded inside a mutated file, no
test reads it, and a battery that killed it too would be pinning prose.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])

VERIFIER = "hub/coherence/ed25519.py"
VETTED = "hub/coherence/ed25519_vetted.py"
PARSER = "hub/coherence/strict_parse.py"

SIG_T = "tests/test_oap_evidence_signature.py"
SCHEMA_T = "tests/test_oap_evidence_schema.py"
CONFORMANCE_T = "tests/test_oap_v2_conformance.py"

MUTATIONS = [
    # M1 — the pure-Python verifier stops rejecting small-order points. Every
    # identity-A/identity-R/S=0 vector then verifies, which is the exact forgery
    # TestStrictPointValidation and TestMandatoryCheckRejectsIdentityForgery
    # assert must never verify.
    ("M1: identity-key acceptance reintroduced into the pure-Python verifier",
     [(VERIFIER,
       "    point = (x, y)\n"
       "    if _is_small_order(point):\n"
       "        raise Ed25519Error(\"low-order point\")\n"
       "    return point",
       "    point = (x, y)\n"
       "    if False:\n"
       "        raise Ed25519Error(\"low-order point\")\n"
       "    return point")],
     [SIG_T], {}),

    # M2 — the vetted provider stops rejecting small-order points before the
    # provider verify. The strict checks run there because linked OpenSSL
    # acceptance of low-order A is version-dependent; removing them reopens the
    # same forgery on the production-signing path. Killed by the cross-provider
    # adversarial tests.
    ("M2: identity-key acceptance reintroduced into the vetted provider",
     [(VETTED,
       "    if raw in _LOW_ORDER_ENCODINGS:\n"
       "        raise Ed25519Error(\"low-order point\")",
       "    if False and raw in _LOW_ORDER_ENCODINGS:\n"
       "        raise Ed25519Error(\"low-order point\")")],
     [SIG_T, CONFORMANCE_T], {}),

    # M3 — the strict parser stops rejecting duplicate keys. A duplicate-key
    # artifact then parses, and the receiver sees a lossy projection of the wire
    # bytes. Killed by the fixture suite and the loopback conformance tests.
    ("M3: duplicate-key acceptance reintroduced into the strict parser",
     [(PARSER,
       "    for key, value in pairs:\n"
       "        if key in obj:\n"
       "            raise StrictParseError(f\"duplicate-key:{key}\")\n"
       "        obj[key] = value",
       "    for key, value in pairs:\n"
       "        if False:\n"
       "            raise StrictParseError(f\"duplicate-key:{key}\")\n"
       "        obj[key] = value")],
     [SCHEMA_T, CONFORMANCE_T], {}),
]

# Must SURVIVE. A comment reworded inside a file the battery mutates: no test
# reads this string, and no guard changed. A battery whose mutation killed this
# too would be pinning prose rather than the acceptance above.
NEGATIVE_CONTROLS = [
    ("N1: a comment reworded, saying exactly the same thing",
     [(VERIFIER,
       "# Gate 0 quarantine marker. True while outputs of this path remain",
       "# Gate 0 quarantine marker: True while outputs of this path remain")],
     [SIG_T], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it proves the guards read the acceptances, not the comments"))
