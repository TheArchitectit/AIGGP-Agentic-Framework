# Design

## Context

The PR-head evidence-claim scan found nine markers: three in generated `.git`
hook samples and three each in the canonical and archived evidence-claims
specifications. The former are administrative metadata. The latter are
intentional normative marker examples, already reviewed and specifically
allowlisted by the detector's established explicit-exemption mechanism.

On Windows the old separator-string check did not recognize `.git` path
components. The existing allowlist did not yet name the two exact normative
spec paths.

## Goals / Non-Goals

**Goals:** exclude `.git` using host-independent path components and exempt
only the two reviewed spec files, each with a stated rationale; keep all other
files, Markdown prose, fenced code, and source under the existing fail-closed
scanner.

**Non-Goals:** parse Markdown, infer literal context, add wildcard Markdown
exemptions, weaken marker definitions, or claim external evidence.

## Decisions

- Use `Path.parts` to recognize the `.git` administrative component and
  `as_posix()` for stable diagnostic and allowlist paths.
- Add only the canonical evidence-claims spec and its archived source delta
  to `docs/evidence-claim-allowlist.txt`, with a rationale naming why these
  exact files contain normative examples.
- Keep positive controls for active prose, escaped backticks, fenced source,
  source markers, `.github`, and zero-input behavior.

## Risks / Trade-offs

- [A broad Markdown exemption could hide findings] -> exempt two exact
  reviewed files only; fixtures prove Markdown and fenced code elsewhere still
  fail.
- [Platform separators could hide metadata] -> test `.git` exclusion through
  `Path.parts` and retain `.github` as a control.

## Migration Plan

Update the explicit allowlist and path-component exclusion, run focused gate
tests and the direct tree scan, then validate with pinned OpenSpec and CI. Keep
the package open for independent review.
