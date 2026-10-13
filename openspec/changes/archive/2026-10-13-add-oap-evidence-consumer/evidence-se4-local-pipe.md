# Evidence — S-E4 local observe-only pipe (DevGate producer -> Go OAP consumer)

**Date:** 2026-10-04
**Status:** EXERCISED (local file transport, observe-only / NON_AUTHORIZING).
Deployed transport and independent reviewer/OAP-owner approval remain NOT_EXERCISED / NOT_RUN.

## What this proves

The DevGate (Python) producer (`tools/oap_produce.py`, commit `24bb274`) emits contract-v2
NDJSON wire envelopes that an independent Go OAP receiver consumes byte-for-byte across a
process/language boundary — the Go observer printed the expected verdict for all 10 cases.

This is a real cross-language consumer boundary (file transport), not an in-process
loopback. It does NOT prove a networked/deployed transport, any effect authorization, or
independent review. The producer is strictly observe-only (`NON_AUTHORIZING = True`).

## Reproducing

```
# AIGGP
python tools/oap_produce.py --all --evidence-dir <dir> --out <dir>/envelopes.ndjson

# Go OAP (C:\git\openagentplatform-audit-plan, cmd/oap-observer commit 9746781)
oap-observer -file <dir>/envelopes.ndjson -dev-keys <dir>/keys.json \
  -expected <dir>/expected.json -payload <dir>/payload.bin -result <dir>/result.bin \
  -manifest <dir>/manifest.bin -attestation <dir>/attestation.bin \
  -reference-time <dir>/reference-time.txt -full
```

## Observed verdicts

valid → `non-authorizing:observed`; identity/low-order forgery → `unknown-key:ed25519:…`;
duplicate JSON key → `duplicate-key:body`; wrong domain tag → `signature-mismatch`;
expired → `envelope-expired`; wrong audience → `key-audience-mismatch:oap-observer`;
wrong tenant → `context-mismatch:tenant_or_project_id`; lying digest →
`result-digest-mismatch`; replayed jti (×2) → `replay:duplicate`.

Full table and interpretation: see the sibling note in the Go OAP repo
(`openspec/changes/oap-security-authority-follow-up/evidence-se4-cross-language-observe-only.md`).

## Remaining for S-E4

- Deployed/networked transport between DevGate and Go OAP (file transport only here).
- Cross-language CI-lane parity + artifact-adapter freeze.
- Independent security reviewer + OAP owner approval before any mandatory use.
