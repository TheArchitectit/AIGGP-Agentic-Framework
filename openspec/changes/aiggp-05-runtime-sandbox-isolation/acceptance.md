## Required conformance fixtures

- Fixture A: filesystem escape attempt - fails, recorded.
- Fixture B: network escape under default-deny - fails, recorded.
- Fixture C: process-namespace escape attempt - fails, recorded.
- Fixture D: undeclared secret access - fails, recorded.
- Fixture E: host missing mechanism - workload refused with diagnostic.
- Fixture F: induced runtime fault - ERROR verdict, no green.

## Release acceptance criteria

- All fixtures pass on reference hosts and in CI; envelopes carry level and runtime identity; certification report published per release.

## Open questions requiring owner decisions

- Reference container backend (rootless podman is the fleet runner standard - confirm it is the reference here).
- Whether ephemeral level requires dedicated hosts at launch or can share contained infrastructure.

## Handoff

Build the escape suite alongside the first enforcer, not after: the fixtures define what the levels mean. Publish the capability matrix early - it is the contract every other spec (and every third-party runner) builds against.
