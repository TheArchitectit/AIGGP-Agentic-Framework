# Design: release pipeline repairs

## Locked decisions

D1. **Gates run against the project, explicitly.** deploy.sh exports
    `DEVGATE_PROJECT_ROOT="$PROJECT_ROOT"` (new, honored by
    regression_check.py) and also `cd "$PROJECT_ROOT"` before every gate.
    The env var — not cwd — becomes the documented contract so no future
    `cd` in the pipeline can re-scoped a gate. If the gate-correctness
    change's unified root contract has landed, this is one line either way.

D2. **npm audit runtime classification uses npm's own signals.** A vuln is
    runtime-blocking when `isDirect` is true AND the package is in
    `dependencies`, or when any entry of `effects` is a runtime dependency.
    Dev-only paths stay warnings. Fixture: the audit's live lodash case
    (blocking) and a devDependency-only case (warning).

D3. **PyPI leg: build once, upload once, fail before publish.** Replace the
    `A || B && C` line with: build if `dist/` lacks artifacts for the target
    version, then a single `twine upload`, stderr shown. Any failure aborts
    (set -e) before anything is uploaded; a successful upload is never
    repeated. Old-version artifacts in dist/ are excluded by uploading only
    the just-built files.

D4. **Stage severities are honest.** Schema health runs with
    `--strict-when-configured`: skipped/unconfigured stays a skip notice, a
    configured adapter's failure blocks. Lint/clippy move to a labeled
    "advisory" step outside the gate step, or become blocking when the tool
    is configured — matching docs/RELEASE_GATE.md's stage table, which is
    updated in the same PR.

D5. **Artifact verify requires a non-empty must_contain.** A contract file
    with no `must_contain` entries is a configuration error (exit 1 with a
    message), not a pass. Absent file keeps the documented skip.

D6. **fix_commit validation covers short SHAs.** Any 7-40 hex value is
    verified with `git cat-file -t` in the owning repo (git resolves
    abbreviations); non-hex sentinels remain the documented dummies.

## Open questions

Q1. Should deploy.sh refuse to run from any branch other than the project's
    default branch? Recommendation: warn, not refuse — hotfix branches are a
    legitimate publish source.

Q2. For D4, is a configured-but-failing schema check ever legitimately
    non-blocking (e.g. read replica lag)? Recommendation: blocking, with a
    documented `--allow-schema-drift` escape that prints a loud banner.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| D2 reclassifies long-warning vulns as blocking in consumers | Medium | Release-note; classifications become *more* correct, and dev-only path stays warning |
| D1 env contract conflicts with gate-correctness change in flight | Medium | Land ordering: gate-correctness first, or make D1 tolerant of both (env wins, cwd fallback) |
| D3 changes publish behavior for projects with hand-built dist/ | Low | Only builds when target-version artifacts are missing; never cleans dist/ |
| D4 turns existing consumer deploys red | Medium | Ship with release note + `--allow-schema-drift` (Q2) |
