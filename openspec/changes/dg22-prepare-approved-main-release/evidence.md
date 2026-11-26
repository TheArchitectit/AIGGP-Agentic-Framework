# DG-22 evidence

On 2026-11-25, the [main Release Coverage run](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45720189201)
rejected `2bf84ddab55695340e91ceb026b319fcae7de3e4` because the annotated
`v1.3.52` tag resolves to an earlier commit. The version and changelog
remain at their current release state. The next release needs reviewed
version and notes before metadata changes can proceed.

OpenSpec 1.14.3 strict validation of `dg22-prepare-approved-main-release`
passed using Docker Desktop on the Windows workspace. The isolated
coverage rehearsal results follow.

## Isolated gate rehearsal

On November 25, the exact Bash block from the `Verify release coverage` step
ran under GNU Bash 5.3.15 against five disposable Git repositories. The
fixture harness used `git init`, `git commit`, and `git tag -a` to set up the
source state, then ran the unmodified extracted step with
`sh.exe <extracted-step.sh>` from each fixture root.

| Fixture | Result |
| --- | --- |
| Annotated synthetic tag at HEAD with matching release notes | Exit 0, annotated release accepted |
| Annotated tag on an earlier commit | Exit 1, HEAD and tag mismatch |
| Annotated tag at HEAD with a missing release heading | Exit 1, changelog heading missing |
| Generated fleet sweep report only | Exit 0, generated-only exemption reported |
| Generated spec sweep report plus a product file | Exit 1, normal HEAD and tag check rejected the earlier tag |

The fixture HEAD and ref inventories matched before and after each execution.
Release approval, candidate selection, metadata, publication, and release
verification remain open.

## Linux fixture replay

The [pinned template test](https://github.com/TheArchitectit/agent-guardrails-template/blob/d0b00a444090c7b8deebc86c352208f3f258320e/tests/test_release_coverage_workflow.py) replayed this repository's coverage step using its structural reader at 1070d3e. All seven cases passed, including missing and lightweight tags in addition to the five recorded controls. The fixture sources and worktrees were disposable. A sentinel repository retained the same refs with inherited Git directory overrides set. Approval and release preparation remain open.
