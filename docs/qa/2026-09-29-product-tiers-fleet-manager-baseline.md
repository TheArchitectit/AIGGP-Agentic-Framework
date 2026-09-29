# Baseline audit — `devgate-product-tiers-fleet-manager` (DEP-003)

**Date:** 2026-09-29
**Act:** Sprint 0 entry audit. DEP-001 is evidenced; this record is DEP-003's
"fresh full-repository audit before Sprint 0 mutates code."
**Audited SHA:** `a37f8424d933df52cf7830f2a9f7374902ba4c90`
**Tree status at measurement:** clean (`git status --porcelain` → 0 lines)
**Predecessor acceptance:** `docs/qa/2026-09-28-spec-coherence-service-acceptance.md`
at accepted SHA `30aa60d505a36e75e46ae5a72b96f3ea2125eabb` (record landed `40d2998`).

This audit **reads and measures**. It creates no `enterprise/` or `fleet-manager/`
scaffolding (DEP-002), redefines no `coh-*` contract, and ticks no owner decision.

## 1. Commands run and results (2026-09-29, this host)

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `a37f8424d933df52cf7830f2a9f7374902ba4c90` |
| `git status --porcelain \| wc -l` | `0` (clean) |
| `python3 -m pytest tests/ -q` | **1290 passed**, 35 subtests passed (0 failures, 0 errors) |
| `python3 scripts/regression_check.py --all --pre-commit` | exit 0 — **0 over hard limit**; 22 pre-existing soft warnings (non-blocking) |
| `node scripts/guardrails-scan.mjs` | exit 0 — "pattern scan clean"; 30 non-blocking PREVENT-024 warnings |
| `npx openspec validate --all --strict` (`@fission-ai/openspec@1.13.0`) | **44 passed, 0 failed** |
| `python3 scripts/spec_traceability.py --root . --report` | 79/142 covered, **advisory** (no blocking mode configured) |
| `python3 scripts/regression_check.py --staged --pre-commit --fail-if-empty` (clean tree) | **exit 2** — WORKING AS DESIGNED zero-input refusal ("NOT evidence of a clean tree") |
| Hosted CI on this SHA (`36527007652`) | Specs + DevGate-gates + secret-scan + publish + evaluator-image **green**; fw-* and Test-suite in progress at write time (jobs listed in §1.1) |

### 1.1 Hosted jobs at write time (`gh run view 36527007652`)

| Job | Status at record time |
|---|---|
| Specs (openspec strict + traceability) | success |
| DevGate gates on DevGate | success |
| Secret scan (pinned gitleaks over the pushed range) | success |
| Publish evaluator image to GHCR (S4) | success |
| Evaluator image builds with its contracts (coh-rt-08) | success |
| The evaluator itself is attacked (fw-*) | in progress |
| Test suite (Python + Node) | in progress |

Prior run on `85b5740` (36526305378) failed on the two defects fixed in the
audited commit: `add-3d-vertical-slice` missing `skip_specs`, and a
PREVENT-003 false hit on `scripts/lib/registry-digest.sh`. Both are closed on
this SHA's tree.

## 2. Machine-readable inventory

Completeness is proven by the tracked file list and the commands that produce it
here (`git ls-files` at the audited SHA = **663 files**). Top-level tracked
entries:

`actions/  AGENTS.md  .benchmarks  CHANGELOG.md  CHECKSUMS.sha256  container/
.containerignore  CONTRIBUTING.md  docs/  engines/  .github/  .gitignore
.guardrails/  hub/  LICENSE  MAINTAINERS.md  openspec/  README.md  scripts/
SECURITY.md  templates/  tests/  VERSION`

**Active OpenSpec changes** (`openspec/changes/*`, excluding `archive/`):

| Package | Role here |
|---|---|
| `devgate-spec-coherence-service` | predecessor (accepted 2026-09-28) |
| `devgate-product-tiers-fleet-manager` | this package (Sprint 0 entry) |
| `add-3d-vertical-slice` | implementation of frozen `coh-3d-*` (not a contract source) |
| `add-runner-image-cycling` | complete 2026-09-29 (image-cycle timers + img-cycle-05 advisory) |
| `add-secret-scanning` | shipped (first fleet run recorded) |
| `ai01-runner-monitor-impl` | complete |
| `consolidate-shared-gate-logic` | complete |
| `docs-and-data-truth-pass` | complete (`skip_specs`) |
| `fix-coherence-container-contract` | complete |
| `fix-size-gate-shell-scope` | complete |
| `fix-specs-gate-audit-2026-09` | 2 owner-gated items remain |
| `harden-test-suite` | complete (`skip_specs`) |
| `self-check-the-mutation-harness` | complete |
| `aiggp-00` … `aiggp-10` | **imported drafts — not DevGate contracts.** Never wire code to `aiggp-*` IDs. |

