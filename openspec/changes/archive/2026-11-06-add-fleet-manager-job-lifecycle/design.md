# Design: Fleet Manager one-job lifecycle

## The rule is about the replacement, not about the destroy

RUN-002 is easy to misread as "destroy the container before starting the next
one". The text is sharper: a replacement SHALL NOT **join capacity** until the
previous instance's cleanup is proven or its resources are quarantined. Destroy
is an operation; admission is the decision the rule governs. So the check lives
where capacity is counted — the warm pool — and the proof is a value that must
exist before admission is allowed.

## One job, and the states a used instance cannot return to

A closed machine, because a lifecycle with an open set of states is a
lifecycle that can be "restarted" by accident:

```
PREPULLED --admit--> ASSIGNED --start--> RUNNING --finish--> terminal
   |                    |                                        |
   |                    +--refuse--> REFUSED --destroy----------+
   |                                                             |
   +--destroy (never took a job)---------------------------------+
                                                                 |
                                                                 v
                                                              DESTROYED
                                                                 |
                        +--proof-------------------------------+--proof fails--> QUARANTINED
                        v
                  PROVEN_CLEAN

terminal = COMPLETED | TIMED_OUT | CANCELLED | DISCONNECTED (uncertain)
```

`USED` from 4.1 is the union of the terminal states; `WARM_STATES` stays exactly
`{PREPULLED, STOPPED_CLEAN}` and a `PROVEN_CLEAN` instance is not warm either —
its resources are disposed of, not returned to the pool. The important edge is
the one arrow that does not exist: a terminal state never returns to a warm one.
The machine has no transition for it, and the pool refuses to count it.

## Cleanup evidence carries five things, and four of them are required

RUN-002 lists them, so the value holds exactly them:

| field | required | why |
| --- | --- | --- |
| `instance_id` | yes | which instance was cleaned — RUN-002's "instance identity" |
| `image_digest` | yes | which image — so a proof cannot be transplanted onto another generation |
| `job_id` | no | "job identity **if known**" — an uncertain disconnect may never learn it |
| `volume_disposal` | yes | result, not a claim: a typed outcome, not a bool |
| `network_disposal` | yes | same |
| `started_at` / `finished_at` | yes | RUN-002's "timestamps" — a proof with no interval is not evidence of a cleanup |

`job_id` is the one optional field because the program says so, and because
requiring it would make an uncertain disconnect impossible to prove clean. A
proof missing any of the other five is refused at construction, so a caller
cannot "forget" a field into existence.

The disposal results are closed values — `DISPOSED`, `ABSENT`, `FAILED` — and a
proof is admissible only if neither result is `FAILED`. `ABSENT` is not a
weaker `DISPOSED`: an instance that never created a volume or a network is
cleaner than one that created and removed them, and saying so is the difference.

## Quarantine is a state with a reason, not an absence

An instance whose cleanup proof fails is not "gone" and not "warm": it is
`QUARANTINED`, and the value that says so names the instance, the failure kind,
and when. Quarantined stock is not capacity — `WARM_STATES` already excludes it
— but the reason is retained, because RUN-002's alternative to a proof is
"resources are quarantined", and a quarantine nobody can inspect is a deletion
with extra steps.

## Resource limits are required, bounded, and in the command

The box asks for resource limits next to the lifecycle, and the reason is the
same as RUN-001's: one job per instance is also one job's worth of a host. An
ephemeral instance therefore carries memory, cpu and pids limits, each required
and each bounded above; a missing or unbounded limit is a refusal at
construction rather than a permissive default, because the permissive default is
what an unattended runner leaks into a shared host.

The limits are rendered into the command (`--memory`, `--cpus`, `--pids-limit`)
so the evidence of the limit is the same value that is executed, and so a
mutation of the rendering is caught by the same suite that pins the command.

## Failures land in the eight kinds

No ninth kind. A lifecycle step that fails raises one of Sec. 5.2's typed
errors, and the mapping is fixed:

| failure | kind |
| --- | --- |
| a job is offered to an instance that already took one | `POLICY_DENIAL` |
| an instance is admitted while an unproven predecessor is unaccounted for | `POLICY_DENIAL` |
| a cleanup proof is incomplete or reports `FAILED` disposal | `CLEANUP_FAILURE` |
| the pool is at its ceiling and nothing is proven clean | `CAPACITY_EXHAUSTION` |
| a lifecycle step meets a state it has no transition for | `UNKNOWN_STATE` |

Anything else a lifecycle call raises is classified by `classify()` into
`RUNTIME_FAILURE` naming the exception type only.

## What is left to 4.3

Producing the evidence from a real host: the volume and network disposal results
have to come from the runtime, the timestamps from a clock the host controls,
and the receipt from the agent's claim about the operation the manager issued.
This change fixes the shape they must have and refuses a shape they do not.
