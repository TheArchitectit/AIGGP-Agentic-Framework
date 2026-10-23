# runner-installs.sh — the files a runner's ticks are made of, installed on a host.
# SOURCED by runner-enroll.sh, never executed: it defines functions and has no
# entry point, so running it directly would exit 0 having installed nothing —
# a silent success. It refuses instead, the way runner-units.sh does.
#
# Split out of lib/runner-units.sh by the same gate that split out that file
# (FAIL-8f9249ca taught the checker to size .sh): adding the toolchain probe to the
# install set pushed runner-units.sh back over its hard limit, and the honest
# response to that limit has always been to move the operation, not to widen the
# limit or to shorten a comment. The seam here is narrower and easier to state
# than the one runner-units.sh draws: this file installs FILES; that one writes
# UNITS and their env namespace. A helper fix and a unit fix are different
# changes, and they now live in different files.
#
# Sourced functions share the caller's shell scope, so $REPO_ROOT, $ENV_DIR,
# $HB_HELPER and $CYC_HELPER are set by runner-enroll.sh before it sources this
# file. install_helper is deliberately HERE rather than in runner-units.sh, so
# this file does not depend on the order its caller sources its libraries in —
# being sourceable first, last or alone is what makes a small library true.
#
# $SWEEP_INTERVAL, $STATE_DIR and every *_UNIT stay with runner-units.sh for the
# reason that file states: a cadence and a unit path are decisions about the fleet
# and about this host's unit namespace, not files to copy.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "runner-installs.sh is a library sourced by scripts/runner-enroll.sh;" \
         "run that instead" >&2
    exit 2
fi

# Install a helper a unit will ExecStart. It is COPIED rather than referenced
# in place, because an inline `bash -c` body in ExecStart loses every variable
# it defines itself before bash runs (incident #1: the JSON went out malformed
# and the unit exited 22 on every tick while enrollment reported success).
#
# An existing copy is never overwritten in silence. A helper that has diverged
# is a fix that will not reach this host, and the operator has to be told —
# enrollment still succeeds, so a WARNING is the only signal there is.
#
# The destination is a parameter, not a name derived from the source, because
# some of what goes through it must NOT be named after itself: the gate has to
# land as `secret-scan.sh` for the sweep to find it, and the two libraries below
# are filed under lib/ in the checkout but installed FLAT next to the helper.
install_helper() {
    local label="$1" src="$2" dest="$3"
    [[ -f "$src" ]] || die "missing $src — cannot install the $label helper" 3
    if [[ -x "$dest" ]]; then
        if ! cmp -s "$src" "$dest"; then
            log "WARNING: $dest differs from $src — future $label helper fixes will not reach this host until it is removed"
        fi
        log "$label helper present, left unchanged: $dest"
    else
        install -m 755 "$src" "$dest"
        log "$label helper installed: $dest"
    fi
}

# Install everything a runner's ticks are made of: the two helpers a unit
# ExecStarts, and the two libraries the heartbeat resolves as its own siblings at
# run time.
#
# Why a library and not four calls in runner-enroll.sh: this is the file that
# owns operations on this host's unit/env namespace (its header states the seam),
# installing a helper is such an operation, and the script sits against the
# size gate's hard limit for .sh — so the honest response to a fourth installed
# file was to move the operation to where the others live, exactly as the
# extraction that created this file was. The DECISION stays in the script: that
# these must all exist before a timer is started.
#
# The gate and the sweep are deliberately NOT pulled into this batch: their order
# relative to each other is load-bearing (install_fleet_sweep installs the gate
# first because the sweep resolves it as a sibling at run time), and a rule about
# ordering is better kept next to the two calls it orders than split across two
# files by a function that would hide it.
install_runner_helpers() {
    install_helper "Heartbeat" \
        "$REPO_ROOT/scripts/runner-heartbeat.sh" "$HB_HELPER"
    install_helper "Image-cycle" \
        "$REPO_ROOT/scripts/runner-image-cycle.sh" "$CYC_HELPER"
    install_runtime_libraries
}

# Install the two libraries a tick resolves at RUN TIME, as siblings of the
# helper that resolves them.
#
# Both are libraries filed under scripts/lib/ in the checkout and installed FLAT
# in $ENV_DIR, under the name the resolver looks for — the same two-names-for-one-
# file arrangement the fleet sweep uses with its gate, and the reason neither can
# be installed under lib/ on the host: the helper resolves a sibling, not a path.
#
# Absent from a host whose install predates either one, the tick degrades rather
# than dying: no registry-digest means the img-cycle-05 divergence goes unchecked
# (`could not check`, not `agrees`), and no probe means the toolchain gap fields go
# absent, which the hub reads as "no opinion" and never as a complete toolchain.
# install_helper still dies on a missing SOURCE, so a checkout that lost either
# file fails enrollment loudly instead of installing a half host.
#
# The probe's install path is declared HERE, not in runner-enroll.sh, on this
# file's own rule that a path belongs beside the code that reads it — and, unlike
# $GATE_HELPER, nothing else in the tree needs the name.
PROBE_LIB="$ENV_DIR/toolchain_probe.py"
install_runtime_libraries() {
    install_helper "Registry-digest" \
        "$REPO_ROOT/scripts/lib/registry-digest.sh" "$ENV_DIR/registry-digest.sh"
    install_helper "Toolchain-probe" \
        "$REPO_ROOT/scripts/lib/toolchain_probe.py" "$PROBE_LIB"
}

