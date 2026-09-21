## ADDED Requirements

### Requirement: canonical subject identity

Every verdict input SHALL be identified by a typed subject structure with a content digest. Names, paths, URLs, branch names, and tags SHALL NOT be accepted as identity without a digest.

#### Scenario: branch-named subject rejected

Given a verdict request identifying its subject only as "main", when the kernel validates it, then validation SHALL fail with an identity error.

#### Scenario: same content, same identity

Given two references to the same revision by different names, when both are resolved, then they SHALL produce the same subject digest.

### Requirement: content-addressed bundle identity

A policy bundle SHALL carry a digest covering its manifest, schema version, policy and module references, parameters, waiver rules, evidence categories, and rendering metadata. A bundle containing a moving reference SHALL be invalid.

#### Scenario: latest tag inside bundle

Given a bundle referencing a module by tag "latest", when the bundle is built, then the build SHALL fail.

#### Scenario: parameter change is a new version

Given two bundles differing only in one parameter value, when digests are computed, then they SHALL differ and both SHALL be traceable to their source.

### Requirement: deterministic bundle build

Building a bundle twice from the same structured source SHALL produce the identical digest.

#### Scenario: rebuild on a second machine

Given the same source on two machines, when both build, then the digests SHALL be equal.
