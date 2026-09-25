#!/usr/bin/env python3
"""Mutation battery for the runner image-state slice (img-cycle-01..03).

Each mutation is a single edit to shipped code (or, for the combined entry, to
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
This lives in the repository (rather than in /tmp) so that "no survivors" can
be re-checked by whoever reads the ledger next.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])


HB = "scripts/runner-heartbeat.sh"
REG = "hub/registry.py"
SRV = "hub/server.py"
MON = "hub/monitor.py"
SCH = "hub/schema/runners.schema.json"
FIX = "tests/fixtures/runner_spoke.py"
ENR = "scripts/runner-enroll.sh"
# The install half of the cycle is now TWO files. The size gate learned to size
# .sh (FAIL-8f9249ca) and found runner-enroll.sh 89 lines over its hard limit,
# so every operation that touches the host's unit/env namespace moved to a
# library sourced by it — enable_image_cycle, install_helper and
# remove_legacy_units with them. Mutations whose anchor is one of those name
# LIB; mutations targeting the unit BODIES (E3, E4, E7) and the revoke sequence
# (E5) still name ENR, because those stayed in the script.
LIB = "scripts/lib/runner-units.sh"

T_REG = "tests/test_hub_registry.py"
T_MON = "tests/test_hub_monitor.py"
T_HTTP = "tests/test_hub_enroll_heartbeat.py"
# The probe's tests, split out of test_runner_enroll.py when that file
# passed the 600-line hard limit. Every mutation here targets
# scripts/runner-heartbeat.sh or the fixture and must be killed by the
# image-probe tests, which is where they now live.
T_IMG = "tests/test_runner_heartbeat_image.py"
# The install half of the cycle lives in runner-enroll.sh, whose tests are
# still in the enroll suite (the split moved out the heartbeat probe, not
# enrollment).
T_ENROLL = "tests/test_runner_enroll.py"

MISSING_BLOCK = '''    missing=""
    [ -n "${COHERENCE_IMAGE:-}" ] || missing="${missing:+$missing, }COHERENCE_IMAGE"
    [ -n "${COHERENCE_IMAGE_MANIFEST_DIGEST:-}" ] \\
        || missing="${missing:+$missing, }COHERENCE_IMAGE_MANIFEST_DIGEST"
    [ -n "${COHERENCE_PODMAN_STORE:-}" ] \\
        || missing="${missing:+$missing, }COHERENCE_PODMAN_STORE"
'''

DETAIL_BLOCK = '''            if reason:
                detail = f"cannot serve the pinned evaluator image: {reason}"
            else:
                detail = ("cannot serve the pinned evaluator image: this host "
                          "has not reported an image state at all, so it cannot "
                          "be counted ready to gate")
'''

IMAGE_DIGEST_BLOCK = '''        "image_digest": {
          "description": "The digest-qualified evaluator ref this host would gate with, or null when it cannot serve the pinned image (img-cycle-03). Null is UNKNOWN, never healthy.",
          "type": ["string", "null"]
        },
'''

CANON_GUARD = ('    elif [ "$(canonical_dir "$graph_root")" != '
               '"$(canonical_dir "$COHERENCE_PODMAN_STORE")" ]; then')
RAW_GUARD = '    elif [ "$graph_root" != "$COHERENCE_PODMAN_STORE" ]; then'

INFO_FAIL = '''    elif ! graph_root="$(podman --root "$COHERENCE_PODMAN_STORE" info \\
            --format '{{.Store.GraphRoot}}' 2>/dev/null)"; then
        image_reason="podman info failed for the configured store (not a path mismatch)"
'''

# (name, [(file, old, new), …], [tests that must fail], {env overrides})
MUTATIONS = [
    # --- scripts/runner-heartbeat.sh ---------------------------------------
    ("S1: the heartbeat stops reporting the image at all", [(HB,
        '    "image_digest": sys.argv[3] or None,\n    "image_reason": sys.argv[4] or None,\n',
        "")], [T_IMG], {}),
    ("S2: the mismatch branch is dropped (a wrong store reads as converged)",
     [(HB, CANON_GUARD, "    elif false; then")], [T_IMG], {}),
    # NB: the whole two-line condition, not just the first line. Replacing only
    # the first leaves `>/dev/null 2>&1; then` orphaned, and the resulting
    # syntax error "kills" the mutation without any behaviour differing — which
    # is what the well-formedness pre-check below exists to refuse.
    ("S3: presence is assumed, never checked (absent reads as converged)",
     [(HB, '    elif ! podman --root "$COHERENCE_PODMAN_STORE" image exists "$pinned_ref" \\\n'
           '        >/dev/null 2>&1; then', "    elif false; then")], [T_IMG], {}),
    ("S4: the reason names every variable, set or not", [(HB, MISSING_BLOCK,
        '    missing="COHERENCE_IMAGE, COHERENCE_IMAGE_MANIFEST_DIGEST, COHERENCE_PODMAN_STORE"\n')],
     [T_IMG], {}),
    ("S5: the probe enforces (a dead heartbeat instead of an unknown image)",
     [(HB, "# The empty strings become JSON null",
           '[ -n "$image_digest" ] || exit 3\n\n# The empty strings become JSON null')],
     [T_IMG], {}),
    ("S6: podman-missing is reported with the absence reason", [(HB,
        '    image_reason="podman not on PATH"',
        '    image_reason="pinned image absent from the store (not pulled)"')],
     [T_IMG], {}),
    ("S7: the reported ref is not digest-qualified", [(HB,
        '        image_digest="$pinned_ref"', '        image_digest="$COHERENCE_IMAGE"')],
     [T_IMG], {}),
    # The store is checked for existence BEFORE podman is asked. Removing the
    # guard is not a cosmetic reordering: podman materialises the store it is
    # pointed at (the fixture's stub does too, exactly as measured), so the
    # tick would leave one behind on a host whose mount has not come up.
    ("S8: the store's existence is assumed (podman creates it as a side effect)",
     [(HB, '    if [ ! -d "$COHERENCE_PODMAN_STORE" ]; then',
           "    if false; then")], [T_IMG], {}),
    ("S9: a failing podman is reported as a path mismatch again", [(HB, INFO_FAIL, "")],
     [T_IMG], {}),
    ("S10: the two store paths are compared as raw strings", [(HB, CANON_GUARD, RAW_GUARD)],
     [T_IMG], {}),

    # --- hub/registry.py ----------------------------------------------------
    ("R1: null is treated as no-news (a stale ref outlives its own report)",
     [(REG, "        if image_digest is not UNREPORTED:",
            "        if image_digest is not None:")], [T_REG, T_HTTP], {}),
    ("R2: the sentinel default is replaced by None (an omission clears)",
     [(REG, "                  image_digest=UNREPORTED, image_reason=UNREPORTED,",
            "                  image_digest=None, image_reason=None,")],
     [T_REG, T_HTTP], {}),
    ("R3: image_missing never reports a deficiency", [(REG,
        '    return not runner.get("image_digest")', "    return False")], [T_MON], {}),
    ("R4: readiness requires a reason (an unreported host counts as ready)",
     [(REG, '    return not runner.get("image_digest")',
            '    return runner.get("image_reason") is not None')], [T_MON], {}),

    # --- hub/server.py ------------------------------------------------------
    ("V1: the server forgets the sentinel (an omission clears over HTTP)", [(SRV,
        '                          data.get("image_digest", UNREPORTED),\n'
        '                          data.get("image_reason", UNREPORTED),',
        '                          data.get("image_digest"),\n'
        '                          data.get("image_reason"),')], [T_HTTP], {}),

    # --- hub/monitor.py -----------------------------------------------------
    ("M1: the readiness check alerts about nobody", [(MON,
        "            if not registry.image_missing(runner):\n                continue",
        "            if True:\n                continue")], [T_MON], {}),
    ("M2: the readiness check is not called by the poll loop", [(MON,
        "        self._check_image_readiness(repo, runners)", "        pass  # mutated away")],
     [T_MON], {}),
    ("M3: the unreported branch is dropped (unreported hosts go silent)",
     [(MON, DETAIL_BLOCK,
        '            detail = f"cannot serve the pinned evaluator image: {reason}"\n')],
     [T_MON], {}),
    ("M4: the reason is dropped from the alert detail", [(MON,
        '                detail = f"cannot serve the pinned evaluator image: {reason}"',
        '                detail = "cannot serve the pinned evaluator image"')], [T_MON], {}),
    ("M5: an unreported image is rendered as a reported fault", [(MON,
        '                detail = ("cannot serve the pinned evaluator image: this host "\n'
        '                          "has not reported an image state at all, so it cannot "\n'
        '                          "be counted ready to gate")',
        '                detail = ("cannot serve the pinned evaluator image "\n'
        '                          "(no reason reported by the host)")')], [T_MON], {}),

    # --- hub/schema/runners.schema.json -------------------------------------
    ("J1: the schema stops declaring image_digest", [(SCH, IMAGE_DIGEST_BLOCK, "")],
     [T_REG], {}),
    ("J2: image_digest is declared non-nullable", [(SCH,
        '"type": ["string", "null"]\n        },\n        "image_reason"',
        '"type": "string"\n        },\n        "image_reason"')], [T_REG], {}),
    ("J3: the example's _comment is undeclared in the runner shape", [(SCH,
        '        "_comment": { "type": "array", "items": { "type": "string" } },\n'
        '        "name": { "type": "string" },',
        '        "name": { "type": "string" },')], [T_REG], {}),

    # --- the fixture's own guards -------------------------------------------
    # The probe branches on COHERENCE_*, so a Spoke that inherited them from
    # the ambient environment would exercise whichever branch the machine
    # happens to be provisioned for. This is why the env override below is
    # required to kill it: on a host that sets none of them the mutation is
    # invisible, which is exactly how the coupling survived until an audit.
    # The stub's other measured fidelity. "The tick did not create the store"
    # is an assertion about the probe only while something WOULD have created
    # it — so the stub keeps podman's side effect, and this pins that.
    ("F2: the podman stub stops materialising the store (an inert assertion)",
     [(FIX, '    [ -z "${store:-}" ] || mkdir -p "$store"\\n', "")], [T_IMG], {}),
    # SECRET_SCAN_DECLARED is set here for the same reason the three
    # COHERENCE_* keys are: it is the ambient value the fixture must not
    # inherit, and setting it is what makes this mutation evaluate the hazard
    # rather than a coincidence. Measured, with the mutation applied: ambient
    # UNSET makes enroll abort under `set -u` ("SECRET_SCAN_DECLARED: unbound
    # variable") and the run dies for a reason unrelated to escaping, which is
    # how this mutation used to be credited to a test that asserts nothing about
    # it. Ambient SET makes enroll succeed and bake the ambient path into the
    # unit — the actual failure — so the killer is now the test that asserts the
    # unit still carries the systemd token.
    ("F1: the Spoke inherits ambient COHERENCE_* (the branch is chosen by the host)",
     [(FIX, '            **{k: v for k, v in os.environ.items()\n'
            '               if not k.startswith("COHERENCE_")},', "            **os.environ,")],
     [T_IMG], {"COHERENCE_IMAGE": "ambient", "COHERENCE_IMAGE_MANIFEST_DIGEST": "sha256:a",
                  "COHERENCE_PODMAN_STORE": "/tmp/ambient-store",
                  "SECRET_SCAN_DECLARED": "/tmp/ambient-declared.txt"}),

    # --- scripts/runner-enroll.sh: installing the cycle (img-cycle-02, D3) ---
    # The cycle is installed the way the heartbeat is — a copied helper, the
    # same per-runner EnvironmentFile, a per-runner timer — and enabled by
    # PROVISIONING rather than by enrollment. Both halves of that are guards,
    # so both are mutated.
    # E1 is killed by the NAMING assertion, not by the timer one: with the
    # whole call gone, a host that is not provisioned is simply never told,
    # which is its own defect. E1b/E1c below are what pin the behaviour, so
    # "a provisioned host actually runs the cycle" is not resting on a message.
    ("E1: the cycle's state is never reported (an operator is told nothing)",
     [(ENR, "    enable_image_cycle\n", "")], [T_ENROLL], {}),
    ("E1b: a provisioned host gets units and no running timer",
     [(LIB, '    systemctl --user start "devgate-imgcycle-$SLUG.timer"\n', "")],
     [T_ENROLL], {}),
    ("E1c: the cycle timer is enabled but does not survive a reboot",
     [(LIB, '    systemctl --user enable "devgate-imgcycle-$SLUG.timer" 2>/dev/null || true\n',
            "")], [T_ENROLL], {}),
    ("E2: the provisioning check accepts an unprovisioned host (a timer that "
     "fails every cycle)", [(LIB, "    if (( ${#missing[@]} )); then",
                            "    if false; then")], [T_ENROLL], {}),
    ("E3: the cycle unit loses its EnvironmentFile (the store has two sources)",
     [(ENR, "EnvironmentFile=$TICKET_FILE\nExecStart=$CYC_HELPER",
            "ExecStart=$CYC_HELPER")], [T_ENROLL], {}),
    ("E4: the cycle's ExecStart becomes an inline shell body (incident #1)",
     [(ENR, "ExecStart=$CYC_HELPER", "ExecStart=bash -c '$CYC_HELPER'")],
     [T_ENROLL], {}),
    # The anchor is the cycle pair's own line in the revoke list, which the
    # sweep's arrival split across two lines (the fleet pair now follows it).
    # Its previous spelling matched through to the end of the line — the moment
    # that line stopped being the last one, the anchor matched nothing, and a
    # mutation that never applied was summarised as a survivor.
    ("E5: revoke leaves the cycle timer behind (a unit failing forever)",
     [(ENR, '          "$CYC_TIMER_UNIT" "$CYC_SERVICE_UNIT" \\\n', "")],
     [T_ENROLL], {}),
    ("E6: an existing helper is overwritten (a host's diverged copy vanishes "
     "without a word)", [(LIB, '    if [[ -x "$dest" ]]; then',
                         "    if false; then")], [T_ENROLL], {}),
    ("E7: the cycle runs at the heartbeat's cadence (a fleet-wide registry hammer)",
     [(ENR, "OnUnitActiveSec=${CYCLE_INTERVAL}", "OnUnitActiveSec=${INTERVAL}")],
     [T_ENROLL], {}),
]

# Negative controls: pairs of edits that must NOT kill anything, because each
# demonstrates that a FIXTURE property is load-bearing. They are reported
# separately from the kill count — a battery entry whose expected outcome is
# "survives" would make the headline number meaningless.
#
# The cycle-install section above has no pair of its own. A candidate was tried
# and does not exist: every masking pair needs BOTH halves of an assertion to
# go vacuous, and here one test asserts the call IS made (provisioned) while
# another asserts it is NOT (unprovisioned), so a stub that stopped recording
# systemctl calls would make the first fail rather than hide it. Stated rather
# than faked — a control invented to fill the list is worse than an absent one.
NEGATIVE_CONTROLS = [
    # The audit's measurement only becomes a TEST because the stub normalises
    # the way podman does. Break both halves and they agree with each other:
    # the byte comparison matches a verbatim stub, and every behavioral test
    # passes — which is exactly how the defect survived the first suite.
    ("N1: raw compare + a verbatim stub — they mask each other",
     [(HB, CANON_GUARD, RAW_GUARD),
      (FIX, '    realpath -m -- "${STUB_GRAPH_ROOT:-${store:-}}"\\n',
            '    echo "${STUB_GRAPH_ROOT:-${store:-}}"\\n')],
     [T_IMG], {}),
]

# (A second control was tried here — the store guard removed alongside the
# stub's side effect, expected to survive because the kill then rests on the
# reason assertion alone. It did NOT survive, and that result is worth keeping:
# the two assertions in that test are independent, so the guard's removal is
# caught by the reason even when the store assertion goes inert. What the
# stub's side effect protects is the STRENGTH of the second assertion, and
# that is pinned directly by F2 plus test_the_podman_stub_materialises_the_store_like_podman_does
# rather than by a control that cannot isolate it.)


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "these MUST survive — they prove a fixture property is load-bearing"))
