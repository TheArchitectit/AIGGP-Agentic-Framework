# Spec: Fleet Manager agent operations

## ADDED Requirements

### Requirement: An operation is a typed instruction and cannot carry a command
<!-- id: fleet-005-01 -->
Every operation SHALL be one of a closed catalogue of adapter operations. A
parameter name that names a command, an argv, a script, a shell, or an
environment SHALL be refused wherever it appears, before any value is read. An
operation SHALL carry no field in which a command could be placed.

An operation SHALL also declare the kinds of subject it acts on, and an
operation whose subject is not one of them SHALL be refused.

#### Scenario: a shell-shaped parameter name is offered

- **WHEN** an operation is built with a parameter named `command`, `argv`,
  `script`, `shell`, `exec`, `entrypoint`, or an environment
- **THEN** it is refused by name, before the value is looked at, and the value
  does not appear in the refusal
- **AND** the refusal SHALL say that host agents expose no remote shell
- **AND** the module that holds the catalogue SHALL import no way to execute a
  process

#### Scenario: a parameter that is not of this kind

- **WHEN** an operation carries a parameter its kind does not declare
- **THEN** it is refused, naming the parameter and the kind
- **AND** each kind SHALL declare a closed set of required and optional
  parameters

#### Scenario: a required parameter is missing

- **WHEN** an operation of a kind with required parameters is built without one
- **THEN** it is refused, naming the missing parameter

### Requirement: An agent may only be given work it declared
<!-- id: fleet-005-02 -->
An agent SHALL declare its capabilities — the runtime adapters installed and the
operation kinds it may perform — and an operation SHALL be refused unless it is
in that declaration. The default SHALL be deny: declaring nothing permits
nothing.

Cancellation or timeout SHALL require an explicit policy grant in addition to
being declared; an agent that has the operation in its allowlist but not the
policy SHALL be refused.

#### Scenario: work the agent never declared

- **WHEN** an operation is permitted against capabilities that do not list its
  kind
- **THEN** it is refused as not in the agent's allowlist
- **AND** an agent with no runtime adapter installed SHALL be given no work
- **AND** observation SHALL be treated as an operation like any other rather than
  as a free action

#### Scenario: cancellation without the policy

- **WHEN** `cancel_or_timeout` is permitted against capabilities that declare it
  but do not grant the explicit policy
- **THEN** it is refused, naming the policy

### Requirement: Parameters and receipts carry references, never secrets
<!-- id: fleet-005-03 -->
A parameter value or receipt detail that matches a credential shape SHALL be
refused and SHALL NOT be echoed in the refusal. A registration parameter SHALL
be an opaque reference of the form `ref:<name>`, never the registration material
itself. Parameter values and receipt details SHALL be bounded in length.

#### Scenario: a token pasted into a parameter

- **WHEN** a parameter value or receipt detail matches a credential shape
- **THEN** it is refused without the value appearing in the message

#### Scenario: registration material instead of a reference

- **WHEN** the registration parameter is not an opaque `ref:<name>`
- **THEN** it is refused as not a reference

### Requirement: A receipt is evidence tied to issued work
<!-- id: fleet-005-04 -->
A receipt SHALL name exactly one operation key the manager issued and the host
that operation was issued to. A receipt for an unissued key, or from a different
host, SHALL be refused. A completion SHALL carry evidence naming a digest and a
location; a completion without evidence SHALL be refused.

One receipt SHALL stand per operation: recording a different receipt for an
operation that already has one SHALL be refused.

#### Scenario: a read-only operation has no receipt

- **WHEN** a read-only operation completes
- **THEN** no receipt is recorded for it
- **AND** a read-only operation SHALL have no receipt at all, because there is
  nothing to attest

#### Scenario: a receipt for work that was never issued

- **WHEN** a receipt names a key that was never issued
- **THEN** it is refused

#### Scenario: a completion with nothing to show

- **WHEN** a receipt claims a completion without an evidence digest
- **THEN** it is refused

#### Scenario: a second, different answer

- **WHEN** a receipt that differs from the recorded one arrives for the same key
- **THEN** it is refused and the recorded receipt stands
- **AND** recording the identical receipt again is idempotent, so the first answer
  is the answer

### Requirement: The authoritative receipt is built, not forwarded
<!-- id: fleet-005-05 -->
The document the evidence plane consumes SHALL be the contract-v1
`operation_receipt`, produced by the manager from an accepted agent receipt.
The manager SHALL NOT forward an agent receipt as the authoritative document.
Every mutating operation kind SHALL have a declared contract operation; a
read-only operation SHALL produce no contract receipt.

An enrollment script that predates this catalogue SHALL have a declared
migration.

#### Scenario: the mapping drifts from the contract

- **WHEN** a declared contract operation is no longer in the contract's
  enumeration
- **THEN** the test that reads the contract schema fails
- **AND** the mapping is declared in one place, and the declared values SHALL be
  members of the contract's own enumeration

#### Scenario: the enrollment script grows an option

- **WHEN** `scripts/runner-enroll.sh` documents an option the migration table
  does not cover
- **THEN** the compatibility test fails and names the uncovered option
- **AND** every option the script accepts SHALL be accounted for in one table
  that names where the duty went, and a test SHALL fail if the script grows an
  option the table does not cover

#### Scenario: an agent claim reaches the evidence plane

- **WHEN** the manager builds the authoritative receipt
- **THEN** it is a contract-v1 document whose operation is the declared mapping
  of the agent's kind, and the agent's own vocabulary does not appear in it
