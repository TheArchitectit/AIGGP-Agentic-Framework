# forge-parity Specification

## Purpose
Define how the hermetic GitHub and GitLab parity corpus exercises gate behavior across supported local fixture hosts.

## Requirements

### Requirement: Hermetic parity seed paths are portable
<!-- id: GLF-14 -->
The hermetic forge-parity drill SHALL materialize structured seed content
with valid absolute paths on supported Windows and POSIX hosts. Host-specific
path formatting SHALL NOT alter the pinned corpus data or expected gate
verdicts.

#### Scenario: Windows path is embedded in JSON seed content
- **WHEN** a Windows absolute fixture path is substituted into serialized
  JSON seed content
- **THEN** the JSON parses, the decoded path remains absolute, and the gate
  receives the expected fixture path

#### Scenario: POSIX fixture path contains a JSON-special character
- **WHEN** a legal POSIX fixture path containing a double quote is substituted
  into serialized JSON seed content
- **THEN** the JSON parses and the decoded path remains absolute and unchanged

#### Scenario: pinned corpus remains host-independent
- **WHEN** the five-case parity drill runs on Windows or POSIX
- **THEN** the corpus lock matches and each case produces its pinned exit
  result without a host-path usage error
