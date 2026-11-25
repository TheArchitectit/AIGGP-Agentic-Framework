# Design

## Context

`docs/SUBMODULE_WIRING.md:10-16,122-124` blocks `.gitmodules` registration and says CI must clone `.devgate/` itself. `templates/gitlab-ci/drift-scan.gitlab-ci.yml:15-22` enables recursive submodule checkout, defaults commands to `${DEVGATE_DIR:-.devgate}`, and has no clone/bootstrap step. GitLab CI will not fetch a tooling submodule that the consumer is explicitly prohibited from registering.

## Goals / Non-Goals

**Goals:** Make each adopted mirror provision its own required in-tree checkout and fail before gate execution when the pin or checkout is invalid.

**Non-Goals:** Change GitHub workflow bootstrap, add a submodule, make a live GitLab instance mandatory, or silently use a moving branch.

## Decisions

Use one shared GitLab bootstrap helper or an equivalent reviewed common setup block invoked before mirror scripts. Require the consumer to set a full 40-character `DEVGATE_SHA`; clone into `.devgate/`, detach to that SHA, verify `HEAD` and required scripts, and only then invoke gates. Keep protected fetch credentials in the GitLab secret store and keep `.devgate/` ignored. Test the include scripts in a clean fixture using a local bare fake-approved-source repository and its full SHA, with no `.gitmodules`, invalid pin, and partial checkout; do not use network or require a running GitLab server. DG-08 owns GitHub workflow bootstrap, while DG-11 owns GitLab mirror provisioning. Both enforce the same path/SHA/preflight policy but retain forge-specific variables and job syntax. DG-10 owns image provenance and digest verification; this package owns checkout bootstrapping only. Coordinate edits to `templates/gitlab-ci/*.yml` with DG-10 so those distinct responsibilities remain reviewable. A floating ref is easier to rotate but weakens reproducibility; retaining recursive submodule setup cannot work under the documented consumer contract.

## Risks / Trade-offs

[Network or clone failure] → fail before any gate output is marked passing; [consumer pin is stale] → expose it as a reviewed variable in the consumer repository; [private AIGGP source requires credentials] → use narrowly scoped protected GitLab variables and never embed them in templates or logs.
