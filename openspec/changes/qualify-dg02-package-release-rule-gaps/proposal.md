# Qualify package, release and rule evidence gaps

## Why

DG-02 batch 008 reviewed package resolution, publish safety, release targeting and rule coverage. A synthetic package with a nonexistent import and a declared digest was accepted by `package.resolve`. A requirement-bearing JSON file classified as informative was also accepted and excluded from the resolved normative inventory. The existing package requirements call for verified frozen import closure and rejection of requirements hidden as informative.

A simulated first failure in the PyPI upload branch caused a build and second upload attempt. The publish requirement calls for aborting on a failed upload. The registry hygiene test also confirms that short overlay `fix_commit` values are not resolved, although the existing requirement calls for verifying hexadecimal commits in the entry owner's history. Other scenarios in this batch lack complete behavioral and historical evidence.

## What Changes

- Implement and test the existing package import and normative-classification contracts, including malformed and adversarial synthetic packages.
- Reconcile upload failure handling with the existing publish contract and qualify actual deployed behavior with isolated fixtures. Define how ambiguous or partial registry outcomes are reported without claiming an unobservable guarantee.
- Verify registry commit identities against the owning repository and qualify release targeting and rule coverage with behavioral controls.
- Seal independently validated, requirement-specific evidence before any DG-02 lifecycle transition.

## Impact

Package resolution, release scripts, registry and rule hygiene tests, and evidence reconciliation. The change proposes work under existing requirements and makes no implementation or deployment claim.
