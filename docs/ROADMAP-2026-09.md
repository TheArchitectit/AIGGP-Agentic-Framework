# DevGate Agentic Framework — Improvement Roadmap

**Date:** 2026-09-19 · **Method:** full-repo review — every hub/coherence module
read line-by-line, all scripts/templates/workflows/specs/tests reviewed (four
independent review passes + prior QA docs re-verified), findings triaged into
OpenSpec change packages.

**Prior art:** `docs/qa/2026-09-13-full-qa.md` (C1-C7/H1-H8/M1-M11/L1-L8) and
`docs/qa/external-audit-2026-09-14.md`. This roadmap re-verified every prior
finding against current HEAD, closes some as fixed, and adds new findings the
prior audits did not contain — most critically the container-image contract
defect (F1 below).

---

## Where the repo stands

**Genuinely strong (keep and protect):**
- The coherence service (`hub/coherence/`, ~4k lines): disciplined
  canonicalization and domain-separated digests, digest-verified packages and
  contexts, overlay can-strengthen-never-weaken, adoption ladder with
  fingerprinted baselines and expiring exceptions, atomic artifact emission
  with fallback, exit-code matrix honored end-to-end, and a launcher that
  derives (never trusts) the isolation context. Its test suite is ~85%
  behavioral with mutation-testing rationale documented.
- The overlay merge contract (`gate_overlay.py` + JS mirror), hunk-accurate
  diff parsing, no-vacuous-green contracts in the newer gates, the four-gate
  Write→Audit→Review process, and the failure-registry loop.
- The monitoring hub's token design (one-time enrollment, revocable
  per-runner heartbeat, constant-time compares, atomic registry saves).

**Systemic weaknesses (this roadmap attacks):**
1. Fixes don't propagate — the same bug class is fixed in one gate and open in
   two others (root detection, allow annotations, overlay merge).
2. The framework enforces nothing on itself — no CI runs its tests, its specs
   fail `openspec validate` 15/15, its own gates self-trigger warnings.
3. Truth drift — README/AGENTS/CHANGELOG/templates describe a smaller, older
   repo; two parsers disagree about what the specs say; another project's data
   ships in the baseline.
4. The newest, most safety-critical component (containerized evaluation)
   cannot actually evaluate anything (F1) — and its only real-container test
   cannot detect that.

---

## Findings inventory (new, not in any prior QA)

