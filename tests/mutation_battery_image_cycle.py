#!/usr/bin/env python3
"""Mutation battery for the image-cycle slice (the cycler's audit fixes).

Each mutation is a single edit to shipped code (or, for a combined entry, to
shipped code AND its fixture) that makes a specific promise false while leaving
everything else alone. A mutation is KILLED when one of the named test files
fails because of it; a SURVIVOR means a guard no test actually depends on — the
guard is decoration, and the suite would not notice its removal.

Two properties this battery asserts about itself, because a battery that lies
is worse than none:

  * A mutation that merely BREAKS THE PARSER kills every test at once, which
    looks identical to a clean behavioural kill. Each mutated artifact is
    checked for well-formedness first and reported INVALID rather than killed.
  * The count of the anchor text is asserted before the edit, and a mutation
    whose anchor has drifted is reported rather than silently skipped.

Run it from the repository root: it rewrites files in place and restores them.
It lives in the repository (rather than in /tmp) so that "no survivors" can be
re-checked by whoever reads the ledger next.

Sibling of tests/mutation_battery_image_state.py; same contract, same output.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])


CYC = "scripts/runner-image-cycle.sh"
T_CYC = "tests/test_runner_image_cycle.py"
# The stubbed podman and the host fixture are the instrument, and they live
# in a shared module rather than in the test file: two mutations below edit
# the stub itself (its rmi side effect, its info normalisation), so the
# fixture mutations and the behavioural ones name different files.
T_HARNESS = "tests/image_cycle_harness.py"

CANON_GUARD = ('if [ "$(canonical_dir "$GRAPH_ROOT")" != '
               '"$(canonical_dir "$COHERENCE_PODMAN_STORE")" ]; then')
RAW_GUARD = 'if [ "$GRAPH_ROOT" != "$COHERENCE_PODMAN_STORE" ]; then'

INFO_SPLIT = '''if ! GRAPH_ROOT="$("${PODMAN[@]}" info --format '{{.Store.GraphRoot}}' 2>/dev/null)"; then
    echo "[img-cycle] podman could not answer for the configured store" \\
         "'$COHERENCE_PODMAN_STORE' (not a path mismatch) — this tick cannot" \\
         "verify which store it would fill" >&2
    exit 7
fi'''
INFO_COLLAPSE = '''GRAPH_ROOT="$("${PODMAN[@]}" info --format '{{.Store.GraphRoot}}' 2>/dev/null || true)"'''

REVERIFY = '''    if ! "${PODMAN[@]}" image exists "$REF" >/dev/null 2>&1; then
        echo "[img-cycle] verification failed after prune: the reap removed the" \\
             "pinned image $REF from this store — this host can no longer gate" >&2
        exit 4
    fi
'''

IDENTITY_VERIFY = '''if [ "$GOT" != "$COHERENCE_IMAGE_MANIFEST_DIGEST" ]; then
    echo "[img-cycle] verification failed: $REF resolves to '${GOT:-nothing}'," \\
         "recorded '$COHERENCE_IMAGE_MANIFEST_DIGEST'" >&2
    exit 4
fi'''

SUCCESS_ECHO = '''# The success claim comes LAST, after every check that could contradict it. It
# used to be printed before the prune, so a run that reaped the pinned image
# announced "converged" and then exited 4 — the one line an operator greps for
# said the opposite of the exit code.
echo "[img-cycle] converged: $REF"'''

RMI_MUTATES = '''    state["images"] = [i for i in state.get("images", []) if i["id"] != target]
    state["present"] = [r for r in state.get("present", []) if r not in gone]'''

# (name, [(file, old, new), …], [tests that must fail], {env overrides})
MUTATIONS = [
    # --- the store comparison (measured: podman normalises) ------------------
    ("K1: the store paths are compared as raw strings again (a trailing slash "
     "reads as a different store)",
     [(CYC, CANON_GUARD, RAW_GUARD)], [T_CYC], {}),

    # --- failing podman is not a wrong path ---------------------------------
    ("K2: a podman that cannot answer collapses into a store mismatch",
     [(CYC, INFO_SPLIT, INFO_COLLAPSE)], [T_CYC], {}),

    # --- the store must exist before podman touches it ----------------------
    # Removing the guard is not a cosmetic reordering: podman MATERIALISES the
    # store it is pointed at (the fixture's stub does too, exactly as
    # measured), so the cycle would create storage on a host whose mount has
    # not come up — and pull into it.
    ("K3: the store's existence is assumed (podman creates it as a side effect)",
     [(CYC, 'if [ ! -d "$COHERENCE_PODMAN_STORE" ]; then', "if false; then")],
     [T_CYC], {}),

    # --- the invariant is checked, not assumed ------------------------------
    ("K4: nothing re-verifies the pinned image after the reap",
     [(CYC, REVERIFY, "")], [T_CYC], {}),

    # --- the success claim: it must be said, and it must come last ----------
    ("K5: the success claim is dropped entirely (a converged host says nothing)",
     [(CYC, SUCCESS_ECHO, "")], [T_CYC], {}),
    ("K5b: the success claim moves back ahead of the prune it can contradict",
     [(CYC, IDENTITY_VERIFY, IDENTITY_VERIFY + '\necho "[img-cycle] converged: $REF"')],
     [T_CYC], {}),

    # --- the fixture's own guard -------------------------------------------
    # The reap only takes anything away if the stub's rmi mutates state. With
    # that removed, losing the pinned image is not something the fixture can
    # express, so "the reap removed the pinned image" stops being an
    # observation and the scenario goes inert.
    ("K6: the podman stub's rmi stops removing what it reaped",
     [(T_HARNESS, RMI_MUTATES, "    pass")], [T_CYC], {}),
]

# Negative controls: edits that must NOT kill anything, because each shows that
# a FIXTURE property is load-bearing. Reported separately from the kill count —
# a battery entry whose expected outcome is "survives" would make the headline
# number meaningless.
NEGATIVE_CONTROLS = [
    # The normalisation measurement only becomes a TEST because the stub
    # normalises the way podman does. Break both halves and they agree with
    # each other: a byte comparison matches a verbatim stub and every
    # behavioral test passes — which is exactly how the defect survived the
    # first suite.
    ("N1: raw compare + a verbatim stub — they mask each other",
     [(CYC, CANON_GUARD, RAW_GUARD),
      (T_HARNESS, 'or (os.path.realpath(root) if root else "")', 'or (root or "")')],
     [T_CYC], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "these MUST survive — they prove a fixture property is load-bearing"))