Archived packages under `openspec/changes/archive/` (including
`2026-09-19-add-runner-to-fleet`) are already landed. They are overlap sources,
not new work.

**Pinned evaluator identity in this tree** (`container/execution-profiles.json`):

- image: `ghcr.io/thearchitectit/aiggp-agentic-framework/devgate-coherence`
- profile `linux-amd64-v1` (only profile; Q5 amd64-only)
- `image_manifest_digest`: `sha256:66190f5a04cd9be31f5de688f0814c0470b29ae775315601503951f087178c2d`
  (built 2026-09-28)

The predecessor acceptance sealed `sha256:d798dc48d1cec73446bbc77459f8a3f1f32008b034bca172ea7ef59f155cc6a4`
at `30aa60d`. The current record is a later published build of the same
mutable tag, kept in sync by the publish/re-pin path (`scripts/lib/registry-digest.sh`,
img-cycle-05). Not a defect here; recorded so Sprint 0 does not treat the
acceptance digest as live-desired-state.

## 3. Runner architecture and capability classes

**Published architecture (this repo only; no private host detail).** The
shipped model is hub-and-spoke:

- **Hub** — long-lived monitor process (`hub/`), persistent registry
  (`hub/registry.py`, never committed), HTTP `/enroll`, `/heartbeat`, `/health`
  (`hub/server.py`). Alerting is outbound-only via
  `hub/alerts.py::GitHubIssueNotifier` (mon-alert-01).
- **Spokes / runner hosts** — one durable Podman runner container per
  repository (`templates/runner/self-hosted-runner.container`), durable work
  volume, per-runner EnvironmentFile (`chmod 600`), labels selected at enroll
  time (`RUNNER_LABELS`, default `devgate`).
- **Out-of-band host agents** installed by `scripts/runner-enroll.sh` beside
  the runner: heartbeat timer, watchdog, image-cycle timer
  (`devgate-imgcycle-<name>`), fleet secret-sweep timer. Units are per-runner
  named so one host can carry several runners.
- **Runner container contract:** the runner is itself a container whose only
  persistent volume is `/_work`. It does **not** see the host Podman store by
  default — evaluator-image convergence writes the host store named by
  `COHERENCE_PODMAN_STORE` (img-cycle / design D3).

**Capability classes observed in-repo** (names only; no addresses, no tokens,
no private infra paths):

1. `devgate` / self-hosted Linux runner containers — general CI gate host.
2. Repo-scoped specialty runners (custom image with language toolchain; pinned
   official runner image) — the existing per-repo durable model.
3. Monitor-hub host — runs `devgate-hub` plus enrolled runner work.
4. Image-cycle hosts — must expose a Podman store the gate can read
   (`COHERENCE_PODMAN_STORE`), and are **not** JSON-schema-enforced to do so;
   the tick fails closed on mismatch.

**Measured gaps named by the predecessor and the private infra source** (restate,
do not re-derive private topology here):

- Registration is still one durable repository container, not ephemeral
  one-job pools. Product-tiers Sprint 4 is the migration.
- `runner-enroll.sh` assumes one runner per host unless the N+1th patterns are
  used (`templates/runner/add-a-runner.md`).
- Host-count and spoke-count disagreements in the operational source remain
  **unresolved here**; Sprint 0's job is to re-measure, not to copy a count.

## 4. Overlap and conflicts

