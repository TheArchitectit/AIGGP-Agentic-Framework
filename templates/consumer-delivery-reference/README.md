# Synthetic hosted consumer

This fixture exercises a small Python CLI and its consumer-owned hosted checks. From the framework checkout, create it in an empty directory with:

```sh
python3 templates/consumer-delivery-reference/materialize.py /tmp/aiggp-reference-consumer
```

The materializer creates a local Git repository, prints its consumer commit, and prints the DevGate commit used by the copied workflow. Pass `--devgate-sha <full-40-character-SHA>` only when intentionally exercising another commit present in the local object database. The generated repository contains the consumer files and workflows; this README and the materializer are deliberately excluded.

## Pilot approval and scope

The owner-approved DevGate pin for this pilot is `bdbd450e0275a05b319ce29d83f761e8ed552e69`. The originally proposed pin was `80d18b0f0f4e080c9e47d4e534cc2c56c29308ca`. The published `templates/github-workflows/text-integrity.yml` at those two commits has Git blob `5d5076ddfb6cc611653040e02c724f3e2f8c90ce` at both commits. Materialization replaces only its SHA placeholder with the approved pin.

That approval selects a tool revision for this synthetic reference consumer. It does not select or authorize an external repository, establish required-check branch protection, qualify a non-hosted runner or another forge, or approve a production deployment.

## Checks and controls

The generated GitHub Actions workflows target `ubuntu-latest` and use synthetic data only. They expose these check names for a disposable consumer configuration:

- `Text Integrity` — charset, encoding, and corruption gates over the app, tests, workflows, and `.guardrails/` overlay. The overlay denies U+00A7. The single em-dash allow row preserves typography already present in the exact published workflow.
- `Reference Consumer` / `Synthetic source behavior` — runs the two real-entry-point behavior tests and invokes `app.py` on valid and invalid input. The invalid input must return a nonzero status.

The framework regression test materializes the repository, checks the generated workflow against the pinned Git object, runs the behavior tests, and adds a generated U+00A7 fixture to confirm the real charset gate rejects it. The [hosted pilot record](../../openspec/changes/qualify-consumer-delivery-evidence/hosted-pilot.md) names the protected branch and links the runs.
