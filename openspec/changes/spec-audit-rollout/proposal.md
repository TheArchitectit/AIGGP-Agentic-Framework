# Proposal: spec-audit-rollout

## Why

Two intake problems, one proven shape. First: repositories get brought in
with no OpenSpec material (`openspec/specs/` empty or absent), and the only
signal is `spec_traceability.py` refusing with exit 2 — a config error no
one reads as "this repo needs specs". MergeKingdom hit exactly this wedge
(DevGate CI run 36665745405) and filed the work order
(`MergeKingdom:docs/SPEC-GAP-SCANNER-WORK-ORDER.md` @ bf7e52f): the fix is a
**gap scanner** doing the mechanical half (inventory × coverage, worst-
tracked first, evidence pointers) with the judgment half (requirement text)
explicitly fenced off behind review. "Find the gaps and make specs" is a
recurring job for every repo in the fleet — the nightly secret sweep already
proved the fleet-walk machinery, so the same walk should classify spacing.

Second: our vendored openspec templates have no provenance. Drift between
our copies and the official site is invisible today — the same exposure
class SGR-06 exists to catch for the secret gate. The fix is the gitleaks
discipline applied to templates: pin + hash + scheduled *detection*, with
adoption staying a human merge.

## What Changes

- **Scanner** — `scripts/spec_gap_scan.py` (+ `--scaffold`, `--draft`,
  `--json`, `--fail-on-gaps`), stdlib-only: mechanical inventory-vs-coverage
  per the work order's scan contract; honesty rails enforced in code
  (evidence-or-no-requirement; drafts born `<!-- draft: unreviewed -->` and
  excluded from every coverage count; CLAIMED-BUT-ABSENT never transitions
  without a code pointer; "looked and found nothing" distinct from "did not
  look"; exits `0` gaps-free / `1` gaps / `2` unusable, the secret-scan
  vocabulary — documented as inverted against gameSessionStart's).
- **Intake gate** — `spec-fleet.yml`: nightly walk of the SAME declaration
  files, classifying each repo `spaced` / `invalid` (openspec present,
  strict-red) / `unspaced` (absent — informational per SGR-10's measured
  lesson, never red) / `unscannable`; trend report committed to
  `docs/qa/spec-sweeps/`; deduped issue via `hub_alert.py --key
  spec_fleet_sweep` naming the repos, not just counting them (T-14
  lesson).
- **Template provenance** — `spec-templates.lock.json` (official-site URLs +
  sha256 per vendored template) + a refresh-check step in the fleet walk
  that compares upstream and files the drift issue when it moved. No
  auto-pull into any tree: detection is automated, adoption is a reviewed
  commit.
- **MergeKingdom acceptance** — the work order's five testbed criteria are
  this package's exit gate for the scanner (gap table backbone = GAPS.md,
  scaffold set matches, known false claims stay claims, traceability exits
  config-refusal into real numbers, CI matrix rows honest).

## Impact

- New specs: `spec-gap-audit` (SGA-01..07), `spec-intake-gate` (SGA-10..14),
  `spec-template-provenance` (SGA-20..22). IDs are safe to wire (SGR
  precedent).
- Reuses: declaration files, clone discipline, hub_alert dedupe, SGR-10
  informational/red split, T-31 census ethics (a report that cannot say is
  red, never clean).
- Does NOT change: `spec_traceability.py` (its exit-2 refusal stands — the
  scanner is an additive discoverer beside it, per the work order),
  `secret-fleet.yml` (sibling workflow, shared declaration, separate
  schedule), CI specs job (still validates this repo's own tree).