| Package / spec | Overlap with product-tiers | Disposition |
|---|---|---|
| `devgate-spec-coherence-service` (accepted) | Frozen decision/exit contract, envelopes, `coh-*` IDs, `ctx-*` well-formedness contract. Product-tiers **consumes**; it MUST NOT copy, rename, fork, or redefine. The only interface this package implements or extends is the hub's well-formed-envelope/`ctx-*` document surface under `hub/coherence/`. | **Import identity; no redefine (DEP-003 / 0.4).** |
| `openspec/specs/runner-monitoring` | Online detection, queue-drain, gate-result, drift-scan recency. Product-tiers host-agent and Fleet Manager must drive these, not replace them. | **Reconcile as consumer.** Fleet desired-state replaces manual provisioning; check classes stay non-negotiable. |
| `openspec/specs/enrollment-and-alerting` | Talk-home enrollment (mon-enroll-01), outbound-rich dedup alerts, monitor-hub duties off-repo. Product-tiers adds a richer host-agent channel (FLEET-004) and paid-tier secrets (SEC-*). | **Consumer + selective extension.** Any change to `mon-enroll-01` (e.g. hub-side revoke-vs-heartbeat credential split) is its own openspec, not a silent edit here. |
| `openspec/specs/hub-architecture` | Single hub, dual evidence channels, registry-as-instance-state, hub-death detection. Commercial boundary and entitlement isolation (TIER-*) sit **beside** this, not instead of it. | **Reconcile as consumer.** No new hub singleton, no committed registry. |
| `archive/2026-09-19-add-runner-to-fleet` (`fleet-add-01`) | N+1th runner walkthrough: shared entrypoint, token hygiene, durability pre-seed, quadlet registration. Product-tiers Sprint 3 assumes this pattern or replaces it wholesale via the host-agent adapter. | **Migration, not rewrite.** Sprint 3 must state "compatible or migrating" before Sprint 4 opens. |
| `add-3d-vertical-slice` / `coh-3d-*` | 3D subject path. Product-tiers Stage-3/4 execution pools must still satisfy `coh-rt-*` runtime pins. | **No overlap in contracts**; only in "what a gate host must be able to run". |
| `add-runner-image-cycling` (complete) | Desired image state, served-vs-record advisory (img-cycle-05). Product-tiers signed-configuration (FLEET-004) must not conflict with the host timer's recorded identity. | **Keep as out-of-band index**; Fleet Manager desired state eventually drives the same record. |

## 5. License files and package boundaries

- Root `LICENSE` — **BSD 3-Clause**, copyright 2026 TheArchitectit.
- `actions/stitcher-codereview/NOTICE.md` — third-party notice for one action.
- No `enterprise/` or `fleet-manager/` directory exists today (DEP-002 held).
- No commercial license text file, no entitlement package, no contributor
  policy split (`CONTRIBUTING.md` has no commercial clause).
- Package boundary today is the public tree only: `hub/`, `scripts/`,
  `actions/`, `templates/`, `container/`, `engines/`, `openspec/`, `tests/`,
  `docs/`.

**Consequence:** Sprint 1.1 (commercial boundary + license manifest + changed-
path license gate) has nothing to extract yet. OD-001 (exact commercial license
text) and OD-002 (`enterprise/` vs `fleet-manager/` root) are **owner
decisions** and are still open (see §8).

## 6. Secret classes and entry points

No secret values are copied here. Classes and where they enter:

| Class | Entry point | Handling today |
|---|---|---|
| Enrollment token (one-time) | Operator → `scripts/runner-enroll.sh` argv → `POST /enroll` | Consumed on success; `hub/tokens.py::mint_token` mints URL-safe 256-bit; constant-time `verify` |
| Heartbeat token (per-runner, revocable) | Hub issues on enroll → operator/host holds in `~/.config/containers/devgate-heartbeat-<name>.env` (mode 600) → `POST /heartbeat` | Revocable via `runner-enroll.sh --revoke`; never echoed by hub |
| Runner registration token | Host drop-in (`devgate-runner.secrets.env`, chmod 600) → runner container EnvironmentFile | Durable, crash-loop-burnable historically; still a replacement target |
| Hub alert/issue token (outbound) | Host environment for `hub/alerts.py::GitHubIssueNotifier` | Used only outbound; never logged here |
| Coherence signer key | Containerized path fail-closed `signer-key-not-configured` (exit 33) today | Named limit on the predecessor acceptance; not a live leak path |
| Scan-report paths | Spoke disk (`SECRET_SCAN_REPORT`) → heartbeat JSON | State and counts travel; finding locations stay on the host |

**Invariants enforced in this tree:** hub never echoes secrets; enroll response
is filtered before stdout; scanner output is redacted (rule/path/line/commit
only); container binds are tailnet/loopback by house rule.

## 7. MissionControl and rad-gateway

- **In this repository:** MissionControl and rad-gateway appear only as
  *referenced* integration targets (product-tiers proposal Sprint 9,
  docs/changelogs, one coherence workflow-template test). There is **no**
  MissionControl client, no rad-gateway SDK, and no outbound trust path in
  `hub/` or `scripts/`.
