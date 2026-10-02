> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures

- Fixture A: seeded broken repo on both forges - identical findings.
- Fixture B: tag-pinned runner image - standard check fails.
- Fixture C: forged webhook without valid secret - rejected.
- Fixture D: backup restore drill - instance recovered, gates runnable.
- Fixture E: inline gate logic in a GitLab template - rejected in review.

## Release acceptance criteria

- All fixtures pass; parity drill green in CI on a pinned corpus version; backup drill evidenced; adapter emits valid envelopes from real lab repos.

## Open questions requiring owner decisions

### Q11.1 — Instance ownership + upgrade policy (who patches GitLab, on what cadence)

**ANSWERED 2026-10-01 (owner).**

**Bundle-declared per-instance.** The product must let any deployer plug
in their own GitLab instance (self-hosted or hosted) with their own
ownership + cadence — it is not a question about the lab instance, it is
a product-surface question. The lab instance is Sprint-0's dev reference
(the fog the handoff warns about), not the product's only instance.

Concrete shape:
- `policy-bundles/[bundle].toml` declares per forge instance: owner
  identity (CA-optional per SA-9, AIGGP-RETIREMENT-2026-10-02.md — identity is a
  key-hash allowlist entry when no CA runs, a CA-signed identity when one
  does), security-patch cadence (e.g. N-days-after-CVE), upgrade cadence
  (e.g. quarterly), and the adapter-supported version.
- No hardcoded ownership or policy in the code — a deployment whose
  GitLab runs on a managed vendor cadence plugs in that cadence; an
  enterprise self-hosting plugs in theirs. Same tier-scaled shape as
  aiggp-05 Q9.2's ephemeral posture.
- The forge matrix is multi-forge from day one: **GitHub (with
  self-hosted runners — what DevGate fleet runs today) is a first-class
  adapter alongside GitLab.** aiggp-07's scope is the GitLab adapter
  only; it does not rewrite or regress the existing GitHub surface.

Rejected: hardcoded policy (B) — different users have different
realities. No policy at all (C) — leaves the handoff's fog permanent
in the contract.

### Q11.2 — External GitLab.com support scope

**ANSWERED 2026-10-01 (owner).**

**Self-hosted vs hosted is a downstream consequence of which CI platform
the deployment uses — not a scope/sequencing question.** The adapter
must serve both shapes; which one a deployment runs is their call.

**Two axes named "self-hosted" (terminology note, 2026-10-01).** The
phrase is overloaded and the record above uses both senses:
- **Self-hosted runners** = *runner infrastructure* (the machines that
  execute CI jobs). GitHub Actions with self-hosted runners is what the
  DevGate fleet runs today — that is a runner-configuration fact about a
  GitHub deployment, and it is the first-class GitHub surface this
  package must not regress.
- **Self-hosted forge instance** = *the forge server itself* (a GitLab
  instance someone operates, vs GitLab.com). That is an instance-fact
  about the GitLab side.
They vary independently: a deployment can be GitHub + self-hosted
runners (today's fleet), GitLab self-hosted + its own runners, or
GitLab.com with any runner pool. Q11.1's per-instance bundle declaration
carries which is which; nothing in the adapter assumes the two axes
travel together.

Therefore there is no "lab-first vs .com-first" question to answer —
that framing is wrong. The right invariant:
- The GitLab adapter's contract covers **both self-hosted GitLab and
  GitLab.com** as surfaces of one adapter, the same way the existing
  GitHub adapter covers GitHub regardless of its runner pool.
- Which surface a deployment uses is declared in the bundle per
  instance (Q11.1's ownership + cadence model already carries it).
- Sprint-0 lifts the lab-instance fog so the adapter has one documented
  dev reference; the parity drill (handoff) runs against whichever
  surfaces the adapter claims. If the adapter claims both self-hosted
  and .com, both surfaces are in the drill.
- Turning on .com as a surface is still an org-scale exposure decision
  (third-party ingress for evidence) under the aiggp-00 Q1
  org-wide-blast-radius invariant — opt-in, never default-on, per
  deployment. Same shape as aiggp-04 Q7's hosted-classifier opt-in.

The proposal's "lab-first, external config as beta" is reinterpreted
as: the *first documented reference* is the lab instance (fog lifting
order), not a claim that .com is second-class. External .com is
first-class in the adapter contract the moment the adapter claims it.

## Handoff

Do not skip Sprint 0: the instance is undocumented and everything else inherits that fog. Build the parity drill before declaring any template done - the drill is the definition of done for this spec.
