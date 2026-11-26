# 2026-10-25 - `log_failure.py` names its target and accepts `--upstream` (`base-write-01`)

Requirement: `baseline-ownership` / `base-write-01` - *"In a submodule layout,
tools that append to the failure registry SHALL write the project's overlay file
by default; writing the shared baseline SHALL require an explicit flag, and the
tool SHALL report which file received the entry."* Scenarios: *"default append
in consumer"* - `log_failure.py` in `<project>/.devgate/` without flags lands in
`<project>/.guardrails/failure-registry.jsonl` **and the output names that
path**; *"explicit upstream append"* - `WHEN log_failure.py runs with
`--upstream``.

## What was measured

The three clauses were checked one at a time against the script at `41d21b5`,
staged into a scratch consumer layout (`<tmp>/.devgate/scripts/log_failure.py`,
which is the directory name that selects the consumer branch of the script):

| Clause | Before this change |
|---|---|
| submodule layout defaults to the project overlay | **held** - `FAIL-5f34c1da`, wrote `<tmp>/.guardrails/failure-registry.jsonl` |
| the shared baseline needs an explicit flag | held in effect (`--baseline`), **but not under the flag the scenario names**: `--upstream` was `error: unrecognized arguments: --upstream`, exit 2 |
| the tool reports which file received the entry | **false** - stdout was the bare `failure_id` and nothing else |

So two of the three clauses were unmet, and the missing one was the one a
consumer would hit first: following the spec's own wording produced a usage
error, not an entry.

## What changed

`scripts/log_failure.py`:

- `--upstream` added on the same destination as `--baseline` (`dest="baseline"`,
  one `store_true`). `--baseline` is kept as an accepted alias rather than
  renamed: agent instructions, QA records and CI steps in this and consuming
  repositories already spell it that way, and a spec-conformance rename that
  breaks every existing caller trades one deviation for a wave of them. The
  help text is written for the maintainer's question ("append to the shared
  DevGate baseline instead of the project overlay").
- After a successful append the tool prints the `failure_id` **and**
  `registry: <absolute path of the file that received the entry>`.
- The CLI moved into `build_parser()` so the flag contract is testable
  in-process, with `main()` unchanged in behaviour otherwise.

The printed path is the resolved target, not the flag: an explicit `--registry`
or `FAILURE_REGISTRY_PATH` is reported as the file it actually wrote, so the
report cannot say "overlay" while the bytes went somewhere else.

## Evidence, old script vs new, same scratch layout

`--upstream`:

```
old: rc=2  log_failure.py: error: unrecognized arguments: --upstream   (no file written)
new: rc=0  FAIL-cfb915e0
           registry: <tmp>/new/.devgate/.guardrails/failure-registry.jsonl
           wrote new/.devgate/.guardrails/failure-registry.jsonl   (overlay not created)
```

no flags:

```
old: rc=0  FAIL-5f34c1da                                 (target unnamed)
new: rc=0  FAIL-2a77f44b
           registry: <tmp>/new/.guardrails/failure-registry.jsonl
           wrote new/.guardrails/failure-registry.jsonl        (baseline untouched)
```

(The new `--upstream` run's baseline file exists because that run wrote it; the
default run in the same tree then added to the overlay only, which is the
separation the requirement asks for.)

## Verification

- `python3 -m pytest tests/test_log_failure.py -q` - **8 passed** (5 before).
  `TestBaseWrite01Contract` stages the script under a literal `.devgate` and
  asserts, for the default run: the overlay exists, stdout contains
  `registry: <overlay>`, exactly one line landed, and the baseline was never
  created; for `--upstream`: the baseline exists, stdout names it, and no
  overlay appeared; plus a positive control that `build_parser()` maps both
  `--upstream` and `--baseline` to `args.baseline is True` and the default to
  `False`.
- The suite was RED before the script change for the right reasons (the staged
  old script exits 2 on `--upstream`, and its default stdout does not name the
  file), which is the pair of behaviours the two new tests pin.
- Full local gate battery re-run after the change: `guardrails-scan`,
  `silent-success`, `failure_registry_check`, `rules_check`, `check_exec_bits`,
  `check_charset`, `check_encoding`, `check_corruption` (content), `gen_floors`,
  `check_manifest_join` - exit 0, and `python3 -m pytest -q` 1820+ passed.

## Not done here

- `--baseline` is not deprecated with a warning. It is the spelling this repo's
  own historical records and entries use; retiring it is a separate decision
  that needs a sweep of the callers first.
- `FAILURE_REGISTRY_PATH` still overrides both flags, which is the documented
  precedence in `failure-registry.jsonl`'s header. The report makes that
  visible rather than changing it.
