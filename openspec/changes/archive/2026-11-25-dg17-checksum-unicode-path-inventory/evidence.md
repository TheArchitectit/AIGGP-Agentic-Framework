# Evidence

## Baseline

- Source observed: exact PR #41 implementation snapshot `ac61e20fa7a4afcc8e2827817446fa01cb5730ff` in a clean detached worktree.
- Relevant source: `scripts/gen-checksums.py:26-34` reads `git ls-files` as line-oriented text and filters `splitlines()` records by suffix.
- Scope is limited to a synthetic disposable Git repository. No remote, live service, credential, or production repository was contacted.

## Reproduction

Fixture created with Git `core.quotePath=true` and two committed supported scripts: `scripts/ordinary.py` and `scripts/r\u00e9sum\u00e9.py`.

- `python scripts/gen-checksums.py generate --repo <fixture>` from the exact `ac61e20` source - exit 0; reports one checksum.
- `python scripts/gen-checksums.py verify --repo <fixture>` from the exact `ac61e20` source - exit 0; reports `VERIFY OK` for one checksum.
- The generated manifest contains only `scripts/ordinary.py`; the tracked Unicode path is omitted. This reproduced a false success at the audited baseline.

## Implementation and local verification

- `scripts/gen-checksums.py` now consumes binary `git ls-files -z` records, filters candidate suffixes before decoding, strictly decodes candidate paths as UTF-8, rejects backslash or any Python `str.splitlines()` separator, and rejects duplicate supported raw path records before either mode reads or writes a manifest.
- `tests.test_gen_checksums` passed on native Windows Python 3.12: 5 passed, 1 POSIX-only test skipped. Unicode paths with `core.quotePath=true`, ordinary paths, internal spaces, nested paths, and a real unresolved three-stage index are covered.
- `tests.test_gen_checksums` passed in the isolated Linux image `aiggp-pr41-lead:20261125`: 6 passed. Separate POSIX fixtures covered LF, CR, backslash, U+2028, and invalid UTF-8 supported paths with specific diagnostics; both modes failed closed, and generation preserved a sentinel manifest. A noncandidate newline path remained outside the inventory. A real unresolved three-stage index failed before manifest I/O in both modes.
- Regenerated `CHECKSUMS.sha256` from LF-materialized tracked sources: 160 records. A second LF-materialized verification reported all 160 checksums matching.
- OpenSpec 1.14.3 strict validation passed for this change. `git diff --check` passed. Registry entries `FAIL-92002cf7` and `FAIL-2f2849c7` record the Unicode omission and unresolved-index duplicate defects with regression prevention rules.

## Acceptance boundary

The independent audit reproduced all six Linux tests and the five applicable Windows tests. It verified all 160 canonical checksums against the final source. The integrated local test floor collected 2,082 tests across 143 suites. The hosted checksum step tested the exact candidate tree
`54acadb13d6a8e931865a58881e7ff49feb0a2b1` at
`69d755e441dbd3172be97cb51b0ca2e880328f69` and verified all 160 records. The
same job passed committed-range corruption checking. GitHub's synthetic merge
commit `764681cf359ee4894d8ac3438188bb4d5f0f183b` used those exact tree bytes.
[Hosted DevGate job](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45671009303/job/139405942794)
