# drift-workflow-setup-instructions Specification

## Purpose

Show consumers the required ignored tool location and immutable pin for the
drift workflow.

## Requirements

### Requirement: Drift setup records the required location and pin
<!-- id: drift-setup-note-01 -->

The drift workflow SHALL document the ignored `.devgate/` checkout path
and require a reviewed full commit for `DEVGATE_SHA`.

#### Scenario: A consumer configures a copied drift workflow

- **WHEN** the consumer reads the workflow setup comment
- **THEN** it identifies the ignore entry and reviewed commit requirement
- **AND** the exact PR range passes the existing data-corruption gate
