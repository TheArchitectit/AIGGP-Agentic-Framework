## Requirement: parent-preserving import

The DevGate import SHALL retain the selected DevGate cutover commit as an ancestor of the unified migration commit. The import SHALL NOT squash DevGate history or represent it as a fresh file addition.

### Scenario: ancestry check

Given a fresh clone of the unified repository, when the verifier tests merge-base ancestry for the DevGate cutover commit and Agent Guardrails cutover commit against the migration commit, then both checks SHALL succeed.

## Requirement: archival ref coverage

Every branch tip and release tag declared in the approved preservation manifest SHALL remain reachable from a documented ref or immutable mirror bundle. The original audit branch tip SHALL be included even though its changes are reconciled by finding rather than branch merge.

### Scenario: forgotten audit branch

Given a preservation manifest naming the audit tip, when reachability verification runs and no unified ref or mirror object reaches it, then migration acceptance SHALL fail.

## Requirement: immutable tag mapping

The migration SHALL never force-move or reuse a predecessor tag. Colliding or ambiguous tags SHALL be namespaced with a machine-readable old-to-new mapping.

### Scenario: both repositories contain v1.1.0

Given identical tag names pointing to different objects, when tags are imported, then each SHALL receive a distinct predecessor namespace and the verifier SHALL resolve both to their expected objects.

## Requirement: blame-friendly moves

Mechanical path moves SHALL be separated from functional edits. The migration ledger SHALL identify the pure-move commits used to preserve reviewability and blame continuity.

### Scenario: behavior change hidden in move

Given a commit labeled as a pure module move, when normalized file contents before and after are compared, then any non-path content change SHALL fail the fixture.
