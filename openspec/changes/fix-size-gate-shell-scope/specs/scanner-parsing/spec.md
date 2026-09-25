## MODIFIED Requirements

### Requirement: Test file sizing
<!-- id: gate-size-01 -->
The file-size gate SHALL discover test files in `tests/` and `test/`
directories and SHALL apply TEST_HARD to files matching test naming
(`test_*.py`, `test_*.sh`, `*_test.py`, `_test.go`, `*.test.*`, `*.spec.*`,
`*_test.rs`).

#### Scenario: pytest file over source limit
- **WHEN** `tests/test_big.py` has 550 lines
- **THEN** it is evaluated against TEST_HARD (600), not SRC_HARD (500)

#### Scenario: shell test file over source limit
- **WHEN** `tests/test_big.sh` has 550 lines
- **THEN** it is evaluated against TEST_HARD (600), not SRC_HARD (500)

## ADDED Requirements

### Requirement: Shell script sizing
<!-- id: gate-size-02 -->
The file-size gate SHALL apply the source limits (SRC_SOFT, SRC_HARD) to shell
scripts (`.sh`) in every directory it walks, and the directories it walks SHALL
include the ones this repository's shipped scripts live in, so that no language
is unsized by omission from a hand-maintained list.

#### Scenario: shell script over the hard limit
- **WHEN** `scripts/giant.sh` has SRC_HARD + 1 lines
- **THEN** it is reported as a blocking violation evaluated at SRC_HARD

#### Scenario: the walk enters the script directory
- **WHEN** a `scripts/` directory exists under the project root
- **THEN** `scripts` is in the gate's source scope and its `.sh` files are
  sized
