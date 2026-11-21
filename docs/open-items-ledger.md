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

- [ ] 2026-10-11 OI-001 add-gitlab-forge-support Sprint 0: the operator must supply the lab GitLab instance (base URL + internal host alias, exact version to pin in `supported_version`, auth shape, reachability); discovery on 2026-10-23 found no server and re-checks on 2026-11-13 and 2026-11-15 still found none. Closes only when someone chooses to use GitLab (owner-deferred 2026-11-15).
- [ ] 2026-10-11 OI-002 add-gitlab-forge-support Sprint 4 / GLF-01 live half: run the parity drill against two live forges on the pinned corpus (`hub/forge/corpus.lock.json`) and get identical findings; the hermetic half is landed and runs in CI, the two-platform green is not claimed without a second live forge.
- [ ] 2026-10-11 OI-003 GLF-10: evidence a backup restore drill before any gate depends on the lab GitLab; `validate_backup_restore_drill` and `audit_deployment` are ready to consume the report and name its absence; blocked on OI-001.
- [ ] 2026-11-15 OI-005 evidence-claim gate flags `hub/alerts.py:67` (`raise NotImplementedError` under `@abc.abstractmethod`) as a bare marker: decide between retuning the gate to match a real raise only, or annotating the line; the abstract-method idiom is not debt, the current regex cannot tell.
- [ ] 2026-11-15 OI-006 secret-rotation gate has no test-fixture disposition: all 42 uncovered secret-scan hits are classified TEST FIXTURE in `docs/secret-rotation.jsonl` (verified 2026-11-15) but fail the gate as still-in-HEAD / never-revoked, because sr-01..04 know only real-secret semantics; decide between an sr-05 fixture disposition in the gate or moving fixture dispositions to `.guardrails/secret-allowlist.json`. Marking fixtures `revoked: true` is refused — it would claim a provider revocation that never happened.
- [x] 2026-11-08 OI-004 add-art-creation-contract 5.4: closed 2026-11-20 — the package archived to `openspec/changes/archive/2026-11-20-add-art-creation-contract/` and the CHANGELOG entry shipped with the archive as v1.3.52; the entry was not pre-written.
