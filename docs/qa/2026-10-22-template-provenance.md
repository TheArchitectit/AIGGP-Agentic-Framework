# Template provenance — first lock (SGA-20..22)

Date: 2026-10-22 (UTC). Package: `spec-audit-rollout`, Sprint 3.

## What was done

`spec-templates.lock.json` created with four entries, each recording the
official openspec template's upstream source URL, sha256 of the copy in
the pinned npm package, and the upstream version. Every hash was verified
locally before being written — the same gitleaks discipline (URL + sha256 +
version assert, verified locally before pinning) applied to content rather
than a binary.

## Verified locally

```
$ sha256sum /mnt/data/git/AIGGP-Agentic-Framework/node_modules/@fission-ai/openspec/schemas/spec-driven/templates/*.md
proposal.md  ea0879a322bb1a3c6e3002c67b5a29e31120dcb17219e3000d43775f48481284
spec.md      1f370642f106589d901c0568e81b5f7741e9289da48df41b70dd21ad99592a0c
design.md    e47df296318c6622f0b0911407e16b1578169403b96f61bf35fe1db7f7b417d6
tasks.md     b2a6a4c08c15f347a1d8c3e2d43e0c8fb066dc5cc0feb795f47555f176f9c421
$ node -e "console.log(require('/mnt/data/git/AIGGP-Agentic-Framework/node_modules/@fission-ai/openspec/package.json').version)"
1.13.0
```

The same pin the `templates/github-workflows/specs.yml` CI template uses
(`OPENSPEC_PACKAGE: "@fission-ai/openspec@1.13.0"`), so the lock and the
gate agree about which upstream produced the hashes.

## The provenance step (SGA-20..22)

Two checks, run at different frequencies — they were one function until
the first sweep showed upstream drift printed once per repo row:

**`check_lock()` — once per sweep** (`spec-fleet-classify.py
--lock-check-only`):

- `pin_source` (the v1.13.0 tag URL each pin was verified at) is fetched
  and hashed; a hash that no longer equals `pinned_sha256` is a gate fault
  — the lock would be lying about its own pin;
- `source` (branch `main`) is fetched and hashed; a difference from the
  pin is **upstream drift**, the SGA-21 alert, not a bad pin;
- unreachable either way -> `unknown` for that template + fault red, never
  read as in-sync (SGA-22). Drift and unlocked are findings (deduped
  issue); fault and unknown are red.

**`check_provenance()` — per tree, no network:**

- compares each vendored copy in the tree against its pin -> local drift
  entry naming template + both hashes (each truncated to 12 hex chars,
  pinned listed first), consistent with the drift alert shape SGR-06 uses;
- a locked copy that is gone, or a template present in tree without a lock
  entry -> `unlocked` finding;
- `vendored_path: null` (documented "no copy yet") -> not-vendored, no
  finding; flagging it made every sweep red forever on a decision the lock
  itself records.

Detection is automated. **No automated process writes into any tree**: the
lock file and any vendored copy change only in one reviewed commit, and the
drift alert's issue closes against that commit (SGA-21 scenario 3).

## State of the lock today

This staging repo vends no openspec templates of its own, and DevGate has
no vendored template copy yet (`vendored_path: null` on all four entries).
The lock therefore records the canonical upstream hashes so a future
vendored copy can be checked against them.

First measured sweep (2026-10-23, AIGGP + MC + tracker): all four
`pin_source` hashes match their pins (`pin_ok`), `lock_provenance.fault`
is false, and **all four upstream `main` copies differ from the v1.13.0
pin** — real drift, reported once for the sweep, which is exactly the
SGA-21 alert the first adoption round-trip will consume.

## First reviewed adoption round-trip (SGA-21 scenario 3)

Not yet executed — it needs a consumer repo to opt in. When it happens:

1. drift alert opens on `spec_fleet_sweep` naming template + both hashes;
2. a human reviews, takes the upstream change, and bumps the vendored copy
   + lock entry in one reviewed commit in that consumer repo;
3. the alert's issue closes against that commit.

The lock file records the adoption date and the commit when it lands.