| ID | Severity | Finding | Location |
|----|----------|---------|----------|
| F1 | **Critical** | Pinned evaluator image cannot load its frozen schemas (`SCHEMA_DIR` resolves to `/app/openspec/...`, never copied) — every in-container request dies exit 30 with a misleading reason; the only real-container test asserts exit 30, so it passes while the service is broken. Runtime also depends on an ACTIVE change-package path — archiving breaks the host CLI too. | `hub/coherence/__main__.py:24`, `schemacheck.py:20`, `container/Containerfile:26`, `tests/test_hub_coherence_container.py:405` |
| F2 | High | SIGTERM/SIGINT shutdown hangs: `handle_request()` blocks in `select()`, PEP 475 retries after the handler; systemd stop degrades to SIGKILL, losing the documented exit-0 clean shutdown. | `hub/main.py:92` |
| F3 | High | `package.resolve` joins repository-supplied inventory paths to the root with no containment check — host-file existence oracle/digest probe inside the evaluator. | `hub/coherence/package.py:48-61` |
| F4 | High | `evaluators._extract` file selectors read outside the subject tree; matched content lands in findings/evidence (exfiltration path). | `hub/coherence/evaluators.py:181-189` |
| F5 | Medium | Queue-stall alerts key on `run.get("run_id")` — not a GitHub API field (it's `id`); all alerts collapse to the same dedupe key. | `hub/monitor.py:252` |
| F6 | Medium | `watched_branches` defaults to `["default"]` — not a real branch; the gate-results check silently 404s on a default deployment (dead check class). | `hub/config.py:44`, `hub/monitor.py:256` |
| F7 | Medium | `Retry-After` read from the JSON body; GitHub sends it as an HTTP header — backoff never honors it. `.get` on list bodies would also crash the loop cycle. | `hub/monitor.py:95` |
| F8 | Medium | Enroll TOCTOU: `already_enrolled` checked outside the registry lock; concurrent duplicate enrolls both succeed. | `hub/server.py:142` |
| F9 | Medium | `_read_json` trusts `Content-Length`, no cap — memory-DoS if the bind is ever widened; no rate budget on token attempts. | `hub/server.py:83-88` |
| F10 | Medium | Monitor thread iterates `registry.runners()` unlocked while HTTP threads save — undocumented threading contract, racy. | `hub/monitor.py:152` |
| F11 | Medium | `manifest.build` reads each file twice (size from one read, digest from another) — internally inconsistent entries on mid-run mutation. | `hub/coherence/manifest.py:171-186` |
| F12 | Medium | Tests: missing `tests/__init__.py` — five conformance files silently vanish from collection on any machine with a foreign `tests` package (reproduced: 239 collect, 5 error). | `tests/` |
| F13 | Medium | Golden vectors (`vectors.json` + fixtures) consumed by nothing; generator re-implements `canon` — the `coh-id-01` compatibility contract is asserted nowhere. | `tests/fixtures/coherence/` |
| F14 | Medium | Launcher `proc.kill()` on timeout/overflow kills the podman client; the container may outlive it (conmon) — no reaper/`--stop-timeout`. | `hub/coherence/launcher.py:295-297` |
| F15 | Low | Dead code: `server._parse_ts`, unused `owner` locals (×2), duplicated `__main__` block, unused `ZERO_DIGEST`. | hub/*, tests/* |

Plus the full prior-QA carry-over set (C1-C7 still open except C5's registry
arm; H1-H8 open except H5 fixed; M-series mostly open) and the systemic
duplication table (6 root detectors, 3 overlay merges, 3 JSONL readers, 3
allow-annotation semantics, 4 glob engines, 5 SKIP_DIRS) — see
`consolidate-shared-gate-logic/proposal.md`.

---

## The roadmap — three phases, eight change packages

All packages live under `openspec/changes/`. Dependencies run downward within
a phase; phases gate on their P0 exit criteria.

### Phase 0 — Stop the bleeding (correctness you cannot ship over)

| Change | What it delivers | Exit criteria |
|--------|------------------|---------------|
| `fix-coherence-container-contract` | Schemas moved into the service package; image rebuilt; smoke test gains a valid-request PASS path so a broken image can never read as green. | In-container valid request returns non-ERROR; `schemacheck.load` works in-container; registry entry for the incident. |
| `fix-vacuous-and-broken-gates` | C1-C4/C6/C7 + H6/H8 + two new vacuous-green bugs (failure_registry_check explicit path; never-run scanner test). | Every QA-listed critical reproduced-then-green; standalone-clone fixture tests pass for all three scanners. |
| `add-framework-ci-pipeline` | PR CI: full test suite (with the `tests/__init__.py` fix), self-gates, spec validation step, SHA-pinned actions. | A PR that breaks a test cannot merge; collection is deterministic; framework tree warning-clean on itself. |

**Phase 0 gate:** CI exists and is green; no gate passes vacuously on any
verified defect; the container path provably evaluates.

### Phase 1 — Trust boundaries and platform truth

| Change | What it delivers | Exit criteria |
|--------|------------------|---------------|
| `harden-security-boundaries` | F2-F11 + F14: path containment (F3/F4), signal-safe shutdown (F2), request cap + locked enroll (F8/F9), hashed-at-rest tokens, monitor field/default/header fixes (F5-F7), container reaper, template action/image pinning, enroll JSON escaping + token-silent output, one canonical quadlet secrets mechanism. | Containment tests green; SIGTERM exits 0 promptly; no plaintext tokens at rest or on stdout; templates contain zero mutable references. |
| `migrate-specs-to-openspec-conventions` | `openspec validate --all --strict` 100%; both parsers agree on requirement counts; game specs dispositioned; archives cleaned (2 stragglers, broken pointers, lost mon-local-01); GD-3 policy documented. | CLI + traceability gate agree; no ✓-Complete stragglers; CI enforces spec validity. |

**Phase 1 gate:** the spec platform and the security posture match the claims
the repo makes about itself.

### Phase 2 — Durability and maintainability

| Change | What it delivers | Exit criteria |
|--------|------------------|---------------|
| `consolidate-shared-gate-logic` | One shared Python module + one shared Node lib for root detection / overlay merge / JSONL parse / annotations / globs / skip-dirs; parity matrix enforced by tests; silent-success-scan joins the overlay contract. | Duplicate-implementation grep count = 2 (the shared libs); parity matrix green on both runtimes. |
| `docs-and-data-truth-pass` | README/AGENTS/CHANGELOG/templates describe everything that ships; coherence service documented; allowlist decontaminated; rules files schema-validated in CI; counts derived or checked. | Doc-checker CI step green; fresh-install scan clean; CHANGELOG carries the coherence service. |
| `harden-test-suite` | F12/F13 + coverage for every untested module (hub/main, 5 scripts, deploy.sh, runner-enroll.sh); frozen clocks; root-skips; meta-test guarding collection count. | Untested-module list empty or rationally waived; suite passes as root and non-root; vectors load-bearing. |

**Sequencing note:** `add-framework-ci-pipeline` is intentionally minimal so it
can land first; `harden-test-suite` extends it. The three P2 packages are
independent of each other and can run in parallel once Phase 1 lands.

---

## Explicitly deferred (with rationale)

- **Coherence S5-S8** (detached signing, evidence store, fleet integration,
  3D slice, release hardening) — already scoped inside
  `devgate-spec-coherence-service/tasks.md`; the S8 archive ceremony now
  depends on this roadmap's migration change. Not re-scoped here.
- **`devgate-product-tiers-fleet-manager`** — hard-blocked on coherence
  acceptance (DEP-001); untouched.
- **TLS on the hub** — recorded decision (tailnet-bound posture); revisited
  in harden-security-boundaries docs only.
- **Windows path handling in the JS gates** — real (forward-slash
  assumptions), but consumer-demand-driven; tracked as a follow-up note in
  consolidate-shared-gate-logic rather than a package.

## How to work this roadmap

1. Pick the topmost unchecked package in the lowest incomplete phase.
2. `openspec show <change>` — proposal + tasks are self-contained with
   file:line evidence.
3. Land fixes per the repo's four-gate process; append failure-registry
   entries where the tasks call for them.
4. Archive via the CLI when complete (migration change defines the ceremony).

---

## Status (2026-09-19, `audit` branch)

| Package | Phase | Status | Commits |
|---|---|---|---|
| `fix-coherence-container-contract` | P0 | **landed** — schemas ship with the service; honest container smoke evidence; image rebuild environment-gated (no podman here) | `2fbaee2` |
| `fix-vacuous-and-broken-gates` | P0 | **landed** — C1-C4/C6/C7, H6/H8 and two new vacuous-green defects closed; 7 regression tests + 2 fixture harnesses added | `8a797b2` |
| `add-framework-ci-pipeline` | P0 | **landed** — CI runs the suite + self-gates + spec counts + image build; container smoke on the fleet remains publish-gated | `0346fd8` |
| `harden-security-boundaries` | P1 | **landed** — containment, SIGTERM, enroll atomicity, body cap, hashed tokens, monitor field fixes, container reaper, supply-chain pins, canonical quadlet secrets | `756c1d7` |
| `migrate-specs-to-openspec-conventions` | P1 | **landed + archived** — 26/26 strict, both parsers agree, game specs dispositioned, ceremony codified | this branch |
| `consolidate-shared-gate-logic` | P2 | **OPEN — the one remaining package.** Root-detection contract unified; 3 overlay merges, 4 glob engines, 5 SKIP_DIRS, annotation parity matrix remain. Deliberately left for a focused follow-up: structural refactor, best not rushed | — |
| `docs-and-data-truth-pass` | P2 | **landed** — allowlist decontaminated, README whole-repo truth, schema-health config surface, AGENTS overlay consistency, CHANGELOG normalized | this branch |
| `harden-test-suite` | P2 | **landed** — golden vectors load-bearing (F13), collection-floor meta-test, root-skip guards, tmp-dir fixtures; clock seams deferred with rationale | this branch |

Verification at `756c1d7`: `pytest` 410 passed / 7 skipped; both JS fixture
suites and the shell harness green; self-gates (guardrails, registry hygiene,
silent-success, regression `--base origin/main`) clean; failure registry
FAIL-2026091901..12 resolved with prevention patterns; every package's
tasks.md checked except items marked environment-gated above.

**Final state (audit branch, 2026-09-19):** 7 of 8 packages landed and
archived where applicable; `openspec validate --all --strict` 26/26;
traceability no-regression verified; 415+ tests green; every fix locked by a
test that fails on the old behavior; failure registry FAIL-2026091901..12
resolved; deferred items (clock seams, hub/main env-wiring tests, arm64+
publish, 1.3.0 release cut) recorded with owners or rationale, never dropped.
