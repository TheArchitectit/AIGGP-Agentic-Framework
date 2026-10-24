# Spec: Fleet manager boundary

## ADDED Requirements

### Requirement: Product-tiers code lives only under the declared root
<!-- id: repo-002-01 -->
Product-tiers code SHALL live only under the top-level `fleet-manager/`
directory. Every file under that root SHALL be matched by a pattern declared in
`fleet-manager/manifest.json`. An unmatched file is a boundary violation, and so
is product-tiers code placed outside the root.

#### Scenario: an undeclared directory appears under the boundary

- **WHEN** a file under `fleet-manager/` matches no declared pattern
- **THEN** the boundary gate exits 1 and names the path
- **AND** the file is not silently accepted as part of the boundary

#### Scenario: product-tiers code is placed outside the boundary

- **WHEN** a changed path sits under a root listed in `forbidden_roots`
- **THEN** the boundary gate exits 1 and names the path

### Requirement: The boundary carries a manifest and a license notice
<!-- id: repo-002-02 -->
`fleet-manager/manifest.json` SHALL declare the boundary paths, the license, and
the roots that must not hold product-tiers code. The license SHALL be BSD
3-Clause with no separate grant: the root `LICENSE` applies (OD-001). The
boundary README SHALL state the license and the dependency rules in prose.

#### Scenario: the manifest claims a separate license grant

- **WHEN** the manifest declares a license other than BSD-3-Clause, or
  `separate_grant` true
- **THEN** the gate exits 2 and the boundary is not reported clean

#### Scenario: the manifest is missing or malformed

- **WHEN** `fleet-manager/manifest.json` cannot be read or parsed
- **THEN** the gate exits 2 rather than reporting a clean boundary

### Requirement: Open-core code does not import the boundary
<!-- id: repo-002-03 -->
No file outside `fleet-manager/` SHALL import, require, or load code from it. The
direction is one-way: boundary code MAY import open-core code; open-core code
SHALL NOT import boundary code. CI SHALL enforce this on every push.

#### Scenario: an open-core module imports boundary code

- **WHEN** a source file outside the boundary imports `fleet_manager` or names a
  `fleet-manager/` path
- **THEN** the gate exits 1, naming the file and line

#### Scenario: boundary code imports open-core code

- **WHEN** a file under `fleet-manager/` imports an open-core module
- **THEN** the gate does not object; that direction is allowed

### Requirement: The boundary gate fails closed
<!-- id: repo-002-04 -->
`scripts/check_boundary.py` SHALL exit 0 when the boundary agrees, 1 on a
violation, and 2 when its manifest or arguments are unusable. It SHALL run as a
required CI step, so a violation fails the repository's own gates rather than
depending on a reviewer noticing.

#### Scenario: the gate is run against a clean tree

- **WHEN** the manifest is valid, every boundary file is declared, and no
  open-core file references the boundary
- **THEN** the gate exits 0
