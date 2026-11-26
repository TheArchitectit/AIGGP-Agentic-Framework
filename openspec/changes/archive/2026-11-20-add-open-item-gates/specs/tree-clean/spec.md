# Tree Clean

## ADDED Requirements

### Requirement: Unclassified working-tree dirt fails the gate
<!-- id: tc-01 -->
A repository whose working tree contains entries that match neither a declared generated
pattern nor a committed change MUST fail the gate, naming the offending paths. Dirt that
is merely untidy and dirt that hides real work MUST NOT be treated identically — the gate
classifies before it judges.

#### Scenario: untracked source file
- **WHEN** a repository has an untracked `.py` file that matches no generated pattern
- **THEN** the gate fails naming that path, because uncommitted work is at risk

#### Scenario: thousands of dirty files
- **WHEN** a repository reports 14,373 modified entries of which all but three match generated patterns
- **THEN** the gate names the three real entries and reports the generated count separately rather than failing on the total

### Requirement: Generated churn is reported, not failed
<!-- id: tc-02 -->
Entries matching declared generated patterns (build output, caches, dependency trees) MUST
be counted and reported but MUST NOT fail the gate. The remedy for generated churn is a
`.gitignore` or `core.fileMode` decision, not a commit, and conflating the two makes the
gate unusable on real repositories.

#### Scenario: cache noise only
- **WHEN** the only dirty entries are `__pycache__` artifacts and `*.pyc` files
- **THEN** the gate passes and reports the generated count

### Requirement: File-mode-only churn is its own class
<!-- id: tc-03 -->
Entries that differ only by file mode MUST be detected and reported separately, because
the correct remedy is `core.fileMode=false` or a `.gitattributes` declaration rather than
deletion or commit.

#### Scenario: mode flip after a copy
- **WHEN** a backup operation flips 219 files from `100644` to `100755`
- **THEN** the gate reports 219 file-mode-only entries with that specific remedy named

### Requirement: No repositories scanned is never a pass
<!-- id: tc-04 -->
When no repositories are discovered, the gate MUST exit with the nothing-scanned code.

#### Scenario: empty root
- **WHEN** the configured root contains no repositories
- **THEN** the gate refuses with a vacuous-pass message
