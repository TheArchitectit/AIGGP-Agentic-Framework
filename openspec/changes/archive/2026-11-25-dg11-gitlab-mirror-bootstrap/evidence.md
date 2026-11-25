# Verification Evidence

## Scope and source

- Source revision: `dec8c22f3b542686e86bec648bf81ae2dc743f24`.
- Validation used an isolated worktree and synthetic local bare repositories. No live GitLab project, credentials, or runner were used.
- Runtime for shell-backed tests: Python 3.12 Alpine with Bash, Git, and pytest. The container base was `python:3.12-alpine`; this was not digest-pinned.

## Results

- `python3 -m pytest tests/test_gitlab_template_bootstrap.py -q` — **10 passed**. The suite executes the extracted bootstrap block against local bare fixtures and covers success, malformed pin, failed/partial clone retry refusal, wrong root, missing required script/rules/registry, tracked consumer paths, dirty/untracked reused checkout, credential non-disclosure, and shell-state isolation.
- `python3 -m pytest tests/test_gitlab_forge_support.py::test_glf01_all_github_workflow_templates_have_pinned_gitlab_mirrors -q` — **1 passed**; the mirror inventory and runner pins remain covered.
- `python3 scripts/forge_parity_drill.py` — **5 cases**, identical findings across both forge paths; four expected failures and one clean control.
- `python3 tests/gen_floors.py` — **142 suites, 2068 tests; floors hold**. Added a floor of 9 for the new 10-test suite.
- `docker run ... node:20-alpine npx --yes @fission-ai/openspec@1.14.3 validate dg11-gitlab-mirror-bootstrap --strict` — **valid**.
- `node scripts/guardrails-scan.mjs` — **exit 0**, pattern scan clean; reports 50 non-blocking warnings, including a test naming warning for this new test file.
- `node scripts/semantic-scan.mjs` — **clean** after supplying `typescript@5` in a temporary container dependency install; no dependency manifest or lockfile was added.
- `git diff --check` — **exit 0**.

## Acceptance boundary

All scoped local/bootstrap, template inventory, and forge parity checks passed. GitLab server parsing, runner execution, protected-variable configuration, private-source authentication, and real project adoption remain unverified and must stay dormant until an operator adopts GitLab. Independent audit approved the integrated candidate. Ten isolated Linux
bootstrap fixtures and the Windows structural inventory check passed. The
reviewed implementation is published at `ac61e20fa7a4afcc8e2827817446fa01cb5730ff`.
