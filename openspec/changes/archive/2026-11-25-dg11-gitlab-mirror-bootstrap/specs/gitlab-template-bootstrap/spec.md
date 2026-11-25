# Spec Delta

## Purpose

Defines how GitLab CI consumers provision DevGate for mirrored gates without tracking tooling as a submodule.

## ADDED Requirements

### Requirement: GitLab mirror provisions pinned DevGate
<!-- id: glf-template-bootstrap-01 -->
A GitLab CI template that invokes DevGate SHALL provision and verify an ignored `.devgate/` checkout at a consumer-declared immutable commit SHA before invoking any gate. Each mirror SHALL declare the exact scripts, rule files, and registries its gate invokes, and bootstrap SHALL verify those files exist in the pinned checkout.

#### Scenario: clean consumer with no submodule
- **WHEN** a consumer runs a copied or project-included GitLab CI mirror with no `.gitmodules` entry
- **THEN** the job checks out DevGate at the declared full SHA under `.devgate/`, verifies required scripts, and runs gates only after preflight succeeds

#### Scenario: invalid or incomplete checkout
- **WHEN** the SHA is not a full commit or required scripts are absent
- **THEN** preflight fails before any gate is reported as passing

#### Scenario: required rule file is missing
- **WHEN** a mirror's pinned checkout lacks a rule file or registry it explicitly requires
- **THEN** preflight fails before the mirror gate runs or reports a green result

#### Scenario: mirror points at canonical rule files
- **WHEN** the drift or compliance mirror invokes `regression_check.py`
- **THEN** its `--rules` input resolves the pinned `.guardrails/prevention-rules/pattern-rules.json` and `semantic-rules.json` files rather than a nonexistent `rules.json`

#### Scenario: hermetic template validation
- **WHEN** template mirror tests run without a live GitLab service
- **THEN** they validate the bootstrap script and gate command ordering using a clean fixture repository without declaring live GitLab adoption
