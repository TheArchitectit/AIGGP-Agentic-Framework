# DG-10 offline verification evidence

**Reviewed tree:** public GitHub `main` was observed with `git ls-remote` on 2026-11-26 at `1b29c5ae1715cee7e2297654f9418dc429c5f5c1`. The detached worktree and Linux test scratch use that exact commit. Hashes below are SHA-256 of raw Git blob bytes read with `git cat-file blob <commit>:<path>`; they are independent of Windows checkout line endings.

## Spec boundary

The active draft is [`gitlab-runner-image-provenance/spec.md`](specs/gitlab-runner-image-provenance/spec.md). `glf-image-prov-01` requires signed provenance binding the immutable runner image digest to reviewed source, authorized build workflow identity, and an approved key/identity policy. `glf-image-prov-02` requires an offline preflight that rejects missing or mismatched provenance without claiming a live registry pull.

The current tree has ten GitLab mirrors pinned to `ghcr.io/aiggp/devgate-runner@sha256:4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b`. [`verify_gitlab_ci_template_mirrors`](../../../hub/forge/instance.py) checks that each GitHub template has a GitLab mirror and that its image reference is digest-pinned; [`test_gitlab_forge_support.py`](../../../tests/test_gitlab_forge_support.py) covers that mirror contract. These checks do not bind the runner-image digest to signed build provenance.

No matching runner-image build workflow, signed provenance statement, approved runner-image trust key/policy, or DG-10 verifier is present in this reviewed tree. The `glf-image-prov-*` identifiers occur in this active spec only; no enforcing source marker or requirement-specific provenance test was found. This repository-only observation does not establish whether an external builder or registry record exists.

## Offline fixtures exercised

The pytest commands ran in isolated Linux containers with `--network none`, against synthetic data and stubbed tools. No GHCR image was pulled, no live registry/host was contacted, and no production credentials were used.

| Fixture | Positive and negative behavior exercised | Result and scope |
|---|---|---|
| `tests/test_gitlab_forge_support.py` | Ten mirror files resolve from the GitHub template set and use digest-pinned images; mirror and webhook contract controls also run. | Included in the 109-pass run. Mirror parity/digest syntax only; no provenance or signature check. |
| `tests/test_runner_image_cycle.py` | Stubbed Podman image-cycle positive path; pulled digest mismatch, failed pull, malformed digest/tag, missing inputs, and unavailable tooling refuse convergence. | Included in the 109-pass run. Exercises local runner-store identity rules, not signed build provenance. |
| `tests/test_repin_operation.py` | Stubbed `curl`/Podman success and refusal cases; checks served digest rather than local-storage digest and rejects unavailable/partial identity changes. | Included in the 109-pass run. This is the evaluator-image re-pin operation, not the GitLab runner image. |
| `tests/test_oap_evidence_signature.py` and `tests/test_oap_trust_store.py` | Synthetic Ed25519 signing/verification and tamper, malformed key/signature, unknown, expired, revoked, and wrong-scope trust cases. | Included in the runs (signature suite in 109-pass run; trust store in 32-pass run). Generic OAP evidence trust contract, not runner-image provenance. |
| `tests/test_hub_coherence_attestation.py` | Synthetic attestation positive path plus substituted digest, wrong/unknown key, revoked and expired signer controls. | Included in the 109-pass run. Generic coherence-run attestation, not a builder provenance statement. |
| `tests/test_coherence_image_identity.py` | Execution-profile registry identity positive/mismatch controls and CI pin/fetchability fixtures. | Included in the 32-pass run. It concerns `localhost/devgate-coherence`, a different image. Its optional real-Podman smoke test was skipped because Podman is unavailable. |

Run results: the first five-file command reported **109 passed**; the two-file identity/trust-store command reported **32 passed, 1 skipped**. Together, **141 passed and 1 skipped**. The skipped Podman smoke is not treated as a pass. These adjacent fixtures show that local digest and generic signature/trust controls execute offline; they do not satisfy either DG-10 requirement for this runner artifact.

