# AIGGP OpenSpec re-audit - read-only

**Checkout:** `fd2c11f08aa74f8b1f4917a7a5c2785860ef4cf1` (`main`, matches `origin/main` at audit time). **Scope:** native OpenSpec published specs, active changes, all archive directories, current ID-marker gate, plus historical state ledger evidence. This is a status/traceability review; a source marker is a locator, not behavioral proof. Cross-repo, deployment, and behavioral review is owned separately by quality.

## Executive findings

- `openspec/specs/` has **56** published spec files and **251** `### Requirement:` headings. `openspec/INDEX.md` reports **CLOSED 1 / DEFERRED 1 / UNPROVEN 42 / PARTIAL 0 / OPEN 0 / UNKNOWN 12**. These are status labels as recorded/generated, not a count of independently verified working capabilities.
- The traceability parser accepts **243 published requirement IDs**; **8 headings** lack IDs (adapters-and-loops 2, reviewer-surfaces 3, traceability-and-drift 3). The strings `<!-- id:  -->` in `spec-platform` prose and `<!-- id: ... -->` in `spec-state-ledger` prose are literal format examples, not requirement ID comments or defects. The raw comment count is not a reliable heading inventory. This conflicts with the AGENTS.md requirement-marker convention.
- At HEAD, `python3 scripts/spec_traceability.py --report` reports **238/252 covered**, 14 uncovered. Those 252 are 243 recognized published IDs + 9 active-change IDs. All 14 findings are advisory because there is no `openspec/gate-config.json`; the CI ratchet floor is 238, so the current report is exactly at its floor. Missing IDs in the 8 heading-only specs are invisible to this gate.
- Current marker gaps: `art-evolve-01`; `fleet-app-01` through `fleet-app-09`; `game-matrix-01` through `game-matrix-03`; `spec-state-09`. The game matrix is explicitly DEFERRED to consuming game repos; `fleet-app-enrollment` is UNKNOWN and its nine IDs are uncovered; `art-evolve-01` and `spec-state-09` need an explicit evidence/status disposition rather than being silently treated as done.
- `openspec/state-ledger.jsonl` has 2 CLOSED rows, both `doc-truth`, with resolved opened/landed commit IDs, named tests, evidence digest, and timestamp. `openspec/state-unproven.jsonl` has 182 rows. There are 251 spec headings total; the rest are the two closed doc-truth requirements, 3 deferred game-matrix requirements, and 64 requirements in UNKNOWN specs. Do not equate UNPROVEN with absent implementation: these requirements have provenance accepted, but no sealed evidence ledger row.
- There are **2 active changes**: `add-gitlab-forge-support` (8/12 tasks checked; 7 draft requirements, 7 marker-covered) and `harden-template-runner-portability` (7/8; 2 draft requirements, 2 covered). Their deltas are authoritative while active per AGENTS.md; do not report these as drift from published specs. They are still active with unchecked work.
- There are **43 archived change dirs**, with **719/829 task checkboxes marked done** (110 unchecked historical boxes). Archive checkbox state is a historical task record and does not independently prove present implementation. The 6 dated 2026-09-13 baseline packages are all archived with 0 tasks checked; later disposition records explicitly explain movement/retirement/supersession. Several fully checked archived delta specs no longer exist as same-named published capabilities; treat that as merge/retirement drift to account for, not automatically as current open work.
- Pinned CI OpenSpec CLI `@fission-ai/openspec@1.14.3` was invoked at this HEAD: `openspec validate --all --strict` **PASS, 58 passed / 0 failed** (56 published specs + 2 active changes). This proves structural validation only; it does not establish source behavior. CI also runs a malformed negative control.

## Published 56-spec inventory

`Req` is heading count; `IDs` is supported-format parser count; marker coverage is the number of those IDs found in current source-like files. `UNPROVEN` means a status/evidence gap, not proof the code is absent. `UNKNOWN` means no closure table/status line per index semantics.

| Spec | Index status | Req | IDs | Marker coverage |
|---|---:|---:|---:|---:|
| `adapters-and-loops` | UNKNOWN | 2 | 0 | 0/0 marker-covered |
| `add-runner-to-fleet` | UNPROVEN | 1 | 1 | 1/1 marker-covered |
| `adoption-and-policy` | UNPROVEN | 7 | 7 | 7/7 marker-covered |
| `art-creation-contract` | UNKNOWN | 12 | 12 | 11/12 marker-covered |
| `assertions-and-evaluators` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `baseline-ownership` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `branch-drift` | UNKNOWN | 4 | 4 | 4/4 marker-covered |
| `canonical-identity` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `ci-template-contract` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `coherence-evaluation` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `container-runtime` | UNPROVEN | 7 | 7 | 7/7 marker-covered |
| `decision-contract` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `doc-truth` | CLOSED | 2 | 2 | 2/2 marker-covered |
| `enrollment-and-alerting` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `evaluation-context` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `evidence-and-attestation` | UNPROVEN | 7 | 7 | 7/7 marker-covered |
| `evidence-claims` | UNKNOWN | 6 | 6 | 6/6 marker-covered |
| `fleet-app-enrollment` | UNKNOWN | 9 | 9 | 0/9 marker-covered |
| `fleet-manager-adapter-contract` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `fleet-manager-agent-channel` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `fleet-manager-agent-operations` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `fleet-manager-boundary` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `fleet-manager-contracts` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `fleet-manager-domain` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `fleet-manager-extraction` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `fleet-manager-job-lifecycle` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `fleet-manager-plan` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `fleet-manager-reconciliation` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `fleet-manager-signed-state` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `framework-ci` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `game-regression` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `game-session-start` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `game-type-phase-matrix` | DEFERRED | 3 | 3 | 0/3 marker-covered |
| `gate-configuration-contract` | UNPROVEN | 2 | 2 | 2/2 marker-covered |
| `gate-execution-contract` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `hub-architecture` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `integrations` | UNPROVEN | 7 | 7 | 7/7 marker-covered |
| `open-item-aging` | UNKNOWN | 4 | 4 | 4/4 marker-covered |
| `package-resolution` | UNPROVEN | 5 | 5 | 5/5 marker-covered |
| `per-screen-tracking` | UNPROVEN | 2 | 2 | 2/2 marker-covered |
| `publish-safety` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `release-gate-targeting` | UNPROVEN | 2 | 2 | 2/2 marker-covered |
| `reviewer-surfaces` | UNKNOWN | 3 | 0 | 0/0 marker-covered |
| `rule-coverage-truth` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `runner-monitoring` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `runner-toolchain-requests` | UNPROVEN | 6 | 6 | 6/6 marker-covered |
| `scanner-parsing` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `secret-rotation` | UNKNOWN | 4 | 4 | 4/4 marker-covered |
| `security-boundaries` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `spec-platform` | UNPROVEN | 3 | 3 | 3/3 marker-covered |
| `spec-state-ledger` | UNKNOWN | 9 | 9 | 8/9 marker-covered |
| `subjects-3d` | UNPROVEN | 4 | 4 | 4/4 marker-covered |
| `surface-reach` | UNKNOWN | 4 | 4 | 4/4 marker-covered |
| `traceability-and-drift` | UNKNOWN | 3 | 0 | 0/0 marker-covered |
| `tree-clean` | UNKNOWN | 4 | 4 | 4/4 marker-covered |
| `zig-opengl-engine` | UNPROVEN | 4 | 4 | 4/4 marker-covered |

## Active changes

| Change | Tasks checked | Draft req IDs | Current marker hits |
|---|---:|---:|---:|
| `add-gitlab-forge-support` | 8/12 | 7 | 7/7 |
| `harden-template-runner-portability` | 7/8 | 2 | 2/2 |

