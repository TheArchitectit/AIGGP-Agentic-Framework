## Required conformance fixtures

- Fixture A: forged-credential runner - rejected, evidence refused.
- Fixture B: expired enrollment - heartbeat refused, unenrolled transition.
- Fixture C: under-classed scheduling - refused.
- Fixture D: stale signed state - execution refused.
- Fixture E: silent runner - suspect then drained, workloads migrated.
- Fixture F: bad bundle rollout - canary detects, rollback evidenced both directions.
- Fixture G: cross-class secret request - denied and logged.

## Release acceptance criteria

- All fixtures pass; drills run in CI; ai01 and the fleet runners migrate onto the protocol; Mission Control renders runner state from verified ledger evidence only.

## Open questions requiring owner decisions

### Q13.1 — Enrollment credential mechanism

**ANSWERED 2026-10-01 (owner).**

**Hybrid (option C): certificates at enrollment + workload-identity for
session renewal.**

Concrete shape:
- **Enrollment** is a one-time proof: the hub (or the org CA under it)
  issues a short-lived enrollment certificate to the runner. The cert's
  public half is what the runner presents on first contact. The
  enrollment is a cert-lifetime + revocation story, matching the
  hostile-runner drill's "forged runner is rejected and its evidence
  refused" demo — a forged runner has no valid cert to present.
- **Session renewal** is workload-identity federation per host (each
  host's own identity provider re-asserts identity on each subsequent
  session) — no long-lived cert sits on a runner's filesystem. Replay
  of a stolen cert is bounded by cert-lifetime; replay of a session is
  bounded by the workload-identity provider's freshness.
- Trust root is the aiggp-00 Q1 hybrid-CA model (same Ed25519 org CA
  that signs install public keys also signs enrollment certs — one CA,
  one blast-radius rule).

Rejected: platform-issued certificates alone (A) — a long-lived cert on
a runner's filesystem is a theft-replay target the hostile-runner drill
would not want to demo as "the" defense. Workload-identity alone (B) —
per-host identity-provider dependency is a real ops surface across a
diverse fleet (personal laptop runners, self-hosted VMs, bare-metal lab
machines); not every host has a federation path ready at enrollment
time, and a hybrid lets the cert cover the enrollment gap.

### Q13.2 — Existing `ai01` monitor on protocol migration

**ANSWERED 2026-10-01 (owner).**

**Retire immediately on protocol migration (option B), with HA
monitoring as an optional deployment feature (not a redundant
transition-window view).**

The redundant-transition-window answer (A) was rejected on the same
principle the whole walk-through has been applying: a live monitoring
view is org-scale visibility, and "run two monitors so one can be
wrong" is a stopgap that can quietly become permanent (option C's
problem). Instead:

- **The new aiggp-09 protocol replaces ai01 at cutover** — one
  protocol, one truth.
- **HA monitoring is optional per deployment** (option-supplied, like
  aiggp-05 Q9.2's tier-scaled ephemeral posture or aiggp-04 Q8's
  optional alert-channel routing): a deployment that wants redundant
  monitoring can run multiple instances of the new protocol's
  monitor, not the old one. If the new protocol has a gap, that gap is
  fixed in the new protocol; the retired ai01 is not the safety net.
- Closure criterion for the hostile-runner drill is the new protocol's
  own demo: forged runner rejected, evidence refused, Mission Control
  shows only ledger-verified state. If the drill finds a gap, it closes
  in the new protocol before cutover, not by keeping ai01 running past
  the migration.

In short: HA is the right answer to redundancy; a legacy dual-view is
not.

## Handoff

Start from the salvaged fleet machinery and the ai01 monitor's real operational lessons. The hostile-runner drill is the demo: show a forged runner being rejected and its evidence refused, then show Mission Control displaying only what the ledger verifies.
