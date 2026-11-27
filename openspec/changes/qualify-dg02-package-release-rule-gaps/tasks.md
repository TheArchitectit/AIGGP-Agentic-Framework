# Tasks

## 1. Package resolution

- [ ] 1.1 Exercise missing packages, moving references and expected-digest matching through the service entry point (`coh-pkg-01`).
- [ ] 1.2 Validate two normative files with conflicting and identical duplicate IDs, reference failures, dependency cycles and declared approval state before evaluation (`coh-pkg-02`).
- [ ] 1.3 Verify normative digest stability for informative changes and separately record full archive digest behavior (`coh-pkg-03`).
- [ ] 1.4 Resolve the entire frozen import closure to content, reject digest mismatches with expected and actual digests, and reject and name cycles. Test missing imports and nested closures (`coh-pkg-04`).
- [ ] 1.5 Enforce and test the normative/informative classifier and authenticated inventory, including a requirement-bearing file classified informative, omitted files and approval invalidation (`coh-pkg-05`).

## 2. Release and registry safety

- [ ] 2.1 Reconcile the failed-upload abort contract and PyPI retry path. Test one successful upload, failed upload, build failure, partial or unknown remote outcomes, and post-publish errors using isolated fake registries. Record limits of what the client can prove (`rel-upload-01`).
- [ ] 2.2 Exercise empty, missing and absent artifact contracts and verify no vacuous success (`rel-artifact-01`).
- [ ] 2.3 Verify all 7–40 character non-sentinel fix commits against the entry owner's repository, including project overlays and unavailable history. Test bundled and overlay repositories independently (`rel-fixcommit-01`).
- [ ] 2.4 Exercise consumer violations and dirty submodule cases through the real deploy entry point without publishing (`rel-target-01`).
- [ ] 2.5 Prove runtime HIGH and dev-only advisory outcomes through the pre-commit exit path (`rel-audit-01`).

## 3. Rule coverage and proof

- [ ] 3.1 Test that enabled semantic rules without registered checkers fail by ID and verify enforcement coverage for every shipped enabled ruleset (`rule-truth-01`).
- [ ] 3.2 Map each former behavior rule to a documented skill template and test the complete mapping (`rule-behavior-01`).
- [ ] 3.3 Bind each requirement's historical claim to an accepted evidence bundle and expected digest, independently validate it, and submit only qualified transitions to the state gate.
