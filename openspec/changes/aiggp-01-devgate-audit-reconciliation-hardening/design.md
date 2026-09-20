## Design principles

- A gate that cannot fail is not a gate; it is a progress bar.
- Fix evidence beats fix claims: every closure names commit, fixture, and before/after behavior.
- Waiver, do not hide: accepted risks are recorded, scoped, owned, and expiring.
- No behavior change without a fixture that exercises it.

## Locked decisions

- Reconciliation strategy: cherry-pick-by-finding, not branch merge. Each audit fix is re-applied to current main as its own commit with its own fixture, because main has moved (v1.1.0 at 3415cc8 through edca86b) and bulk merge would re-import stale assumptions.
- Deploy gate scope: the deploy gate audits the consuming project's tree and history, never the DevGate submodule's. The wrong-tree behavior is a P0 fix.
- Test floor: run-tests fails EMPTY when discovery returns zero; the floor count is per-project configurable in the bundle projection, never below one.
- Scanner non-vacuity: every scanner gate fails EMPTY when its target set is empty, and fails ERROR when its parser errors; neither is green.
- Baseline isolation: the shared baseline carries no consuming-repo allowlists; per-repo exceptions live in that repo's .devgate/.aiggp overlay with scope and expiry.
- Severity handling: dependency audit maps upstream HIGH/CRITICAL to blocking severity by default; downgrade requires a waiver.
- Forward compatibility: gate result objects gain subject digest, gate identity/version, and raw-result fields, matching the AIGGP-00 envelope contract.

## Major components

1. Finding ledger: the 34+ findings plus Kit + Ryan items, each with state (open/fixing/closed/waived), evidence, and owner.
2. Adversarial corpus: one fixture per false-green class (unscanned diff, missing history, parser failure, dead config, contaminated baseline, wrong-tree deploy, severity misclassification, path traversal, zero discovery).
3. Negative-control harness: runs the corpus in CI; any fixture passing a gate fails the build.
4. Honest-result plumbing: gate result objects with the envelope fields above.
5. Bootstrap repair: dependency install and test discovery that work from a clean clone, so the floor is reachable.

## Trust boundaries

- The corpus is adversarial input: it must be maintained as attack fixtures, not examples to be special-cased. A gate that pattern-matches the corpus instead of fixing the class fails review.
- Waivers enter through the same path as everything else; no direct baseline edits.
