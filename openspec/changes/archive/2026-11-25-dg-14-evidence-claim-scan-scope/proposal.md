# Proposal

## Why

The Windows evidence-claim gate run at PR head `dec8c22f3b542686e86bec648bf81ae2dc743f24`
reported nine findings that were not live evidence claims: three generated
Git hook sample comments under `.git/hooks/sendemail-validate.sample`, and
three normative examples in each of the canonical evidence-claims spec and
its archived delta. The detector's separator-dependent VCS path check misses
`.git` on Windows; its exact-path allowlist lacked the two reviewed normative
spec files.

The detector, workflow, and published spec are unchanged between PR head and
current `main` `cb96da16da4d59e102b68005a9094404a41a0c3f`; main's newer commits
are automated QA sweeps.

## What Changes

- Exclude VCS metadata using host-independent path components.
- Add only the canonical spec and archived source delta to the established
  explicit allowlist, with a rationale naming each file's normative examples.
- Add regression tests proving ordinary Markdown and fenced code outside exact
  exemptions remain scanned, alongside `.git` and `.github` controls.
- Preserve zero-scan failure and all other marker checks.

## Capabilities

### Modified Capabilities

- `evidence-claims`: make VCS exclusion portable and intentional exemptions
  explicit by exact path and rationale.

## Impact

`scripts/evidence_claim_check.py`, `docs/evidence-claim-allowlist.txt`,
`tests/test_open_item_gates.py`, and the evidence-claims OpenSpec delta. No
live or external evidence is claimed.
