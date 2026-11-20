# Change: Six Open-Item Gates, One per Deficiency Family

> **Status:** Gates and specs are implemented in `scripts/`. Enforcement placement
> is NOT wired by this change — where each gate runs is an owner decision.

## Why

The daily digest's open-items ledger (`ai-news/nextday-actions.md`, 2026-08-27
through 2026-11-05 — 67 days, 762 SAGE turns across 39 dates) shows six
recurring deficiency families. Each is a class of finding the existing DevGate
suite cannot detect, and each recurred often enough that "we will be careful"
is not a control:

| Family | Recurrence in the 67-day ledger |
|--------|--------------------------------|
| Unpushed or local-only work | 51 of 67 days (76%) |
| A fix that never reached a declared surface | 59 of 67 days (88%) |
| Unclassified working-tree dirt | 42 of 67 days (63%) |
| Aged open items that never retire | flat ~7/day, nothing retires |
| Secrets scrubbed from `HEAD` but never revoked | 26 of 67 days (39%) |
| Mock / stub / deferral with nothing followable | recurring, family NEXT-014 |

DevGate's shipped gates cover file size, pattern rules, semantic patterns,
regression ranges, test floors, and spec traceability. None reads local-vs-remote
ref state, working-tree classification, triage aging, revocation status, surface
parity, or evidence claims. This change specifies and implements one gate per
family so a reviewer can accept or reject each independently.

## What Changes

- **Six new gates** under `scripts/`:
  - `open_item_aging_check.py` — aged open item must carry a live triage
    disposition (`fixed` / `deferred` / `not-actionable`); an expired deferral
    fails.
  - `branch_drift_check.py` — a local ref whose tip is reachable from no remote
    ref is drift; comparison is against advertised remote refs, not a cached
    remote-tracking ref.
  - `tree_clean_check.py` — working-tree entries matching neither a declared
    generated pattern nor a committed change fail, named individually.
  - `secret_rotation_check.py` — removal from `HEAD` is not revocation; an
    unrevoked detection past its window fails.
  - `surface_reach_check.py` — every declared surface of one artifact must hold
    identical content; a vanished surface is a failure, never a skip.
  - `evidence_claim_check.py` — `DEFERRED` carries owner, reason, and a future
    review date; a mock or stub must point at the real thing it stands in for or
    a tracked issue.
- **Six spec deltas** under `openspec/changes/add-open-item-gates/specs/`, one
  capability per gate, 26 requirement IDs total (`bd-*`, `evc-*`, `oia-*`,
  `sr-*`, `srch-*`, `tc-*`). Each script carries the markers for its own family.
- **A shared honesty contract, reused rather than reinvented.** Every gate keeps
  DevGate's existing nothing-scanned semantics: exit `3` when it evaluated zero
  inputs, never a bare green. Exit codes are frozen as `0` pass, `1` violation,
  `2` usage/config error, `3` nothing scanned.
- **Frozen CLI shapes.** Each gate takes its input as an explicit path argument
  (backlog, triage ledger, rotation ledger, surfaces manifest) or a `--root`
  walk; none guesses a project layout and none writes state.

## What Does Not Change

- **No CI wiring.** The commit that adds the scripts records: "Not wired into
  CI in this change: enforcement placement is an owner decision, and push-time
  CI detects rather than prevents on a repo that takes direct pushes to main."
  Nothing here enables, blocks, or slows a push.
- **No existing item is triaged, closed, or reclassified.** The triage and
  rotation ledgers are inputs the gates read; this change does not create them
  with content.
- **No existing spec is modified.** All six deltas are ADDED requirements.

## Impact

- New CLI surface only; no library imports change, so the test suite's behaviour
  is untouched apart from the requirement markers traceability now sees.
- Traceability coverage rises from 202 to 228 covered IDs; the ratchet floor is
  raised to match, so a later removal of a marker is a gate failure rather than
  an advisory note.
- Enforcement placement remains tracked as an open decision: until a caller
  runs a gate, it is a tool on disk, not a control.
