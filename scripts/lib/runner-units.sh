# runner-units.sh — the systemd user units and helper/env files that
# runner-enroll.sh installs on a host. SOURCED, never executed: it defines
# functions and has no entry point, so running it directly would exit 0 having
# done nothing — a silent success. It refuses instead.
#
# Split out of runner-enroll.sh when the size gate learned to size .sh (task
# #13, FAIL-8f9249ca) and found that script 89 lines over its hard limit, and
# widened once more in 5.3a when the scan report's path crossed it with them
# (the same gate, one slice later: the extraction is a response to the limit,
# not a tidying that happened to fit). The seam is what this file IS: the paths
# a runner's units are named by, and every operation that writes into or
# removes from the host's unit/env namespace. runner-enroll.sh keeps what it
# DECIDES — which runner, which hub, which token, which host may own a slug —
# and emits the heartbeat's and the image cycle's units; the units that arrive
# whole with their own enablement rule (the watchdog, the fleet sweep) live
# here, where that rule stays beside the unit it governs.
#
# Sourced functions share the caller's shell scope, so the globals they read
# ($ENV_DIR, $STATE_DIR, $HB_HELPER, $CYC_HELPER, $FLEET_HELPER, the cadences)
# are set by the caller. The path globals ($SLUG, $TICKET_FILE, every *_UNIT,
# $SCAN_REPORT) are the exception: declared and derived in this file by
# set_unit_paths(), so that the paths a unit reads are defined beside it. The
# heredoc discipline and the "never inline into ExecStart" rule (FAIL-6e7b6f84)
# are documented where the units using them live.
#
# $SWEEP_INTERVAL is deliberately the exception to the watchdog's arrangement,
# where the cadence is clamped and computed beside the unit that uses it: a
# cadence is a decision about the FLEET, not an operation on this host's unit
# namespace, so it stays in runner-enroll.sh with the other decisions. That is
# the seam this file is, not an oversight to tidy up.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "runner-units.sh is a library sourced by scripts/runner-enroll.sh;" \
         "run that instead" >&2
    exit 2
fi

# --- the runner's name, and every path derived from it ------------------------
#
# These are declared HERE, beside the units that read them and the one function
# that derives them, rather than in runner-enroll.sh where they used to sit:
# they are the interface between the two files, and a reader of a unit that
# reads $FLEET_TIMER_UNIT should be able to find where that value comes from
# without opening the other file.
#
# Be exact about what the declaration buys, because it is not silence-proofing:
# every one of these is assigned by set_unit_paths() before any reader runs, and
# under `set -u` a read of an undeclared variable ABORTS LOUDLY rather than
# defaulting — so deleting the block would not make a unit path quietly empty,
# it would make enrollment fail with a message. What the block is for is that
# the set of paths a runner owns is stated in one place, next to the derivation.
#
# $SLUG_OWNER and $SLUG_ATTRIBUTABLE are deliberately declared NOWHERE, in either
# file: slug_owner() in runner-enroll.sh assigns both unconditionally on entry,
# and every one of the three sites that reads them calls it on the line before.
# A declaration would be a line that never runs. runner-enroll.sh supplies
# $STATE_DIR and $ENV_DIR, the two directories these paths are built under,
# because choosing the host's layout is a decision that stays with the script's
# other decisions.
SLUG=""
TICKET_FILE=""
SERVICE_UNIT=""
TIMER_UNIT=""
WATCHDOG_SERVICE_UNIT=""
WATCHDOG_TIMER_UNIT=""
CYC_SERVICE_UNIT=""
CYC_TIMER_UNIT=""
FLEET_SERVICE_UNIT=""
FLEET_TIMER_UNIT=""
SCAN_REPORT=""

# The runtime directory a user unit's `%t` resolves to, resolved HERE so that
# the sweep and the heartbeat can be handed one value rather than each
# resolving it independently.
#
# `%t` is systemd's own answer and the sweep unit could be left to expand it —
# but the heartbeat is a bash script and has no specifiers, so it would have to
# re-derive the path, and it knows `$RUNNER_NAME` where the unit names the file
# by `$SLUG`. Those differ for any name systemd cannot take literally
# ("prod/web 1" -> "prod-web-1"), so the two would disagree about which file to
# look at and a scanning host would read unknown forever. One value, computed
# once, handed to both.
#
# XDG_RUNTIME_DIR is unset over a non-login ssh session while the user manager
# still sets it for its units, so the fallback is not cosmetic: it is the
# difference between naming the file the sweep writes and naming one it does
# not. /run/user/$UID is exactly what systemd falls back to.
runtime_dir() {
    printf '%s' "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
}

