> **Status: imported draft — not a commitment.** The AIGGP program has not started; this package is imported reference material held for future acceptance. It does not modify, supersede, or bind the shipped DevGate specification ladder, and no code, traceability ID, or gate configuration is wired to its requirements. (Added 2026-09-20 per the spec-coherence drift audit; see the AIGGP-02 reconciliation.)

## Summary

Reconcile the 2026-09-13 audit branch against current DevGate main, close every known false-green and crash path with file-evidenced fixes, add a nonzero test floor and adversarial negative controls, and bring DevGate to the point where its green is trustworthy enough to become the AIGGP repository module.

## Problem

The September QA and gap analysis (34 findings) plus the Kit + Ryan audit found that DevGate's blocking gates can report success over missing or wrongly scoped work: vacuous scanner gates, a deploy gate auditing the DevGate submodule instead of the consuming project, path traversal reads, a broken container schema path, dead semantic-rule configuration (9 of 10 rules), shared-baseline contamination from consuming-repo allowlists, duplicated discovery rules, stale workflow pins, npm audit missing HIGH/CRITICAL runtime vulnerabilities, and a test runner that discovers zero tests and exits green. The audit branch with many fixes was never merged, so main still carries every failure. Sprint 3's verified review (248 tests passing at 7981431) improved honesty of individual gates but did not reconcile the branch.

## Desired outcomes

- Every finding from both audits is either closed with a tested fix or explicitly accepted with a scoped, expiring waiver recorded as a finding, not a footnote.
- Each gate has at least one negative control: a fixture that must make it fail, proving the gate can fire.
- The test runner must discover a nonzero number of tests or the run fails; zero discovery is never green.
- Local and CI runs of the same gate over the same revision produce identical verdicts.
- The adversarial corpus (fixtures for each false-green class) passes: no fixture slips through.

## Product boundary

This spec fixes the existing DevGate engine and its gates as they are. It does not re-architect DevGate behind the kernel module interface (that is migration Phase 5), and it does not add new capability (Stitcher parity and GitLab are AIGGP-08 and AIGGP-07). It does make one forward-compatible change: gate results gain the fields needed to emit AIGGP-00 evidence envelopes later, so shadow adapters in Phase 3 require no rework.

## Users and calling systems

- Every consuming repo with DevGate cloned as a submodule (sunset-rush, game-idea-bible, others).
- The fleet CI runner executing DevGate templates.
- AIGGP-00 conformance fixtures consuming DevGate's honest outputs.

## Success measures

- Adversarial corpus: 100 percent of false-green fixtures are caught; none pass.
- Nonzero test floor enforced: a repo with zero discovered tests fails the test gate with an explicit EMPTY verdict, not a green exit.
- Identical local/CI runs on the pinned revision, three repetitions, bitwise-identical reports modulo timestamps.
- Finding ledger: every one of the 34+ findings mapped to fix commit, waiver, or accepted-risk record.

## Risks

- Reconciling an 8-commit unmerged branch against a moved main creates semantic conflicts that look resolved but are not. Control: fix-by-fix re-verification with negative controls, not a bulk merge.
- Owners patch findings cosmetically (exit codes changed, logic still vacuous). Control: every fix requires a failing-then-passing fixture pair.
- Scope creep into re-architecture. Control: the boundary above; kernel-shape work is deferred to AIGGP-00 and Phase 5.
