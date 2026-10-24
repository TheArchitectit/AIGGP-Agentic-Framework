# Spec Fleet Sweep — first live runs (SGA-10..13, SGA-21)

Date: 2026-10-24 (UTC). Program package `spec-audit-rollout`, box 2.3
(`hub_alert --key spec_fleet_sweep` wiring + the three T-style proofs) and the
SGR-11 drift channel behind box 3.2.

## How these runs happened, and why not on the cron

The workflow had **never run** before this window (`gh run list --workflow=
spec-fleet.yml` was empty), and the first scheduled fire (`47 4 * * *`) had not
happened by 05:08Z. Scheduled runs do work on this repository, but the cron
clock is hours late: the Secret Fleet Sweep's `17 4` cron landed at 09:23–09:28
on 2026-10-21, -22 and -23. So the evidence below is from `workflow_dispatch`
runs of the same workflow, job and steps, not from a cron fire. That
difference is stated rather than papered over.

## The three plumbing defects the dispatches found first

Pre-flight dispatches were run precisely because a first-ever workflow is more
likely to fail on plumbing than on findings. They did:

1. **`npm` on the runner is broken.** Run `40062683265` died in "Install the
   pinned openspec CLI": `Cannot find module '../lib/cli.js'` from
   `/home/runner/externals…/node20/bin/npm`. `ci.yml` already sidesteps this
   with `actions/setup-node`; the sweep now does the same (`581ad56`).
2. **The declaration generator had no token.** Run `40062752087` got past the
   install and died in `secret-scan-declared.sh`: `gh repo list failed`, exit 2.
   Fixed by giving that step `GH_TOKEN` (`3b8536b`).
3. **The alert was unreachable.** Run `40062808349` walked successfully and
   redded (`RED: ['rad-gateway', 'radcode', 'RADICAL-CODE',
   'stitcher-codereview', 'spec-audit-probe-deleted-20261024']`) — but under
   `set -eu` the failing red-check heredoc aborted the step before `rc=$?`, so
   the `hub_alert` line never ran and issue #35 received no comment. Fixed with
   `|| rc=$?` in both the red check and the provenance check (`161e0de`).

A fourth, non-defect observation from the same run: the shared declaration
carries private repos (four `drwhofan2k18-pixel/*` entries on this run), and
the walk clones unauthenticated, so they can only be `unscannable` — red every
night. The step now asks GitHub per declared repo and drops only what the API
positively reports as private, naming what it dropped; a repo the API cannot
read is **kept** on purpose, because 404 is also how a deleted repo answers and
SGA-12 requires that one to red (`fe057c6`, with the
`fleet-sweep-include.txt` probe removed in `69e0dc0`).

## The proofs

**SGA-12 — an unscannable repo names itself.** The declaration carried one
deliberately dead URL (`TheArchitectit/spec-audit-probe-deleted-20261024`).
Runs `40065113656` and `40065279255` produced, in the alert that lands as a
comment on the open issue for the key:

```
could not be scanned (name — reason):
  rad-gateway — unscannable: Command '['git', 'clone', '--depth', '1', …
  …
  spec-audit-probe-deleted-20261024 — unscannable: Command '['git', 'clone', …
```

The repo is named, not merely counted, and the reason is the git invocation.

**SGA-13 — one issue, recurrences comment.** Five occurrences of the key across
`40062683265`, `40062752087`, `40062808349`, `40065113656`, `40065279255` — and
still exactly **one** open issue for `spec_fleet_sweep` (#35), with the
recurrences as comments. The first two were `no report` alerts (the plumbing
defects above); the last three carry the full report body.

**SGA-21 / SGR-11 — drift has its own channel, and a red night does not
swallow it.** On the same red night, issue #36 (`spec_template_drift`) was
raised, carrying the four upstream drifts:

```
template drift (template, kind, hashes, pin version):
  openspec-design  upstream  e47df296318c → 6ccc87f5017f  (pin 1.13.0)
  openspec-proposal  upstream  ea0879a322bb → 0dd70e35db5c  (pin 1.13.0)
  openspec-spec  upstream  1f370642f106 → 1cccfb573f03  (pin 1.13.0)
  openspec-tasks  upstream  b2a6a4c08c15 → fa67d99fb4a9  (pin 1.13.0)
```

**SGA-10 — discovery, in its measured half.** The report's `unspaced[]` names
eleven repositories (`NemoClaw`, `claw-code`, `openclaw`, `pi-mega-compact`,
`pi-setup`, `plexus`, `smallcode`, …) that no human declared in any per-repo
file: they came from owner-scope generation and were classified without a
discovery action. The strict form of the scenario — a repository that did not
exist yesterday appears in tonight's list — has no before/after pair yet; that
needs a newly created public repo, which is an owner action, not this gate's.

## Census (run `40065369473`, after the probe line was removed)

`declared 22 — spaced 4, invalid 3, unspaced 11, unscannable 4`. The four are
the private `drwhofan2k18-pixel/*` repos (`rad-gateway`, `radcode`,
`RADICAL-CODE`, `stitcher-codereview`).

## Residual, recorded as open rather than fixed quietly

Those four private repos still red the sweep every night, and the same four
red the Secret Fleet Sweep (#24, 28 comments). Three ways out, and the choice
is an owner decision because two of them move a credential:

1. **Authenticated clone** for unreadable repos. Safe to implement without
   leaking into the report (a `CalledProcessError`'s `str()` is the argv, and
   the argv URL stays token-free) but it puts a token into a subprocess
   environment on the runner — a credential-plumbing design, not a one-line fix.
2. **Exclude them** in `fleet-sweep-exclude.txt` with a reason. This is the
   reviewed exclusion mechanism, but it applies to both sweeps and would stop
   any scanning of those repos rather than fixing it.
3. **Accept the red** as an honest "we cannot read these" signal, deduped to
   one issue.

Until one is chosen, the nightly is red for exactly these four names.
