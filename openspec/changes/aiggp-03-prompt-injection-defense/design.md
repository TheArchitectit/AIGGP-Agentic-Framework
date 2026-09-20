## Design principles

- Content is data until the kernel of authority says otherwise: instructions arrive only through authorized channels with provenance.
- Fail closed on ambiguity at destructive boundaries; fail visible everywhere.
- Every mediation decision is evidence: who/what/when, classifier version, policy digest.
- Detection is versioned claims, not vibes: detector version plus corpus version plus pass rate is the public claim.

## Locked decisions

- Mediation points: command execution, edit application, git operations, external action calls - the same boundaries Guardrails already mediates.
- Classification tiers: trusted instruction (authenticated user channel with provenance), content (data, inert by default), suspected injection (mediated per policy).
- Default posture: suspected injection at a destructive boundary blocks and escalates; at a read-only boundary it sanitizes and discloses.
- Classifier identity: model/heuristic identity and version are part of every envelope; a silent classifier swap invalidates prior conformance claims.
- Corpus governance: the adversarial corpus is public, versioned, and contribution-open; each module release names the corpus version it passed.

## Major components

1. Boundary interceptors in the MCP/REST surfaces.
2. Classifier pipeline (heuristics plus model-backed classification, versioned).
3. Mediation engine applying bundle policy to classification.
4. Disclosure renderer: what the user/agent is told when mediation fires.
5. Evidence emitter (AIGGP-00 envelopes).
6. Adversarial corpus runner with per-category reporting.

## Trust boundaries

- Classifier output is advisory to the mediation engine; policy (bundle) decides.
- Corpus fixtures are attack input; the runner treats them as hostile even in test harnesses.
- No self-authorization: content can never elevate its own classification.
