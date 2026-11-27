# Hosted reference consumer pilot

The owner approved AIGGP commit `bdbd450e0275a05b319ce29d83f761e8ed552e69` for this synthetic pilot on November 27, 2026. The original handoff candidate `80d18b0f0f4e080c9e47d4e534cc2c56c29308ca` contains the same published text-integrity workflow blob, `5d5076ddfb6cc611653040e02c724f3e2f8c90ce`. A different pin remains a different tool revision.

The existing public AIGGP repository hosted a separate Git history rooted at `e4c6f33647d54d6c7925eb898f20c6b1bcf3395f`. Its disposable protected target is `codex/reference-promotion`. The repository default branch is `main`. Each synthetic PR checks out GitHub's two-parent test merge. The named runs use GitHub-hosted Linux, `ubuntu-latest`, Python 3.12 and SHA-pinned actions. The framework's UCS03 workflows have their own job receipts.

## Enforcing surfaces and owners

| Decision | Enforcing surface | Accountable role |
| --- | --- | --- |
| Consumer inputs and behavior | A Python CLI and two tests that invoke it as a subprocess. Test discovery fails on zero cases. | Reference application owner |
| Tool provenance and text quality | A clean, ignored `.devgate/` bootstrap checks the full commit. The published workflow executes charset, encoding, corruption content and range scans, then its gate controls. | AIGGP tooling maintainer and consumer CI owner |
| Candidate and runtime evidence | The trusted operator on AI02 uses the Mission Control App to publish each required result against the immutable PR head after checking the tested merge, job, runner and tooling. | Lab CI operator |
| Synthetic branch promotion | Strict required checks tied to App ID 2550930 on `codex/reference-promotion`, with administrator enforcement. A new candidate needs its own App check for each job. | Repository administrator and consumer release owner |
| Artifact release and deployment | The release owner must provide a separately verifiable approval binding exact artifact, authority, scope and validity, plus the recovery reference. Runtime verification needs readback from the intended destination. | Consumer release, deployment and destination owners |

The pinned [infra-info runbook](https://github.com/TheArchitectit/infra-info/blob/cc62e68128bcfb86528baf2718bc42caee57b932/ci-fleet/github-app-api-access.md) owns the AI02 access procedure. GitHub Actions (App ID 15368) executed the jobs. The separate `mission-control-ci-cd` App (ID 2550930) published the candidate checks. The consumer CI owner must qualify another runner class or forge with the same inputs, negative controls, exact check identities and branch enforcement before adopting it.

## What the controls exercised

The passing consumer ran all three text gates on ten files, the corruption diff on the candidate change, 55 gate self-tests and two application tests. One negative candidate introduced a single denied U+00A7 in tracked `case.txt`. A different candidate changed the real CLI so input 21 produced 23 where its contract requires 42. The stale candidate ran both native workflows successfully with the superseded tool pin. See the paired receipts below for each native result and the App's decision.

The published corruption step runs a content command and a range command in one shell block. Its shell can continue after the first command returns nonzero. For each passing text receipt the operator checked the actual success output and input count of the content scan, then the separate range result, before the gate self-tests began.

The framework baseline has a separate [UCS03 receipt inventory](receipts/framework-baseline.json). All ten job records carry the runner ID, actual checkout, native workflow/job and App check. The release coverage job failed at the approved source revision. Open-item and spec-state push findings are observational. The baseline does not count toward hosted consumer execution.

## Candidate receipts

All five cases ran on GitHub-hosted Linux. The [machine-readable receipts](receipts/hosted.json) include both job IDs, both runner IDs, the tool SHA, event, attempt and skipped steps for every candidate. Each App check links directly to its native job.

| Candidate | Consumer head / tested merge | Text integrity | Application behavior |
| --- | --- | --- | --- |
| [Approved (#65)](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/65) | `27e177d3525602d302008d5f7baf7ef8ed7eeda3` / `9a60f46b879cb77a6667a81865918fba6a0aec9a` | [App success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140618583112) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46031782121/job/140617140858) | [App success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140618597712) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46031781967/job/140617139630) |
| [Denied character (#62)](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/62) | `eace14c488d9190d78b293c73899fa5eddb6d4ef` / `66e2cd69d4a7bb72302741090efb9dcd894fcad8` | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140617760937) / [job failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030212214/job/140611800801) | [App success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140617778097) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030212242/job/140611799877) |
| [Incorrect CLI result (#63)](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/63) | `9ac6ed4b5b932f393ae7608628f07069f2201434` / `e1c0c04362019c9a18439da8341f2303647eb5f5` | [App success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140617968533) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030218684/job/140611821924) | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140617930536) / [job failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030218647/job/140611821261) |
| [Superseded tooling (#64)](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/64) | `bb1392a557a968f4db9ef0b5e693872b1331934c` / `53b9775e250aa97ca380683cb27013d0752576f8` | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140618233093) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030226131/job/140611845830) | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140618202422) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46030226027/job/140611844786) |
| [Missing checks, then superseded merge (#61)](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/pull/61) | `664956666fbfeed0c0839ad3c377c2d3a65aa0b0` / `54add079013d24785ae721ff8ddce11d17659636` | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140618483677) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46031511848/job/140616220761) | [App failure](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140612841128) / [job success](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46031511831/job/140616219113) |

GitHub returned HTTP 405 on two attempts to merge #61. The first attempt had a missing required App check and a second check still in progress. The later attempt had two failing App checks. The protected branch retained its original SHA after each attempt. The first refusal regenerated GitHub's temporary merge ref. A second pair of native jobs used a superseded merge checkout and received failing App checks. PR #65 provides the clean positive control on a current merge ref. PRs #62, #63 and #64 were also blocked. [Protection and rejection receipts](receipts/protected-branch.json).

## Replay

From a trusted framework checkout, run the collector with the operator-reviewed consumer head and a full infra-info clone. The default invocation reads evidence. The operator uses `--publish` to update the two App-owned checks. A new head requires a new operator run. A failure exit leaves the reason visible in the receipt.

```sh
python3 openspec/changes/qualify-consumer-delivery-evidence/lab/hosted_checks.py \
  --infra /path/to/infra-info --pr 65 --head 27e177d3525602d302008d5f7baf7ef8ed7eeda3
```

## Remaining delivery evidence

Delivery tasks 2.2 and 4.1 remain open. At the approved baseline, `verify_promotion` in `hub/coherence/attest.py` checks the signed subject against the candidate. The package-approval contract in `coh-ev-07` requires an independent authority. This pilot has no deployment approval verifier or destination readback receipt. The [bank owner tracker](../audit-bank-ai-tooling-platform-fit/tasks.md) identifies the remaining acceptance evidence and its accountable functions.