set_unit_paths() {
    local name="$1"
    # SLUG keeps only characters systemd accepts in a unit name, so a runner
    # named "prod/web 1" does not silently produce an unusable unit.
    SLUG="$(printf '%s' "$name" | LC_ALL=C sed 's/[^A-Za-z0-9_-]/-/g')"
    [[ -n "$SLUG" ]] || die "runner name '$name' yields no usable unit name"
    TICKET_FILE="$ENV_DIR/devgate-heartbeat-$SLUG.env"
    SERVICE_UNIT="$STATE_DIR/devgate-hb-$SLUG.service"
    TIMER_UNIT="$STATE_DIR/devgate-hb-$SLUG.timer"
    WATCHDOG_SERVICE_UNIT="$STATE_DIR/devgate-watchdog-$SLUG.service"
    WATCHDOG_TIMER_UNIT="$STATE_DIR/devgate-watchdog-$SLUG.timer"
    CYC_SERVICE_UNIT="$STATE_DIR/devgate-imgcycle-$SLUG.service"
    CYC_TIMER_UNIT="$STATE_DIR/devgate-imgcycle-$SLUG.timer"
    FLEET_SERVICE_UNIT="$STATE_DIR/devgate-secretscan-$SLUG.service"
    FLEET_TIMER_UNIT="$STATE_DIR/devgate-secretscan-$SLUG.timer"
    SCAN_REPORT="$(runtime_dir)/devgate-secretscan-$SLUG.json"
}

# Install a helper a unit will ExecStart. It is COPIED rather than referenced
# in place, because an inline `bash -c` body in ExecStart loses every variable
# it defines itself before bash runs (incident #1: the JSON went out malformed
# and the unit exited 22 on every tick while enrollment reported success).
#
# An existing copy is never overwritten in silence. A helper that has diverged
# is a fix that will not reach this host, and the operator has to be told —
# enrollment still succeeds, so a WARNING is the only signal there is.
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

# Retire the pre-multi-runner fixed-name units. They cannot coexist with the
# per-runner layout: both read the single ~/.devgate-heartbeat.env, so a second
# enroll overwrites the first runner's token and the wrong runner reports.
remove_legacy_units() {
    local only="${1:-}"
    local -a legacy=(
        "$STATE_DIR/devgate-heartbeat.service"
        "$STATE_DIR/devgate-heartbeat.timer"
        "$STATE_DIR/devgate-hub-watchdog.service"
        "$STATE_DIR/devgate-hub-watchdog.timer"
    )
    local f present=0
    for f in "${legacy[@]}"; do [[ -e "$f" ]] && present=1; done
    (( present )) || return 0

    # Touch only what belongs to the runner being acted on (or is orphaned) —
    # another runner on this host may still depend on the legacy units. A file
    # we cannot attribute gets the same refusal as the per-runner path: an
    # unreadable owner check must not be read as permission to delete. `-e` and
    # `-L` rather than `-f`, so a directory or dangling symlink here is treated
    # as "names no runner" instead of as "nothing to protect".
    if [[ -e "$HOME/.devgate-heartbeat.env" || -L "$HOME/.devgate-heartbeat.env" ]]; then
        local owner
        owner="$(grep -E '^RUNNER_NAME=' "$HOME/.devgate-heartbeat.env" 2>/dev/null | cut -d= -f2- || true)"
        if [[ -z "$owner" ]]; then
            log "Legacy env at $HOME/.devgate-heartbeat.env names no runner — left in place"
            return 0
        fi
        if [[ "$owner" != "$only" ]]; then
            log "Legacy units belong to '$owner' (not '$only') — left in place"
            return 0
        fi
    fi

    log "Removing legacy fixed-name units (they cannot coexist with per-runner units)"
    systemctl --user stop devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user disable devgate-heartbeat.timer 2>/dev/null || true
    systemctl --user stop devgate-hub-watchdog.timer 2>/dev/null || true
    systemctl --user disable devgate-hub-watchdog.timer 2>/dev/null || true
    # Only the units go. ~/.devgate-heartbeat.env is deliberately left behind:
    # it may still hold another runner's token, and removing a token file on the
    # strength of a possibly-unreadable owner check is not a risk worth taking.
    rm -f "${legacy[@]}" \
          "$STATE_DIR/timers.target.wants/devgate-heartbeat.timer" \
          "$STATE_DIR/timers.target.wants/devgate-hub-watchdog.timer"
    systemctl --user daemon-reload 2>/dev/null || true
}