- **From their own repositories:** not verified in this audit. Sprint 9
  (INT-001..003) requires read-only views, mediated commands with receipts, and
  proof that rad-gateway is absent from the trust path. That verification is
  deferred to Sprint 9 and remains an **uncertainty** while those integrations
  stay in scope (see §9).

## 8. Sprint 0 checklist disposition at this SHA

| Task | Disposition |
|---|---|
| 0.1 DEP-001 predecessor accepted | **EVIDENCED** (this record cites the acceptance document + SHA). Tick against the evidence. |
| 0.2 DEP-003 fresh audit + baseline doc | **This document.** |
| 0.3 Predecessor identity imported; no contract redefined here | **Imported** in §2 and §4: sealed identity cited; `coh-*` consumed not redefined; this package's stage-3 envelope surface is a hub `ctx-*` well-formedness extension only. |
| 0.4 Overlaps reconciled | **Recorded** in §4 with consumer-vs-mutator dispositions per package. |
| 0.5 OD-001 / OD-002 | **OPEN — owner decisions.** Not ticked. |

### 0.5 staged as owner questions (architect)

1. **OD-001 — commercial license text and contribution policy split.**
   - (A) Propose a specific commercial text now (needs owner redlines).
   - (B) Ship Sprint 1.1 as a *boundary + manifest* only, with a marked
     placeholder, and land text in a later package.
   - (C) Drop the commercial split for Phase 1; keep BSD 3-Clause and gate only
     path boundaries.
2. **OD-002 — commercial root directory name.**
   - (A) `enterprise/` (proposal's current preference).
   - (B) `fleet-manager/`.
   - (C) A third root (name it).

## 9. Findings (severity-ranked) and uncertainties

Findings (facts about this tree at `a37f842`):

| Sev | Finding |
|---|---|
| F1 — informational | Openspec path is green (44/0 strict) only because `add-3d-vertical-slice` carries `skip_specs: true`. Its implementation still owes `coh-3d-01..04` / `coh-assert-05` work (that is #56, not Sprint 0). |
| F2 — informational | Test floor: 1290 collected vs `tests/expected-counts.json` total_floor 1160 across 96 suites. Floors are a ratchet, not census. |
| F3 — low | PREVENT-024 (`__main__`) remains a **non-blocking** class of warning (30 hits on the whole-tree guardrails scan; 3 of them were in-range on the previous push and are fixed as out-of-range now). Not a commercial/product-tiers blocker. |
| F4 — low | Spec traceability is advisory 79/142. 63 uncovered IDs incl. `coh-3d-*` and `spec-fmt-*`. Product-tiers must not claim coverage it cannot measure. |
| F5 — informational | Zero-input gate correctly refuses a clean-tree `--staged` scan (exit 2). Sprint 0 CI changes must keep `--base` / `--fail-if-empty` semantics or gates silently pass empty input. |

Uncertainties (not findings, not asserted):

| ID | Uncertainty | Why unresolved here |
|---|---|---|
| U1 | Live fleet counts (how many runner containers, how many heart-beating spokes, over-scoped CLI token presence) | Gated on re-measurement against the private infrastructure source and live hub; "we need to validate" — do not paste private infra claims as approvals. |
| U2 | Whether `add-runner-to-fleet` credential pre-seed is still the rail every host uses | Requires host/operational check; Sprint 3.2 owns the compatible-or-migrating statement. |
| U3 | MissionControl / rad-gateway contract facts from their own repos | In scope only through Sprint 9; not verified in this tree-time audit. |
| U4 | Whether host Podman stores are actually the ones the runner container mounts | Declared by the unit, checked by the cycle tick against `COHERENCE_PODMAN_STORE`; 7.1/7.2 of image-cycling remain on a host checklist (NOT_RUN). |
| U5 | Arms race with mutable image tags vs sealed acceptance digest | Publish/re-pin and img-cycle-05 track divergence; product-tiers signed configuration must land on the same record, not on `:main` (TBD Sprint 3). |

## 10. What Sprint 0 does next (after OD-001/OD-002)

1. Land OD-001 / OD-002 answers.
2. Freeze v1 contracts (`contracts/v1`) and the commercial boundary per the
   chosen root.
3. Dependency-review record fixture that fails if `openspec/specs/**` gained a
   product-tiers-owned `Requirement` under a `coh-*` / `mon-*` / `fleet-*`
   ID this package did not own before.
4. Threat model + secret inventory pass over the **staged** commercial path
   (no secrets in the public tree).

Nothing in Sprint 0 mutates shipped `hub/` behavior other than additive
tests/fixtures that prove the record above.