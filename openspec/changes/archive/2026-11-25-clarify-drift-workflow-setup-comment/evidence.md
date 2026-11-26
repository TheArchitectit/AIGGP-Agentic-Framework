# DG-20 evidence

Hosted draft #41 ran DevGate Data Corruption in workflow `45689587069`, job
`139471185205`. Its content scan passed; the PR range scan reported a
substitution flip at `templates/github-workflows/drift-scan.yml:22` and exited
1. The exact failing revision (`4bc3f050c7178c8642fb38738b0a4328329c13d9`)
was reproduced locally against base
`cb96da16da4d59e102b68005a9094404a41a0c3f`: the content scan passed and the
range scan reported the same 68% substitution flip. [Hosted job](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45689587069/job/139471185205)

The setup comment now gives `.devgate/` ignore guidance and the reviewed
`DEVGATE_SHA` requirement on independent short lines. Focused template tests
passed (5 passed), strict OpenSpec validation passed, and the content scan
passed (1274 text files, 0 grandfathered findings).

For exact candidate-range verification, a disposable full-history clone was
based on the candidate worktree. Its local `origin/main` ref was set to the
specified base commit, and a synthetic local commit contained the candidate
setup-comment correction. `python3 scripts/check_corruption.py --repo .
--range origin/main..HEAD` passed. No workflow runtime or gate logic changed.

Independent Linux replay reproduced the exact one-finding baseline. The
corrected tracked candidate passed content checks for 1,268 files and the
same committed-range scan with zero findings. All five drift tests and
strict change validation passed.