The active draft IDs total 9. Because `ci-tpl-01/02` overlap published `ci-template-contract` IDs by design, the gate counts capability keyed by draft path; these remain current active draft requirements, not an accidental double-count in published specs.

## Archive inventory (raw task checkbox state)

| Archived change | Checked / total | Unchecked |
|---|---:|---:|
| `2026-09-13-baseline-hygiene` | 0/12 | 12 |
| `2026-09-13-ci-templates-docs` | 0/13 | 13 |
| `2026-09-13-deploy-pipeline` | 0/15 | 15 |
| `2026-09-13-gate-correctness` | 0/20 | 20 |
| `2026-09-13-rule-enforcement-gaps` | 0/16 | 16 |
| `2026-09-13-runner-monitor` | 0/15 | 15 |
| `2026-09-19-add-framework-ci-pipeline` | 14/14 | 0 |
| `2026-09-19-add-runner-to-fleet` | 5/5 | 0 |
| `2026-09-19-fix-size-gate-test-scope` | 11/11 | 0 |
| `2026-09-19-fix-vacuous-and-broken-gates` | 26/26 | 0 |
| `2026-09-19-harden-security-boundaries` | 21/21 | 0 |
| `2026-09-19-migrate-specs-to-openspec-conventions` | 19/19 | 0 |
| `2026-10-01-devgate-spec-coherence-service` | 90/92 | 2 |
| `2026-10-03-add-runner-image-cycling` | 19/19 | 0 |
| `2026-10-03-add-secret-scanning` | 29/29 | 0 |
| `2026-10-03-ai01-runner-monitor-impl` | 20/20 | 0 |
| `2026-10-03-consolidate-shared-gate-logic` | 9/9 | 0 |
| `2026-10-03-docs-and-data-truth-pass` | 14/14 | 0 |
| `2026-10-03-fix-coherence-container-contract` | 14/14 | 0 |
| `2026-10-03-fix-size-gate-shell-scope` | 18/18 | 0 |
| `2026-10-03-fix-specs-gate-audit-2026-09` | 60/62 | 2 |
| `2026-10-03-harden-test-suite` | 10/10 | 0 |
| `2026-10-03-self-check-the-mutation-harness` | 16/16 | 0 |
| `2026-10-13-add-oap-evidence-consumer` | 6/18 | 12 |
| `2026-10-13-harden-oap-evidence-verification` | 13/16 | 3 |
| `2026-11-06-add-fleet-manager-adapter-contract` | 18/18 | 0 |
| `2026-11-06-add-fleet-manager-agent-channel` | 15/15 | 0 |
| `2026-11-06-add-fleet-manager-agent-operations` | 21/21 | 0 |
| `2026-11-06-add-fleet-manager-boundary` | 7/7 | 0 |
| `2026-11-06-add-fleet-manager-contracts-v1` | 11/11 | 0 |
| `2026-11-06-add-fleet-manager-domain-models` | 8/8 | 0 |
| `2026-11-06-add-fleet-manager-extraction-rehearsal` | 9/9 | 0 |
| `2026-11-06-add-fleet-manager-job-lifecycle` | 18/18 | 0 |
| `2026-11-06-add-fleet-manager-plan-apply` | 9/9 | 0 |
| `2026-11-06-add-fleet-manager-reconciliation-fixtures` | 10/10 | 0 |
| `2026-11-06-add-fleet-manager-signed-state` | 22/22 | 0 |
| `2026-11-06-add-game-session-start` | 15/15 | 0 |
| `2026-11-06-add-runner-toolchain-requests` | 46/46 | 0 |
| `2026-11-18-fleet-app-auto-enroll` | 17/17 | 0 |
| `2026-11-20-add-art-creation-contract` | 24/24 | 0 |
| `2026-11-20-add-open-item-gates` | 20/20 | 0 |
| `2026-11-20-add-spec-state-ledger` | 26/26 | 0 |
| `2026-11-20-aiggp-08-stitcher-proof-parity` | 9/9 | 0 |

Pinned OpenSpec 1.14.3 `validate --archived --strict --json` at the baseline reports 43 archives: 33 pass / 10 fail, all ten due to incomplete task checkboxes. The failing IDs are `2026-09-13-baseline-hygiene` (12), `2026-09-13-ci-templates-docs` (13), `2026-09-13-deploy-pipeline` (15), `2026-09-13-gate-correctness` (20), `2026-09-13-rule-enforcement-gaps` (16), `2026-09-13-runner-monitor` (15), `2026-10-01-devgate-spec-coherence-service` (3; CLI counts 90/93), `2026-10-03-fix-specs-gate-audit-2026-09` (2), `2026-10-13-add-oap-evidence-consumer` (12), and `2026-10-13-harden-oap-evidence-verification` (3). The separate template archive baseline is 4/4 pass. DG-04 acceptance must rerun this validator and explicitly disposition every failing task; changing old checkboxes is not the disposition mechanism.

Interpretation: the first six 2026-09-13 packages are known legacy imports and have dedicated later disposition documentation; 110 unchecked boxes across all 43 archives are not a meaningful ?open work? total by themselves. The current archive set includes fully checked packages such as runner-image-cycling and secret-scanning whose delta directory names are absent under published specs; their implementation/spec fate requires commit-level disposition (likely consolidated/merged, but do not infer closure only from the checkmarks). OAP packages remain partially checked (6/18 and 13/16) and their final disposition should be clarified. `AIGGP-DISPOSITION-2026-10-03.md` documents 12 moved packages and 10 shipped/archive packages, and notes a 31-spec base at that earlier date; the current 56-spec tree has since grown. `AIGGP-RETIREMENT-2026-10-02.md` records retired kernel packages and surviving split-out GitLab change.

## Historical ledger and evidence quality

- `doc-truth` is the only CLOSED spec in the current index. Both state rows share opened commit `0a26e37a33929ed671255da83b591795f84c8b0f` and landed commit `4f6f3bc6c3d7e9265604a3af5c428e3dafc03ac9`, identify behavioral test cases and point to `openspec/evidence/doc-truth` with digest `sha256:d6e020...f2a781`. This is a concrete auditable trail, although current run/pass status is not implied by the ledger timestamp.
- `state-unproven.jsonl` is explicitly provenance accepted but awaiting sealed evidence; marker coverage does not upgrade these rows. The closed/unproven distinction is encoded by state files and INDEX, so do not read ?238 covered? as 238 proven requirements.
- CI?s main job runs strict OpenSpec validation and the traceability report plus `--ratchet` at `.github/workflows/ci.yml`; this is the designed enforcement surface. The local audit did not run the full CI workflow; only strict OpenSpec validation and the read-only traceability report were run.

## Supported discrepancies / follow-up

1. Add valid IDs directly beneath the eight unmarked requirement headings. Keep the two prose examples of malformed syntax unchanged; add negative controls to exercise malformed IDs without misclassifying those examples as requirement markers.
2. Resolve the 14 uncovered IDs explicitly. Three game-matrix IDs are owner-deferred; nine fleet-app IDs have no source marker and the spec remains UNKNOWN; art-evolve and spec-state-09 lack markers despite the corresponding capability being counted in the current report.
3. 12 specs are UNKNOWN; add closure/status evidence or consciously retain UNKNOWN. Specifically includes `art-creation-contract`, `fleet-app-enrollment`, `evidence-claims`, `branch-drift`, `open-item-aging`, `secret-rotation`, `surface-reach`, `tree-clean`, `spec-state-ledger`, `reviewer-surfaces`, `traceability-and-drift`, and `adapters-and-loops`. Three of those have zero supported IDs due to the missing-marker issue.
4. Reconcile archived delta names absent from `openspec/specs/` against actual publication/retirement commits: `runner-image-cycling`, `secret-scanning`, `openspec-format-conformance`, `scanner-root-anchoring`, `oap-evidence-consumer`, and `oap-evidence-hardening`. Their checkbox state alone cannot establish current canonical spec mapping.
5. Keep active changes separate from published canonical specs until archive: current active changes still have 5 unchecked tasks total; archive ceremony is not complete.

