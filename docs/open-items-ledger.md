# Open Items Ledger

Append-only aging backlog for `scripts/open_item_aging_check.py` (local pre-commit
hook and the push-time CI job that **detects** violations after they land).

Row contract (enforced by the gate):

- one line per open item: `- [ ] <source-date> <ID> <text>`
- `<source-date>` is the date the item was first raised (ISO), parseable by the
  gate — a row without one fails, it is never defaulted
- `<ID>` matches `[A-Z]+-<three digits>` and is the key used in
  `docs/open-items-triage.jsonl`
- `- [x]` rows are closed and are not aged; keep them at the bottom

Triage rule: every open row older than 14 days must carry a live disposition in
`docs/open-items-triage.jsonl` (`fixed`, `deferred` with `review_by` + `reason`,
or `not-actionable`). A deferral past its `review_by` fails again.

Provenance: seeded 2026-11-15 from the open boxes in `openspec/changes/*/tasks.md`
and from findings this gates rollout itself produced. The MC-routed digest
backlog (`docs/DIGEST-FOLLOWUPS.md`, NEXT-* ids, triaged in Mission Control) is
deliberately NOT duplicated here — two ledgers tracking the same rows is how a
row loses its single owner.

## Open

- [ ] 2026-10-11 OI-001 add-gitlab-forge-support Sprint 0: real-instance selection/enrollment is optional operator acceptance after explicit GitLab adoption, not a prerequisite to ship the GitLab support option (owner scope confirmed 2026-11-25). Keep the live task open; this records no selected instance.
- [ ] 2026-10-11 OI-002 add-gitlab-forge-support Sprint 4 / GLF-01 live half: two-live-forge parity is optional operator acceptance after explicit GitLab adoption, not a prerequisite to ship (owner scope confirmed 2026-11-25). Keep the live task open; no two-forge result is claimed. Hermetic parity remains required and is verified separately.
- [ ] 2026-10-11 OI-003 GLF-10: a real backup/restore drill remains required before any gate depends on an adopted GitLab instance, but is optional operator acceptance before adoption (owner scope confirmed 2026-11-25). Keep the live task open; no restore result is claimed.
- [ ] 2026-11-15 OI-005 evidence-claim gate flags `hub/alerts.py:67` (`raise NotImplementedError` under `@abc.abstractmethod`) as a bare marker: decide between retuning the gate to match a real raise only, or annotating the line; the abstract-method idiom is not debt, the current regex cannot tell.
- [ ] 2026-11-15 OI-006 secret-rotation gate has no test-fixture disposition: all 42 uncovered secret-scan hits are classified TEST FIXTURE in `docs/secret-rotation.jsonl` (verified 2026-11-15) but fail the gate as still-in-HEAD / never-revoked, because sr-01..04 know only real-secret semantics; decide between an sr-05 fixture disposition in the gate or moving fixture dispositions to `.guardrails/secret-allowlist.json`. Marking fixtures `revoked: true` is refused — it would claim a provider revocation that never happened.
- [x] 2026-11-08 OI-004 add-art-creation-contract 5.4: closed 2026-11-20 — the package archived to `openspec/changes/archive/2026-11-20-add-art-creation-contract/` and the CHANGELOG entry shipped with the archive as v1.3.52; the entry was not pre-written.
