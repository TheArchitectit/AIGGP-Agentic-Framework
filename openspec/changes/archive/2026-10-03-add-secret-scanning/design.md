# Design: add-secret-scanning

## D1 — A scan that did not run is not a pass

The failure this whole repository is built around, and the reason the gate is a
script with an exit-code contract rather than three lines in a workflow: a
scanner that is absent, uninstalled, or invoked wrongly produces no findings,
and no findings reads as clean. So the scanner missing is exit 2 with the
install named, a bad invocation is exit 3, a finding is exit 1, and 0 is
reserved for "the scanner ran over the named scope and found nothing". The same
shape as `run-tests.mjs` refusing to report success after discovering zero tests
and `semantic-scan.mjs` failing when its parser is absent.

## D2 — Scope: the pushed range by default, history on purpose

Two scopes exist and they answer different questions:

- **The push gate** asks "did *this* push add a credential?" and scans the
  commits being pushed plus the working tree. This is the per-push contract, and
  it is what a developer can act on.
- **The history sweep** asks "is there a credential anywhere in this
  repository?" It is expensive, it cannot be fixed by editing the current tree,
  and running it on every push would make the gate fail for reasons no author of
  the push can address.

Conflating them is how a real gate gets disabled. So the push gate takes a range
and does not silently widen; the sweep is an explicit flag. One wrinkle has to
be handled rather than ignored: a first push or a forced update has no usable
base commit, so the range is unavailable and the gate falls back to the full
history **and says so** in its output, rather than scanning nothing and
reporting success.

## D3 — Redaction is not optional

Every invocation passes the scanner's redact flag, and every report the gate
writes is a redacted one. A secret scanner that prints the secret into CI logs
and uploaded artifacts has published it a second time, to a wider audience than
the commit did. The trade-off is real and worth stating: redaction makes the
report harder to act on, because the operator cannot see the value. That is the
right side of the trade — the finding carries rule, path, line, and commit,
which is everything needed to find the value locally.

## D4 — Dispositions are explicit, reasoned, and expire visibly

The prose `RUNNER_TOKEN` match on the audit branch (see the proposal) is the
case that forces this decision: a rule firing on documentation *about* the rule.
Three options were available — weaken or disable the rule, exclude docs from the
scan, or list the single occurrence.

Weakening the rule is global and silent. Excluding documentation is nearly as
bad: docs are where people paste real credentials, so it removes coverage
exactly where it is most needed. So: an allowlist file keyed on rule plus path,
each entry carrying a `reason`, mirroring `.guardrails/silent-success-allowlist.json`
and the health script that watches it. An occurrence not covered by an entry
still fails, and the gate reports entries that no longer match anything — an
allowlist nobody prunes is a list of bugs the team agreed to keep.

## D5 — Pin the scanner, not an action

The existing template reaches for `gitleaks/gitleaks-action@v2`. That is a
third-party marketplace action (supply-chain surface this repo explicitly
minimises — it pins `actions/checkout` by SHA and has a test forbidding floating
`@vN` references), it wants a licence for organisation-owned repositories, and
it assumes a GitHub-hosted runner. The gate instead installs a pinned release
binary and verifies it against the project's published checksum file before
running it. Measured 2026-09-24: `v8.30.1`, `linux_x64` tarball
`sha256:551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`,
matching the vendor's own `gitleaks_8.30.1_checksums.txt`. A version bump is
therefore a deliberate, reviewable two-line change. The cost is honestly stated:
the gate needs either network access to fetch that release, or the scanner
pre-installed on the runner — the fleet shape (D6) is the second case.

## D6 — A fleet sweep, because adoption is the weak half

A per-push gate protects repositories that adopt it. Roger's ask included the
other half — *"or a runner for all public repos"* — and it matters, because a
public repository with no workflow is exactly the one nobody is scanning. The
fleet sweep is a periodic tick installed beside the heartbeat: for each declared
public repository, clone or fetch, scan the tree and history, and report per-repo
state to the hub. Its reporting follows the rule already established for image
state (img-cycle-03): presence is reported positively, and absence is reported
as an explicit reason, never as silence that reads as health.

This is specified now and built later; the ordering is deliberate, because a
push gate is what stops new credentials from landing.
