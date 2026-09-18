# S3 delivery record — slice hardening and pilot-shaped demos

Ledger for the S3 batch: what shipped, which commit, what was verified how,
what is open, and what the gate disposition is. Written by the lead at
`b538c79` + this doc; the audit-chain rules in `docs/WRITE_AUDIT_REVIEW.md`
mean none of below counts as *independent* verification until the round-5
pass (see "Independent verification" at the end).

Provenance labels per R9: all fixture content described here is SYNTHETIC —
LobsterWars-shaped, not captured from a live repo.

## What shipped

| Area | Deliverable | Commit | Spec ids |
|---|---|---|---|
| Envelope honesty | Runtime schema validation at every trust door (request, context, adoption sets) via stdlib `schemacheck`; consolidates the round-3/4 crash-vector family into one door guard; protocol guard (exit 40) still precedes schema validation; `_require()` names missing keys | `c9a34c5` | coh-req-01, coh-dec-02 |
| Envelope honesty | `test_frozen_schema_files_are_strict` — every wire-contract object schema must carry `additionalProperties: false`; a relaxed file fails the suite | `c9a34c5` | coh-ev-04 |
| Control plane | `hub/coherence/issue.py` (174 lines): pilot context issuance — authoritative stage registry with downgrade refusal, baseline/exception sets written to the policy dir and digest-bound into the context, HMAC countersignature stand-in (`hmac-sha256:`, key `HUB_COHERENCE_CP_KEY`; real signing is S5/ADR-018) | `85b9cda` | coh-ctx-02 |
| Control plane | `context.load` requires a valid signature whenever a CP key is configured; `verify_bound_sets` fails closed on post-issuance baseline/exception swaps | `85b9cda` | coh-ctx-01 |
| Reporting | `hub/coherence/report.py`: advisory age and exception expiry computed against the CONTEXT `evaluation_time` — never the host clock — so reports for sealed results are reproducible; `summarize` marks replay results non-promotion-authorizing | `85c6f5e` | coh-pol-03, coh-pol-06 |
| Semantics | Replay path pinned end-to-end: identical-context re-run is byte-for-byte identical; a replay-labeled run matches the fresh run on decision fields and differs only in labels (context/semantics digests ride along by design); issuance refuses bad semantics; an expired-advisory repo cannot dodge expiry by claiming replay | `85c6f5e` | coh-ctx-03 |
| Demo | Acceptance Fixture C ladder through the **real CLI** on a 13-finding synthetic world (8 tests): Stage 1 ADVISORY 0/13/0 → Stage 2 named-debt ADVISORY → new violation FAIL 1/13/0 → expired exception FAIL 1/12/0 → live exception ADVISORY 0/12/1 → wildcard exception exit 31. Narrative: `demo/ladder-report.md` | `b538c79` | coh-pol-04, coh-pol-05, coh-dec-01 |
| Gate hygiene | GD-3 recorded: publishing `openspec/specs/` while the change is active double-counts shared ids (measured 48/125 with 25 dup listings vs 48/99); publish deferred to S8 archive | `b538c79` | — |

Test counts: S2 closed at 108 coherence / 204 repo-wide; S3 batch ends at
**152 coherence / 248 repo-wide**, all green at the recorded pin. Every guard
added in the batch was mutation-caught on a `/tmp` copy of the tree (mutation
in the working tree is banned after the round-4 freeze-break findings; ledger
in `s2-remediation.md`).

## Decisions made in this batch (lead, recorded for architect review)

1. **Gate-config posture: none yet — coherence stays advisory.** No
   `openspec/gate-config.json` entry for `coh-*` until the ladder demo is
   lead-reviewed AND S4's container closes (coh-rt-02/06 tests). A blocking
   posture before the runtime boundary exists would gate on what the spec
   itself calls incomplete (coh-dec-04 ERROR semantics demand
   launcher-validated execution). The flip to `blocking` will be its own
   review-gated commit. Rationale per ADR-006: enforcement where it counts
   now is the baseline ratchet, not the repo gate.
