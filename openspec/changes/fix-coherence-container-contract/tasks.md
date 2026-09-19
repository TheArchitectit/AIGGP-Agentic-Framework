# Tasks: fix-coherence-container-contract

## 1. Stable schema home

- [x] 1.1 `git mv openspec/changes/devgate-spec-coherence-service/schemas
       hub/coherence/schemas` (13 files); leave a pointer note in the change
       package so its docs stay navigable.
- [x] 1.2 `hub/coherence/__main__.py`: `SCHEMA_DIR = Path(__file__).parent /
       "schemas"`; delete the change-package path and its comment.
- [x] 1.3 `hub/coherence/schemacheck.py`: same resolution.
- [x] 1.4 Grep the tree for the old path string; update
       `tests/test_hub_coherence_schema.py` and any docs/design references.
- [x] 1.5 Host-side regression: full `pytest tests/test_hub_coherence*.py`
       green (schema negative controls still fire).

## 2. Image rebuild and identity

- [ ] 2.1 Rebuild with the documented reproducible-ish invocation
       (`podman build --timestamp 0`), record the new manifest digest +
       `built` date in `container/execution-profiles.json`.
- [ ] 2.2 Verify in-container: `podman run --rm --read-only ... <image>
       python3 -c "from hub.coherence import schemacheck;
       schemacheck.load('request.schema.json')"` succeeds.

## 3. Honest smoke evidence

- [x] 3.1 Add `TestContainerExecReal::test_incontainer_valid_request_passes`:
       fixtures A-class valid request mounted through the launch contract →
       expect exit 0 (or 10 with a documented advisory), `decision != "ERROR"`,
       `error is null`, and `result.json` present in the output bind.
- [x] 3.2 Keep the exit-30 rejection case but tighten it: assert the envelope
       reason names the *invalid field*, not a FileNotFoundError — so a
       missing-schema regression fails this test.
- [x] 3.3 CI: `.github/workflows/ci.yml` job `container-image` builds the
       pinned image on every PR and runs the in-image schema check (3.1's
       real-container PASS case needs the identity registry to match — that
       stays publish-gated, see 2.1/2.2).

## 4. Change-package reconciliation

- [x] 4.1 Append an S4 regression entry to
       `openspec/changes/devgate-spec-coherence-service/tasks.md` recording the
       defect (image could not load contracts; only-detecting-blind smoke
       test) and the fix.
- [x] 4.2 Confirmed: `grep -rn "openspec/changes/.*schemas" hub/` is empty —
       runtime resolves schemas package-relative, so archiving the change
       (S8 spec publication) cannot affect the CLI or the image.
- [x] 4.3 Failure-registry entry for the incident class
       ("smoke test asserts an exit code achievable by a broken service").

## 5. Spec delta

- [x] 5.1 `specs/container-runtime/spec.md` delta (see specs/ in this change):
       ADDED requirements `coh-rt-08` (image self-containment) and
       `coh-rt-09` (container smoke evidence must include a valid-request
       success path), so the contract is enforceable after archive.
