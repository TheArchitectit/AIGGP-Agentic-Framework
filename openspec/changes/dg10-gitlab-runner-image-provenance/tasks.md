# Tasks

## 1. Implementation and verification

- [ ] 1.1 Identify authoritative image source/build workflow; review build identity and minimum permissions and verify source is independently reviewable.
- [ ] 1.2 Publish signed provenance binding source revision, workflow and builder identities/permissions to the image digest; verify signature against the approved trust key and identity policy, with explicit wrong-digest and wrong-signer negatives.
- [ ] 1.3 Implement offline preflight over local signed provenance, approved trust material, and all GitLab mirrors; verify missing metadata, bad signature, wrong signer, digest mismatch, and mirror drift fail without registry access or a live-image claim.
- [ ] 1.4 Coordinate with DG-11 so provenance/digest edits to shared GitLab mirror files do not overwrite bootstrap changes; verify responsibilities and file changes are separated in review. Reconcile release docs; verify digest, signer/source binding, provenance reference, and offline-check limitations are clear.
