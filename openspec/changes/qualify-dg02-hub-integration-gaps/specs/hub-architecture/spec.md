## ADDED Requirements

### Requirement: Hub listener address validation
<!-- id: mon-local-02 -->

The hub SHALL validate each effective listener address before opening a socket. It SHALL accept loopback addresses and addresses within explicitly configured local network ranges. It SHALL reject wildcard, public, invalid, unresolved, and out-of-range addresses, including IPv4 and IPv6 forms. Names SHALL resolve entirely to permitted addresses before use. Failure SHALL stop startup with a non-zero result and a diagnostic.

#### Scenario: wildcard listener rejected
- **WHEN** the configured listener is a wildcard address
- **THEN** the hub fails before opening a listener and reports the rejected address

#### Scenario: configured local address accepted
- **WHEN** the listener is within an explicitly configured local network range
- **THEN** the hub may bind that address

#### Scenario: name resolves outside allowed ranges
- **WHEN** a listener name resolves to any address outside the permitted ranges or cannot be resolved
- **THEN** the hub fails before opening a listener