# The cycle is enabled by PROVISIONING, not by enrollment.
#
# Its three variables are a per-fleet choice the script does not own (D3: the
# store is either inside the runner container or socket-shared from the host),
# so an unprovisioned host gets the units on disk and no running timer. Starting
# one anyway would exit 1 here, and 6/7 on a shape-(a) fleet that never sets
# COHERENCE_* on the host at all — a unit failing every cycle is noise, and
# noise is how the alert that matters gets ignored.
#
# Enabling is therefore an operator's second step: add the three keys to the
# per-runner EnvironmentFile (they survive re-enrollment — that is what the
# preservation fix above buys) and run enroll again.
enable_image_cycle() {
    local missing=() key
    for key in COHERENCE_IMAGE COHERENCE_IMAGE_MANIFEST_DIGEST COHERENCE_PODMAN_STORE; do
        if ! grep -qE "^${key}=.+" "$TICKET_FILE" 2>/dev/null; then
            missing+=("$key")
        fi
    done

    if (( ${#missing[@]} )); then
        log "Image cycle installed but NOT enabled: the environment file does not set ${missing[*]}"
        log "  Add them to $TICKET_FILE (store per design D3), then re-run enroll to enable it."
        log "  Units are in place: devgate-imgcycle-$SLUG.service / .timer"
        return 0
    fi

    systemctl --user enable "devgate-imgcycle-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-imgcycle-$SLUG.timer"
    log "Image cycle timer enabled: devgate-imgcycle-$SLUG.timer (helper: $CYC_HELPER)"
}

# The fleet secret sweep: its two units, and the two conditions under which its
# timer is allowed to run. It lives here rather than in runner-enroll.sh for the
# same reason the watchdog does — it is entirely unit-namespace work — and
# because that script was at its hard size limit.
#
# The ExecStart is a bare path like the other two, and the declaration is
# written `"\$SECRET_SCAN_DECLARED"`: ESCAPED so the unquoted heredoc does not
# expand it at write time, and QUOTED so systemd hands its own expansion through
# as ONE word. systemd splits an unquoted `$VAR` on whitespace, and a
# declaration path is allowed to contain a space.
#
# The `--report "$SCAN_REPORT"` beside it is the deliberate OPPOSITE, and the
# difference is worth stating rather than looking like an inconsistency. It is
# NOT escaped: enroll expands it here, at write time, and the unit ends up
# naming the report file literally. It has to, because the report is now read
# by the HEARTBEAT as well — a bash script with no access to systemd's `%t` —
# so the path must exist as a resolved value somewhere both can read it, and
# the env file is that somewhere. What keeps the two carriers honest is a test
# (test_the_sweep_unit_reports_to_the_path_the_heartbeat_reads) rather than the
# hope that one assignment was written twice the same way.
#
# What escaping `$SCAN_REPORT` would actually do is worse than a mismatch, and
# is worth stating precisely because the obvious guess is wrong. It would NOT
# make the heartbeat re-derive anything: the heartbeat reads
# `SECRET_SCAN_REPORT` from the env file, and enrollment writes that line
# whatever the unit says. Escaped, systemd would look up `$SCAN_REPORT` in the
# unit's own environment — and `SCAN_REPORT` is not a key the env file carries
# (the five keys there are HUB_URL, RUNNER_NAME, HEARTBEAT_TOKEN, LAST_JOB_SEEN
# and SECRET_SCAN_REPORT), so it expands to the EMPTY STRING and the unit runs
# `--report ""`. Measured: the sweep takes an empty report path as "no report
# requested" (secret-scan-fleet.sh: `if [ -n "$REPORT" ]`) and writes no file at
# all — so the fleet would have no per-repository state while the unit exited
# on the scan's own verdict, and nothing on the host would say the report was
# the thing that went missing. A silent total no-op, not a name mismatch.
#
# This is the one place `%t` was load-bearing and is now reimplemented by
# hand: systemd's specifier was authoritative, and `runtime_dir()` above is
# this repository's answer to it. Stated because it is a real (small) loss of
# authority, bought for the heartbeat being able to find the same file at all.
#
# What the escaping defends against, measured rather than assumed (all four
# combinations, against the real enroll and a stub systemctl):
#
#   ambient unset, escaped    -> rc 0, unit carries `$SECRET_SCAN_DECLARED`
#   ambient set,   escaped    -> rc 0, unit carries `$SECRET_SCAN_DECLARED`
#   ambient unset, UNESCAPED  -> rc 1: `SECRET_SCAN_DECLARED: unbound variable`
#                                (enroll runs `set -u`), and no unit is written
#   ambient set,   UNESCAPED  -> rc 0, and the AMBIENT path is baked into the
#                                unit as a literal, where no later change to
#                                the env file can reach it
#
# So the unset case is loud — enroll aborts, nothing is installed — and the
# hazard the escaping actually prevents is the third line's opposite: a value
# from enroll's own environment frozen into the unit. That is the silent one,
# and it is the case `test_an_ambient_declaration_is_not_baked_into_the_unit`
# pins. (An earlier revision of this comment claimed the unset case expanded to
# the empty string "while enrollment reported success". It does not: that is a
# crash. Incident #1's shape is the ambient-value trap, one heredoc over.)
#
# The timer is enabled by PROVISIONING, exactly as the cycle's is, and for a
# sharper version of the same reason: the sweep REFUSES to run on an empty
# declaration (exit 3 — zero repositories scanned is not a clean fleet). A host
# that has not been provisioned has nothing to sweep, and enabling the timer
# anyway puts a unit that fails every tick on it, which on a dashboard is
# indistinguishable from a sweep that ran and found nothing.
install_fleet_sweep() {
    cat > "$FLEET_SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate fleet secret sweep ($SLUG)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$FLEET_HELPER --declared "\$SECRET_SCAN_DECLARED" --report "$SCAN_REPORT"
TimeoutStartSec=3600
EOF

    cat > "$FLEET_TIMER_UNIT" <<EOF
[Unit]
Description=DevGate fleet secret sweep timer ($SLUG)

[Timer]
OnBootSec=${SWEEP_INTERVAL}
OnUnitActiveSec=${SWEEP_INTERVAL}
AccuracySec=300

[Install]
WantedBy=timers.target
EOF

    # Last assignment wins in both readers, so `tail -n 1` matches what systemd
    # will do with a duplicated key rather than picking a line systemd ignores.
    local declared
    declared="$(grep -E '^SECRET_SCAN_DECLARED=' "$TICKET_FILE" 2>/dev/null \
        | tail -n 1 | cut -d= -f2- || true)"

    # One matching pair of surrounding quotes comes off, because systemd
    # unquotes a value and the ExecStart above is quoted precisely so a path
    # containing a space survives. Measured divergence without this: with
    # `SECRET_SCAN_DECLARED="/tmp/with space/declared.txt"` — a line systemd
    # reads, unquotes and runs perfectly — this test resolved the literal
    # `"/tmp/with space/declared.txt"` (quotes and all), found no such file, and
    # left the sweep disabled on a host whose operator had provisioned it.
    #
    # The boundary, stated rather than implied: this is ONE layer of quotes, not
    # an EnvironmentFile parser. Escape sequences and a trailing `# comment`
    # after a value are not emulated, so a declaration written either way reads
    # here as a path that does not exist — and the message below prints the
    # value it read, so the operator can see the quotes or the comment in it.
    # Two full parsers would drift; the sweep stays the authority on whether a
    # declaration it was handed is usable.
    case "$declared" in
        \"*\"|\'*\')
            declared="${declared:1:${#declared}-2}"
            ;;
    esac

    # ONE condition, deliberately, not an `-s` check followed by a "does it name
    # a repository" check. This grep already fails on a file that is missing or
    # empty, so a second existence test would be a message selector rather than
    # a guard — the shape the battery's F3 found in the first draft of this
    # block, where `-z` and `-s` were two branches over one fact.
    #
    # The pattern is the sweep's OWN rule, not an approximation of it, because
    # the two must not disagree: `secret-scan-fleet.sh` strips a line at its
    # first `#`, removes every whitespace character, and skips it if nothing
    # remains. So a line counts here exactly when it has a non-`#`, non-blank
    # character BEFORE its first `#` — which is what `^[^#]*[^#[:space:]]`
    # matches. Measured counter-example to the obvious shorter form: the
    # `^[^#[:space:]]` a review proposed would refuse `  https://…` (an INDENTED
    # url), which the sweep reads and scans happily — enroll would report a
    # provisioned sweep as not enabled, the same false negative the quoted-path
    # strip above exists to prevent, in the other direction.
    #
    # Closing this is the point of the whole block: a declaration that names
    # nothing makes the sweep exit 3 on every tick, and a unit that fails every
    # tick is indistinguishable on a dashboard from a sweep that ran and found
    # nothing. The scope is still deliberately not "is this a valid URL" — that
    # IS the sweep's parser, and two of those drift.
    if ! grep -qE '^[^#]*[^#[:space:]]' "$declared" 2>/dev/null; then
        log "Fleet secret sweep installed but NOT enabled: SECRET_SCAN_DECLARED=${declared:-<unset>} is not a file naming at least one repository"
        log "  Set SECRET_SCAN_DECLARED=/path/to/declared-repos.txt (one repo URL per line) in $TICKET_FILE, then re-run enroll."
        log "  Blank lines and # comments are skipped, and the sweep exits 3 on a declaration that names nothing, so enabling it here would fail every tick."
        log "  Units are in place: devgate-secretscan-$SLUG.service / .timer"
        return 0
    fi

    # Reload before enabling, as install_watchdog does: a re-enroll rewrites
    # both units, and enabling without a reload leaves the MANAGER running the
    # previous revision of a unit whose file on disk is already the new one.
    # The watchdog's reload used to cover this by running later in the flow —
    # until the watchdog is absent, when it returns before reloading and this
    # unit is left unreloaded.
    systemctl --user daemon-reload
    systemctl --user enable "devgate-secretscan-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-secretscan-$SLUG.timer"
    log "Fleet secret sweep timer enabled: devgate-secretscan-$SLUG.timer (helper: $FLEET_HELPER)"
}

# The inverted dead-man switch: this spoke checks the HUB, so a dead hub is
# noticed by a machine that is still up. Its own unit failing IS the signal
# (local-only by design — no GitHub issue, no token on the spoke).
install_watchdog() {
    local watchdog="$REPO_ROOT/scripts/hub-watchdog.sh"
    if [[ ! -x "$watchdog" ]]; then
        log "WARNING: $watchdog not found/executable — skipping hub watchdog install"
        return 0
    fi

    # Independent cadence from the heartbeat: the watchdog watches the HUB, so
    # it should not inherit a very short or very long heartbeat interval.
    # Clamped to [5 min, 15 min] — always well inside the script's staleness grace.
    if (( INTERVAL < 300 )); then WATCH_INTERVAL=300
    elif (( INTERVAL > 900 )); then WATCH_INTERVAL=900
    else WATCH_INTERVAL=$INTERVAL; fi

    log "Installing hub watchdog (checks the hub every ${WATCH_INTERVAL}s)..."

    # Runs the in-repo script directly; HUB_URL comes from the heartbeat env
    # file, which enrollment already wrote.
    cat > "$WATCHDOG_SERVICE_UNIT" <<EOF
[Unit]
Description=DevGate hub watchdog (spoke-side dead-man check, $SLUG)

[Service]
Type=oneshot
EnvironmentFile=$TICKET_FILE
ExecStart=$watchdog
EOF

    cat > "$WATCHDOG_TIMER_UNIT" <<EOF
[Unit]
Description=DevGate hub watchdog timer ($SLUG)

[Timer]
OnBootSec=${WATCH_INTERVAL}
OnUnitActiveSec=${WATCH_INTERVAL}
AccuracySec=10

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable "devgate-watchdog-$SLUG.timer" 2>/dev/null || true
    systemctl --user start "devgate-watchdog-$SLUG.timer"

    log "Watchdog installed: devgate-watchdog-$SLUG.timer (status: systemctl --user status devgate-watchdog-$SLUG)"
}
