# Cross-language parity: independent Go OAP receiver vs the frozen v2 vectors

This report records a real, reproducible parity run in which the **independent
Go OAP receiver** consumed the **frozen `devgate.oap-evidence/v2` reference
vectors** and reproduced the AIGGP vectors' expected verdicts for **all 13
cases** (1 positive + every Gate 1-2 negative).

## What was exercised

- **Receiver:** `cmd/oap-observer` from the sibling `openagentplatform` repo,
  built at the tip of `origin/feat/oap-evidence-v2-receiver`
  (commit `ff5c552767c1be62c42dfd97f16bfd7216e5a130`,
  "feat(policy): close the OAP evidence v2 receiver gaps"), on a fresh
  throwaway branch off that ref (no existing branch disturbed).
- **Vectors:** `openspec/changes/add-oap-evidence-consumer/vectors/oap-evidence-v2-vectors.json`,
  **byte-identical** to the Python side
  (SHA-256 `8f3cec8f6d62c02cc15e0299db238af60ff41e6b96c08cd8fe3b1bbdb86197d7`).
- **Transport:** local file / stdin (observe-only). Deployed transport is out of
  scope here (see the split below).

## Exact build + drive

```sh
# Go side (independent receiver), fresh branch off origin/feat/oap-evidence-v2-receiver
cd <oap-w2>
git checkout -b forge/oap-v2-receiver-parity ff5c552767c1be62c42dfd97f16bfd7216e5a130
GOTOOLCHAIN=auto go build ./cmd/oap-observer

# drive: read the frozen vectors, serve the fixture trust/evidence material,
# feed each case's canonical_bytes through the observer, compare per case.
```

The vectors carry no transport; each case's wire artifact is the
`canonical_bytes_hex` NDJSON line. The receiver is driven in two modes matching
how the Python reference verifies each case:

- **wire mode** (10 cases): `-dev-keys <trust-store> -reference-time <R> [-audience <A>] -payload/-result/-manifest/-attestation <bytes>`.
  The audience binds at the wire stage.
- **full observer mode** (`-full`, 3 cases): the context/cross-binding/replay
  stages run, using `-expected <ctx.json>`; audience is bound via the expected
  context's `consumer_audience` (as the Python `oap_observer.observe` does),
  not a separate flag.

Per-case observer command lines are in `PARITY-COMMANDS.txt`; raw observer
output is in `PARITY-OBSERVER-OUTPUT.jsonl`.

## Result — 13/13 MATCH

| case | category | expected | Go observer actual |
|------|----------|----------|--------------------|
| `valid_artifact` | valid | `ok=true` | `ok=true, reason=""` |
| `identity_low_order_key_forgery` | forgery | `signature-mismatch` | `signature-mismatch` |
| `duplicate_json_key` | structural | `duplicate-key:body` | `duplicate-key:body` |
| `wrong_domain_separation_tag` | forgery | `signature-mismatch` | `signature-mismatch` |
| `expired_timestamp` | window | `envelope-expired` | `envelope-expired` |
| `not_yet_valid_timestamp` | window | `envelope-not-yet-valid` | `envelope-not-yet-valid` |
| `key_out_of_window` | window | `key-expired` | `key-expired` |
| `wrong_audience` | context | `audience-mismatch:oap-observer` | `audience-mismatch:oap-observer` |
| `key_audience_mismatch` | context | `key-audience-mismatch:other-audience` | `key-audience-mismatch:other-audience` |
| `lying_digest` | binding | `result-digest-mismatch` | `result-digest-mismatch` |
| `lying_cross_link` | binding | `result-binding-mismatch:subject_digest` | `result-binding-mismatch:subject_digest` |
| `wrong_tenant` | context | `context-mismatch:tenant_or_project_id` | `context-mismatch:tenant_or_project_id` |
| `replayed_jti` | replay | call1 `ok=true` / call2 `replay:duplicate` | call1 `ok=true, reason="non-authorizing:observed"` / call2 `replay:duplicate` |

**13 matched, 0 mismatched.** Every case's `ok` and `reason` agree exactly. The
`replayed_jti` sequence (call 1 admitted non-authorizing, call 2 duplicate
denial) matches on both calls; the Go observer additionally reports
`outcome`/`replay_status` fields, which are observe-only annotations and do not
diverge from the vectors' `{ok, reason}` contract.

No divergence was found; there is nothing to paper over.

## Verifications

- Go side: `GOTOOLCHAIN=auto go build ./cmd/oap-observer` → exit 0.
- Python side: `python -m pytest tests/test_oap_evidence_vectors.py -q` →
  `3 passed`.

## EXERCISED vs NOT_EXERCISED

**Now EXERCISED (this run):**

- The independent **Go OAP observe-only receiver** (`cmd/oap-observer`)
  **consumed the frozen v2 vector FILE** — a process/language boundary, not an
  in-repo mock — and reproduced the vectors' expected verdict exactly for the
  positive case and **every Gate 1-2 negative** (identity forgery, wrong domain
  tag, duplicate key, expired / not-yet-valid, key out of window, wrong
  audience, key-audience mismatch, lying digest, lying cross-link, wrong tenant,
  replay).

**Still NOT_EXERCISED:**

- **Deployed transport.** This run used local file/stdin. The Go receiver's
  HTTP(S)/mTLS transport is scaffolding and is *not* exercised here.
- **Independent review.** No independent security reviewer and no OAP owner have
  assessed this evidence (Gate 3.4 / S-E3.1's review remainder).
- **Effects.** Nothing here authorizes, promotes, or produces an OAP effect; all
  verdicts remain NON-AUTHORIZING / observe-only.

Accordingly this report closes the **negative-fixture parity** gap of
`harden-oap-evidence-verification` Gate 3.1 (`local loopback EXERCISED; frozen
vectors EXERCISED; Go OAP consumer now EXERCISED`), but the full S-E3.1 exit is
**not** claimed: deployed transport and independent review remain
NOT_EXERCISED.