2. **Published-spec creation deferred to S8 archive.** Tried it, measured the
   double-count, reverted the directory cleanly. Follows the
   `2026-09-13-runner-monitor` archive precedent. Durable fix is in
   `scripts/spec_traceability.py` (GD-3), not in a workaround here.
   Marker-coverage anchor measured at this writing: 38 of 64 unique coh-*
   requirement ids carry `// spec:` markers in `hub/coherence/`; the 26
   uncovered are exactly the not-yet-built capabilities — all seven
   `coh-int-*` fleet ids, all four `coh-3d-*` ids, `coh-rt-*` runtime ids
   except the slice subset, `coh-ev-01/04/05` sealing/attestation,
   `coh-eval-01/04` plugin/3D evaluators, `coh-assert-05/06`,
   `coh-ctx-04/05`, `coh-pol-07`, `coh-id-04` — the marker gap tracks the
   implementation gap, which is the intended shape. (Counting note: the
   `coh-3d-*` slug contains a digit; measurement regexes that assume
   `[a-z]+` slugs undercount the corpus by 4. The committed "32 of 64"
   anchor at `b538c79` predated issue.py/report.py markers and was stale
   low, not regex-wrong.)
3. **HMAC is a labeled stand-in, not a signature story.** `issue.py` and
   `test_hub_coherence_issue.py` say so in-module; the one strict behavior
   added: with a CP key configured, an unsigned context cannot load. S5
   replaces the primitive (ADR-018), not the contract.
4. **Replay equality is field-level, not byte-level, across semantics.** An
   earlier overclaim ("replay is byte-identical to fresh") was corrected
   mid-batch: the context digest differs by design because `semantics` is
   part of the manifest. What holds, and is pinned: fresh↔fresh byte
   identity, and replay↔fresh equality on the decision fields only.
5. **Test-file split deferred alongside the GD-1/GD-2 gate fix.** Splitting
   now, before the scanner ordering is fixed, risks both files becoming
   commit-blockers if GD-2 lands before GD-1. Ordering rationale stays in the
   open checklist item below.

## Open items (carried out of S3)

| Item | Why open | Lands in |
|---|---|---|
| ~~`traceability_completeness` consuming this repo's marker conventions (`<!-- id: -->` ↔ `// spec:`)~~ **LANDED 2026-09-18** — see "S3 tail progress" below | ~~structural planning check exists (coh-assert-04); repo-marker wiring is the remaining half~~ | done |
| Submodule commit-pinning (manifest records `submodule-pinned` entries but not the pinned commit digest) | round-1 partial; needs a fixture repo with a real submodule | S3 tail |
| Split `test_hub_coherence_conformance.py` (519) / `test_hub_coherence_exitcodes.py` (523) | sequencing hazard with GD-1/GD-2 (see decision 5) | with gate fix |
| Wrap success-path `_emit` at `__main__.py` (race-only window) | round-3 info-severity | any batch |
| ADR-001…019 clause dispositions + owner-decision confirmations (Q1–Q5/Q9, defaults in `s1-freeze-record.md` §7) | architect-only; audit covered code, not clause acceptance | architect |
| `semantic-scan.mjs` root detection (resolves to repo PARENT; never scanned this repo) | GD-adjacent; either scope it here or declare out of service — do not keep a silently-parent-scanning gate | separate tooling change |
| Independent verification of `c9a34c5..HEAD` | see below | round 5 |

## Known environment incidents during this batch

- **Shared-tree npm incident (2026-09-17):** while trying to make
  `semantic-scan.mjs` functional, `npm install --no-save typescript@5` was run
  from this repo, which has no `package.json` — npm walked up to
  `/mnt/data/git` and downgraded the shared `typescript` 7.0.2 → 5.9.3 (the
  parent dir is not under VCS). Restored with
  `npm --prefix /mnt/data/git install typescript@7.0.2 --no-save`; residual
  "missing" entries verified to be 29 platform-optional packages. The episode
  is also why the semantic-scan item above exists: the scanner's root
  detection (`scripts/semantic-scan.mjs:33`) is broken for this repo, and
  "fixing the gate" by installing packages from inside a repo without one is
  exactly the hazard. No service code or committed content was affected.

## Gate disposition (S3)

The S3 gate reads: *"ladder demo reviewed by lead; published spec traceable."*

- **Ladder demo reviewed by lead:** the demo, report, and all 8 pins exist at
  `b538c79` (`demo/ladder-report.md`). Lead review is the architect's
  10-minute read; **not yet signed off** as of this record. This document is
  the review package.
