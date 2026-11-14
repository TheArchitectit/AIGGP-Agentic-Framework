# Art contract extension path

`art-creation-contract` is not a fixed list of checks. It is a contract that
grows from the failure registry: every art failure class that reaches a human is
appended to `.guardrails/failure-registry.jsonl` with a prevention rule, and
where no existing requirement covers the class the contract is extended to cover
it (`art-evolve-01`).

This page is that path, end to end. It is deliberately mechanical: a class that
is only described in a conversation is the next class written after the next
mess.

## 1. Log the class

Append one entry with the repository's own writer, never by hand-editing the
JSONL:

```sh
python3 scripts/log_failure.py \
  --error-message "<the class, stated as a class — this repo is public>" \
  --category config --severity high \
  --root-cause "<the mechanism, not the symptom>" \
  --affected-files scripts/art_checks.py \
  --fix-commit <sha-that-made-it-checkable> \
  --regression-pattern "" \
  --prevention-rule "<the art requirement id(s) that would have prevented it>" \
  --status resolved
```

Rules that matter for this registry:

- **One JSON object per line, append-only.** `log_failure.py` never rewrites,
  reorders or deletes an entry; neither does anything else.
- **The class, not the title.** Operational detail belongs in the title's
  private repo. This repository is public, so an entry names the failure class.
- **The prevention rule names requirement ids**, e.g.
  `art-brief-01, art-brief-02` for "no shared language". A rule that cites
  nothing is a class with no home.
- **`regression_pattern` is compiled and matched against added diff lines** by
  `scripts/regression_check.py`. Leave it empty unless the regression is a
  literal string a future diff would contain; a pattern that matches ordinary
  code reds every later commit that touches it.
- **`fix_commit` must be a real commit.** Use the commit that made the class
  checkable; `pending` is a sentinel for an entry whose fix is the entry
  itself, and it does not survive review.

## 2. Decide whether the contract already covers it

Search the requirement ids. The capability is still an open change, so until it
is archived the authoritative file is the change's delta; after archive the same
ids live under `openspec/specs/art-creation-contract/spec.md`:

```sh
grep -n 'id: art-' openspec/changes/add-art-creation-contract/specs/art-creation-contract/spec.md
```

- **A requirement covers it** — the prevention rule cites that id and nothing
  else changes. Example: a target that clears the buffer and calls it a frame
  is already `art-draw-01`; the entry cites it and no contract change lands.
- **No requirement covers it** — the entry names the gap, and the contract is
  extended (step 3). No `Status: CLOSED` claim for the class until the
  extension is published.

## 3. Extend the contract

A new class becomes a spec delta, not a prose addition to a shipped spec:

1. Add the requirement under
   `openspec/changes/<change>/specs/art-creation-contract/spec.md` with
   `### Requirement: <one sentence>`, a `<!-- id: art-<name>-NN -->` marker,
   SHALL statements, and at least one `#### Scenario:`. The scenario is the
   check that proves the requirement can fail.
2. Put the `# spec: art-<name>-NN` marker immediately above the function that
   enforces it in `scripts/art_checks.py`, `scripts/art_check_outcome.py` or
   the entry point. A marker above a module docstring covers nothing — the
   traceability sweep treats a marker with no enforcement site as a false
   claim.
3. Add the negative control to `scripts/test_art_creation_scan.py` **first**
   (it must fail), then the check that makes it pass. Each case asserts the
   exact requirement-id set it trips, not only the exit code.
4. If the class is a process obligation on a human rather than a code
   enforcement site, say so in the requirement and record it as deliberately
   uncovered — as `art-evolve-01` itself is. Do not paper it over with a
   marker on a function that does not enforce it.

## 4. Verify before landing

```sh
python3 scripts/test_art_creation_scan.py            # fixtures + exit contract
python3 scripts/failure_registry_check.py            # registry well-formed
python3 scripts/spec_traceability.py --root . --ratchet
npx openspec validate --all --strict
python3 scripts/regression_check.py --staged --pre-commit
```

The first three are the ones that go red when an entry cites a requirement that
does not exist, when a marker has no enforcement site, or when the registry
entry is malformed. A class is not covered because a check was written; it is
covered when the negative control proves the check can fail.

## 5. Scope boundary

Per-game content is out of scope. A title's pillars, palette, shape rules and
camera statement live in the title's repository. This repository owns only the
schema of the brief, the stage contract, the ledger format and the checks.
