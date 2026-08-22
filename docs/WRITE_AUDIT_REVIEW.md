# Write → Audit → Review Standard

> A four-gate pipeline for agent-assisted work: **Write → Audit → Lead Review → Commit & Push**.
> The agent that *writes* must not be the only agent that *validates*.

**Related:** [RELEASE_GATE.md](./RELEASE_GATE.md) | [AGENTS.md](../AGENTS.md) | [pre-work-check.md](../.guardrails/pre-work-check.md)

---

## Overview

DevGate's automated gates catch *known* failure patterns. They cannot tell you whether the work actually does what was asked, whether the tests assert anything meaningful, or whether an agent quietly reported success it never achieved. That requires a second pair of eyes.

This document defines the process model that surrounds the automated gates. It applies to any task an agent performs — code, tests, docs, or configuration.

```text
           ┌────────┐   ┌─────────┐   ┌────────────┐   ┌──────────────┐
  TASK ──► │ WRITE  │──►│  AUDIT  │──►│    LEAD    │──►│ COMMIT+PUSH  │
           │ (agent)│   │ (agent) │   │   REVIEW   │   │    (lead)    │
           └────────┘   └─────────┘   └─────┬──────┘   └──────────────┘
                                            │ approve / request changes
                                            └────────► back to Write
```

## Quick Reference

| Gate | Actor | Definition of done |
|---|---|---|
| 1. Write | **Writer agent** | Target changed; scoped; no out-of-scope files; self-checked |
| 2. Audit | **Independent auditor agent** | Evidence gathered first-hand; explicit verdict |
| 3. Review | **Lead** | Findings reconciled; gates re-run; fixes applied |
| 4. Commit & Push | **Lead** | Clean diff, documented message, pushed |

**Hard rules:**

- The **write step is performed by an agent** under a bounded scope — not improvised and skipped.
- The **audit is performed by a different agent in a different session** than the writer.
- The **lead reviews after the audit** and is the **only** role that commits and pushes.
- A task is **not complete** until commit and push succeed.

### Why the separation matters

An agent auditing its own work re-reads its own reasoning and finds it persuasive. It has already concluded the work is correct; asking it again mostly re-derives that conclusion. An auditor that sees **only the produced artifact** — the diff, the files, the test output — has to derive correctness from evidence instead, which is what catches:

- tests that pass because they assert nothing
- a "fixed" bug whose fix was never exercised
- validation reported as passing that was never run
- scope creep into files the task never authorized

---

## Gate 1 — Write

Dispatch a writer agent with an explicit, bounded task.

**The writer's brief must include:**

- **Read-first list** — the files and docs to read before editing (start with `.guardrails/pre-work-check.md`).
- **Exact scope** — in-scope files, and explicitly **which files must not be touched**.
- **Ordered steps** and the **validation commands** to run for the surfaces being changed.
- **An acceptance contract** — the structured report below.

**Definition of done:**

- Only authorized files changed.
- Self-run validation passes, or is reported as `NOT_RUN` **with the blocker stated** — never claimed as passed.
- A factual acceptance report is produced.

---

## Gate 2 — Audit

Dispatch an **independent** agent — a different session from the writer — to audit the output. Audits are **read-only** by default.

**The auditor's brief must include:**

- The files and deliverables in scope.
- A checklist: correctness, internal consistency, broken links, file-size limits, and every factual claim checked against the tree with `file:line` evidence.
- Instruction to **run the real commands** when a shell is available; if not, record `NOT_RUN` with the blocker.
- A required verdict: **`APPROVE`** / **`REQUEST-CHANGES`** / **`BLOCK`**, with severity-tagged findings and a one-line fix for each actionable one.

**Definition of done:**

- Findings carry `[severity] file:line` evidence.
- The verdict is explicit.
- No unauthorized edits were made.
- Unavailable checks are marked `NOT_RUN`, never reported as passed.

---

## Gate 3 — Lead Review

The lead is the final authority and the only role that commits.

1. **Read the audit report in full.**
2. **Reconcile** the writer's claims against the auditor's findings — where they disagree, check the tree yourself.
3. **Re-run the gates independently:**
   ```bash
   node scripts/guardrails-scan.mjs
   node scripts/semantic-scan.mjs
   python3 scripts/regression_check.py --all --pre-commit
   bash scripts/silent-success-scan.sh
   node scripts/run-tests.mjs
   ```
4. **Apply or delegate fixes** for `REQUEST-CHANGES` findings, then re-run the affected gates.
5. **Decide:** `APPROVE`, or return to Gate 1 — with a **limit of three cycles** before escalating to a human.

---

## Gate 4 — Commit & Push

Only after all gates pass:

1. `git status --short` — confirm exactly the intended files changed.
2. Stage **only** intended files (`git add <file>...`); avoid `git add -A`.
3. `git diff --cached --name-only` — confirm nothing out of scope is staged.
4. Commit with a descriptive message: type, scope, and a body explaining **why**.
5. Push, then confirm `git status -sb` shows up to date.
6. Mark the task complete **only after the push succeeds**.

When a bug was fixed, this gate also includes appending its failure-registry entry (`scripts/log_failure.py`) — see [RELEASE_GATE.md](./RELEASE_GATE.md#the-failure-registry-loop).

---

## Acceptance Report Contract

Every agent — writer and auditor — ends with a fenced JSON block tagged `acceptance-report`:

```json
{
  "criteriaSatisfied": [
    { "id": "criterion-1", "status": "satisfied", "evidence": "specific proof" }
  ],
  "changedFiles": ["path/to/file"],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    { "command": "python3 scripts/regression_check.py --all", "result": "passed", "summary": "0 errors" }
  ],
  "residualRisks": ["none"],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": ["file:line - observation"],
  "manualNotes": "anything else the lead should know"
}
```

`commandsRun[].result` is **exactly one of** `passed`, `failed`, `NOT_RUN`.

> Failed, skipped, unavailable, and NOT_RUN checks can never be reported as passed.
> A gate falsely reported green is worse than a gate that was never run — it removes the reason to look.

---

## Halt Conditions

Halt and escalate to a human when:

- Unexpected working-tree changes appear.
- A required gate cannot be run and there is no documented workaround.
- Three write→audit cycles have not resolved the findings.
- The task appears to require touching files it was told not to.

---

## Checklist

```
+------------------------------------------------------------------+
| Pipeline:  WRITE (agent) -> AUDIT (independent agent)            |
|            -> LEAD REVIEW -> COMMIT & PUSH (lead)                |
+------------------------------------------------------------------+
| MANDATORY:                                                        |
|   [ ] Writer is an agent with a bounded scope                     |
|   [ ] Auditor is a DIFFERENT agent in a different session         |
|   [ ] Lead reviews and is the sole committer/pusher               |
|   [ ] Out-of-scope files untouched and unstaged                   |
|   [ ] Gate commands run with real exit codes recorded             |
|   [ ] Acceptance report JSON produced                             |
+------------------------------------------------------------------+
| NEVER:                                                            |
|   [ ] Commit or push without the review gate                      |
|   [ ] Report NOT_RUN / skipped / failed as passed                 |
|   [ ] Let the writer be its own auditor                           |
+------------------------------------------------------------------+
```

---

**Last Updated:** 2026-08-21
