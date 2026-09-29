# Secret-scan fleet — first run over the declared public repositories

Date: 2026-09-29T05:06:59Z (per-report `scanned_at`)
Package: `openspec/changes/add-secret-scanning` task 6.2
Scanner: gitleaks `8.30.1`, the same pin as the `secrets` CI job
(`linux_x64` tarball `sha256:551f6fc8…470eb`; checksum verified `OK` before
install). Host path was `~/.local/bin/gitleaks` because `/usr/local/bin` is
not writable here — same binary, same version gate as CI.

## How it was run

```
bash scripts/secret-scan-fleet.sh \
  --declared /tmp/declared-public-repos.txt \
  --report /tmp/secret-fleet-first-run.json \
  --work /tmp/secret-fleet-work
```

Exit code **1** — at least one declared repository has an uncovered finding.
Every line in the gate's own output and in the report is redacted; this
document carries counts and locations (rule / path / line / commit) only,
and never a matched value.

## The declaration (9 URLs)

What was swept is what was declared. The list below is every public
repository under `TheArchitectit` at the time of the run
(`gh repo list TheArchitectit --limit 50 --json name,isPrivate,url`, filtered
to `isPrivate == false`). Private repositories are deliberately not in this
declaration: the sweep's fetch path is anonymous / public, and a private
repository that cannot be cloned would render as `unfetchable` rather than as
a verdict.

1. https://github.com/TheArchitectit/AIGGP-Agentic-Framework
2. https://github.com/TheArchitectit/smallcode
3. https://github.com/TheArchitectit/radimagetovisio
4. https://github.com/TheArchitectit/plexus-debug-ui
5. https://github.com/TheArchitectit/NemoClaw
6. https://github.com/TheArchitectit/engine-free-jam-one-button
7. https://github.com/TheArchitectit/radicaltrainingplatform
8. https://github.com/TheArchitectit/pi-mega-compact
9. https://github.com/TheArchitectit/openagentplatform

## Verdict

```
declared 9, scanned 9, states: clean=4, findings=5, unfetchable=0, unscannable=0
```

| Repository | state | findings | uncovered | notes |
|---|---|---:|---:|---|
| AIGGP-Agentic-Framework | clean | 2 | 0 | both covered by the allowlist (`generic-api-key` on the prose `RUNNER_TOKEN` in `docs/qa/2026-09-19-audit-delta.md`) |
| smallcode | clean | 0 | 0 | |
| radimagetovisio | clean | 0 | 0 | |
| plexus-debug-ui | findings | 4 | 4 | `curl-auth-header` in `docs/superpowers/plans/2026-08-27-provider-report.md` (history + working tree) |
| NemoClaw | findings | 11 | 11 | `slack-app-token`, `discord-client-secret`, `generic-api-key`, `curl-auth-header` across `src/lib/sandbox-channels.ts`, `.github/workflows/nightly-e2e.yaml`, `test/**` |
| engine-free-jam-one-button | clean | 0 | 0 | |
| radicaltrainingplatform | findings | 34 | 34 | `generic-api-key`, `curl-auth-header`, `curl-auth-user` in `Web/js/**` and `studyguides/NCM-MCI-LAB-WALKTHROUGH.md` (same cluster under the older `CertForge.*` paths) |
| pi-mega-compact | findings | 34 | 34 | `generic-api-key` in `conformance/vector-cortex/**`, `scripts/**` (fetch/bench/gen helpers), `src/vector-cortex/cache/crystal.ts`, and inside `assets/vector-cortex/encoder-v1/model.onnx` |
| openagentplatform | findings | 85 | 85 | `generic-api-key`, `curl-auth-header`, `stripe-access-token`, `jwt`, `aws-access-token` concentrated in `docs/**`, `mcp-server/DEPLOYMENT_GUIDE.md`, `mcp-server/internal/security/secrets_scanner_test.go`, `gate/gates/secret_scan_test.go`, and the root file `cpofopencode` |

This repository is **clean**: the two hits are the already-dispositioned
prose `RUNNER_TOKEN` false positive (`secret-allowlist.json`, reason
recorded). `uncovered = 0` is why it is `clean` while `findings = 2` —
the covered/undiscovered split working as specified.

## What this record is and is not

- It **is** the first production run of `scripts/secret-scan-fleet.sh`
  against real declared public repositories, with a pinned scanner, and the
  evidence that the per-repo state vocabulary (clean / findings / unfetchable
  / unscannable) and the exit-code contract behave as designed outside a test.
  9/9 declared repositories appear in the report exactly once (`secret-scan-07`).
- It is **not** a remediation of the other five repositories. Those findings
  live outside this repository and outside this package's scope. The point of
  the sweep is to make them visible; what to do about each cluster is an
  owner call in each owning repository, not work this package invents.
- It is **not** a clean-fleet claim. Exit 1 is the measured answer to
  "is there a credential sitting in a repository we own", and the answer is
  yes, in five of nine declared public repositories.

## Residuals from the run (recorded, not tidied)

1. **Coverage of the declaration, not of the org.** Nine URLs is exactly the
   public set at this timestamp. A new public repository created tomorrow is
   not in this declaration until someone updates the file the host's
   `SECRET_SCAN_DECLARED` names. The emptiness rule (`exit 3` on an empty
   declaration) prevents a *vacuous* clean; it cannot prevent a *stale* list.
2. **Private repositories are out of scope here.** They need a
   credentialed fetch path, which is a different contract from the one
   `secret-scan-fleet.sh` implements (it clones public URLs).
3. **Location lists in the raw JSON are deliberately not transcribed in
   full above**, so this document stays readable. The measured report for
   this run was the redacted JSON produced by the sweep (fields:
   `commit`, `line`, `path`, `rule` per location; no `Match`/`Secret`/`raw`
   fields of any kind — verified by field-name census before this record was
   written).
4. **`scan_state` on a live host** is the hub-facing half (5.3); this run was
   a one-shot operator sweep from a working machine, not a spoke timer tick.
   No hub row was updated and none is claimed.