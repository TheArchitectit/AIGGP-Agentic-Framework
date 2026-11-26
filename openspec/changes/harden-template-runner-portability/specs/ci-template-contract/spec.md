# CI Template Contract

## ADDED Requirements

### Requirement: A fetched scanner is installed where the job can write
<!-- id: ci-tpl-01 -->
The shipped secret-validation template MUST install the checksum-verified
scanner into a directory the job is permitted to write and MUST make it visible
to later steps with `$GITHUB_PATH`. It MUST NOT require root privileges or
assume `/usr/local/bin` is writable, because a rootless self-hosted runner is a
supported placement and a step that dies on permissions has protected nothing.

#### Scenario: rootless self-hosted runner
- **WHEN** the template's scanner step runs on a runner whose user cannot write `/usr/local/bin`
- **THEN** the step succeeds, the binary is installed under `$RUNNER_TEMP`, and the version step that follows finds it on PATH

#### Scenario: the pin is still enforced
- **WHEN** the fetched artifact does not match the pinned checksum
- **THEN** the step fails before installation and no binary is placed on PATH, whatever directory installation would have used

### Requirement: A declared runner placement is consumed as a placement
<!-- id: ci-tpl-02 -->
The drift-scan template MUST emit the resolved placement as a JSON array and
consume it with `fromJSON`. A YAML flow sequence reported by `detect-host-ci.py`
MUST be split into its labels, and a `${{ ... }}` expression MUST be skipped,
because a job requesting one queues forever. With no usable value the template
MUST fall back to `ubuntu-latest`. Distinct declared values are alternatives and
MUST NOT be merged into one placement.

#### Scenario: flow sequence
- **WHEN** the host declares `runs-on: [self-hosted, devgate-rtp]`
- **THEN** the scan job requests the labels `self-hosted` and `devgate-rtp`, not the literal string `"[self-hosted, devgate-rtp]"`

#### Scenario: expression-shaped declaration
- **WHEN** the only extracted `runs-on:` value is a `${{ ... }}` expression
- **THEN** the template resolves to `ubuntu-latest` rather than requesting a label that no runner carries

#### Scenario: several alternatives
- **WHEN** the host declares more than one plain `runs-on:` value
- **THEN** the first usable value is used whole and labels from different values are not combined into one placement

#### Scenario: no declaration
- **WHEN** `detect-host-ci.py` reports no labels
- **THEN** the template resolves to `ubuntu-latest`