- **Published spec traceable:** **formally deferred** to S8 archive per the
  measured GD-3 double-count and the runner-monitor precedent. The clause
  cannot close inside S3 without either accepting inflated traceability
  numbers or building the GD-3 fix early. Disposition proposed: gate clause
  moves to S8; S3 closes on the demo-review clause + this record.
- **Independent verification:** **Round 5 COMPLETE — APPROVE** (fresh agent
  session, 2026-09-18, pin `0db45ed` == origin/main, tree clean, all
  mutations confined to `/tmp/dg-mut` and `/tmp/dg-r5-audit/`). All six
  falsification experiments confirmed the batch: protocol-before-schema
  (foreign api_version → exit 40), HMAC battery (tamper/wrong-key/unsigned
  refused with key set), set-swap fail-closed (exit 31 with bound-digest
  reason), replay (byte-identical re-run; fresh-vs-replay diff confined to
  context_digest+semantics; summarize non-authorizing), clock independence
  (no now()/utcnow()/time.time in report.py), and 6/6 guard mutations caught
  on a /tmp copy. Gates re-verified: pytest 248, strict-valid, regression
  exit 0 (exactly 2 soft warnings), guardrails exit 0 (exactly 1 nonblocking
  PREVENT-024 at tests/test_regression_check.py:46), silent-success exit 0.

  Two minor findings, both remediated same-day:
  1. design.md repo-wide traceability number unpinned/stale (observed 49/100
     at HEAD vs claimed 48/99; delta: `b24ef75` marker → +1 covered,
     `a2fc2a0` add-runner-to-fleet → +1 total). FIXED: number re-pinned with
     explicit volatility note — re-measure at every gate.
  2. `exception.schema.json` declared `reason minLength 1` but
     `schemacheck.SUPPORTED` omitted the keyword — the set door silently
     accepted an empty reason. FIXED: minLength implemented in schemacheck,
     class-level lock added (`test_frozen_schemas_use_no_unenforced_vocabulary`
     — any constraint keyword used by a frozen file must be in SUPPORTED),
     set-door pin added (`test_empty_reason_exception_rejected_at_issuance`),
     arm test added to `TestSchemacheckNegativeControls`. Mutation on a /tmp
     copy (arm disabled) fails all three. These remediations are post-APPROVE
     and ride into the next audit round with the S3 tail.
  Info-only: 1 pre-existing PytestUnhandledThreadExceptionWarning outside the
  audited range (tests/test_hub_monitor.py::test_github_client_backoff).

  **S3 remains DELIVERED, not ACCEPTED**: the fresh-round blocker is cleared;
  architect sign-off on the ladder demo is the remaining clause.

## S3 tail progress (post-round-5, 2026-09-18)

- **Repo-marker wiring LANDED.** `traceability_completeness`
  (`devgate.builtin.traceability-completeness`) gained an opt-in
  `parameters.marker_scan` that consumes this repo's marker convention:
  testable requirement ids in the package registry must be claimed by a
  `// spec: <id>` marker in subject source, using the exact grammar of
  `scripts/spec_traceability.py` (comma-anchored multi-id marker lines;
  trailing prose such as `// spec: a-01 -- why` cannot fake coverage;
  `target/node_modules/.git/openspec/.devgate` skipped; `.rs .py .mjs .js
  .ts` scanned). A missing subject tree raises UNRESOLVED
  (`subject-root-missing`), never VIOLATED, per coh-assert-02 — a scan of a
  nonexistent tree would otherwise report every requirement unmarked.
  Findings are `unmarked-requirement`, one per requirement id with the id as
  location so `finding_key` stays distinct (coh-assert-06).
- **coh-eval-04 marker gap closed.** The bidirectional registry rule
  ("every testable requirement MUST trace to at least one assertion") was
  already enforced by `plan.check_traceability` and the evaluator's
  `orphan-requirement` half, but carried no `// spec:` marker — the
  round-5 traceability report listed it UNCOVERED. Markers added to
  `evaluators.py` and `plan.py`. Repo-wide traceability: 50/100 (was 49/100
  at `0db45ed`; the +1 is exactly coh-eval-04).
- **Verification:** pytest 257 (+6 marker-scan tests, all in
  `TestTraceabilityMarkerScan`); regression exit 0 (2 soft warnings);
  mutation checks on `/tmp` copies only — marker branch disabled (4 tests
  fail), UNRESOLVED guard dropped (1 fails), marker regex loosened (2 fail);
  working tree never mutated.
