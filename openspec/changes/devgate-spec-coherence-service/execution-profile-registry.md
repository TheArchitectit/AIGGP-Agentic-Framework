# Execution-profile registry

**Status:** proposed for owner decision (acceptance Q5) · 2026-09-17
**Governs:** coh-id-04 (image and platform identity), determinism equivalence promises.

An execution profile names an equivalence class of runners: the platform image manifest digest, the architecture, and the equivalence promise attached to that class. The evaluation context carries exactly one `execution_profile` label; the canonical result records both the image **index** digest and the executed platform **manifest** digest.

## Equivalence promises

| Promise | Meaning |
|---|---|
| `byte-equivalent` | Two runs on members of this profile produce byte-identical canonical result bytes and evidence manifest digests. |
| `semantic-equivalent` | Two runs agree on decision, assertion ledger, and findings, but canonical bytes may differ (e.g. platform digests differ across architectures). |

Byte-equivalence is promised **within** a profile; cross-profile equivalence is at most semantic. Cross-profile byte-equivalence is explicitly NOT promised while platform manifest digests legitimately differ.

## Registry

| Profile label | Architecture | Runner platform | Image manifest digest | Equivalence | Status |
|---|---|---|---|---|---|
| `linux-amd64-v1` | amd64 | actions-runner rootless Podman (dell-u2, ai01–ai03) | `<pinned at build, S4>` | byte-equivalent | proposed |
| `linux-arm64-v1` | arm64 | TBD — owner decision Q5 | `<pinned at build, S4>` | byte-equivalent | pending owner decision |

## Owner decision (Q5)

Which architectures must be byte-equivalent at launch. Current proposal: launch with **only `linux-amd64-v1` byte-equivalent** (the existing fleet is amd64); treat arm64 as a declared semantic-equivalence profile only, added when a second architecture is actually provisioned. Do not declare arm64 byte-equivalence until an arm64 runner exists to verify it.

## Rules

- A profile MAY NOT be added without a provisioned runner of that architecture to verify the claim.
- Removing a profile requires a deprecation entry and a compatibility note (see Sprint S8 compatibility policy).
- A runner whose platform matches no registered profile is rejected at invocation (exit 30), per `canonical-identity/spec.md` scenario "undeclared profile".
