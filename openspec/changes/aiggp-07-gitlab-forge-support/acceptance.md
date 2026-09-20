## Required conformance fixtures

- Fixture A: seeded broken repo on both forges - identical findings.
- Fixture B: tag-pinned runner image - standard check fails.
- Fixture C: forged webhook without valid secret - rejected.
- Fixture D: backup restore drill - instance recovered, gates runnable.
- Fixture E: inline gate logic in a GitLab template - rejected in review.

## Release acceptance criteria

- All fixtures pass; parity drill green in CI on a pinned corpus version; backup drill evidenced; adapter emits valid envelopes from real lab repos.

## Open questions requiring owner decisions

- Lab instance ownership and upgrade policy (who patches GitLab, on what cadence).
- Whether external GitLab.com support is a launch goal or lab-first (proposal: lab-first; document external config as beta).

## Handoff

Do not skip Sprint 0: the instance is undocumented and everything else inherits that fog. Build the parity drill before declaring any template done - the drill is the definition of done for this spec.
