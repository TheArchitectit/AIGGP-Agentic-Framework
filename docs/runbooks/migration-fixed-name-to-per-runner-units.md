# Migration Guide: Fixed-Name Units → Per-Runner Units

**Audience:** operators of spoke hosts that enrolled a runner (or the
hub's own watchdog) before the per-runner layout landed in
`bfb7e99` (2026-09-22). It describes the one automated migration
(`remove_legacy_units`) and the one manual action it deliberately
refuses to do. Sibling runbooks live in [./README.md](./README.md); the
requirement is the coherence-service ledger's multi-runner line
(`coh-int-07`).

## Before → after

| Era | Unit / file names |
|---|---|
| Before `bfb7e99` (fixed names, one runner per host) | `devgate-heartbeat.service` / `.timer`, `devgate-hub-watchdog.service` / `.timer`, `~/.devgate-heartbeat.env` |
| After `bfb7e99` (per-runner names, multi-spoke hosts) | `devgate-hb-<runner>.{service,timer}`, `devgate-watchdog-<runner>.{service,timer}`, `devgate-imgcycle-<runner>.{service,timer}`, `devgate-secretscan-<runner>.{service,timer}`, `~/.config/containers/devgate-heartbeat-<runner>.env` |

The fixed names cannot coexist with the per-runner layout: both read the
single `~/.devgate-heartbeat.env`, so a second enroll overwrites the
first runner's token and the wrong runner reports (the comment above
`remove_legacy_units` in `scripts/lib/runner-units.sh` states this as
its reason for existing).

## What is automatic

Re-enroll the runner:

```bash
bash scripts/runner-enroll.sh <hub-url> <enrollment-token> --runner-name <name>
bash scripts/runner-enroll.sh --revoke <hub-url> <heartbeat-token> <runner-name>
```

Both call `remove_legacy_units` (`scripts/runner-enroll.sh` lines 234
and 477). It stops and disables the legacy timers, then removes the
legacy unit files under `$STATE_DIR` (plus the
`timers.target.wants` symlinks). Re-enrolling with the **same** runner
name is therefore the complete migration: the owner attribution below
resolves to that name, and the sweep runs.

## What stays manual, and why

`~/.devgate-heartbeat.env` is deliberately left behind — the comment at
its removal site says removing a token file on the strength of a
possibly-unreadable owner check is not a risk worth taking. After a
successful migration, once you confirm no runner still reads it:

```bash
shred -u ~/.devgate-heartbeat.env    # or rm -f if shredding is unavailable
```

The owner check that gates the sweep reads
`^RUNNER_NAME=` from that file. Three outcomes, each logged:

| Condition | Behavior |
|---|---|
| file absent or no `RUNNER_NAME` line | "names no runner" → legacy units left in place |
| `RUNNER_NAME` ≠ the runner being enrolled/revoked | "belong to '<other>'" → left in place (another spoke on this host may still depend on them) |
| `RUNNER_NAME` = the acted-on runner | legacy units stopped, disabled, removed |

An unreadable owner check gets the same refusal as a foreign owner —
failure is never read as permission to delete.

## Verification

```bash
systemctl --user list-units --all 'devgate-*'   # only per-runner names remain
ls ~/.config/containers/                       # devgate-heartbeat-<runner>.env present
```

Hosts with per-runner units only (every spoke enrolled since
2026-09-22) need nothing: `remove_legacy_units` returns early when no
legacy file exists. This is the shape measured on ucs03 (2026-09-26):
8 `devgate-hb-<name>` heartbeat units with matching watchdogs, zero
fixed-name units on disk.

## What this guide does NOT cover

- **Hub registry or policy-format changes.** Those lifecycles are the
  sibling runbooks: [hub-outage.md](./hub-outage.md),
  [policy-rollback-and-key-rotation.md](./policy-rollback-and-key-rotation.md),
  [evidence-and-attestation.md](./evidence-and-attestation.md).
- **The evaluator-image re-pin** (S4, publish-gated). The unit-name
  migration never touches the image; the image pin moves with
  `execution-profiles.json` + the template's
  `COHERENCE_IMAGE_MANIFEST_DIGEST` + `DEVGATE_PIN` as one operation
  (template comment, "Moving the pin and the digest is one operation").
- **New-repo onboarding** (no legacy to migrate): see
  [../NEW_REPO_ONBOARDING.md](../NEW_REPO_ONBOARDING.md).

## Pins

The behavior this guide describes is pinned where it is implemented:
`tests/mutation_battery_image_state.py` (its header documents the
`remove_legacy_units` split into `scripts/lib/runner-units.sh` after the
size gate learned to size `.sh`), and `tests/test_runner_enroll.py` /
`tests/test_runner_enroll_sweep.py` — named tests
`test_legacy_units_are_retired_for_the_runner_being_reenrolled` and
`test_legacy_units_are_left_when_they_belong_to_another_runner`.