## Unresolved authoritative evidence

Keep DG-10 tasks 1.1–1.4 open. In particular:

- **NOT_RUN:** identify and independently review the authoritative source repository, builder workflow/revision, restricted build identity, and permission boundary for `ghcr.io/aiggp/devgate-runner`.
- **NOT_RUN:** obtain an authoritative signed provenance statement whose subject is the pinned runner-image digest; verify it against an approved builder identity and trust key/policy, including wrong-digest and wrong-signer negatives for this artifact.
- **NOT_RUN:** no DG-10 offline preflight exists here to test missing metadata, invalid signature, wrong signer, mirror digest mismatch, or mirror drift as one runner-image verification path.
- **NOT_RUN:** no DG-11 coordination/review or release-document reconciliation was performed. Mirror files were not changed.
- **NOT_RUN:** registry availability, live pulls, deployed production trust, and actual image contents were not queried or asserted.

Runner-image acceptance requires the authoritative signed statement and a DG-10-specific preflight.

## Source fingerprints at reviewed commit

| Path | Raw-blob SHA-256 |
|---|---|
| `openspec/changes/dg10-gitlab-runner-image-provenance/tasks.md` | `81ab961a468603e35879a285cfe2fc44914f4d7e3df918ad55e510009ff90d61` |
| `openspec/changes/dg10-gitlab-runner-image-provenance/design.md` | `ed0604ef34cc526845ea0f89cc34221ff7e332d3fcb5fe6a84d17ce644fee1c5` |
| `openspec/changes/dg10-gitlab-runner-image-provenance/specs/gitlab-runner-image-provenance/spec.md` | `49dc7ccb6079e1c6ed4c188e2174d168169125fd4909d13b5936ded21cba90c4` |
| `hub/forge/instance.py` | `29fa26ed478aa48622d62fab95055a46a6018342e4f41aee6bef4266025f23f4` |
| `tests/test_gitlab_forge_support.py` | `6af0f932fb98ec53fc67bddb7e0cfe61e45f279041e3674bc19fce76f8574efa` |
| `tests/test_runner_image_cycle.py` | `0bdc4cc4a0a8090b45612d698a9504ce59fdb92f1037dde40280c2c5112677ae` |
| `tests/test_repin_operation.py` | `4f23bb2e5d7c06b325dd33aefb6b700e79311d51893cb67ea18dec03f1ce08eb` |
| `tests/test_oap_evidence_signature.py` | `cda2ff8a9edbf4082d5e6079f98a6ccd5bd145b8b833cda1ef398ac1f6bdb35e` |
| `tests/test_hub_coherence_attestation.py` | `5a07246fff664a733476e9e1229442f298cd1309f3a8f5dfd54bb83036d619ce` |
| `tests/test_oap_trust_store.py` | `e3a710dd795d71b944ab8f4c7c33f8a6576db613136f4e51f24dda856b32bc25` |
| `tests/test_coherence_image_identity.py` | `3a33d9937b4cc085e746aa3df385c896b7e9d0869fc797ca1bab8ff19ef435b3` |

The active task links this offline baseline.
## Local repository gates

After adding this evidence file to the Linux-local checkout:

- `python3 scripts/regression_check.py --all` — **passed**, no potential regressions, 0 blocking hard-limit findings, 0 scope gaps, and no package vulnerabilities. Existing file-size warnings were reported for unrelated files.
- `python3 scripts/spec_traceability.py` — **261/304 requirements covered**; 43 are advisory uncovered items, including the active DG-10 requirements with no implementation marker. This is not a pass for DG-10 behavior.
- `python3 scripts/spec_index.py --check` — **passed**.
- `python3 scripts/spec_state_gate.py` — **passed** for the current local checkout.
- Pinned OpenSpec 1.14.3 `validate dg10-gitlab-runner-image-provenance --strict` — **passed**.
- Pinned OpenSpec 1.14.3 `validate --all --strict` — **81 passed, 0 failed**.
- `git diff --cached --check` — **passed** for the single staged evidence file.