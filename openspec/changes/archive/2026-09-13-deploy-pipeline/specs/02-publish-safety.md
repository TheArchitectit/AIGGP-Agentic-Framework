# Spec: Publish leg safety

## Requirement: Upload exactly once
<!-- id: rel-upload-01 -->
For every registry leg, a successful upload shall be attempted exactly once;
a failed upload shall abort the pipeline before any byte is published; the
pipeline's exit status shall be 0 only when the publish fully succeeded and
every post-publish step succeeded.

#### Scenario: successful PyPI publish
- **WHEN** `twine upload` succeeds
- **THEN** no second upload of the same artifact is attempted and the
  pipeline continues to the release step

#### Scenario: failed build
- **WHEN** the build step fails
- **THEN** no upload is attempted and the pipeline exits non-zero

## Requirement: No vacuous artifact verify
<!-- id: rel-artifact-01 -->
When a release-artifact contract file exists, it shall declare at least one
`must_contain` entry; otherwise the stage shall fail as a configuration
error. When no contract file exists, the stage shall print its documented
skip notice and continue.

#### Scenario: empty contract
- **WHEN** `.guardrails/release-artifact-contract.json` exists with an empty
  or missing `must_contain`
- **THEN** deploy.sh exits 1 naming the contract file as misconfigured

## Requirement: fix_commit verification
<!-- id: rel-fixcommit-01 -->
Any hex `fix_commit` of 7-40 characters shall be verified to exist in the
git history of the repository that owns the registry entry; documented
sentinel values are exempt.

#### Scenario: abbreviated SHA
- **WHEN** an entry's fix_commit is a valid 7-character abbreviation
- **THEN** the hygiene gate accepts it; a non-existent abbreviation errors
