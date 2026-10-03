# Proposal: add-secret-scanning

## Why

The repository ships a drop-in secret-scanning workflow
(`templates/github-workflows/secret-validation.yml`) that **this repository does
not run on itself**. Every push to `main` therefore passes six CI jobs — specs,
tests, image build, evaluator attack, identity, self-gates — and not one of them
looks for a credential.

Measured on 2026-09-24, so the baseline is a fact rather than a worry:

- Working tree: `gitleaks detect --no-git` over the checkout — **clean**.
- Full history across all refs (`--all`, 253 commits, 4.95 MB) — **one** hit:
  `generic-api-key` in `docs/qa/2026-09-19-audit-delta.md:89` on
  `origin/audit`. The match is the *prose* `RUNNER_TOKEN` inside a sentence
  describing redaction false positives; the value gitleaks reported was its own
  `REDACTED` marker. No credential. It is a real false positive of the rule,
  which is exactly the case a disposition path has to handle honestly.

Two problems follow. First, nobody is watching: the repo's credential posture is
whatever the last author remembered. Second, the template that would watch is
written for a different environment than this project runs in — it uses
`gitleaks/gitleaks-action@v2` on `runs-on: ubuntu-latest`, i.e. a third-party
marketplace action, a licence question for organisations, and hosted minutes.
Roger's constraint is the opposite: *"we have full github access just zero
budget, it will all go on internal runners."*

## What Changes

- **A gate script, `scripts/secret-scan.sh`**, that scans the pushed range and
  the working tree with a pinned `gitleaks`, always redacting, and fails the
  build on a finding. It treats "the scanner did not run" as a failure, not as
  a clean result — the same rule the other gates in this repo follow.
- **An explicit disposition path** in the established idiom: a tolerated finding
  needs an allowlist entry carrying a reason, and stale entries are reported, so
  suppression cannot accumulate silently. The prose match above is the first
  entry, with its reason written down.
- **A `secrets` job in this repository's own CI**, on every push and pull
  request, installing the scanner from a pinned release **with its published
  checksum verified** and running the gate script. No new marketplace action.
- **The consumer template updated to the same mechanism**, so the workflow a
  consumer copies enforces the contract this repo now enforces, and works on a
  self-hosted runner without a licence.
- **A fleet sweep for repositories that never adopt the workflow** — a periodic
  scan over the declared repositories, reporting per-repo state with absence
  explicit. Specified here; built in a later sprint, because the per-push half
  is what stops the bleeding.

## Impact

- Affected specs: `secret-scanning` (new capability).
- Affected code: `scripts/secret-scan.sh` (new), `.github/workflows/ci.yml`,
  `templates/github-workflows/secret-validation.yml`, `.guardrails/`.
- Out of scope: rotating anything (nothing was found to rotate), and rewriting
  history. The one historical match is a documentation false positive, so there
  is no secret in the history to purge — but the disposition is recorded rather
  than assumed, so a later reader can check that claim instead of trusting it.
