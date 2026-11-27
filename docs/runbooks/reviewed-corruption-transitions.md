# Review an exact substitution in the corruption gate

This procedure applies to `fw-corruption-01` on a committed Git range. It lets the gate report a substitution that an independent reviewer accepted and continue enforcing other findings. The branch implements the evaluator. Fleet use needs upstream approval, a trusted controller and passing CI on the exact integration range.

## Give the reviewer the evidence

Supply the authenticated repository ID, full base and head commit IDs, path, whole-file Git blob ID at each end, and the resulting line number. The reviewer inspects both file versions and the surrounding change. Record the reason, decision owner, approving authority, expiry and remediation reference. For credential redactions, keep source values in the authorized repository and give reviewers the object references.

## Bind the evaluator to the review

A privileged controller selects the installed evaluator, uses the authenticated GitHub event to identify the repository and commits, and creates two external inputs. Grant write access to the controller alone. Run the evaluator under an unprivileged account separate from the job that executes subject code.

| Input | Fields the evaluator checks |
| --- | --- |
| `/etc/aiggp/corruption-reviews.json` | `api_version` is `aiggp.corruption-review-catalog/v1`. Each member of `exceptions` identifies the finding, its disposition and the independent review. |
| `/run/aiggp/corruption-reviews/<checkout-hash>.json` | `api_version` is `aiggp.corruption-review-binding/v1`. Supply the canonical absolute `checkout`, immutable `subject_ref` in the form `github:<host>:<numeric repository ID>`, full `base` and `head`, UTC `issued_at` and `expires_at`, and `catalog_sha256` over the catalog's raw bytes. The filename hash is SHA-256 of the canonical checkout path encoded with the filesystem encoding. |

A catalog record uses `exception_id`, `subject_ref`, `subject_path`, `assertion_id`, `finding_fingerprint`, `owner`, `reason`, `approving_authority`, `created_at`, `expires_at`, `remediation_ref` and `enforcement_treatment`. For this check the assertion is `fw-corruption-01` and the treatment is `EXCEPTION-ADVISORY`. The fingerprint repeats the assertion ID, uses integer `assertion_version` 1 and sets `subject_location` to the exact path. Its `violation_key` is `substitution-flip:<before-blob>:<after-blob>:<new-line>`.

The controller sets separate expiry times for the decision and the run binding under its approval-duration policy. The evaluator checks both validity intervals at the verdict. Root must own the inputs and their enclosing directories. Group and other users must have read-only access at most. Mount the **containing directories** read-only into the evaluator so atomic catalog replacements remain visible to an in-flight check. Independently audited provisioning establishes who can issue a decision.

## Run the comparison

Use the protected evaluator installed outside the subject checkout. Give it a local object database containing both commits and their file blobs. It reads those objects through a fresh bare repository using the system Git executable and fixed diff options.

```sh
python3 -I /opt/aiggp/scripts/check_corruption.py \
  --repo "$CHECKOUT" --reviewed-transitions --range "$BASE..$HEAD" --list
```

| Exit | Meaning |
| --- | --- |
| 0 | The comparison completed without a blocking finding. Each matched review appears as `VIOLATED EXCEPTION-ADVISORY` with its location and exception ID in the full report. |
| 1 | The comparison found a blocking change, such as another substitution or a bulk rewrite. Inspect the reported findings. |
| 2 | The evaluator could not validate its inputs. Check the checkout, commits, file protections, schema, catalog digest and validity times before issuing a fresh binding. |

Use `--list` for the audit receipt. The normal display caps detail and reports a total when it truncates the list. Run the separate whole-tree corruption and secret checks in CI. A single mass rewrite follows the existing warning policy or blocks when `--strict-mass-rewrite` is selected.

## Withdraw a decision

Remove or amend the record through the controller. Atomic replacement changes the catalog digest, which invalidates outstanding bindings. Issue a fresh binding against the current catalog for the next exact-range run. Retain the redacted report alongside the evaluator version, repository and range, catalog digest, decision reference and reviewer identity. Keep the subject change held while approval, protected provisioning or exact integration CI is pending.

## Repeat the protected filesystem test

The evaluator-image CI job runs this test on the rootless Podman runner. To repeat it locally, run the following from the repository root on a Linux host with rootless Podman.

```sh
python3 tests/protected_store_smoke.py --run
```

The build fetches the pinned Python base if absent and installs Git. The test container runs offline with a read-only root filesystem. It creates synthetic decisions under two empty in-memory mounts and invokes the real evaluator as an unprivileged user. The harness checks the ordinary blocking result, the exact advisory, atomic revocation, rejection of writable or symlinked policy, and rejection of a missing run binding. It removes the disposable image when the run ends.
