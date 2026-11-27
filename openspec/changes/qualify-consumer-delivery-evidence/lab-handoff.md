# Resume consumer delivery qualification in the lab

**Checkpoint, November 27, 2026.** Start with the hosted reference consumer (delivery tasks 1.1, 1.2 and 2.1). In parallel, investigate the separate approval required by the deployment readback fixture (4.1). The interrupted session produced a design and source findings. The reference application, its materializer, its hosted runs and the readback fixture still need to be created. The working tree was clean before this handoff. All six bank qualification tasks remain open. [Delivery tasks](tasks.md) and [bank qualification tasks](../audit-bank-ai-tooling-platform-fit/tasks.md).

## Fresh checkout

Use the lab's normal Git authentication for publishing. A public HTTPS clone is sufficient for reading and running the baseline. Use full history for the regression and evidence checks. These commands assume a Linux shell, Git, Python 3.12 and Node.js 20.19 or newer with npm.

```sh
git clone https://github.com/TheArchitectit/AIGGP-Agentic-Framework.git
cd AIGGP-Agentic-Framework
git switch main
git pull --ff-only origin main
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor ab8ac7dd4de811f3b6c0c8cbf0df655dba49b881 HEAD
git switch -c lab/consumer-delivery-qualification
```

The ancestry check exits zero when the lab checkout contains the reviewed baseline. If resuming an existing lab branch, switch to that branch in place of creating it. Read the current [repository instructions](../../../AGENTS.md), [pre-work checklist](../../../.guardrails/pre-work-check.md), [delivery contract](specs/consumer-delivery-evidence/spec.md) and [design](design.md). The framework scripts live at the repository root here. In the standalone consumer they run from its ignored `.devgate/` checkout.

## What is already upstream

