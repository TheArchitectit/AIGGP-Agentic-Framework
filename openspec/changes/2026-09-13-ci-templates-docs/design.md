# Design: CI templates, repo CI, doc reconciliation

## Locked decisions

D1. **drift-scan.yml: full history + parser provisioning.** Both checkouts
    get `fetch-depth: 0`. The semantic arm runs only when TS/JS files exist
    and is preceded by `npm install --no-save typescript@5`. The gate table
    gains a SKIPPED state so a gate that legitimately did not run is
    distinguishable from PASS/FAIL.

D2. **guardrails-compliance.yml: exact-name matching.** Forbidden patterns
    are matched with `find`/basename equality (`.env`, `*.pem`, `*.key`,
    `credentials.json`, `secrets.json`) instead of `grep -E`; `.env.example`
    and friends are explicitly allowed. The AI-attribution splitter becomes
    `git log --format=%B -z`-style per-commit iteration (or awk on the
    literal separator), not `tr`.

D3. **Framework self-CI.** A single `.github/workflows/ci.yml` on
    pull_request + push to main: pytest tests/, node tests/*.mjs,
    guardrails-scan.mjs, semantic-scan.mjs, failure_registry_check.py,
    regression_check.py --all --pre-commit (with fetch-depth: 0), and — once
    baseline-hygiene D5 lands — baseline_check.py. Required status check on
    main.

D4. **Version truth.** VERSION bumps to match the latest tag (1.2.0) and
    CHANGELOG gains [1.1.0] and [1.2.0] sections reconstructed from
    `git log v1.0.0..v1.2.0`; deploy.sh's manifest-bump table gains a
    VERSION-file row so the next release cannot drift again (coordinates
    with deploy-pipeline D-notes; implemented there or here, not both).

D5. **AGENTS.md rewritten to the overlay contract.** "Adding Custom Rules"
    points at the project-root overlay (merge semantics from the README);
    the database section points at schema-contract.json
    (rule-enforcement-gaps D5) with the edit-the-script path removed; rule
    counts are generated or deleted rather than hand-maintained.

D6. **Small alignments.** file-size-check.yml uses `>` to match
    regression_check.py and drops the dead check_file_sizes.sh reference;
    secret-validation.yml exempts the same `.env.*` suffix set as
    guardrails-scan.mjs (.example/.template/.sample); the PREVENT-024
    self-hit on tests/test_regression_check.py gets a scoped
    guardrails-allow or rule retune so the repo is warning-clean on itself.

## Open questions

Q1. Should self-CI also run the deploy.sh dry-run harness (deploy-pipeline
    Sprint 3.2)? Recommendation: yes, as a non-blocking job until that
    harness stabilizes, then required.

Q2. Minimum runner matrix (ubuntu only, or macOS for the .tscn/parser
    paths)? Recommendation: ubuntu-only now; the gates are platform-light.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| fetch-depth: 0 slows scheduled drift runs on large consumers | Low | Only the drift template; PR templates keep shallow checkouts |
| Turning on self-CI immediately fails main (existing warnings) | Medium | Land D6's self-clean first; CI merges green |
| Reconstructed CHANGELOG misattributes entries | Low | Source is git history; mark reconstructed sections |
