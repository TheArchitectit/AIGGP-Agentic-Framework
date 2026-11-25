# AIGGP release coverage rehearsal

Extract the actual Verify release coverage step from
`.github/workflows/release-coverage.yml` for the fixture. Build one temporary
Git repository per scenario with a private local identity and controlled
`VERSION`, changelog and commit contents. Exercise an annotated tag at the
candidate HEAD, missing and stale tags, a lightweight tag, a missing changelog
heading, a generated-only change, and a generated change mixed with product
files. Temporary tags exist only in the fixture repositories. Use the output
and exit status as evidence, and verify the working repository's refs and
metadata were preserved.

Release-owner approval supplies the version, notes, and acceptance for the
candidate release. Review the metadata in the usual review flow and use the
supported release procedure. Record the remote annotated tag target and the
published release only after verifying both against the reviewed commit.
