# Proposal: fix-coherence-container-contract

## Problem

A 2026-09-19 line-by-line review found a **critical, previously unreported
defect**: the pinned evaluation image cannot process any request.

`hub/coherence/__main__.py:24-25` and `hub/coherence/schemacheck.py:20-21`
resolve the frozen contract schemas as:

```
Path(__file__).resolve().parent.parent.parent / "openspec/changes/devgate-spec-coherence-service/schemas"
```

Two consequences:

1. **The image is broken.** `container/Containerfile` copies only `hub/`
   (`COPY hub/ ./hub/`, line 26). In-container, `parent.parent.parent`
   resolves to `/app`, so `SCHEMA_DIR` is
   `/app/openspec/changes/devgate-spec-coherence-service/schemas` — which does
   not exist in the image. Every invocation reaches
   `schemacheck.validate(req, _schema("request.schema.json"))`
   (`__main__.py:105`), raises `FileNotFoundError`, and is caught by the
   OSError handler at line 114 → exit 30 with the misleading reason
   `malformed request: [Errno 2] No such file or directory: '/app/openspec/...'`.
   The containerized execution path (S4's headline deliverable) can never
   return PASS/ADVISORY/FAIL on a valid request.
2. **The only real-container test cannot detect it.**
   `tests/test_hub_coherence_container.py::TestContainerExecReal` (lines
   405-438) feeds a deliberately-invalid request and asserts `rc == 30` /
   `decision == "ERROR"` — the same exit a schema-load failure produces. The
   test passes whether the service honestly rejects the request or cannot load
   its own contracts. (It also skips entirely when the image is not built
   locally, which is the default contributor environment.)

Additionally, the runtime path depends on schemas living **inside an ACTIVE
OpenSpec change package**. When `devgate-spec-coherence-service` is archived
(S8, per its own tasks.md), the directory moves to
`openspec/changes/archive/...` and the *host-side* CLI breaks the same way.
Runtime code must not depend on change-package layout; that coupling is a
landmine documented nowhere in the change's design.md.

## Solution

1. Move the 13 frozen schemas to a stable, shipped location owned by the
   service: `hub/coherence/schemas/` (they are runtime contracts, not change
   documentation; the change package keeps its copies until archive, or
   references the moved path).
2. Resolve `SCHEMA_DIR` relative to the package (`Path(__file__).parent /
   "schemas"`), which works identically host-side and in-container.
3. `COPY hub/ ./hub/` then carries the schemas into the image implicitly.
4. Rebuild the pinned image; update `container/execution-profiles.json`
   (`image_manifest_digest`, `built`).
5. Make the real-container smoke test honesty-preserving: add a **valid
   request → expected PASS (exit 0)** case beside the honest-rejection case,
   so a contract-loading failure can never masquerade as a pass. Assert the
   result bundle's `decision` and `error == null`, not just the exit code.
6. Add a build-time check (test or CI step) that the pinned image contains
   `hub/coherence/schemas/request.schema.json` and that
   `python -m hub.coherence --request <valid-minimal-request>` exits 0/10/20
   in-container.

## Impact

- `hub/coherence/__main__.py`, `hub/coherence/schemacheck.py` (path change),
  `container/Containerfile` (comment path note), git-mv of 13 schema files.
- `container/execution-profiles.json` (new digest after rebuild).
- `tests/test_hub_coherence_container.py`, `tests/test_hub_coherence_schema.py`
  (path updates + the new in-container PASS case).
- `openspec/changes/devgate-spec-coherence-service/tasks.md` — S4 regression
  note; unblocks the S8 archive step (spec publication) which currently would
  break the CLI on archive.
- Spec delta: adds `container-runtime` requirements
  (image self-containment + honest smoke evidence), MODIFYING the coherence
  change's own capability delta so the contract survives archive.
