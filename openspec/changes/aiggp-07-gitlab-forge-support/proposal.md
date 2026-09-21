> **Status: imported draft — not a commitment.** The AIGGP program has not started; this package is imported reference material held for future acceptance. It does not modify, supersede, or bind the shipped DevGate specification ladder, and no code, traceability ID, or gate configuration is wired to its requirements. (Added 2026-09-20 per the spec-coherence drift audit; see the AIGGP-02 reconciliation.)

## Summary

Add GitLab as an additive second forge: instance discovery and backup for the lab instance, a GitLab runner standard mirroring the GitHub fleet, the CI gate templates mirrored 1:1 as GitLab includes running identical scripts, a forge adapter in the hub, and a blocking parity drill proving identical findings across forges.

## Problem

The lab runs GitLab; DevGate gates GitHub only. Repos on the lab instance get no gate truth at all, and any GitLab support bolted on later risks divergent behavior - the same change passing on one forge and failing on the other. The September 19 package designed the integration (29 normative requirements, 6 sprints); this spec keeps that design and re-anchors its evidence to the AIGGP envelope so forge identity is metadata, not meaning.

## Desired outcomes

- The lab GitLab instance is discovered, documented, pinned (tailnet-only), and backup-tested before any gate work depends on it.
- GitLab runners meet the same standard as the GitHub fleet: rootless podman, digest-pinned images, fail-closed.
- All five CI gate templates run on GitLab as includes executing the identical scripts the GitHub templates run.
- The hub monitors GitLab repos through a forge adapter with the same evidence envelope.
- A parity drill proves identical findings on both forges over a seeded-failure corpus, and runs in CI forever after.

## Product boundary

This spec adds a forge, not new gates. Gate logic is forge-neutral and shared; only webhooks, auth, CI template syntax, and API surfaces are forge-specific. Forge-specific verdict behavior is a defect by definition. GitLab instance administration beyond backup verification is out of scope.

## Users and calling systems

- Lab repos on the tailnet GitLab instance.
- The fleet hub consuming forge-adapter evidence.
- Future external adopters running GitLab (the adapter is public like everything else).

## Success measures

- Parity drill: identical findings (same gate, same rule, same file evidence) on GitHub and GitLab over the seeded corpus, enforced in CI.
- Every GitLab-emitted envelope validates against AIGGP-00 and names forge identity as metadata.
- Backup restore drill on the lab instance passes before gates are declared available there.
- Zero forge-specific branches in gate logic (checked by code review plus the drill).

## Risks

- The lab GitLab server is undocumented; building on an undiscovered instance bakes in wrong assumptions. Control: Sprint 0 is instance discovery and gates everything else (carried from the September 19 package).
- Template drift: GitHub and GitLab CI syntax differ, so mirrored templates rot apart. Control: templates are thin launchers calling identical scripts; parity drill catches divergence.
- Tailnet-only access breaks external reproducibility. Control: the adapter targets any GitLab instance; the lab is the first consumer, not the only supported shape.
