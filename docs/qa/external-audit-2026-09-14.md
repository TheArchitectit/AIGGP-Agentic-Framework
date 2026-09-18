# External QA audit - DevGate-Agentic-Framework main @ 1e9b3e18 (2026-09-14)

Delta window: 12 commits, 2026-09-14T02:30:11Z..04:05:19Z (a8447d1559..1e9b3e1872), reviewed against live diffs at HEAD 1e9b3e1872feb06558bf3e1658243e59ca58e815. Audit-trail tally: 0 docs/qa/** paths in the window.

VERDICT: Two stories. (1) The ledger caught a real event: the seeded default_head 9f3f83ab is NOT an ancestor of current main - compare reports diverged (ahead=83, behind=71, merge-base e6f8a593b5). The default branch's history was rewritten within a day of the 2026-09-13 seed. (2) The new work itself, the AI01 runner-monitor hub, is disciplined: spec-marked modules, constant-time token verification, one-time enrollment tokens, atomic registry saves, instance state never committed, and four new hub test files. Shipped caveats: plain-HTTP token endpoints and plaintext token values in the hub-volume registry JSON.

## ROUND TABLE
- Architecture: thin ThreadingHTTPServer with clean registry/tokens/alerts/monitor separation; spec traceability markers (mon-hub-01, mon-enroll-01, mon-registry-01, mon-alert-01) in module docstrings; handler stays thin per its own contract.
- Product: closes the loop from the 2026-09-13 ai01-runner-monitor change package to running code - enroll, heartbeat, health, GitHub polling loop, deduped alerting, dead-man switch, Containerfile + quadlet template.
- Delivery/quality: tests/test_hub_{registry,enroll_heartbeat,monitor,alerts}.py land alongside the code; a8447d15 fixes "no vacuous green" and small-repo --all handling, the exact overclaiming class called out in the Sep 13 audits. Heartbeat env file and .pi/ session dir gitignored.
- Skeptic: bearer tokens over plain HTTP (no TLS in-repo) are sniffable/replayable if the hub is reachable off the tailnet, and no bind-address requirement is documented in the window. Registry stores raw token strings at rest. The dead-man workflow is new and unexercised in this window.

## FINDINGS
### HIGH
1. Default-branch history rewritten since the 2026-09-13 ledger seed. Seeded default_head 9f3f83ab10f6270f6eb2f08edc0ba819ce289df6 is not an ancestor of current main: compare = diverged, ahead=83, behind=71, merge-base e6f8a593b5. 71 commits on the seeded line are gone from main. Cause not visible via API (force-push vs reset-and-rebuild). The ledger did its job: reported here, not silently re-walked. Ledger updated to the new head with this finding on record.
### MEDIUM
2. Hub token endpoints ship without TLS in-repo (hub/server.py ThreadingHTTPServer; scripts/runner-enroll.sh posts bearer tokens to <hub-url>). Acceptable only if the hub is tailnet-bound; nothing in the window documents the bind. Confirm deployment binding before any exposure beyond Tailscale.
### LOW
3. Enrollment/heartbeat token values stored plaintext in runners.json on the hub volume (registry.py appends raw token strings; tokens.py compares against stored values). Instance state only, never committed - mon-registry-01 honored, redacted example in hub/schema/. Hash-at-rest would cut the blast radius of a volume read.
4. Audit trail: the Sep 13 audit/2026-09-13-* change-package branches (gate-correctness, rule-enforcement-gaps, baseline-hygiene, deploy-pipeline, ci-templates-docs) are merged into this main line and their refs remain. No docs/qa/** churn in the window.

## VERIFIED CLEAN (at 1e9b3e18)
Constant-time token comparison (hmac.compare_digest; absent expected fails closed). One-time enrollment token consumed on successful enroll. Server never echoes secrets (handler contract). Atomic registry save (tmp + os.replace). Tests added for all four hub concerns in the same window as the code.

## NOT INDEPENDENTLY VERIFIED
Hub test execution (reviewed statically, not run). Actual hub bind address / deployment posture. Dead-man workflow behavior. GitHub-issue notifier token permissions. Whether the history rewrite was intentional.

Source links:
- https://github.com/TheArchitectit/DevGate-Agentic-Framework/blob/1e9b3e1872feb06558bf3e1658243e59ca58e815/hub/server.py
- https://github.com/TheArchitectit/DevGate-Agentic-Framework/blob/1e9b3e1872feb06558bf3e1658243e59ca58e815/hub/tokens.py
- https://github.com/TheArchitectit/DevGate-Agentic-Framework/blob/1e9b3e1872feb06558bf3e1658243e59ca58e815/hub/registry.py
- https://github.com/TheArchitectit/DevGate-Agentic-Framework/blob/1e9b3e1872feb06558bf3e1658243e59ca58e815/scripts/runner-enroll.sh