| Work | Starting evidence |
| --- | --- |
| Bank fit assessment and PR closeout | [PR #57](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/57) published the 12-area assessment, six qualification tasks and earlier merge receipts at `804e221`. [Bank assessment](../audit-bank-ai-tooling-platform-fit/bank-platform-fit.md) and [PR reconciliation](../archive/2026-11-25-reconcile-upstream-aiggp-pull-requests/evidence.md). |
| Monitor state inventory | [PR #58](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/58) merged at `ab8ac7d` and completed monitor task 1.1. Start with 1.2 and its manifest/receipt schemas. The inventory identifies pending enrollment values, legacy credentials and private alert data that make raw file copying unsuitable for a backup. [Inventory](../qualify-monitor-recovery/state-inventory.md) and [monitor tasks](../qualify-monitor-recovery/tasks.md). |
| DG-02 review | [PR #59](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/59) tracks the separate 025-036 evidence review. Twelve sealed batches now cover rows 001-144. All 182 remain UNPROVEN. Resume at DG02-U-145. [DG-02 review index](../dg-02-evidence-ledger-reconciliation/README.md). |
| Release coverage | At `ab8ac7d`, `VERSION` was `1.3.52` and the annotated tag still targeted `7d17d6f`. The main Release Coverage workflow failed. The release owner selects the candidate, version and notes under DG-22. [Workflow receipt](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46020968872) and [DG-22 tasks](../dg22-prepare-approved-main-release/tasks.md). |

## First lab run: a clean hosted consumer

1. **Select the target.** Use a disposable consumer repository whose owner permits GitHub-hosted Linux, the required check configuration and synthetic test commits. Record the repository, default branch, runner label and check owners. Target selection and Actions eligibility were still open at transfer. AIGGP's own CI uses its self-hosted runner. Keep that runner configuration intact. Qualify any additional private runner or forge separately when adopted.
2. **Materialize the consumer.** The proposed source directory is `templates/consumer-delivery-reference/`. Build a small Python application with a behavior test that invokes its real entry point. A Python 3.12 and Git materializer can populate an empty directory and produce a standalone repository. Keep the application's positive path, its failing cases and its named required checks reproducible from the lab clone.
3. **Reuse the published workflow.** Use the candidate tool pin `80d18b0f0f4e080c9e47d4e534cc2c56c29308ca`. Extract `templates/github-workflows/text-integrity.yml` from that Git object and replace the single `DEVGATE_SHA` placeholder with the full SHA. Keep its pinned checkout and setup-python actions. Supply the consumer's applicable scope/allowlists, LF attributes and `.gitignore` entry for `.devgate/`. Verify that a clean checkout bootstraps the pinned tooling. [Workflow template](../../../templates/github-workflows/text-integrity.yml), [bootstrap tests](../../../tests/test_github_workflow_bootstrap.py) and [onboarding](../../../docs/NEW_REPO_ONBOARDING.md).
4. **Run both positive and negative controls on the hosted runner.** The existing workflow is named `Text Integrity` and the job `Text integrity (charset / encoding / corruption)`. The proposed application workflow/job names are `Reference Consumer` and `Synthetic source behavior`. Use the actual check names GitHub emits when configuring the disposable promotion path. Run a passing consumer revision. On a separate fixture revision, introduce a tracked, in-scope text file containing U+00A7 and observe the pinned charset gate reject it. Also exercise a failing application case at the normal entry point. Keep the failed run and its diagnostic as evidence.
5. **Capture the receipts.** For each revision save the consumer SHA, actual checkout SHA, tool SHA, runner class, event, workflow/run and job URLs, check names, conclusions and nonzero input counts. Identify the tested merge SHA when a PR run tests a merge ref. Attribute each check to the revision it evaluated. For task 2.3, demonstrate that a failed or missing required check actually blocks the disposable protected promotion path. A post-push detection is observational. Check off only the tasks exercised.

## Parallel lab run: approval and deployment readback

The current `verify_run` checks a sealed evaluation and its evidence. `verify_promotion` additionally compares the attested subject digest with the candidate. The published `coh-ev-07` contract describes detached **package** approval, binding the digest, authority, repository scope and validity window. The review found no executable verifier for a separate deployment approval in the inspected coherence implementation. An exact match between the selected and reported artifact still leaves approval unresolved. [Attestation code](../../../hub/coherence/attest.py), [detached attestation](../../../hub/coherence/attest_detached.py), [package resolution](../../../hub/coherence/package.py) and [approval contract](../../specs/evidence-and-attestation/spec.md).

| What to exercise in the lab | Evidence required for delivery tasks 2.2 and 4.1 |
| --- | --- |
| Subject and promotion evidence | Produce a real signed synthetic evaluation with the [existing fixtures](../../../tests/fixtures/coherence/fixtures.py). Replay matching and wrong source, candidate and artifact digests, missing/failed/skipped checks, and an incorrect recovery reference. Keep source revision, evaluated subject digest and deployable artifact digest as distinct fields. |
| Independent approval | Identify the consumer-owned authority and its verification interface. Exercise scope, validity and exact approved subject/artifact. If an interface still needs design, record that dependency in the active OpenSpec and keep the successful deployment case open. |
| Destination readback | Use an isolated fake destination. Exercise exact match, wrong target, wrong or missing digest and unavailable readback. Require verified attestation, separate approval and a matching observed immutable artifact before emitting a verified deployment receipt. Retain the reason for each unresolved result. |

## Bank-owned work after the delivery pilot

| Bank task | Owner and next evidence |
| --- | --- |
| 2.1 and 2.2, hosted delivery and promotion | Consumer CI and release owners supply hosted checks, branch protection, artifact identity, approval and rollback evidence from the selected path. |
| 2.3, monitor recovery | Monitor maintainer and operator define recovery objectives and rehearse restore, writer fencing, heartbeat reconciliation and alert continuity using the [monitor recovery change](../qualify-monitor-recovery/tasks.md). |
| 3.1, read-only runtime pilot | Runtime and data owners use synthetic identities and records to prove scoped access, revocation and durable evidence for one named tool. [Consumer evidence boundary](../define-consumer-evidence-boundary/tasks.md). |
| 3.2, controlled action pilot | Action, identity and target owners exercise independent approval, credential scope, idempotency and reconciliation against a simulator. Record effect counts for accepted and denied cases. |
| 3.3, operational acceptance | Tenant, security and platform owners supply entitlement, policy, deployment and recovery evidence for the selected services. Keep bank-controlled receipts with the bank. Publish reusable synthetic findings upstream. |

## Validate and deliver from the lab

Run the existing targeted tests first. These commands use an isolated Python environment outside the checkout and the OpenSpec CLI version pinned by the [CI workflow](../../../.github/workflows/ci.yml).

```sh
lab_venv="$(mktemp -d)/aiggp-lab"
python3 -m venv "$lab_venv"
. "$lab_venv/bin/activate"
python3 -m pip install pytest cryptography==45.0.7 PyNaCl==1.5.0
python3 -m pytest -q tests/test_github_workflow_bootstrap.py tests/test_hub_coherence_attest.py tests/test_hub_coherence_attestation.py
npx --yes --package=@fission-ai/openspec@1.14.3 openspec validate --all --strict
python3 scripts/spec_index.py --check
python3 scripts/spec_traceability.py --root . --ratchet
```

Use one Luna agent to write the fixture and another to audit the actual positive and negative runs. The lead reconciles findings, stages the intended changes, runs the pre-commit gates in `AGENTS.md`, then commits and pushes. Run staged regression with `--fail-if-empty` while there is a staged diff. For committed changes, use `--base origin/main` on the feature branch. Record the exact head SHA and wait for the applicable GitHub checks before merging. Verify the merged files on upstream `main`. Update the linked OpenSpec tasks with the receipts and archive only when their acceptance criteria are met.
