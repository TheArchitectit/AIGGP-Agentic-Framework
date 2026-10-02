# Alignment review — measured repository topology (2026-10-01)

Status: **evidence for an owner decision**, not a decision record. This file
records what the provider and local clones actually show as of 2026-10-01,
against ADR-001 / `design.md` "Locked decisions → Canonical repository". It does
not amend ADR-001. Overturning a locked ADR is an owner call; the measurements
below are here so that call is made against facts rather than draft wording.

## What the drafts assert

`adrs.md` ADR-001: *"Use the Agent Guardrails repository as the AIGGP host.
Rationale: it preserves the policy/runtime product lineage and avoids a third
repository. Consequence: host-root content must be moved carefully into
modules/policy."*

`design.md` (Locked decisions → Canonical repository): *"The existing Agent
Guardrails repository becomes the physical host for the unified AIGGP
repository… The repository is renamed to the settled AIGGP name only as a
separately approved hosting operation; provider redirects SHALL be verified if a
rename occurs."*

Target layout from the same file: `modules/policy/` (Agent Guardrails
policy/runtime) + `modules/devgate/` (DevGate subtree merge) + `kernel/` +
`schemas/` + `bundles/` + `conformance/` + `integrations/` + `docs/generated/` +
`tools/migration/`.

## What the provider shows (measured 2026-10-01)

| Repository | Role per its own description | Last push | Local clone |
|---|---|---|---|
| `TheArchitectit/AIGGP-Agentic-Framework` | **is the DevGate repository, renamed** — same root commit `8bf306e`, same remote as the DevGate clone | active | `/mnt/data/git/{DevGate,AIGGP}-Agentic-Framework` (one history, two paths) |
| `TheArchitectit/agent-guardrails-template` | Go MCP product, "Template repository with AI agent guardrails, safety protocols, and sprint task framework" | **2026-10-01** (v3.7.1) | `/mnt/data/git/agent-guardrails-template` |
| `TheArchitectit/guardrails-control-plane` | "Composition root for the guardrails architecture: pins guardrail-mcp, DevGate-Agentic-Framework, and guardrail-policy-packs as versioned submodules. One-way dependencies." | 2026-09-11 | none |
| `TheArchitectit/guardrail-mcp` | "Runtime guardrail MCP server extracted from agent-guardrails-template (mcp-server/)" | 2026-09-11 | none |
| `TheArchitectit/guardrail-policy-packs` | "Versioned policy packs: core rules plus domain packs" | 2026-09-11 | none |

`TheArchitectit/policy-bundles` does **not** exist yet (aiggp-02 Q5 stands it up
as a separate action; not a contradiction).

## Three facts that complicate ADR-001 as written

1. **The rename already happened, in the opposite direction.** ADR-001 says the
   *Agent Guardrails* repository is renamed to the settled AIGGP name as a
   separately approved operation. Measured: the repository carrying the AIGGP
   name is the **DevGate** repository (shared root commit and remote). Neither
   `agent-guardrails-template` nor `guardrails-control-plane` holds that name.
   "Provider redirects SHALL be verified if a rename occurs" is therefore not a
   future condition — it is a past event pointing the other way.

2. **"The Agent Guardrails repository" is not one repository.** The guardrails
   product is split across at least four: `agent-guardrails-template` (the
   lineage, still shipping — v3.7.1 today, and still containing `mcp-server/`),
   `guardrail-mcp` (extracted engine), `guardrail-policy-packs` (rule packs),
   and `guardrails-control-plane` (composition root). ADR-001's singular "the
   Agent Guardrails repository" is unambiguous only if the reader assumes it
   means `agent-guardrails-template`; the drafts never name a repo. Which one
   hosts `modules/policy/` is exactly the question ADR-001 answers by
   implication, and the four-way split means the answer is no longer implied.

3. **A second unification story already exists and is different in shape.**
   `guardrails-control-plane` composes the pieces as **pinned submodules**
   (`engines/guardrail-mcp`, `engines/devgate`, `policy/packs`) under a
   one-way dependency rule — control plane → engines and packs, never back.
   AIGGP-10 composes them as **a subtree merge into one monorepo**
   (`modules/devgate/`, `modules/policy/`). Both can be true sequentially, but
   they are not the same architecture, and AIGGP-10 does not mention the
   control plane at all. The aiggp drafts speak at product level only
   ("DevGate, Agent Guardrails, and Mission Control" — `aiggp-00/proposal.md`),
   never naming these repos.

## What this file does not claim

- It does not declare ADR-001 wrong. A monorepo host with `modules/policy/` and
  `modules/devgate/` remains a coherent end state; it just is not what the
  provider currently looks like.
- It does not decide whether `guardrails-control-plane`'s submodule composition
  is a predecessor stage that AIGGP-10 replaces, a consumer of AIGGP-10, or a
  competing end state.
- It does not touch ADR-002..ADR-008 (ancestry-preserving import, tag
  namespacing, archive-never-delete, no filter-repo by default). Those are
  orthogonal to which repo hosts, and they stay valid under any host choice.

## Corroborating package findings from the same review pass

Recorded here because they are the same class — draft wording drifted from
measured DevGate reality — and the fixes landed in their own packages:

- **aiggp-07, four sites** claimed "all five CI gate templates"; DevGate ships
  seven in `templates/github-workflows/` (guardrails compliance, secret
  validation, file size, smoke gate, scheduled drift scan, spec-coherence,
  specs-validation — `README.md:389`). Corrected to seven; the requirement now
  counts from the directory instead of a hard-coded integer.
- **aiggp-02 Q5** gained "Where the pin lives": CA-less ≠ repo-controlled. The
  `coh-pol-02` authority boundary is not optional even when the CA is.
- **aiggp-08 Q12.2** census corrected to `declared=135, scanned=131,
  findings=59` (`docs/qa/2026-09-30-sprint1-mutation-proofs.md:21`).
- **aiggp-04** straggler "hybrid-CA enrollment model" → "CA-optional
  enrollment model".

## Owner decision this file exists to frame

ADR-001's host choice must be re-stated against the measured topology before
AIGGP-10 can proceed. Until it is, the terminal layout (`modules/policy/`,
`modules/devgate/`) has no confirmed destination repository, and the
"separately approved hosting operation" language is overtaken by the rename
that already occurred.