## Limits

This is a bounded OpenSpec/status/traceability audit at the pinned checkout. Marker coverage means an ID appears in a supported code-like file; it can still be a test/source comment marker and does not establish executable behavior, passing tests, production deployment, or end-to-end compliance. The overall behavioral/deployment review is separately assigned.


## Requirement-level inventory (all 251 published headings)

Every requirement is listed by its published spec and heading. `MISSING` means no supported marker in that heading block; literal format examples elsewhere in prose are not treated as IDs. Source paths list every matching marker location found at HEAD; `-` means no marker found. These are traceability pointers only. The active 9 IDs are summarized separately above because they are draft delta requirements and not part of the 251 published headings.

| Published spec | Requirement heading | Parsed ID | Marker path(s) at HEAD |
|---|---|---|---|
| `adapters-and-loops` | identity-preserving ingestion | `MISSING` | - |
| `adapters-and-loops` | agent-loop verdict contract | `MISSING` | - |
| `add-runner-to-fleet` | Documented N+1th runner procedure | `fleet-add-01` | `tests/test_template_supply_chain.py` |
| `adoption-and-policy` | centrally enforced minimums | `coh-pol-01` | `hub/coherence/plan.py`, `hub/coherence/policy.py`, `tests/test_hub_coherence_allowlist.py`, `tests/test_hub_coherence_antirollback.py`, `tests/test_hub_coherence_modes.py`, `tests/test_hub_coherence_modes_cli.py` |
| `adoption-and-policy` | authenticated policy authority | `coh-pol-02` | `hub/coherence/__main__.py`, `hub/coherence/attest_detached.py`, `hub/coherence/policy.py`, `tests/test_hub_coherence_antirollback.py`, `tests/test_hub_coherence_attest.py` |
| `adoption-and-policy` | bounded advisory stage | `coh-pol-03` | `hub/coherence/policy.py`, `hub/coherence/report.py`, `tests/test_hub_coherence_adoption_policy.py`, `tests/test_hub_coherence_ladder.py`, `tests/test_hub_coherence_report.py` |
| `adoption-and-policy` | no-regression ratchet | `coh-pol-04` | `hub/coherence/adoption.py`, `scripts/ratchet_demo.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence_adoption_policy.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_ladder.py`, `tests/test_hub_coherence_modes.py`, `tests/test_hub_coherence_modes_cli.py`, `tests/test_hub_coherence_schema.py`, `tests/test_ratchet_demo.py` |
| `adoption-and-policy` | finding fingerprint definition | `coh-pol-05` | `hub/coherence/adoption.py`, `hub/coherence/issue.py`, `scripts/ratchet_demo.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence_adoption_policy.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_issue.py`, `tests/test_hub_coherence_schema.py`, `tests/test_ratchet_demo.py` |
| `adoption-and-policy` | scoped exceptions | `coh-pol-06` | `hub/coherence/adoption.py`, `hub/coherence/report.py`, `scripts/ratchet_demo.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_ladder.py`, `tests/test_hub_coherence_report.py`, `tests/test_hub_coherence_schema.py`, `tests/test_ratchet_demo.py` |
| `adoption-and-policy` | enforcement boundary is external | `coh-pol-07` | `hub/coherence/attest.py`, `hub/coherence_view.py` |
| `art-creation-contract` | one definition of done | `art-done-01` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | art brief before generation | `art-brief-01` | `scripts/art_checks.py` |
| `art-creation-contract` | shape language names a rule per class | `art-brief-02` | `scripts/art_checks.py` |
| `art-creation-contract` | every stage names its consumer | `art-stage-01` | `scripts/art_checks.py` |
| `art-creation-contract` | provenance ledger is the inventory | `art-ledger-01` | `scripts/art_checks.py` |
| `art-creation-contract` | bytes are versioned and replicated | `art-bytes-01` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | fidelity gate | `art-accept-01` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | retention measured beside the verdict | `art-accept-02` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | every target must draw | `art-draw-01` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | rights recorded at generation | `art-rights-01` | `scripts/art_checks.py` |
| `art-creation-contract` | quantity gates run last | `art-qty-01` | `scripts/art_check_outcome.py` |
| `art-creation-contract` | the contract grows from the failure registry | `art-evolve-01` | - |
| `assertions-and-evaluators` | assertion schema is operational | `coh-assert-01` | `hub/coherence/plan.py`, `tests/test_hub_coherence_assertion_schema.py` |
| `assertions-and-evaluators` | identity assertions compare against approved values | `coh-assert-02` | `hub/coherence/evaluators.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_traceability.py` |
| `assertions-and-evaluators` | release-claim binding order | `coh-assert-03` | `hub/coherence/evaluators.py` |
| `assertions-and-evaluators` | traceability checks are separated by phase | `coh-assert-04` | `hub/coherence/evaluators.py`, `hub/coherence/plan.py`, `tests/test_hub_coherence_traceability.py` |
| `assertions-and-evaluators` | model-generated advice is non-canonical | `coh-assert-05` | `hub/coherence/adoption.py`, `hub/coherence/evaluate.py`, `hub/coherence/evaluators.py`, `hub/coherence/result.py`, `scripts/world_slice_tool.py`, `tests/test_hub_coherence_3d_slice.py` |
| `assertions-and-evaluators` | finding key stability | `coh-assert-06` | `hub/coherence/evaluators.py` |
| `baseline-ownership` | Baseline contains only this repo's data | `base-own-01` | `scripts/baseline_ownership_check.py`, `scripts/failure_registry_check.py` |
| `baseline-ownership` | Project bugs land in the project overlay | `base-write-01` | `scripts/log_failure.py` |
| `baseline-ownership` | Game-dev gates and specs live in this framework | `base-specs-01` | `scripts/baseline_ownership_check.py`, `scripts/spec_traceability.py`, `tests/test_spec_traceability.py` |
| `branch-drift` | A commit that exists only on local disk is a failure | `bd-01` | `scripts/branch_drift_check.py`, `tests/test_open_item_gates.py` |
| `branch-drift` | Archiving is a recorded decision, not silence | `bd-02` | `scripts/branch_drift_check.py`, `tests/test_open_item_gates.py` |
| `branch-drift` | Scale is reported, not flattened | `bd-03` | `scripts/branch_drift_check.py` |
| `branch-drift` | No repositories scanned is never a pass | `bd-04` | `scripts/branch_drift_check.py` |
| `canonical-identity` | digest and canonicalization profile | `coh-id-01` | `hub/coherence/canon.py`, `tests/fixtures/coherence/compute_golden.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_golden.py` |
| `canonical-identity` | subject manifest | `coh-id-02` | `hub/coherence/manifest.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_runtime_mutation.py`, `tests/test_hub_coherence_submodule_pin.py` |
| `canonical-identity` | package normative digest | `coh-id-03` | `hub/coherence/package.py` |
| `canonical-identity` | image and platform identity | `coh-id-04` | `hub/coherence/container_exec.py`, `hub/coherence/launcher.py`, `hub/coherence/profiles.py`, `tests/fixtures/repin.py`, `tests/test_coherence_image_identity.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_launcher.py`, `tests/test_repin_operation.py` |
| `canonical-identity` | domain-separated digests | `coh-id-05` | `hub/coherence/canon.py`, `tests/fixtures/coherence/compute_golden.py` |
| `ci-template-contract` | Templates run the gates they name | `ci-run-01` | `tests/test_template_supply_chain.py` |
| `ci-template-contract` | Blocking checks match what they describe | `ci-match-01` | `tests/test_template_supply_chain.py` |
| `ci-template-contract` | The framework gates itself | `ci-self-01` | `tests/test_template_supply_chain.py` |
| `coherence-evaluation` | deterministic evaluation | `coh-eval-01` | `hub/coherence/canon.py`, `tests/test_hub_coherence_conformance.py` |
| `coherence-evaluation` | complete required assertion execution | `coh-eval-02` | `hub/coherence/evaluate.py`, `hub/coherence/plan.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_assertion_schema.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_decision.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_schema.py` |
| `coherence-evaluation` | assertion results ledger | `coh-eval-03` | `hub/coherence/result.py`, `tests/test_hub_coherence_adoption_ledger.py` |
| `coherence-evaluation` | semantic assertion traceability | `coh-eval-04` | `hub/coherence/evaluators.py`, `hub/coherence/plan.py`, `tests/test_hub_coherence_allowlist.py`, `tests/test_hub_coherence_traceability.py` |
| `coherence-evaluation` | underlying truth is preserved | `coh-eval-05` | `hub/coherence/adoption.py`, `tests/test_hub_coherence_adoption_ledger.py`, `tests/test_hub_coherence_adoption_policy.py`, `tests/test_hub_coherence_modes.py` |
| `coherence-evaluation` | evaluators execute only declared inputs | `coh-eval-06` | `hub/coherence/evaluate.py`, `hub/coherence/evaluators.py` |
| `container-runtime` | immutable runtime | `coh-rt-01` | `hub/coherence/container_exec.py`, `hub/coherence/invoke.py`, `hub/coherence/launcher.py`, `tests/test_coherence_image_identity.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_invoke.py`, `tests/test_hub_coherence_launcher.py` |
| `container-runtime` | launcher-validated isolation | `coh-rt-02` | `hub/coherence/container_exec.py`, `hub/coherence/launcher.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_launcher.py` |
| `container-runtime` | default-deny network | `coh-rt-03` | `hub/coherence/evaluate.py`, `hub/coherence/evaluators.py`, `tests/test_hub_coherence_runtime.py` |
| `container-runtime` | least-privilege secrets | `coh-rt-04` | `hub/coherence/evidence.py`, `tests/test_hub_coherence_runtime.py` |
| `container-runtime` | bounded execution | `coh-rt-05` | `hub/coherence/container_exec.py`, `hub/coherence/evaluate.py`, `hub/coherence/launcher.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_launcher.py` |
| `container-runtime` | built-in evaluators for the initial runtime | `coh-rt-06` | `hub/coherence/evaluate.py`, `hub/coherence/plan.py`, `tests/test_hub_coherence_allowlist.py`, `tests/test_hub_coherence_assertion_schema.py`, `tests/test_hub_coherence_compat.py` |
| `container-runtime` | writable output handling | `coh-rt-07` | `hub/coherence/container_exec.py`, `hub/coherence/evidence.py`, `hub/coherence/launcher.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_launcher.py`, `tests/test_hub_coherence_runtime.py` |
| `decision-contract` | single decision precedence matrix | `coh-dec-01` | `hub/coherence/__main__.py`, `hub/coherence/result.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_decision.py` |
| `decision-contract` | structured error envelopes | `coh-dec-02` | `hub/coherence/__main__.py` |
| `decision-contract` | canonical versus envelope separation | `coh-dec-03` | `hub/coherence/result.py`, `hub/coherence/schemacheck.py` |
| `decision-contract` | exit code contract | `coh-dec-04` | `hub/coherence/__main__.py`, `hub/coherence/container_exec.py`, `hub/coherence/result.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_decision.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_ladder.py`, `tests/test_hub_coherence_schema.py` |
| `decision-contract` | finding sort order and stability | `coh-dec-05` | `hub/coherence/result.py` |
| `doc-truth` | Version artifacts agree | `doc-version-01` | `scripts/check_version_truth.py`, `scripts/deploy.sh`, `tests/test_check_version_truth.py`, `tests/test_template_supply_chain.py` |
| `doc-truth` | Instructions follow the overlay contract | `doc-overlay-01` | `tests/test_template_supply_chain.py` |
| `enrollment-and-alerting` | Talk-home enrollment over the local network | `mon-enroll-01` | `hub/registry.py`, `hub/tokens.py` |
| `enrollment-and-alerting` | Deduplicated failure alerts, outbound-only | `mon-alert-01` | `hub/alerts.py`, `scripts/hub_alert.py` |
| `enrollment-and-alerting` | monitor-hub machine duties stay off-repo | `mon-monitor-hub-01` | `hub/main.py` |
| `evaluation-context` | versioned evaluation context | `coh-ctx-01` | `hub/coherence/context.py`, `hub/coherence/issue.py`, `tests/test_hub_coherence_issue.py` |
| `evaluation-context` | trusted context issuance | `coh-ctx-02` | `hub/coherence/context.py`, `hub/coherence/issue.py`, `tests/test_hub_coherence_issue.py`, `tests/test_hub_coherence_modes.py`, `tests/test_hub_coherence_modes_cli.py` |
| `evaluation-context` | replay versus fresh promotion | `coh-ctx-03` | `hub/coherence/context.py`, `tests/test_hub_coherence_conformance.py`, `tests/test_hub_coherence_exitcodes.py`, `tests/test_hub_coherence_schema.py` |
| `evaluation-context` | bound external facts | `coh-ctx-04` | `hub/coherence/evaluate.py`, `hub/coherence/evaluators.py`, `tests/test_hub_coherence_runtime.py` |
| `evaluation-context` | cache key completeness | `coh-ctx-05` | `hub/coherence/cache.py`, `hub/coherence/store.py`, `tests/test_hub_coherence_cache.py`, `tests/test_hub_coherence_store.py` |
| `evidence-and-attestation` | acyclic sealing order | `coh-ev-01` | `hub/coherence/__main__.py`, `hub/coherence/attest.py`, `hub/coherence/attest_detached.py`, `tests/test_hub_coherence_attest.py`, `tests/test_hub_coherence_attestation.py`, `tests/test_hub_coherence_evidence.py` |
| `evidence-and-attestation` | complete evidence manifest | `coh-ev-02` | `hub/coherence/evidence.py`, `hub/coherence/store.py`, `hub/coherence/verification.py`, `tests/test_hub_coherence_evidence.py`, `tests/test_hub_coherence_store.py` |
| `evidence-and-attestation` | reproducible findings | `coh-ev-03` | `hub/coherence/evidence.py`, `hub/coherence/verification.py`, `tests/test_hub_coherence_evidence.py` |
| `evidence-and-attestation` | authorized input retention | `coh-ev-04` | `hub/coherence/retention.py`, `hub/coherence/store.py`, `tests/test_hub_coherence_retention.py`, `tests/test_hub_coherence_store.py` |
| `evidence-and-attestation` | attestation binding | `coh-ev-05` | `hub/coherence/__main__.py`, `hub/coherence/attest.py`, `hub/coherence/attest_base.py`, `hub/coherence/attest_detached.py`, `hub/coherence/cli_verify.py`, `tests/fixtures/coherence/fixtures.py`, `tests/test_hub_coherence_attest.py`, `tests/test_hub_coherence_attestation.py`, `tests/test_hub_coherence_verify_cli.py` |
| `evidence-and-attestation` | minimal disclosure | `coh-ev-06` | `hub/coherence/evidence.py`, `hub/coherence/verification.py` |
| `evidence-and-attestation` | approval records are detached | `coh-ev-07` | `hub/coherence/package.py` |
| `evidence-claims` | A deferred marker must name owner, reason, and expiry | `evc-01` | `scripts/evidence_claim_check.py`, `tests/test_open_item_gates.py` |
| `evidence-claims` | A mock must point at the real thing it stands in for | `evc-02` | `scripts/evidence_claim_check.py`, `tests/test_open_item_gates.py` |
| `evidence-claims` | A stub must reference a tracked issue | `evc-03` | `scripts/evidence_claim_check.py` |
| `evidence-claims` | A bare marker is a violation, but prose is not | `evc-04` | `scripts/evidence_claim_check.py` |
| `evidence-claims` | Exemptions are declared, not inferred | `evc-05` | `scripts/evidence_claim_check.py` |
| `evidence-claims` | No files scanned is never a pass | `evc-06` | `scripts/evidence_claim_check.py` |
| `fleet-app-enrollment` | Discovery follows every installation page | `fleet-app-01` | - |
| `fleet-app-enrollment` | Archived repositories are skipped visibly | `fleet-app-02` | - |
| `fleet-app-enrollment` | Variable reconciliation is idempotent | `fleet-app-03` | - |
| `fleet-app-enrollment` | Secret creation is idempotent and non-destructive | `fleet-app-04` | - |
| `fleet-app-enrollment` | Dry run performs zero writes | `fleet-app-05` | - |
| `fleet-app-enrollment` | App authentication fails closed | `fleet-app-06` | - |
| `fleet-app-enrollment` | Execution is scheduled and fleet-only | `fleet-app-07` | - |
| `fleet-app-enrollment` | No credential reaches a report or a log | `fleet-app-08` | - |
| `fleet-app-enrollment` | Per-repository errors do not stop the fleet | `fleet-app-09` | - |
| `fleet-manager-adapter-contract` | One closed adapter contract, checked without calling it | `fleet-007-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/adapters.py`, `fleet-manager/tests/test_adapters_v1.py` |
| `fleet-manager-adapter-contract` | Adapter failures are typed and closed | `fleet-007-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/adapters.py`, `fleet-manager/tests/test_adapters_v1.py` |
| `fleet-manager-adapter-contract` | The runner image is pinned by an immutable digest | `fleet-007-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/adapters.py`, `fleet-manager/tests/test_adapters_v1.py` |
| `fleet-manager-adapter-contract` | One job per instance, and warm means never used | `fleet-007-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/adapters.py`, `fleet-manager/tests/test_adapters_v1.py` |
| `fleet-manager-agent-channel` | The manager never initiates contact with a host | `fleet-004-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/channel.py`, `fleet-manager/tests/test_channel_v1.py` |
| `fleet-manager-agent-channel` | Enrollment is one-time and bound; a key belongs to one host | `fleet-004-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/channel.py`, `fleet-manager/tests/test_channel_v1.py` |
| `fleet-manager-agent-channel` | Reports are signed over one frozen profile | `fleet-004-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/channel.py`, `fleet-manager/tests/test_channel_v1.py` |
| `fleet-manager-agent-channel` | Replay protection is stateful and strict | `fleet-004-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/channel.py`, `fleet-manager/tests/test_channel_v1.py` |
| `fleet-manager-agent-channel` | Rotation overlaps for a bounded window; revocation is immediate | `fleet-004-05` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/channel.py`, `fleet-manager/tests/test_channel_v1.py` |
| `fleet-manager-agent-operations` | An operation is a typed instruction and cannot carry a command | `fleet-005-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/operations.py`, `fleet-manager/tests/test_operations_v1.py` |
| `fleet-manager-agent-operations` | An agent may only be given work it declared | `fleet-005-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/operations.py`, `fleet-manager/tests/test_operations_v1.py` |
| `fleet-manager-agent-operations` | Parameters and receipts carry references, never secrets | `fleet-005-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/operations.py`, `fleet-manager/tests/test_operations_v1.py` |
| `fleet-manager-agent-operations` | A receipt is evidence tied to issued work | `fleet-005-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/operations.py`, `fleet-manager/tests/test_operations_v1.py` |
| `fleet-manager-agent-operations` | The authoritative receipt is built, not forwarded | `fleet-005-05` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/operations.py`, `fleet-manager/tests/test_operations_v1.py` |
| `fleet-manager-boundary` | Product-tiers code lives only under the declared root | `repo-002-01` | `scripts/check_boundary.py` |
| `fleet-manager-boundary` | The boundary carries a manifest and a license notice | `repo-002-02` | `scripts/check_boundary.py` |
| `fleet-manager-boundary` | Open-core code does not import the boundary | `repo-002-03` | `scripts/check_boundary.py` |
| `fleet-manager-boundary` | The boundary gate fails closed | `repo-002-04` | `scripts/check_boundary.py` |
| `fleet-manager-contracts` | Cross-boundary documents are versioned and declared | `repo-003-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-contracts` | A consumer refuses versions it does not implement | `repo-003-02` | `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-contracts` | Contract tests run in both directions | `repo-004-01` | `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-contracts` | A producer cannot emit a document its contract rejects | `repo-004-02` | `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-contracts` | Decisions and receipts carry what makes them actionable | `repo-004-03` | `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-contracts` | The boundary's open-core import surface is pinned | `repo-004-04` | `fleet-manager/fleet_manager/contracts.py`, `fleet-manager/tests/test_contracts_v1.py` |
| `fleet-manager-domain` | Desired state is held by the manager, and it is immutable | `fleet-001-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/model.py`, `fleet-manager/fleet_manager/observation.py`, `fleet-manager/tests/test_model_v1.py` |
| `fleet-manager-domain` | A pool declares its whole contract or is refused by field | `fleet-001-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/documents.py`, `fleet-manager/fleet_manager/model.py`, `fleet-manager/tests/test_model_v1.py` |
| `fleet-manager-domain` | Secrets are referenced, never carried | `fleet-001-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/documents.py`, `fleet-manager/tests/test_model_v1.py` |
| `fleet-manager-domain` | A host may run a pool only where capabilities, allow-list and state agree | `fleet-001-04` | `fleet-manager/fleet_manager/model.py`, `fleet-manager/tests/test_model_v1.py` |
| `fleet-manager-domain` | Capacity, drain and rollout refuse impossible states | `fleet-001-05` | `fleet-manager/fleet_manager/model.py`, `fleet-manager/tests/test_model_v1.py` |
| `fleet-manager-extraction` | The boundary package builds and tests from declared inputs alone | `repo-005-01` | `fleet-manager/scripts/extraction_rehearsal.py` |
| `fleet-manager-extraction` | The open core builds and tests with the boundary absent | `repo-005-02` | `fleet-manager/scripts/extraction_rehearsal.py` |
| `fleet-manager-extraction` | Files allowed to name the boundary are declared and pinned | `repo-005-03` | `scripts/check_boundary.py` |
| `fleet-manager-job-lifecycle` | One job per instance, and no way back to warm | `fleet-008-01` | `fleet-manager/fleet_manager/lifecycle.py`, `fleet-manager/tests/test_lifecycle_v1.py` |
| `fleet-manager-job-lifecycle` | Cleanup is proved before a replacement joins capacity | `fleet-008-02` | `fleet-manager/fleet_manager/lifecycle.py`, `fleet-manager/tests/test_lifecycle_v1.py` |
| `fleet-manager-job-lifecycle` | Quarantine is a state with a reason | `fleet-008-03` | `fleet-manager/fleet_manager/lifecycle.py`, `fleet-manager/tests/test_lifecycle_v1.py` |
| `fleet-manager-job-lifecycle` | Resource limits are required and rendered | `fleet-008-04` | `fleet-manager/fleet_manager/lifecycle.py`, `fleet-manager/tests/test_adapters_v1.py`, `fleet-manager/tests/test_lifecycle_v1.py` |
| `fleet-manager-job-lifecycle` | Lifecycle failures are the closed typed errors | `fleet-008-05` | `fleet-manager/fleet_manager/lifecycle.py`, `fleet-manager/tests/test_lifecycle_v1.py` |
| `fleet-manager-plan` | A plan is deterministic, complete, and impossible to edit | `fleet-002-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/plan.py`, `fleet-manager/tests/test_plan_apply_v1.py` |
| `fleet-manager-plan` | An apply is bound to its revision and its principal | `fleet-002-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/apply.py`, `fleet-manager/fleet_manager/auth.py`, `fleet-manager/tests/test_plan_apply_v1.py` |
| `fleet-manager-plan` | Retry is idempotent by key, and a key covers one plan | `fleet-002-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/apply.py`, `fleet-manager/fleet_manager/audit.py`, `fleet-manager/tests/test_plan_apply_v1.py` |
| `fleet-manager-plan` | The audit log is append-only and cannot be back-dated | `fleet-002-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/apply.py`, `fleet-manager/tests/test_plan_apply_v1.py` |
| `fleet-manager-reconciliation` | Reconciliation is a deterministic diff, never a state | `fleet-003-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/reconcile.py`, `fleet-manager/tests/test_reconcile_v1.py` |
| `fleet-manager-reconciliation` | Convergence is bounded and every deferral is named | `fleet-003-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/reconcile.py`, `fleet-manager/tests/test_reconcile_v1.py` |
| `fleet-manager-reconciliation` | The reconciler never disturbs work it cannot prove finished | `fleet-003-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/reconcile.py`, `fleet-manager/tests/test_reconcile_v1.py` |
| `fleet-manager-reconciliation` | Deterministic fixtures are the evidence | `fleet-003-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/reconcile.py`, `fleet-manager/tests/test_reconcile_v1.py` |
| `fleet-manager-signed-state` | A desired state is a signed document and cannot carry a command | `fleet-006-01` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/state.py`, `fleet-manager/tests/test_state_v1.py` |
| `fleet-manager-signed-state` | A signed state names exactly one audience | `fleet-006-02` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/state.py`, `fleet-manager/tests/test_state_v1.py` |
| `fleet-manager-signed-state` | A state is fresh and cannot be replayed | `fleet-006-03` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/state.py`, `fleet-manager/tests/test_state_v1.py` |
| `fleet-manager-signed-state` | Two test hosts reconcile signed no-op desired state | `fleet-006-04` | `fleet-manager/fleet_manager/__init__.py`, `fleet-manager/fleet_manager/state.py`, `fleet-manager/tests/test_two_hosts_v1.py` |
| `framework-ci` | The framework runs its own tests in CI | `fw-ci-01` | `tests/test_template_supply_chain.py` |
| `framework-ci` | The framework applies its own gates to itself | `fw-ci-02` | `tests/test_template_supply_chain.py` |
| `framework-ci` | Workflow actions are digest or SHA pinned | `fw-ci-03` | `tests/test_template_supply_chain.py` |
| `game-regression` | failure registry is append-only | `game-reg-04` | `scripts/log_failure.py` |
| `game-regression` | registered patterns block staged changes | `game-reg-05` | `scripts/game_regression.py` |
| `game-regression` | determinism evidence for gameplay crashes | `game-reg-06` | `scripts/log_failure.py` |
| `game-regression` | Game-class pattern scan | `game-reg-01` | `scripts/game_regression.py` |
| `game-regression` | Registry patterns honor scoping and annotations | `game-reg-02` | `scripts/game_regression.py` |
| `game-regression` | Empty scope is not a pass | `game-reg-03` | `scripts/game_regression.py` |
| `game-session-start` | One manifest describes every session | `session-01` | `engines/godot/game_session_hooks.gd`, `hub/sessions.py`, `scripts/game_session_start.py`, `templates/hooks/claude-code/session-start.sh`, `templates/hooks/codex/session-start.sh`, `templates/hooks/mimo/session-start.sh`, `templates/hooks/opencode/session-start.mjs`, `templates/hooks/pi-extension/session-init.ts`, `tests/test_game_session_start.py` |
| `game-session-start` | The seed rule is one hard rule, at boot | `session-02` | `engines/godot/game_session_hooks.gd`, `scripts/game_session_start.py`, `templates/hooks/claude-code/session-start.sh`, `templates/hooks/codex/session-start.sh`, `templates/hooks/mimo/session-start.sh`, `templates/hooks/opencode/session-start.mjs`, `templates/hooks/pi-extension/session-init.ts`, `tests/test_game_session_start.py` |
| `game-session-start` | The advisory block is kind-filtered and honest-empty | `session-03` | `engines/godot/game_session_hooks.gd`, `scripts/game_session_start.py`, `templates/hooks/claude-code/session-start.sh`, `templates/hooks/codex/session-start.sh`, `templates/hooks/mimo/session-start.sh`, `templates/hooks/opencode/session-start.mjs`, `templates/hooks/pi-extension/session-init.ts`, `tests/test_game_session_start.py` |
| `game-session-start` | Accepted sessions append to one immutable log | `session-04` | `engines/godot/game_session_hooks.gd`, `hub/sessions.py`, `scripts/game_session_start.py`, `templates/hooks/claude-code/session-start.sh`, `templates/hooks/codex/session-start.sh`, `templates/hooks/mimo/session-start.sh`, `templates/hooks/opencode/session-start.mjs`, `templates/hooks/pi-extension/session-init.ts`, `tests/test_game_session_start.py` |
| `game-session-start` | The gap line reads the scanner's report, never a second inventory | `session-05` | `hub/sessions.py`, `scripts/game_session_start.py`, `tests/test_game_session_start.py` |
| `game-session-start` | Exit codes say which kind of signal this is | `session-06` | `engines/godot/game_session_hooks.gd`, `scripts/game_session_start.py`, `templates/hooks/claude-code/session-start.sh`, `templates/hooks/codex/session-start.sh`, `templates/hooks/mimo/session-start.sh`, `templates/hooks/opencode/session-start.mjs`, `templates/hooks/pi-extension/session-init.ts`, `tests/test_game_session_start.py` |
| `game-type-phase-matrix` | Manifest-driven phase gate (planned) | `game-matrix-01` | - |
| `game-type-phase-matrix` | Phase gating follows the matrix row (planned - NOT IMPLEMENTED) | `game-matrix-02` | - |
| `game-type-phase-matrix` | Unknown game types fail closed (planned - NOT IMPLEMENTED) | `game-matrix-03` | - |
| `gate-configuration-contract` | Configuration lives in the project overlay | `rule-config-01` | `scripts/gate_overlay.py`, `scripts/schema-health-check.mjs`, `scripts/silent-success-scan.sh` |
| `gate-configuration-contract` | Fresh installs are green | `rule-fresh-01` | `scripts/gate_overlay.py`, `scripts/silent-success-scan.sh` |
| `gate-execution-contract` | Project-root resolution | `gate-root-01` | `scripts/gate_common.py`, `scripts/lib/project_root.py` |
| `gate-execution-contract` | No vacuous green | `gate-vacuous-01` | `scripts/lib/test-runner-select.mjs`, `tests/test_run_tests_runner.mjs` |
| `gate-execution-contract` | --all diff window | `gate-allwindow-01` | `scripts/regression_check.py`, `scripts/regression_diff.py` |
| `hub-architecture` | Single hub on monitor-hub | `mon-hub-01` | `hub/config.py`, `hub/main.py`, `hub/request_limits.py`, `hub/server.py` |
| `hub-architecture` | Dual evidence channels | `mon-channels-01` | `hub/github_client.py`, `hub/monitor.py` |
| `hub-architecture` | Registry is instance state, never committed | `mon-registry-01` | `hub/registry.py`, `tests/test_hub_registry_schema.py` |
| `hub-architecture` | Hub death is detected by a spoke | `mon-deadman-01` | `hub/server.py` |
| `hub-architecture` | Local-only network posture | `mon-local-01` | `hub/config.py` |
| `integrations` | stable CI integration | `coh-int-01` | `hub/coherence/invoke.py`, `tests/test_coherence_local_wrapper.py`, `tests/test_coherence_workflow_template.py`, `tests/test_hub_coherence_invoke.py` |
| `integrations` | fleet visibility | `coh-int-02` | `hub/coherence_view.py`, `hub/monitor.py` |
| `integrations` | promote-or-halt contract | `coh-int-03` | `scripts/world_slice_tool.py` |
| `integrations` | no implicit trust from upstream | `coh-int-04` | `hub/coherence/oap_evidence.py` |
| `integrations` | adapters never weaken the contract | `coh-int-05` | `hub/coherence/invoke.py`, `hub/coherence_view.py`, `hub/monitor.py`, `tests/test_coherence_local_wrapper.py`, `tests/test_hub_coherence_invoke.py`, `tests/test_hub_monitor_default_deny.py` |
| `integrations` | gate runs or reports explicit SKIPPED | `coh-int-06` | `hub/coherence_view.py`, `tests/test_coherence_workflow_template.py` |
| `integrations` | per-repository fleet independence | `coh-int-07` | `hub/coherence_view.py`, `hub/monitor.py`, `tests/test_runbook_claims.py` |
| `open-item-aging` | An aged open item must carry a triage disposition | `oia-01` | `scripts/open_item_aging_check.py`, `tests/test_open_item_gates.py` |
| `open-item-aging` | Deferral expires and carries a reason | `oia-02` | `scripts/open_item_aging_check.py`, `tests/test_open_item_gates.py` |
| `open-item-aging` | An unparseable age fails rather than defaulting | `oia-03` | `scripts/open_item_aging_check.py` |
| `open-item-aging` | A vacuous scan is never a pass | `oia-04` | `scripts/open_item_aging_check.py` |
| `package-resolution` | explicit package resolution | `coh-pkg-01` | `hub/coherence/package.py` |
| `package-resolution` | package structural validity | `coh-pkg-02` | `hub/coherence/__main__.py`, `hub/coherence/package.py`, `hub/coherence/schemacheck.py` |
| `package-resolution` | normative boundary | `coh-pkg-03` | `hub/coherence/package.py`, `tests/test_hub_coherence_normative.py` |
| `package-resolution` | frozen import closure | `coh-pkg-04` | `hub/coherence/package.py` |
| `package-resolution` | authenticated normative inventory | `coh-pkg-05` | `hub/coherence/package.py` |
| `per-screen-tracking` | Scene inventory and orphan detection | `screen-inv-01` | `scripts/scene_inventory.py` |
| `per-screen-tracking` | Empty scene scope is not a pass | `screen-inv-02` | `scripts/scene_inventory.py` |
| `publish-safety` | Upload exactly once | `rel-upload-01` | `scripts/deploy.sh`, `tests/test_schema_health_exitcodes.py` |
| `publish-safety` | No vacuous artifact verify | `rel-artifact-01` | `scripts/deploy.sh`, `tests/test_schema_health_exitcodes.py` |
| `publish-safety` | fix_commit verification | `rel-fixcommit-01` | `scripts/failure_registry_check.py` |
| `release-gate-targeting` | Gates evaluate the project being deployed | `rel-target-01` | `scripts/deploy.sh`, `scripts/regression_check.py`, `tests/test_schema_health_exitcodes.py` |
| `release-gate-targeting` | Runtime vulnerability classification | `rel-audit-01` | `scripts/regression_audit.py` |
| `reviewer-surfaces` | SARIF validity | `MISSING` | - |
| `reviewer-surfaces` | local-CI parity | `MISSING` | - |
| `reviewer-surfaces` | evidence-linked review comments | `MISSING` | - |
| `rule-coverage-truth` | Enabled means enforced | `rule-truth-01` | `scripts/rules_check.py` |
| `rule-coverage-truth` | Behavior rules live in skills | `rule-behavior-01` | `scripts/rules_check.py`, `tests/test_template_supply_chain.py` |
| `rule-coverage-truth` | Language-aware spec markers | `rule-marker-01` | `scripts/findings_to_spec.py`, `scripts/lib/spec_discovery.py`, `scripts/spec_traceability.py`, `tests/test_spec_traceability.py` |
| `runner-monitoring` | Runner online detection | `mon-online-01` | `hub/monitor.py`, `tests/fixtures/runner_spoke.py` |
| `runner-monitoring` | Queue-drain detection | `mon-queue-01` | `hub/monitor.py` |
| `runner-monitoring` | Gate-result tracking | `mon-gates-01` | `hub/monitor.py` |
| `runner-monitoring` | Drift-scan recency | `mon-drift-01` | `hub/monitor.py` |
| `runner-toolchain-requests` | A runner reports a capability gap drawn from a closed vocabulary | `mon-tc-01` | `hub/registry_observations.py`, `hub/toolchain_evidence.py`, `hub/toolchain_requests.py`, `hub/toolchain_store.py`, `scripts/lib/toolchain_probe.py` |
| `runner-toolchain-requests` | The hub is the system of record, and lane identity is explicit | `mon-tc-02` | `hub/registry_observations.py`, `hub/toolchain_api.py`, `hub/toolchain_queue_read.py`, `hub/toolchain_registry.py`, `hub/toolchain_requests.py`, `hub/toolchain_store.py` |
| `runner-toolchain-requests` | Decisions are attributable and cannot be made by a runner | `mon-tc-03` | `hub/toolchain_api.py`, `hub/toolchain_creds.py`, `hub/toolchain_evidence.py`, `hub/toolchain_registry.py`, `hub/toolchain_transitions.py`, `tests/test_hub_operator_auth.py` |
| `runner-toolchain-requests` | Request state changes only through a guarded transition | `mon-tc-04` | `hub/toolchain_api.py`, `hub/toolchain_creds.py`, `hub/toolchain_evidence.py`, `hub/toolchain_registry.py`, `hub/toolchain_transitions.py`, `tests/test_hub_operator_auth.py` |
| `runner-toolchain-requests` | Fulfillment requires evidence from a trusted builder and a later convergence | `mon-tc-05` | `hub/toolchain_api.py`, `hub/toolchain_evidence.py` |
| `runner-toolchain-requests` | Absence is never reported as health | `mon-tc-06` | `hub/registry_observations.py`, `hub/toolchain_evidence.py`, `hub/toolchain_requests.py`, `hub/toolchain_store.py` |
| `scanner-parsing` | Godot scene parsing | `gate-tscn-01` | `scripts/scene_inventory.py` |
| `scanner-parsing` | Rust test-scope exemption | `gate-rstest-01` | `scripts/guardrails-scan.mjs` |
| `scanner-parsing` | Test file sizing | `gate-size-01` | `scripts/regression_sizes.py` |
| `secret-rotation` | Scrubbing a secret from HEAD is not revoking it | `sr-01` | `scripts/secret_rotation_check.py`, `tests/test_open_item_gates.py` |
| `secret-rotation` | A revocation must carry date and evidence | `sr-02` | `scripts/secret_rotation_check.py`, `tests/test_open_item_gates.py` |
| `secret-rotation` | A malformed row cannot be partially trusted | `sr-03` | `scripts/secret_rotation_check.py` |
| `secret-rotation` | An empty ledger passes; an unparseable one does not | `sr-04` | `scripts/secret_rotation_check.py` |
| `security-boundaries` | Repository-supplied paths are contained | `coh-sec-01` | `hub/coherence/context.py`, `hub/coherence/manifest.py`, `hub/coherence/store.py`, `scripts/check_manifest_join.py`, `scripts/findings_to_spec.py`, `scripts/gate_common.py`, `scripts/regression_corpus.py`, `scripts/spec-fleet-classify.py`, `tests/test_gate_containment.py`, `tests/test_hub_coherence_containment.py` |
| `security-boundaries` | Hub request and shutdown contracts | `mon-sec-01` | `tests/test_hub_hardening.py` |
| `security-boundaries` | Tokens are not stored or logged in plaintext | `mon-sec-02` | `tests/test_hub_registry_schema.py`, `tests/test_template_supply_chain.py` |
| `security-boundaries` | Template actions and images are immutably referenced | `ci-sec-01` | `tests/test_template_supply_chain.py` |
| `spec-platform` | Main specs are CLI-valid and marker-parseable | `spec-fmt-01` | `scripts/lib/spec_discovery.py`, `scripts/migrate_spec_format.py`, `scripts/spec_traceability.py`, `scripts/specs-validate-negative-control.sh`, `tests/test_spec_traceability.py` |
| `spec-platform` | Completed changes are archived | `spec-fmt-02` | `scripts/spec_traceability.py`, `tests/test_spec_traceability.py` |
| `spec-platform` | Change-local authority policy is documented | `spec-fmt-03` | `scripts/spec_traceability.py`, `tests/test_spec_traceability.py` |
| `spec-state-ledger` | State transitions are recorded in an append-only ledger | `spec-state-01` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | The gate derives transitions from the diff, not from prose | `spec-state-02` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | Bounding commits resolve, are ordered, and are distinct | `spec-state-03` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | Work must land at the requirement's declared location | `spec-state-04` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | Terminal closure requires verifiable evidence | `spec-state-05` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | A spec is terminal only when every requirement is exercised | `spec-state-06` | `scripts/spec-state-validate-negative-control.sh` |
| `spec-state-ledger` | The published index is generated, and drift fails | `spec-state-07` | `scripts/spec_index.py` |
| `spec-state-ledger` | Migration proves what is provable and marks the rest | `spec-state-08` | `scripts/spec_state_backfill.py` |
| `spec-state-ledger` | Enforcement placement is stated honestly | `spec-state-09` | - |
| `subjects-3d` | 3D subject manifest | `coh-3d-01` | `hub/coherence/manifest.py`, `scripts/world_slice_tool.py`, `tests/test_hub_coherence_3d_slice.py` |
| `subjects-3d` | repair invalidates prior results | `coh-3d-02` | `hub/coherence/evaluators.py`, `scripts/world_slice_tool.py`, `tests/test_hub_coherence_3d_slice.py` |
| `subjects-3d` | pipeline consumes the common contract | `coh-3d-03` | `hub/coherence/evaluators.py`, `scripts/world_slice_tool.py`, `tests/test_hub_coherence_3d_slice.py` |
| `subjects-3d` | captures are declared inputs | `coh-3d-04` | `hub/coherence/evaluators.py`, `hub/coherence/manifest.py`, `scripts/world_slice_tool.py`, `tests/test_hub_coherence_3d_slice.py` |
| `surface-reach` | A change must reach every declared surface | `srch-01` | `scripts/surface_reach_check.py`, `tests/test_open_item_gates.py` |
| `surface-reach` | A vanished surface is a failure, not a skip | `srch-02` | `scripts/surface_reach_check.py`, `tests/test_open_item_gates.py` |
| `surface-reach` | Comparison mode is declared per group | `srch-03` | `scripts/surface_reach_check.py` |
| `surface-reach` | A group with fewer than two surfaces is a configuration error | `srch-04` | `scripts/surface_reach_check.py` |
| `traceability-and-drift` | bidirectional task traceability | `MISSING` | - |
| `traceability-and-drift` | spec-to-diff review | `MISSING` | - |
| `traceability-and-drift` | reverse drift detection | `MISSING` | - |
| `tree-clean` | Unclassified working-tree dirt fails the gate | `tc-01` | `scripts/tree_clean_check.py`, `tests/test_open_item_gates.py` |
| `tree-clean` | Generated churn is reported, not failed | `tc-02` | `scripts/tree_clean_check.py`, `tests/test_open_item_gates.py` |
| `tree-clean` | File-mode-only churn is its own class | `tc-03` | `scripts/tree_clean_check.py` |
| `tree-clean` | No repositories scanned is never a pass | `tc-04` | `scripts/tree_clean_check.py` |
| `zig-opengl-engine` | engine detection follows the manifest then project files | `zig-engine-01` | `scripts/scene_inventory.py` |
| `zig-opengl-engine` | Zig UI screens are inventoried under src/ui | `zig-ui-inv-01` | `scripts/scene_inventory.py` |
| `zig-opengl-engine` | scan scope is declared by the project manifest | `zig-scope-01` | `scripts/game_regression.py` |
| `zig-opengl-engine` | Zig + OpenGL regression classes block staged changes | `zig-regress-01` | `scripts/game_regression.py` |


## Targeted evidence anchors rechecked in this audit

- Fleet App enrollment: `scripts/fleet-app-enroll.py` defines `list_repositories`, `reconcile_repo`, `seal_secret`, argument/auth validation, and report emission. `tests/test_fleet_app_enroll.py` has hermetic scenarios for pagination, archived skip, create/update/no-op variable, absent-only sealed secret and rotation, dry-run no-write, per-repository failure continuation, redaction, missing token, and workflow trigger/default. `.github/workflows/fleet-app-enroll.yml` wires scheduled apply, manual dry-run default, required credential pair, and report artifact. These code/test/CI anchors do not create source markers today and do not prove a live fleet run.
- Art contract: `docs/ART-CONTRACT-EXTENSION.md` explicitly treats a human-only requirement such as `art-evolve-01` as intentionally uncovered, requiring real registry failure evidence and warning against marking a non-enforcing helper. This supports the non-coverage rationale; no actual end-to-end human failure-class event or external game consumer proof was verified, so that evidence remains NOT_RUN.
- Spec-state enforcement: `.github/workflows/spec-state.yml` runs on `push` to `main` and calls the range audit with explicit detection-after-the-fact error text. `scripts/hooks/pre-commit` documents local prevention and bypass with `--no-verify`. No remote default-branch protection setting was read in this audit; that owner-controlled setting is NOT_RUN. The YAML workflow is not an eligible source marker location for the marker scanner, so `spec-state-09` remains uncovered rather than receiving a false binding.


## Spec-gate source/history details

- `spec-fmt-04` already has an enforcing negative control at `scripts/specs-validate-negative-control.sh` and is invoked at `.github/workflows/ci.yml` after strict validation. Its exact archived requirement title is ?strict validation is proven able to fail? (`openspec/changes/archive/2026-10-03-fix-specs-gate-audit-2026-09/specs/openspec-format-conformance/spec.md`). The current canonical `spec-platform` has only `spec-fmt-01..03`; therefore DG01 carries this already-coded, source-marked requirement into a current delta and does not claim new code. The separate new identity-completeness requirement is `spec-fmt-05` and remains uncovered until implemented. Adding the already-coded `spec-fmt-04` marker raises coverage from 238 to 239 without new implementation.
- Rechecked `python3 scripts/spec_state_gate.py --base 479b609 --head fd2c11f`: exit 1 with exactly three unsupported-format findings for `adapters-and-loops`, `reviewer-surfaces`, and `traceability-and-drift`. This pins the DG01 missing-ID work to a current gate consequence.


The pinned archive validation baseline at fd2c11f is 33/43 passing; ten archive failures are incomplete historical task checkboxes, not strict-format errors. See the archive table and DG-04 acceptance task for exact failing IDs.
