# Evidence — T134: OAP mutation-kill battery and strict-spec validation

Scope: task **3.3** of this change (Gate 3). This note records two controls and
their real outcomes. It does **not** claim any gate is complete and does not
promote anything out of quarantine.

Baseline revision: `02927bc` (`main`, at the time of this run).

## 1. OAP mutation-kill battery

Added `tests/mutation_battery_oap_acceptance.py`, wired into the CI
"mutation batteries" step in `.github/workflows/ci.yml:408` (also listed so
`tests/test_mutation_harness.py::test_every_battery_runs_in_the_suite` accepts
it). It uses the shared `tests/mutation_harness.py`; it defines no private
runner or verdict.

The battery reintroduces the two unsafe acceptances Gate 3 names as the stop
condition, and asserts the existing suite FAILS on each — a survivor means a
guard no named test depends on:

| Mutation | Reintroduced acceptance | Killed by |
|----------|-------------------------|-----------|
| M1 | identity-key (small-order A/R) acceptance in the pure-Python verifier `hub/coherence/ed25519.py` | `tests/test_oap_evidence_signature.py` (`TestStrictPointValidation`, `TestMandatoryCheckRejectsIdentityForgery`) |
| M2 | identity-key acceptance in the vetted provider `hub/coherence/ed25519_vetted.py` | `tests/test_oap_evidence_signature.py`, `tests/test_oap_v2_conformance.py` |
| M3 | duplicate-key acceptance in the strict parser `hub/coherence/strict_parse.py` (`_object_pairs_hook`) | `tests/test_oap_evidence_schema.py`, `tests/test_oap_v2_conformance.py` |

Negative control N1 (a comment reworded in a mutated file) must SURVIVE.

### Observed result

Run on this host by driving the real harness with a no-op `fcntl` stub (Windows
has no POSIX advisory locks; the harness `fcntl.flock` is a no-op under the stub,
hashing/restore logic is the real one):

```
killed  M1: identity-key acceptance reintroduced into the pure-Python verifier
killed  M2: identity-key acceptance reintroduced into the vetted provider
killed  M3: duplicate-key acceptance reintroduced into the strict parser
SURVIVED N1: a comment reworded, saying exactly the same thing

3/3 mutations killed
1/1 negative controls behaved
BATTERY EXIT: 0
```

Independently, each mutation was applied by hand and the named suite run
directly: M1 → 18 failed, M2 → 16 failed, M3 → 3 failed; the tree was restored
after each. So the controls genuinely kill the mutations.

**NOT_EXERCISED on the CI lane from this host:** the battery's own
`fcntl.flock` refusal/lock path and `tests/test_mutation_harness.py` are POSIX
only. CI (`ubuntu-latest`) runs the battery for real; on this Windows host those
two run as `NOT_RUN: needs fcntl` (see `tests/platform_caps.py`).

## 2. Strict OpenSpec validation

Command (identical to the CI gate, `.github/workflows/ci.yml:266-269`):

```
npm install --no-save --no-audit --no-fund @fission-ai/openspec@1.13.0
npx openspec validate --all --strict
```

Observed result at the baseline revision (`02927bc`): **NOT green — 1 failed.**
Recorded honestly, not suppressed.

```
Totals: 32 passed, 1 failed (33 items)
Details: openspec validate add-oap-evidence-consumer --type change

npx openspec validate add-oap-evidence-consumer --type change --strict  →  exit 1
  ✗ [ERROR] oap-evidence-consumer/spec.md: No delta sections found. Add headers
    such as "## ADDED Requirements" or move non-delta notes outside specs/.
  ✗ [ERROR] file: Change must have at least one delta. No deltas found. ...
```

`change/harden-oap-evidence-verification` validates **green** under the same
command.

The failing item was pre-existing at the baseline revision and was **not**
introduced by T134: `add-oap-evidence-consumer/specs/oap-evidence-consumer/spec.md`
used no native `## ADDED Requirements` delta grammar.

### Re-run after the delta-grammar fix

That grammar was then fixed (the `oap-evidence-consumer` delta was restructured
under `## ADDED Requirements` with `### Requirement:` / `#### Scenario:`
blocks, and requirement `coh-oap-08` records that only a bounded non-authorizing
local observer exists — no real Go OAP receiver and no cross-language vectors).
The same pinned command was re-run:

```
npm install --no-save --no-audit --no-fund @fission-ai/openspec@1.13.0
npx openspec validate --all --strict
```

Observed result: **green — 0 failed.**

```
Totals: 33 passed, 0 failed (33 items)
```

`npx openspec validate add-oap-evidence-consumer --type change --strict` →
`Change 'add-oap-evidence-consumer' is valid` (exit 0).

## Re-verification at the remediation head (2026-10-06)

All controls re-run at `3d92411` (`main`):

- Mutation battery: `python tests/mutation_battery_oap_acceptance.py` under the
  same documented no-op `fcntl` stub — **3/3 killed, negative control N1
  survived** (unchanged from the recorded run above).
- Strict OpenSpec validation (`npx @fission-ai/openspec@1.13.0 validate --all
  --strict`): **33 passed, 0 failed**.
- Secret scan (gitleaks 8.30.1, checksum-pinned): full-history + working-tree
  sweep → 68 findings, all 20 allowlist dispositions matched,
  **0 uncovered / 0 stale**. (Run through Git-bash on a Windows host, the
  script's own report hand-off loses gitleaks' temp-file report to a
  POSIX/Windows path mismatch; the numbers above come from running gitleaks
  directly and diffing rule+path against `.guardrails/secret-allowlist.json`.
  CI's Linux lane runs the script as written.)
- OAP-focused suite: `pytest tests/ -k oap` → **146 passed, 147 subtests**;
  the single skip is the POSIX-only `tests/test_mutation_harness.py` fcntl lane.
- Traceability: `scripts/spec_traceability.py` → **advisory, 76/132
  requirements covered** (56 uncovered; advisory, not a pass claim).
- CI on the same revision: [run 37354967182](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/37354967182) — success.

## What remains absent (unchanged by this note)

- No Go OAP receiver exists in this repository. The only in-repo consumer is
  the non-authorizing local observer (`hub/coherence/oap_observer.py`,
  `NON_AUTHORIZING = True`). The loopback in `tests/test_oap_v2_conformance.py`
  is a bounded local path, **not** an OAP integration claim.
- The cross-language canonical-byte/signature vectors
  (`openspec/changes/add-oap-evidence-consumer/vectors/oap-evidence-v2-vectors.json`)
  are now frozen and byte-pinned, but they are Python-produced; consumption of
  the vector FILE by a Go implementation is NOT_EXERCISED
  (`vectors/README.md`). The independent Go receiver
  (`cmd/oap-observer`, sibling `openagentplatform` repo) exercised the live
  producer's output over a local file transport (S-E4,
  `../add-oap-evidence-consumer/evidence-se4-local-pipe.md`) — observe-only,
  no deployed transport, no full negative-fixture parity.
- Independent security-reviewer and OAP-owner approval (task 3.4) remain
  NOT_EXERCISED. Everything here stays observe-only and non-authorizing.
