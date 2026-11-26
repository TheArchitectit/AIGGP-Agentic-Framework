# DG-02 task 1.1 — baseline roster and input seal

**Baseline:** `7ec9983466f1ba5dada04c29700f68dfaed15d9e` (ready #42). The source checkout is detached at this exact commit. The original `openspec/state-unproven.jsonl`, `openspec/state-ledger.jsonl`, canonical specs, and generated `openspec/INDEX.md` were read only.

## Extraction and exact mapping

[`unproven-baseline-roster.jsonl`](unproven-baseline-roster.jsonl) contains 182 stable rows (`DG02-U-001`–`DG02-U-182`) in original `state-unproven.jsonl` source-line order. Each entry preserves the source fields, source line and per-record SHA-256, canonical owner-spec path and Git blob ID. [`input-manifest.json`](input-manifest.json) records the pinned source tree and per-file Git blob/content hashes.

Reconciliation against the owning files found:

- 182 data records and 182 unique `(spec, req)` pairs across 42 specs; no duplicate pair.
- All 182 requirement IDs exist under the corresponding canonical `openspec/specs/<spec>/spec.md` file.
- The generated index lists the same 42 specs as **UNPROVEN**; its per-spec “unproven requirement” counts sum to 182.
- No matching `(spec, req)` pair appears in the current state ledger.
- `python3 scripts/spec_index.py --check` passed: `INDEX.md matches the generator`.

This verifies the source roster’s exact one-to-one mapping. It does not validate any proof claim or change lifecycle state.

## Stable digest

The source input digest is **`sha256:5de4a469e82c1b40cc750f9ab57b8b3c055f728fd6c925466f8d8ad81dd35804`**. It is SHA-256 over canonical UTF-8 JSON (`sort_keys`, compact separators) containing the exact baseline commit and the ordered 58-file input manifest. The files include the original unproven roster, generated index, ledger and OpenSpec config; the state gate, index generator and evidence validator; the current and change-delta spec-state-ledger contracts plus the archived ledger design; all 42 owning spec files; and every tracked file under `openspec/evidence/`.

The original unproven source file independently hashes to **`sha256:7b508628884863d3aa94f68b50fa0dfcfdbe280fefb2e0a69e489d1879114d1b`**, matching the independent raw-Git-byte check. The derived JSONL roster hashes to **`sha256:92c30d3b19cebdfac4a99f3a8a47ebbdb7ca3e28dcd8b35d63e16d1e4da4b27a`**. The manifest records all three values and the 58 input paths. The extraction was rerun at the same clean baseline and produced the same source digest and roster digest.

## Provenance drift to carry into task 1.2

The 182 rows are not uniform proof candidates:

- 113 rows across 27 specs have `provenance: accepted`; their reasons still say no sealed evidence bundle is landed, so all remain UNPROVEN.
- 69 rows across 16 specs have `provenance: rejected`: 61 cite no implementation path; 4 cite `templates/github/workflows/`, absent at this baseline; 4 cite short commit `4b69262`, which the source reason says does not resolve in reachable history.
- There are 28 distinct citation values: 25 full commit ranges, one empty citation, one absent-path citation, and one short-commit citation. Task 1.1 preserves these values; resolving commit reachability/order and changed-file overlap belongs to task 1.2.

No row is inferred proven from its claim, accepted provenance, marker, index text, or source/test name. No lifecycle transition, closure change, or evidence bundle was created.

## Required sources for the next proof review

Task 1.2 must evaluate each row’s own proof conjuncts from the immutable baseline: the cited lower/upper commits and their ancestry; the exact changed-file range; the current implementation/enforcement location in the owning source tree; the named behavioral test and its actual result; and the row’s sealed evidence bundle, manifest/digest, and `scripts/evidence-validate.py` result. The state gate’s acceptance must be recorded per row, along with reviewer and review time. Where a conjunct is absent, stale, unresolved, or rejected, record it as missing and keep the requirement UNPROVEN. This roster only provides the complete row key, original citation/reason, and owner-spec mapping needed to start that review.

## Commands and limits

- `python3 scripts/spec_index.py --check` in a disposable canonical-LF clone at the pinned commit — **passed**.
- `python3 scripts/regression_check.py --all` in the same clone after canonical-LF checkout — **passed**: no potential regressions, 0 scope gaps, 0 hard-limit findings; 11 pre-existing oversize warnings and 62 soft warnings; no package vulnerabilities.
- Repo-pinned OpenSpec 1.14.3 strict validation — **NOT_RUN**: the writer’s standalone offline lookup did not find the pinned CLI; an offline `npx --offline --yes @fission-ai/openspec@1.14.3 --version` lookup returned `ENOTCACHED`. No network fetch or package installation was attempted.
- No external queries or owner contact occurred. The original ledger and roster bytes were not changed.

## Validation environment note

The first `regression_check.py --all` attempt from the Windows worktree failed closed because its `.git` file pointed to a Windows-only worktree path inside the Linux container. A first Windows clone also materialized CRLF and Linux Git treated the checkout as modified, so that scan output was discarded. The final pre-work run used a disposable clone reset inside Linux with `core.autocrlf=false` and `core.eol=lf`; it completed successfully with no potential regressions. No product or ledger file was changed during these attempts.
