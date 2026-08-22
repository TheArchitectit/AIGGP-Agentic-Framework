# Release Gate

> The gate suite that must pass before any publish, and the stage order that makes a *failed* release safe.

**Related:** [WRITE_AUDIT_REVIEW.md](./WRITE_AUDIT_REVIEW.md) | [AGENTS.md](../AGENTS.md) | [README.md](../README.md)

---

## Overview

`scripts/deploy.sh` is the supported publish path. It auto-detects your package manager (npm, cargo, pip/twine, go, Godot, or none) and runs the appropriate build, test, and publish commands. Never publish by hand, and never publish from a dirty or unpushed tree.

**A published version is immutable.** You cannot re-cut `1.4.0` after shipping a broken artifact — you can only burn a version number. Every gate below exists because skipping it has already cost a real release somewhere.

The ordering principle: **everything reversible happens before the one irreversible step.** Build, test, scan, pack, verify, commit, tag, and push all come first. Publishing is last, so any failure aborts while `publish` still hasn't run.

---

## Quick Reference

| # | Stage | What it does | Failure means |
|---|-------|--------------|---------------|
| 1 | **Clean tree** | rejects unstaged changes and a dirty index | Abort; nothing changed |
| 2 | **Gate suite** | regression check, guardrails scan, then the project's own build/test/lint | Abort; nothing changed |
| 3 | **Schema health** | validates DB schema when an adapter is configured; skips otherwise | Warn only (non-blocking) |
| 4 | **Version bump** | writes the new version into the detected manifest | Abort; revert the bump |
| 5 | **Commit + tag + push** | commit, **annotated** tag, push with captured stderr | Abort **before** publish |
| 5b | **Tag-reached-remote verify** | `git ls-remote` proves the tag is upstream; explicit retry, then re-verify | Abort **before** publish |
| 5c | **ARTIFACT VERIFY** | packs and proves the required files are really inside the artifact | Abort **before** publish |
| 6 | **Publish** | `npm publish` / `cargo publish` / `twine upload` / tag-only | Version number is burned |
| 7 | **GitHub release** | `gh release create` with notes from the commit log | Warn only (best-effort) |

### Per-stack detection

| If your project has | Build / test | Publish |
|---------------------|--------------|---------|
| `package.json` | `npm run build`, `npm test`, `npm run lint` | `npm publish` |
| `Cargo.toml` | `cargo build --release`, `cargo test`, `cargo clippy` | `cargo publish` |
| `pyproject.toml` / `setup.py` | `pytest` | `twine upload` |
| `go.mod` | `go build ./...`, `go test ./...` | tag pushed (no central registry) |
| `project.godot` | skipped (run headless tests manually) | tag pushed (manual export) |
| none of the above | skipped | tag pushed; publish manually |

---

## Why each gate exists

### ARTIFACT VERIFY — the artifact can be empty

A packer will happily produce a **well-formed archive with the built binary missing**. One project shipped exactly that: the package installed cleanly and then failed at first run, for every user, on a version number that could not be recalled. `files`/`include` lists drift away from the build output, and nothing warns you.

So the check happens **before** publish, and it inspects the *packed artifact* rather than the working tree — the working tree is not what users receive.

Enable it by creating `.guardrails/release-artifact-contract.json` (copy `release-artifact-contract.example.json`):

```json
{
  "artifact_glob": "*.tgz",
  "must_contain": ["bin/my-tool-linux-x64", "package.json"],
  "must_be_executable": ["bin/my-tool-linux-x64"],
  "entry_prefix": "package/"
}
```

- **`must_contain`** entries are matched **exactly** against the archive listing (`grep -Fqx`), not by substring — a partial match is how a wrong path slips through. On failure the **full listing is dumped** so you can see what actually got packed.
- **`entry_prefix`** absorbs the packer's top-level directory (npm uses `package/`; cargo uses `<name>-<version>/`; use `""` for none), so the same `must_contain` list is portable.
- **`must_be_executable`** re-checks on-disk permission bits, because a non-executable launcher breaks the installer's `spawn` even when the file is present.
- Listing command per stack: `.tgz`/`.tar.gz` → `tar -tzf`; `.whl`/`.zip` → `unzip -Z1`; cargo → `cargo package --list`.

**When the contract file is absent the stage prints a skip notice and continues.** A fresh install needs no configuration and stays green — the gate imposes nothing until you opt in.

### Push before publish — don't strand your source

Publishing from an unpushed commit strands the source of an immutable artifact: the registry has the version but nobody can reproduce it. One project published and only then discovered its release commit had never left the machine.

Stage 5 therefore commits, tags, and pushes **before** stage 6, and any failure aborts while publish still hasn't run.

### Real push errors must not be swallowed

The push previously ran as `git push --follow-tags 2>/dev/null`, discarding stderr and retrying with `--set-upstream` on *any* failure. That made every problem — rejected non-fast-forward, auth failure, network error — look like a missing upstream, and the real message was gone.

Now stderr is **captured to a temp file** and the two cases are separated: a genuine no-upstream error retries with `-u`; anything else **aborts and prints what git actually said**.

### Annotated tags and `--follow-tags`

`git push --follow-tags` pushes **annotated tags only**. A lightweight `git tag v1.4.0` is silently left behind — the push reports success and the tag simply never arrives.

`deploy.sh` creates tags with `git tag -a` and then *verifies*:

```bash
git ls-remote --exit-code --tags origin "refs/tags/$TAG"
```

If the tag isn't upstream it retries with an explicit `git push origin "$TAG"`, then **re-verifies** and aborts if it still isn't there. Trusting the exit code of `--follow-tags` alone is not enough.

---

## The failure-registry loop

```
bug found → fix it → log_failure.py records it (with a regression_pattern)
          → regression_check.py fails the build if that pattern is re-added
```

- **`scripts/log_failure.py`** appends one JSON line to `.guardrails/failure-registry.jsonl`. The registry is **append-only** — never edit or reorder existing lines.
- **`scripts/regression_check.py`** compiles every active/resolved entry's `regression_pattern`, plus the `critical`/`error` rules from `pattern-rules.json`, and matches them against the **ADDED** lines of the diff under review.

Scanning only added lines is what makes the patterns usable: a pattern may match one legitimate pre-existing line without failing the build, because that line isn't in the diff — while any *new* introduction fails the gate.

An entry may scope its pattern with a `file_glob`, so docs and helper scripts can quote a pattern without tripping the gate. The two files that *define* the patterns (the registry and `pattern-rules.json`) are excluded from the scan, since every pattern trivially matches its own definition.

> **A bug fixed without a failure-registry entry is not fixed.**
> It is a bug waiting to come back, with no gate standing in its way.

---

## Usage

```bash
# Full release: gates → bump → commit+tag+push → verify → artifact verify → publish
bash scripts/deploy.sh 1.4.0

# Gate suite only, without releasing
python3 scripts/regression_check.py --all --pre-commit
node scripts/guardrails-scan.mjs
bash scripts/silent-success-scan.sh
```

Before a release that matters, rehearse the artifact contract by packing manually (`npm pack`, `cargo package --list`, `python3 -m build`) and confirming the listing contains what `must_contain` claims.

---

**Last Updated:** 2026-08-21
