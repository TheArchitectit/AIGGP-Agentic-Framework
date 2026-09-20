## Summary

Add semantic content filtering to the Guardrails runtime module: policy-declared categories, versioned classifiers, per-category mediation actions, declared failure modes, and envelope evidence for every decision, with conformance proving both detection and acceptable false-positive behavior per category.

## Problem

Agents move content at machine speed. Without semantic filtering, a deployment cannot enforce "never send customer data to an external endpoint" or "do not commit secrets" as runtime policy rather than hope. Guardrails main already has content-classification surfaces; what is missing is the evidence contract: decisions that name their classifier and version, categories with declared failure modes, and conformance that proves the filter can fail in both directions and knows it.

## Desired outcomes

- Deployments declare content categories and per-category actions (allow, redact, block, escalate) in the policy bundle.
- Every filtering decision records classifier identity, model version, category, confidence handling, and action in an AIGGP envelope.
- Each category declares its failure modes: what a false negative costs, what a false positive costs, and the tuned balance.
- Classifier upgrades are bundle changes: new version, new digest, re-run conformance before the old claims carry over.
- Redaction is lossless-auditable: what was removed is recorded in evidence (hashed), never silently dropped.

## Product boundary

Semantic filtering classifies content against declared categories; it does not detect hostile instructions (AIGGP-03) and does not contain execution (AIGGP-05). It is advisory-shaped machinery with enforcement wiring: the kernel owns verdict algebra; the filter supplies categorized findings.

## Users and calling systems

- Guardrails runtime mediation surfaces (command, edit, git, action).
- Deployments with regulatory or policy obligations mapping categories to their own controls (non-certifying - see the proposed compliance-mapping spec).
- Operators reviewing filtering evidence in the ledger.

## Success measures

- Per-category detection and false-positive rates measured on versioned corpora and published with each release.
- 100 percent of decisions carry classifier identity and version in verifiable envelopes.
- A classifier version bump without conformance re-run is automatically flagged stale.
- Zero silent content drops: every redaction/block has a hashed evidence trail.

## Risks

- Category inflation: dozens of vague categories nobody can tune. Control: ship a minimal core set; new categories require corpora and failure-mode declarations.
- Model drift changes behavior silently. Control: version pinning in the bundle; drift detection via scheduled corpus re-runs.
- False positives train users to click through. Control: false-positive budgets per category are release gates, and escalations are measured.
