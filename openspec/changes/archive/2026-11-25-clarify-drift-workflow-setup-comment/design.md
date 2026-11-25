# Design

## Context

Hosted run `45689587069`, job `139471185205`, step 17 reported a
substitution flip at `templates/github-workflows/drift-scan.yml:22`. The
file passed the content scan. The intentional setup change belongs to DG-08.

## Decisions

Use separate short instructions to ignore `.devgate/` and set
`DEVGATE_SHA` to a reviewed full commit. Retain the original check and its
configuration. Compare the old and new draft ranges using the same checked-in
script and verify the workflow's bootstrap and gate steps.

## Risks / Trade-offs

A broad exception would hide unrelated damage. The change is confined to
the drift template's setup text and the verification record.
