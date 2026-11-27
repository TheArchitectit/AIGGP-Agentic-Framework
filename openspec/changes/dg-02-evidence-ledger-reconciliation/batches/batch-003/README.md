# DG-02 evidence review batch 003

Reviewed rows `DG02-U-025` through `DG02-U-036` at AIGGP revision
`80d18b0f0f4e080c9e47d4e534cc2c56c29308ca`. All twelve remain **UNPROVEN**.
Eleven citations resolve to ordered ranges reachable from that revision. Row
025 cites a historical directory that is absent. Its owner spec also names the
template supply-chain test, which exercises files under the current template
directory. The path citation still lacks an implementation range.

Each [disposition](batch-003-disposition.jsonl) records the source paths and
tests named by the owning spec, tests from the prior discovery, and the actual
files changed in the cited Git range. The in-range lists are intersections
with that diff. Row 031 illustrates why the owner spec was read again. Its
earlier discovery named no tests, while the spec names two.

## Behavioral results

The check used a clean, network-isolated Linux Git checkout with all 56 tag
refs, running as a non-root user. The worktree stayed clean.

| Test inputs | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| 23 test modules from the owner specs and prior discovery | 439 | 7 | 0 |
| Four additional modules changed in the cited ranges | 79 | 0 | 0 |

The runner also reported 20 passing subtests. The named `fixtures.py` supplies
fixture data and collected no tests. All seven skips reported
`podman not available`. One came from the image-identity module, three from
the real-container module and three from the launcher module. The four
additional modules covered game session start, GitLab forge support,
the coherence 3D slice and coherence issues. The combined JUnit XML had SHA-256
`99cdd9b7ae3cc63af8695d400597353e1d9015f69e55766900ebca467748d2ec`.

## Seal and scope

The [batch manifest](batch-manifest.json) records the raw Git roster and
prior-discovery digests, the disposition file digest, and the evidence seal.
Each sealed finding includes the SHA-256 of its review row's sorted, compact
ASCII JSON before the two evidence reference fields are added. Verify the
bundle at the repository root with the recorded expected digest:

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-003/evidence \
  --expected sha256:2eb3803fa4b467b79416e92de85877cd858db6cfa4588aaef9363114021c0c13
```

The batch preserves what reviewers observed. Individual requirements still
need behavioral evidence and an accepted canonical bundle under their own
closure criteria. The original roster, ledger and lifecycle states are unchanged.
