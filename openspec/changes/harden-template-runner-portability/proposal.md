# Change: Two Template Defects a Rootless Fleet Runner Exposed

> **Status:** Implemented in `templates/github-workflows/`. Found by adopting the
> templates wholesale in a consumer repository that runs its gates on the
> DevGate fleet runner; both defects were measured there, not inferred.

## Why

Two consumer repositories adopted `secret-validation.yml` and `drift-scan.yml`
as shipped, ran them on the fleet runner, and each template failed in a way
that reads as a repository problem rather than a template problem:

| Template | What happened on the runner | What an operator saw |
|---|---|---|
| `secret-validation.yml` | `install -m 0755 gitleaks /usr/local/bin/gitleaks` — Permission denied. The runner is rootless by design. | A red job, before any scan ran. |
| `drift-scan.yml` | `detect-host-ci.py` reports `runs-on:` values verbatim, so a host writing `runs-on: [self-hosted, devgate-rtp]` yields the single value `"[self-hosted, devgate-rtp]"`. The scan job asked a runner for that literal label. | Nothing. The job queued forever; a schedule that never runs is indistinguishable from a quiet repository. |

The first defect is a placement mistake: the framework's own `ci.yml` already
installs into `$RUNNER_TEMP` and appends `$GITHUB_PATH`; the template it ships
to consumers did not. The second is a type mistake: a YAML flow sequence is a
list of labels, and the template consumed it as a scalar.

Neither defect is visible on a GitHub-hosted runner, which is why they survived
until a fleet consumer ran the templates. That is the reason to fix them in the
framework rather than leave each consumer to rediscover them.

## What Changes

- **`templates/github-workflows/secret-validation.yml`** installs the
  checksum-verified scanner into `$RUNNER_TEMP/bin` and appends that directory
  to `$GITHUB_PATH`, matching the framework's own CI. The SETUP header states
  the constraint and names the measured failure.
- **`templates/github-workflows/drift-scan.yml`** resolves placement to a JSON
  array (`runner_json`) and the scan job consumes it with `fromJSON`. Flow
  sequences are split into their labels; `${{ ... }}` expressions are skipped
  (an expression is not a label); with no usable value the template falls back
  to `ubuntu-latest`. Distinct `runs-on:` values are alternative placements, so
  the first usable one wins whole — merging them would ask for a runner
  carrying labels from two different jobs at once, which is the same
  never-queues failure in another shape.
- **Two spec deltas** under `specs/ci-template-contract/` (`ci-tpl-01`,
  `ci-tpl-02`) and tests that execute the step bodies against stubbed tools,
  because a text assertion cannot distinguish "installed elsewhere" from
  "installed nowhere" and cannot observe a malformed output at all.

## What Does Not Change

- **No scanner pin change.** Version `8.30.1` and its checksum are untouched;
  `test_template_and_ci_name_the_same_scanner_pin` still holds the template and
  the framework's `ci.yml` together.
- **No gate behaviour change.** Both workflows still invoke the same gate with
  the same scope arguments; only where the binary lives and how a runner is
  selected changed.
- **No framework CI change.** `ci.yml` already had the correct scanner
  placement; this change brings the shipped template up to it.

## Impact

- Consumers on rootless self-hosted runners can run the secret gate as shipped.
- A host whose workflows declare a flow sequence gets a scheduled scan that
  actually runs.
- Coverage grows by two requirement IDs (`ci-tpl-01`, `ci-tpl-02`); the
  traceability ratchet is raised to match so deleting either test is a gate
  failure rather than a quiet loosening.
