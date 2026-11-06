# Design: Fleet Manager agent operations

## The catalogue is the boundary

`OperationKind` is eight values — `ensure_image`, `create_runner`, `mark_drain`,
`destroy_runner`, `cancel_or_timeout`, `observe_runner`, `prove_cleanup`,
`rollback_adapter` — and `_PARAMETERS` is a closed table mapping each kind to
exactly the parameter names it accepts. A parameter that is not in the table
does not exist for that kind. This is the structural half of "no arbitrary
command endpoint": the type cannot hold what the table does not name.

The other half is `_SHELL_SHAPED`: a frozen set of names (`command`, `cmd`,
`argv`, `args`, `shell`, `script`, `exec`, `entrypoint`, `env`, `environment`,
`stdin`, `sh`, `bash`, `commands`, `stdout`) refused wherever they appear. The
check runs by name, before the value is read, so a future table edit that adds
`("command", ...)` is refused even though the table named it. Belt and braces
because the two halves fail differently: the table stops unlisted parameters,
the name set stops a listed one that would turn the operation into a shell.

## Values: closed forms, sorted, and no secret is echoed

`Operation.parameters` is a tuple of `(name, value)` pairs, validated and then
stored sorted, so two equal operations are equal values and a retry can be
compared by equality. Values are strings, capped, and checked against the
package's one definition of "looks like a credential" (`audit._SECRET_SHAPED`),
reused rather than copied so there is a single such pattern. A value that
matches is refused and never echoed.

`registration_ref` is `ref:<name>`: an opaque reference, which is what SEC-001
means by "opaque secret references and metadata, never secret values". The
refusal for a pasted GitHub token therefore hits the secret-shape rule first and
says "references, never secrets"; a bare name with no `ref:` prefix hits the
reference rule. Both are tests.

## Capabilities: deny by default

`AgentCapabilities` holds what the agent declares it has installed —
`adapters` (a frozenset of `Runtime`), `operations` (a frozenset of
`OperationKind`), and `allow_cancel_or_timeout`. `permit()` refuses when there
is no adapter at all, when the kind is not declared, and — separately — when the
kind is `cancel_or_timeout` without the policy flag. The third check exists
because the adapter contract allows cancellation "only under explicit policy",
and a policy that defaults to yes is not a policy.

Observation is not exempt: `observe_runner` goes through the same allowlist.
"Deny by default" that has a free read path is not deny by default.

## A receipt is evidence; the contract receipt is authority

`AgentReceipt` claims an outcome for one `operation_key`. `OperationLedger`
holds what was issued and what was receipted:

- `issue()` refuses an operation `permit()` refuses, and refuses a key that was
  already issued for *different* work. Issuing the same key with the same
  operation is a retry and returns what was issued. Widening what a key covers
  is how a retry becomes a second mutation, and the 2.2 idempotency ledger
  already earned that lesson.
- `record()` refuses an unissued key, a receipt from another host, a completion
  without evidence, and a second receipt that differs. The identical receipt
  twice is idempotent.
- read-only kinds (`observe_runner`, `prove_cleanup`) produce no receipt and no
  contract receipt.

`authoritative_receipt()` then builds the contract-v1 `operation_receipt` from
the recorded claim via `build_receipt`, which validates what it built. The
mapping is one dict, `_CONTRACT_OPERATION`: `ensure_image`/`rollback_adapter` →
`apply`, `create_runner` → `assign`, `mark_drain` → `drain`,
`destroy_runner`/`cancel_or_timeout` → `release`. Read-only kinds are absent
from that dict on purpose.

Two tests keep the mapping honest in opposite directions: one walks every
mutating kind and asserts the built document's `operation` field, and one reads
`contracts/v1/operation-receipt.schema.json` and asserts every mapped value is
in the contract's own enumeration (and that a read-only kind is not). Reading
the schema is the point: the contract is the authority for its own vocabulary.

## runner-enroll.sh: a declared migration, not a silent drop

The existing `scripts/runner-enroll.sh` talks to the monitor hub and takes
`--runner-name`, `--repo`, `--labels`, `--host-alias`, `--interval`, `--revoke`.
Those inputs are not discarded quietly. `RUNNER_ENROLL_MIGRATION` maps each to
where the duty went — a pool's declared repositories and labels in desired
state, `create_runner.runner_name`, the agent's poll, `AgentChannel.revoke` —
and a skip-guarded test parses the script's own documented option lines and
fails if the set ever differs from the table's keys. Skip-guarded because the
extraction rehearsal does not copy `scripts/`, so a missing script is a skip and
a changed one is a failure.

## What is deliberately not here

No executor and no transport. No adapter implementations. No persistence: the
ledger is memory, like `AgentChannel`. No signature on the receipt: authenticity
comes from the channel, which is why a receipt is keyed to issued work instead
of self-certified. No decision on the Ed25519 provider — still an open security
sign-off, not a default.
