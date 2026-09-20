## Requirement: no vacuous gates

Every blocking gate SHALL enumerate its target set and SHALL return EMPTY (never PASS) when the set is empty, and ERROR (never PASS) when its parser or scanner fails.

### Scenario: scanner finds nothing

Given a diff with no files matching a scanner's patterns, when the gate runs, then it SHALL report EMPTY and the aggregate SHALL NOT be green.

### Scenario: parser crash

Given a valid input the parser cannot handle (for example the Godot scene-inventory failure), when the gate runs, then it SHALL report ERROR with the parser diagnostic and SHALL NOT exit green.

## Requirement: correct audit subject

Every gate SHALL audit the consuming project's tree, revision, and history. A gate SHALL NOT audit the DevGate submodule's tree or history in place of the project's.

### Scenario: deploy gate wrong tree

Given a consuming project with unaudited changes and a clean DevGate submodule, when the deploy gate runs, then it SHALL evaluate the project's changes and SHALL FAIL on them.

## Requirement: no dead configuration

Every rule referenced by gate configuration SHALL be loaded and executed, or the gate SHALL fail ERROR naming the dead rule. Extracted-rules corpora that nothing executes SHALL fail validation at gate startup.

### Scenario: nine dead semantic rules

Given the pre-fix configuration where 9 of 10 semantic rules are unreachable, when the gate starts, then startup validation SHALL FAIL and name each unreachable rule.
