# Design

**Version:** v2 (contract-freeze candidate) · 2026-09-17  
**Amends:** v1 as submitted. Every change from v1 is logged in "Amendment log" at the end, keyed to review findings R1–R9. ADR acceptance status is recorded in `adrs.md`; nothing here is self-accepting.

## Design principles

1. **Fail closed for required truth.** Missing package, missing assertion, unresolved subject, evaluator error, or incomplete evidence is not a pass.
2. **Determinism before breadth.** A smaller deterministic assertion set is better than a broad gate nobody trusts.
3. **Content identity over location.** Paths and branch names help discovery; digests establish identity.
4. **Policy outside repositories.** Repositories declare intent and local facts. Fleet policy decides minimum controls and enforcement.
5. **Evidence before opinion.** Every finding points to the assertion, subject location, observed value, expected value, and reproducer.
6. **Advisory is a stage, not a destination.** Every stage has entry, exit, owner, and expiry rules.
7. **One decision contract.** CI, fleet review, release promotion, and 3D pipelines consume the same result shape.
8. **No hidden repair.** The service evaluates. It does not modify source, specs, or artifacts.
9. **Identity is never self-referential.** No digest, approval, or attestation may include itself or its own downstream objects (R1).
10. **Time and stage are inputs, not ambient.** Anything policy-relevant that varies with time or adoption state enters through the signed evaluation context (R2).

## Context and flow

```text
Repository / artifact candidate
        |
        v
Subject resolver -----> immutable subject manifest (+ subject digest)
OpenSpec resolver ----> immutable package manifest (+ normative package digest)
Policy resolver ------> central bundle + validated overlay (+ policy digest)
Context issuer -------> evaluation-context manifest (+ context digest)   [control plane]
        |
        v
Pinned DevGate runtime (launcher-validated isolation profile)
  1. validate request + context (fail: 30/31/40)
  2. snapshot/verify inputs, build subject manifest
  3. plan assertion graph (structural + traceability checks)
  4. execute built-in evaluators with declared inputs only
  5. seal evidence -> evidence manifest digest
  6. compute canonical decision (ledger + findings)
  7. emit detached attestation (Stage >= 2 promotion-authorizing)
        |
        +--> decision + exit code (one matrix)
        +--> canonical result  |  run envelope (noncanonical)
        +--> CI check / fleet record / promote-or-halt consumer
```

Sealing order is acyclic and mandatory: **inputs → evidence objects → evidence manifest → canonical decision → detached attestation → transport envelope** (R1).

## Major components

### 1. Invocation adapter

Accepts a versioned request from CI, local tooling, fleet runner, or pipeline. Validates schema and protocol version (unsupported → exit 40 before any resolver runs), normalizes declared paths, refuses unknown required fields, and refuses caller-supplied `evaluation_time`, stage, or policy authority. Requested `mode` is advisory input only; the effective stage comes from the context (R2).

### 2. Subject resolver

Builds the immutable subject manifest: normalized relative paths, raw-byte SHA-256 per file, explicit policy outcomes for symlinks, submodules, generated outputs, large files, exclusions. Rejects path traversal and normalization collisions (exit 30). Snapshots or re-verifies digests at evaluator read time; mutation mid-run is ERROR (exit 32), never a mixed-content pass. Composite subjects (3D bundles) are part manifests digested under the canonical profile.

### 3. OpenSpec resolver

Finds the package through the invocation request or repository declaration; validates structure; resolves the import closure to digested content before evaluation (no lazy mutable imports); enforces the authenticated normative inventory so normative content cannot be reclassified as informative without changing the digest and invalidating approval (R6). Computes the normative package digest (canonical manifest + normative closure). Approval is verified against detached control-plane records, never against repository-declared `approval.state` (R4).

### 4. Policy resolver

Combines centrally managed minimum policy with an allowed repository overlay, both resolving from control-plane trust roots. Anti-rollback: older signed bundles are rejected unless explicitly grandfathered for a recorded window. Overlay may strengthen only. Policy resolution failures are exit 31.

#### S6 Cycle B — the anti-rollback binding (round-15)

The signed evaluation context is the only control-plane artifact the CLI consumes, so it is the trust root: at issuance the control plane binds a **`policy_binding`** record into the context — `{expected_digest, min_bundle_epoch, grandfathers[]}`, where `expected_digest` is the current central bundle's content digest, `min_bundle_epoch` is the floor resolved from that bundle's own `min_bundle_epoch` field, and each grandfather record is `{bundle_digest, valid_until, reason}` naming ONE older bundle and the window it stays acceptable. `valid_until` is evaluated against the context's `evaluation_time` (never the host clock, same doctrine as exception expiry). The bundle itself gains a required `bundle_epoch` — its self-declared ordinal, comparable against the bound floor.

Enforcement sits at policy resolution, after identity verification, and runs BOTH checks on the run path (ratified round-15: defense in depth — the digest check catches substitution, the epoch check catches a dishonest or buggy issuer binding; a grandfather record is the one exception to both):
- A context with **no** binding is a policy-substitution attempt — resolution fails exit 31 (coh-pol-02's scenario, literally: "no control-plane binding → resolution fails").
- Un-grandfathered: the pinned bundle's computed digest must equal `expected_digest` AND its `bundle_epoch` must be ≥ `min_bundle_epoch` (a bundle that does not declare an ordinal fails closed). Each failing check is rejected exit 31 with a reason prefixed `anti-rollback:` naming what mismatched, so the attempt is machine-visible to fleet reporting (the MonitorLoop check class added in a later S6 item alerts on the prefix; the envelope's `error.class` stays `policy-resolution` — no exit-matrix or error-enum change).
- Grandfathered: a record whose `bundle_digest` matches the pinned content and whose `valid_until` is in the future at `evaluation_time` accepts the bundle, exempting it from both checks — the recorded window is the exception mechanism the spec describes ("rejected unless explicitly grandfathered"); an expired record exempts nothing.

Consequences accepted: (1) every evaluation context issued from this slice on names its central bundle — a breaking context-contract change (`evaluation-context.schema.json` gains the required `policy_binding`; `policy-bundle.schema.json` gains required `bundle_epoch`), so fixtures, `issue.issue_context`, and hand-built contexts all gain bindings; a context that predates the field is rejected, never grandfathered by silence. (2) In the pilot stand-in, `issue.issue_context` computes the binding from the `policy.json` it is pointed at — the same operator-trust level as the stage registry; the authority is the ISSUER, and a deployment control plane binds its own published bundle. (3) The request's `policy.expected_digest` remains an identity claim verified against content; the context binding is the authority claim — the two failing together is the normal tamper case, and the request-side check still fires first.

### 5. Context issuer (control plane)

Produces the versioned evaluation-context manifest: trusted `evaluation_time`, effective adoption stage (from the authoritative adoption record), baseline and exception set identities, capability grants, captured external-fact digests, execution profile, supported-runner declaration. Issued or countersigned by the control plane, or derived deterministically from control-plane-published state at a recorded issuance time. Digested and bound like every other input (R2).

### 6. Assertion planner

Creates a directed acyclic assertion graph from package + policy + context. Planning-time checks (before any evaluator runs): duplicate IDs, missing dependencies, cycles, unsupported or unapproved evaluators, undeclared inputs, forbidden capabilities, assertion schema completeness, structural traceability (assertion ↔ normative requirement both directions). Planning failures are exit 30/31 per the matrix.

### 7. Evaluator runtime

Executes **bundled, reviewed, deterministic built-in evaluators** shipped in the pinned image by digest. No repository executable code, no network, no secrets by default (R5). Each evaluator receives only declared read-only inputs (enforced by the runtime mediator, not convention), deterministic environment values from the context, and granted capabilities. Limits: CPU, memory, time, files, processes, output size — exhaustion is ERROR (exit 32). A future plugin sandbox is a separate ADR with its own capability-isolation design; until accepted, "evaluator plugin" means built-in.

### 8. Decision engine

Applies one published total precedence matrix: ERROR-class conditions (invalid input, untrusted policy, evaluator/resource failure, evidence/signing failure) dominate FAIL-class within a run; FAIL > ADVISORY > PASS. Emits the `assertion_results` ledger (exactly one entry per planned required assertion: ID, version, outcome SATISFIED/VIOLATED/UNRESOLVED, reason code, enforcement) plus zero-or-many findings per assertion. Canonicalizes finding order and serializes under the canonical JSON profile. Assertion outcome is never rewritten by enforcement; exceptions attach enforcement metadata only (R3, ADR-005).

### 9. Evidence store adapter

Seals the evidence bundle inside bounded scratch: minimum-disclosure evidence objects, evidence manifest (objects by digest, media type, assertion ID, retention class; never hashes itself or downstream objects). Local sealing failure on an enforced finding is exit 33. Remote upload is retryable after sealing and never changes sealed digests; policy states per-stage whether confirmed remote durability is a promotion prerequisite. Where reproduction needs exact input bytes, an authorized retention channel stores the immutable input bundle separately from public evidence, under a distinct retrieval authorization; retention expiry invalidates cache reuse (R8).

### 10. Attestation emitter

Produces a **detached** signed statement binding: subject, package, policy, evaluation-context, evaluator image, canonical decision digest, evidence manifest digest. The canonical decision contains no attestation fields — the envelope references the detached attestation location. Required for every promotion-authorizing result from Stage 2 onward; Stage 0–1 observation runs may skip signing but are labeled non-promotion-authorizing. Verification checks the current approved signer set and fails closed on expiry or revocation (R1, R8). The evaluator image digest resolves through an ordered chain: `HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST` (container mode, authoritative — the actually-executed image) first, else the execution-profile registry pin for the context's declared profile (local mode — the "run the pinned runtime locally" equivalence); an undeclared profile fails closed at invocation.

## Trust boundaries

### Repository boundary

Repository files are untrusted input. They may declare package location, local assertions, and metadata, but cannot: disable central policy; select enforcement stage; supply trusted approval claims; choose evaluation time; pin obsolete policy (anti-rollback); select executable evaluators; or grant network access. Repository digests establish identity, never authority (R4).

### Container boundary

The container is ephemeral, non-root, read-only root, read-only input mounts; bounded scratch plus a designated bounded output location are the only writable filesystem. Capabilities dropped; privilege escalation, host sockets, sibling-container control, host networking forbidden. The **launcher/orchestrator establishes and verifies the effective security context outside the container**; container self-reporting is not trusted. A mismatch between claimed and effective context is a launch failure (R5).

### Evaluator boundary

Evaluators are built-ins allowlisted by immutable digest. The runtime mediator enforces declared-input-only access: an evaluator cannot discover extra inputs, read sibling inputs, access ambient environment or clock, or open sockets. Undeclared access is denied and recorded; required assertions depending on denied access end UNRESOLVED. Secret grants are per-named-capability, short-lived where possible, redacted from all evidence and logs. Network-dependent facts enter only as pre-captured, digested context facts (R5, R7).

### Control-plane boundary

Policy publication, evaluator approval, approval records, baselines, exception grants, adoption stages, context issuance, and signing keys belong to the control plane. A repository pull request cannot alter them. Enforcement anchoring (required checks, rulesets, promotion controller binding) is external configuration; deleting a workflow file does not delete the gate (R4).

## Deterministic execution contract

The runtime fixes or normalizes: image and evaluator digests; locale and encoding; time zone; file traversal and finding sort order; line endings **in canonical representation only — file digests commit to raw bytes**; JSON serialization (restricted RFC 8785 profile: sorted keys, no duplicates, UTF-8, int64 integers, single number format); pseudorandom seed when an approved evaluator declares sampling; CPU/memory/file/output/time bounds; declared clock behavior (context time only); network state (disabled); all input digests including the context digest (R6).

Domain-separated, versioned digest prefixes keep artifact roles from colliding: `subject-manifest/v1`, `package/v1`, `policy/v1`, `context/v1`, `evidence-manifest/v1`, `decision/v1`.

Wall-clock time may appear only in the noncanonical run envelope and never affects the canonical payload. Human prose may explain a result but never changes classification.

**Image identity:** the context records the image index digest (if any), the executed platform image manifest digest, and the execution profile label. Launch acceptance promises **byte-equivalence within one execution profile** and **semantic equivalence (decision, findings, ledger) across profiles** when declared; cross-profile byte-equivalence is not promised while platform digests legitimately differ (R6).

## Result states and exit matrix

| State | Exit | Meaning |
|---|---|---|
| `PASS` | 0 | all required assertions SATISFIED; advisory findings only where policy permits without changing top-level state |
| `ADVISORY` | 10 | ≥1 assertion VIOLATED/UNRESOLVED but current stage does not block |
| `FAIL` | 20 | ≥1 enforced assertion VIOLATED, missing, expired-exception, or UNRESOLVED from a successfully completed evaluation |
| `ERROR` (invalid input/package) | 30 | request, subject, or package untrustworthy |
| `ERROR` (policy resolution) | 31 | policy or context failed trust/validation |
| `ERROR` (evaluator/execution) | 32 | evaluator crash, limit exhaustion, input mutation, incomplete ledger |
| `ERROR` (evidence/attestation) | 33 | sealing, signing, or verification failure |
| `ERROR` (protocol) | 40 | unsupported `api_version` |

Precedence: within one run, ERROR-class conditions dominate FAIL-class; the result records **all** condition classes so the dominant one is explainable. A skipped required assertion is never PASS. An evaluator crash is never converted to advisory. Exceptions affect enforcement, not outcomes. Missing or malformed result with any exit code is ERROR for the caller. Exit/result disagreement resolves never in favor of the more permissive signal. In Stage 0 inventory mode, ERROR states change no release decision but MUST NOT be reported as a coherence authorization (R3).

Error runs emit a **structured error envelope**: stable error class, reason code, verified identities, and explicitly null/absent identities that could not be computed — never fabricated digests (R3).

## Assertion model

```yaml
id: product.current-game-identity
version: 1
requirement_refs:            # normative requirement IDs in the package
  - prod-identity-01
owner: portfolio-owner       # accountable human/team for this assertion
requirement: The shipped executable and primary documentation identify the same approved game.
subjects:
  - kind: file
    path: README.md
    extract: structured-metadata   # declared extraction rule, versioned
  - kind: artifact-metadata
    selector: product.name         # typed selector; empty resolution is UNRESOLVED
evaluator:
  id: devgate.builtin.identity-consistency
  digest: sha256:...
parameters:                  # validated against evaluator's published schema
  approved_value_ref: package:product.identity.name
  normalization: trim-casefold
severity: high
dependencies: []
finding_key: [assertion_id, subject_location, violation_class]
evidence:
  retention_days: 365
```

Identity assertions compare observed values against the **approved package value**, not merely against each other; two matching-but-wrong identities are VIOLATED (R7). Release-claim assertions bind the manifest to an inner build-payload digest before the outer subject digest, forbidding self-referential claims. Model-generated (including vision) output stays non-canonical advisory evidence unless rubric, model digest, inputs, and seed are pinned, captured, and replay-identical (R7).

## OpenSpec package identity

```yaml
schema_version: devgate.openspec.package/v1
package_id: com.vroger.gamerepo01
package_version: 2026.09.17
normative_inventory:        # authenticated list; reclassification changes the digest
  - path: specs/product-identity.yaml
    kind: normative
  - path: notes/history.md
    kind: informative
imports:
  - package_id: com.vroger.platform-core
    digest: sha256:...      # resolved to digested content before evaluation
```

Canonical package identity = normalized manifest + normative closure under the canonical profile; informative content digests separately as an archive digest. **Approval is detached:** a control-plane record binds (package digest, authority, repository scope, validity window). The package itself carries no self-referential `approved_revision` field (R1, R4).

## Request contract

```json
{
  "api_version": "devgate.spec-coherence/v1",
  "request_id": "caller-supplied-stable-id",
  "subject":   { "kind": "source-tree", "root": "/input/subject",  "expected_digest": "sha256:..." },
  "openspec":  { "root": "/input/openspec", "expected_digest": "sha256:..." },
  "policy":    { "root": "/input/policy",   "expected_digest": "sha256:..." },
  "context":   { "root": "/input/context",  "expected_digest": "sha256:..." },
  "semantics": "fresh-promotion",
  "outputs": "/output"
}
```

`request_id` is correlation only. There is no caller `mode` field: effective stage and time come exclusively from the context. `semantics` is `fresh-promotion` (current authority/revocation/expiry checked; may authorize) or `replay` (original context re-executed; byte-reproduces a historical decision; labeled non-promotion-authorizing unless re-attested) (R2).

## Canonical result contract

```json
{
  "api_version": "devgate.spec-coherence.result/v1",
  "decision": "FAIL",
  "semantics": "fresh-promotion",
  "subject_digest": "sha256:...",
  "openspec_digest": "sha256:...",
  "policy_digest": "sha256:...",
  "context_digest": "sha256:...",
  "evaluator_image_digest": "sha256:...",
  "platform": { "index_digest": "sha256:...", "manifest_digest": "sha256:...", "profile": "linux-amd64-v1" },
  "assertion_summary": { "planned": 43, "satisfied": 41, "violated": 2, "unresolved": 0 },
  "assertion_results": [
    { "assertion_id": "product.current-game-identity", "version": 1,
      "outcome": "VIOLATED", "reason": null, "enforcement": "BLOCK" }
  ],
  "findings": [
    { "assertion_id": "product.current-game-identity",
      "finding_key": "product.current-game-identity|README.md|identity-mismatch",
      "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
      "subject_locations": ["README.md:1-12", "artifact:product.name"],
      "expected": "approved identity 'Y' (package:product.identity.name)",
      "observed": "declared identities differ / unapproved",
      "evidence_refs": ["evidence/findings/product.current-game-identity.json"] }
  ],
  "evidence_manifest_digest": "sha256:...",
  "error": null
}
```

The ledger contains exactly one entry per planned required assertion; summary counts equal ledger tallies. Findings sort by assertion ID, subject location (defined path ordering), stable finding key. No timestamps, durations, hostnames, or attestation fields inside the canonical result; those live in the run envelope and the detached attestation reference (R1, R3).

**Error envelope** (same api_version family): `{ "decision": "ERROR", "error": { "class": "invalid-input", "reason": "...", "stage": "package-resolution" }, "identities": { verified digests, explicit nulls } }` — never a PASS/ADVISORY decision, never fabricated digests.

## Advisory-to-enforced ladder

Stages 0–4 as proposed (Inventory → Advisory baseline → Ratchet → Enforced core → Enforced full), with these amendments:

- Stage assignment is authoritative-record driven; requested mode cannot weaken it (R2/R4).
- **All promotion-authorizing results from Stage 2 onward require detached attestation** — resolving the v1 ambiguity between "required before enforced promotion" and "before Stage 3" (R8).
- Stage 2 ratchet operates on **finding fingerprints** (assertion ID+version, normalized location, content-derived violation key — never whole-subject digests or timestamps), with defined behavior for assertion-version increments and severity escalation of existing debt (escalation blocks or requires a new approved exception; never silently inherits advisory) (R9).
- Baseline entries are removed on accepted remediation; recurrence of a removed fingerprint blocks as new (R9).
- Repositories MUST NOT remain at Stage 1 indefinitely; central policy defines maximum advisory age; renewal requires owner, written reason, new expiry, control-plane approval. LobsterWars' 13 unenforced advisory violations remain the explicit anti-goal.

**The five modes ARE the five stages.** `inventory`/`advisory`/`ratchet`/`enforced-core`/`enforced-full` are names 0–4, one canonical ordinal axis — not a second, parallel knob. A mode name is a derived label computed from the authoritative stage record; nothing in the pipeline reads a name for behavior, and no input ever carries an authoritative mode (coh-ctx-02: stage comes from the record; requested-mode weakening is refused at issuance; a *stronger* request earns nothing — promotion is a control-plane act, never a repo's own ask). What each stage turns on, monotonically — each row is the diff to the previous stage:

| Stage | Mode | What turns on |
|---|---|---|
| 0 | `inventory` | Observe-only: every required assertion is planned and evaluated; all findings report `ADVISORY`; nothing blocks and no baseline exists yet. ERROR states change no release decision but are never reported as a coherence authorization (R3). Runs are non-promotion-authorizing. |
| 1 | `advisory` | The Stage-0 inventory is **ratified as a control-plane-approved baseline**; findings matching it are named debt (still advisory). The advisory-age cap and renewal regime (coh-pol-03) begins here — a repository MUST NOT park indefinitely, and Stage 1 is the dwelling state the cap is introduced to bound. Promotion 0→1 is the ratification act itself; the blocking behavior is unchanged. |
| 2 | `ratchet` | Enforcement begins **regressively**: a finding whose fingerprint is not in the baseline BLOCKS, as does `UNRESOLVED`; baseline-named debt stays advisory. Promotion-authorizing results now require detached attestation (`attest.required`: stage ≥ 2, fresh-promotion). The ratchet only tightens — baseline entries leave only via accepted remediation, and recurrence of a removed fingerprint blocks as new. |
| 3 | `enforced-core` | Baseline shelter stops applying to the **enforced-core assertion classes**: named debt in those classes BLOCKS like a regression. The core set is central policy (the bundle's `stages` data), defaulting to the Q2 freeze: product-identity consistency, traceability completeness, release-claim consistency — matched by evaluator ID, the identity every assertion already carries. Non-core named debt stays advisory. |
| 4 | `enforced-full` | Baseline shelters nothing: every `VIOLATED`/`UNRESOLVED` finding blocks. A scoped, expiring, control-plane-approved **exception** is the only softening path at this stage — `EXCEPTION-ADVISORY` survives at every stage because exceptions never rewrite outcomes (coh-eval-05); what stages 3–4 remove is a repository's inherited-debt shelter, never a control-plane's written approval. |

Invariants across the whole ladder: the decision/exit matrix, ledger shape, and fingerprint semantics are identical at every stage — only the shelter surface shrinks; evaluation time and stage enter exclusively through the signed context (R2); severity floors and anti-rollback (`min_bundle_epoch`) are separate policy mechanisms, orthogonal to the mode axis, and this section does not decide them.

### Advisory-age escalation (round-16, ratified)

coh-pol-03 is a **policy** mechanism, not a ladder stage, so it lives beside
the severity floor rather than inside `stages`. `stages.max_advisory_age_days`
is only a duration; it says how long an advisory sits, never what expiring
does. The escalation is a top-level `advisory_escalation` object in the
bundle:

```json
"advisory_escalation": {
  "on_expiry": "block",
  "renewal": { "requires": "central-approval", "max_extension_days": 30 }
}
```

- `on_expiry` is a **closed enum**, initially `block` alone. One value that
  means what the spec says, and future values are considered on their merits
  rather than pre-guessed into a vocabulary now — the field exists so the
  policy is expressible, not so today's single behavior gets a synonym.
- **It is deliberately not an optional field.** Presence of the age cap
  requires it (schema `dependentRequired`) and the service refuses a bundle
  that declares a cap without a policy — exit 31, `advisory-escalation:`
  prefix. A bundle that names a dwell limit but no consequence for exceeding
  it is incomplete configuration, and silence must not read as "cap declared,
  nothing happens" — the same standing as a missing `policy_binding`, which
  refuses rather than evaluating without it.
- **Absent `advisory_escalation` is meaningful in one direction only**: a
  bundle with no `max_advisory_age_days` at all has no cap and therefore
  nothing to escalate. Absence never means "expire silently".
- **The escalation is stage-invariant from Stage 1 up.** Expiry changes
  enforcement the way an expired exception does — the shelter is removed and
  the violation BLOCKS — because the shelter is the thing being protected. At
  Stage 0 nothing blocks at all, so an expired advisory is reported and
  nothing follows; from Stage 1 the age is measured, and from Stage 2, where
  a ratchet exists to withhold shelter, the escalation bites
  (`adoption.evaluate`'s `stage < 2` arm is unchanged and still comes first).
  **Normative disambiguation (round-16):** coh-pol-03's scenario requires
  blocked promotion when the age is exceeded and is written in terms of
  "advisory-stage promotion", not in terms of the Stage-1 ordinal —
  `report.advisory_status`'s early return for `stage != 1` implements the
  *reporting* reading of "advisory stage", and that reading must not be
  stretched into the enforcement path, where it would make the cap inert for
  every repository that had already reached the ratchet — exactly the ones
  the rule targets.
- Expiry is judged against the context's `evaluation_time`, never the host
  clock — the service's standing rule, and the reason the age data must reach
  `adoption.evaluate` through the signed context rather than being recomputed
  at the call site.
- **An unexpired renewal is an exception**, not a second mechanism: it is the
  existing scoped, control-plane-approved, expiring exception record, which
  already survives the cap because exceptions never rewrite outcomes
  (coh-eval-05). `renewal.max_extension_days` bounds what an approving
  authority may grant; it does not create a parallel record type.

An advisory that expires with no covering exception blocks as a regression
does — `BLOCK`, on both new and existing required violations, which is what
"new AND existing" in the spec requires and what a per-finding shelter
removal naturally produces.

## Exception model

An exception binds: repository/subject identity; assertion ID and optional subject path; finding fingerprint; owner; reason; approving authority; creation and expiry; enforcement treatment; remediation reference. Wildcards forbidden. Expired/mismatched/malformed exceptions FAIL in enforced modes. Exceptions never rewrite VIOLATED to SATISFIED — enforcement becomes `EXCEPTION-ADVISORY` with the exception identity recorded.

## Service availability

In enforced mode, inability to produce a trustworthy result blocks promotion. Anti-fragility: evaluator images and policy bundles are content-addressed and mirrorable; callers may run the pinned runtime locally; normal evaluation has no online dependency; evidence upload retries after sealing. **Cache reuse requires the complete bound key** — subject, package, policy, context, evaluator image, plugin digests, captured-fact digests — plus TTL, retention validity, and signer validity. The v1 four-digest key is insufficient (R2/R8).

## Observability

Operational metrics: duration, resource use, cache behavior, evaluator failure rate, advisory age, exception age, findings by assertion class. Telemetry MUST NOT contain source content, secrets, evidence payloads, or unredacted excerpts. Metrics never affect deterministic classification.

## Fleet integration notes (DevGate-Agentic-Framework)

Confirmed against fleet reconnaissance on 2026-09-17 (sources: framework repo + private `TheArchitectit/infra-info`):

- **Hub is live on dell-u2** (`devgate-hub.service`, bound to `127.0.0.1:8443` + Tailscale `100.85.128.54:8443` only), deployed as a Podman quadlet. Runners are GitHub Actions agents in rootless Podman quadlets (`ghcr.io/actions/actions-runner`), repo-scoped, durable registration.
- **dell-u2 is the gateway box**, hosting the hub and multiple repo-scoped runners: `dell-u2` (this framework), `dell-u2-mc` (missioncontrol), `dell-u2-game` (**gamerepo01**, labels `devgate-game`). gamerepo01 is a real registered fleet repo — the coherence pilot's motivating subject exists in the fleet. The lineage-mismatch narrative remains uncaptured (R9 provenance still applies: synthetic fixture until captured from the real repo with owner approval).
- **Hub monitoring** (`hub/monitor.py` `MonitorLoop`, 60s poll) runs four check classes per registered repo: runner online+heartbeat, queue drain, gate/check-run conclusions, drift-scan recency. Coherence integrates as a **fifth check class** (e.g. `_check_spec_coherence(repo, owner)`) polling the check-runs API for a coherence workflow conclusion on watched branches, alerting via the existing `_raise_alert` → `AlertSink` path (deduped by `(repo, check-class, runner)`, GitHub issues + JSONL). This satisfies `coh-int-07` (per-repo independence).
- **Runners are repo-scoped** — one runner cannot evaluate another repo's subject; the hub iterates registered repos independently. Stock `runner-enroll.sh` is single-runner-per-host (fixed unit names); multi-runner hosts already diverge to per-runner units (`devgate-hb-<name>.{service,timer}`). New spoke enrollment for coherence must account for this.
- **CI side**: gates run as job steps in workflows targeting `runs-on: devgate` (or repo labels), following the `templates/github-workflows/drift-scan.yml` pattern. The fleet CI-template contract (`ci-run-01`) requires every named gate to execute or report explicit SKIPPED — encoded as `coh-int-06`. `HUB_WATCHED_BRANCHES` controls which branches are checked (dell-u2 overrides to `main`).
- **Constraints honored**: stdlib-only (`urllib.request`, `secrets`, `hmac`); `HUB_*` env convention; `// spec: coh-*` markers in Python source; 500-line hard / 300 soft file budgets (the `hub/coherence/` split in tasks.md S2 keeps each module under budget); instance state (`runners.json`) never committed.
- **Traceability marker convention confirmed**: delta specs use `<!-- id: <domain>-<topic>-<nn> -->`; archived change specs use numbered filenames (`01-<topic>.md`) while this package uses `specs/<capability>/spec.md` — both layouts are scanned by `spec_traceability.py` (`changes/*/specs/**/*.md`), so the `coh-*` IDs register correctly. Scoped counts at head 7981431 (2026-09-17 re-measure, replacing the stale "62 IDs" note): **64 unique `coh-*` IDs in this active package** (64 `### Requirement` blocks, 64 marker lines, all distinct). The **repository-wide** traceability run is a separate total and is **volatile by design** — it moves with every package delta and marker addition, so pin each citation: measured **49/100 covered, advisory** at head `0db45ed` (was 48/99 at `7981431`; `b24ef75` added the coh-assert-06 marker → +1 covered; `a2fc2a0` added the add-runner-to-fleet package with uncovered `fleet-add-01` → +1 total). The 100 counts requirement markers across every active change in the repo, not just this package's 64; do not conflate the two numbers. (Round-5 finding 1; re-measure at every gate rather than quoting stale pins.)

## Amendment log (v1 → v2)

| Finding | Amendment |
|---|---|
| R1 | Acyclic sealing order; detached attestation outside canonical decision; detached approval records; evidence manifest never hashes downstream |
| R2 | Evaluation-context manifest as bound input; context issuer component; `semantics: fresh-promotion/replay`; complete cache key; no caller `mode` |
| R3 | Single decision/exit matrix with ERROR-class precedence; `assertion_results` ledger; structured error envelopes with explicit nulls; Stage 0 error reporting rule |
| R4 | Authenticated policy authority; anti-rollback; external enforcement boundary; approval verified against control-plane records |
| R5 | Built-in evaluators only until a plugin-sandbox ADR; launcher-validated isolation; runtime-mediated declared-input-only access; output handling in scratch |
| R6 | SHA-256 + restricted RFC 8785; raw-byte file hashing; domain-separated digests; frozen import closure; authenticated normative inventory; input mutation = ERROR; index vs platform identity; byte-equivalence within profile, semantic across |
| R7 | Operational assertion schema (requirement refs, owner, typed selectors, finding keys); approved-value comparison; release-claim binding order; planning vs post-seal traceability; model advice non-canonical |
| R8 | Attestation required for promotion-authorizing Stage 2+; offline sealing in slice 1; retryable upload; authorized input retention distinct from public evidence; retention expiry invalidates cache |
| R9 | Fingerprint definition and lifecycle (version increment, severity escalation, recurrence-after-fix); provenance rules for pilot baselines (see acceptance.md) |

New capability specs added in v2: `canonical-identity`, `decision-contract`, `evaluation-context`, `assertions-and-evaluators`, `subjects-3d`.

### Implementation progress notes (post-freeze, no contract change)

Recorded so the frozen design stays the single reading of the contract while
implementation history stays visible. Full ledger: `s3-delivery.md`.

- S3 `85b9cda`: `issue.py` ships an HMAC countersignature as a **labeled
  stand-in** for the control-plane signature (coh-ctx-02); the primitive is
  replaced in S5/ADR-018, the contract (bound sets, downgrade refusal,
  signature-required-when-key-configured) is not.
- S3 `85c6f5e`: replay equality pinned as **field-level across semantics**
  (decision fields match; context/semantics digests differ by design) and
  byte-level only fresh↔fresh (coh-ctx-03). An earlier doc claim of
  byte-identity across semantics was wrong and is corrected here, not in the
  spec text.
- S3 `b538c79`: gate posture decided — coherence advisory until demo review
  + S4 container close; published-spec creation deferred to S8 archive
  (measured GD-3 double-count).
- S6 round-18 (CI gate could not execute): the Request contract above was
  always correct — seven fields, four `inputRef` roots each with a mandatory
  `expected_digest`. The CI template as first shipped (`07d1275`) violated it
  (three fields) and carried two further fatal defects that are execution
  mechanics, not contract, recorded here so the frozen design stays the single
  reading of what a request IS while this notes what a request must be fed
  through:
  - **Mount topology.** A containerized run names FOUR read-only mounts —
    subject→`/input`, openspec→`/openspec`, policy→`/policy`,
    context→`/context` (targets are free-form but unique;
    `launcher._validate_mounts` requires each entry's `readonly` to be the
    literal `true` and rejects a duplicate target). `/output` is NEVER in the
    `mounts` list — the launcher adds it itself as the one writable bind
    (`podman_args`, `launcher.py:259`), and `run_containerized` rejects an
    output dir that falls inside any input mount source.
  - **Digest provenance within the request.** subject/openspec digests are
    self-computed on the host from repo content (`manifest.build`/
    `package.resolve`, no signing). The policy `expected_digest` MUST be read
    from the context's signed `policy_binding`, never recomputed from the policy
    bytes the same fetch returned — recomputing it makes the identity check a
    tautology and discards the `check_anti_rollback`/`verify_bound_sets`
    authority the signed binding carries.
  - **Invocation form.** The in-container CLI is `python -m hub.coherence` (the
    image's own ENTRYPOINT); `python hub/coherence/__main__.py` is an
    ImportError (relative imports need a package context). Host-side, the pinned
    clone is invoked with cwd/PYTHONPATH at the clone root.
  - **Schemas are part of the image.** `schemacheck.SCHEMA_DIR` resolves OUTSIDE
    `hub/` (into `openspec/changes/.../schemas`), so `COPY hub/` alone ships an
    image whose CLI cannot load its own frozen contract — the F1 regression
    (`ci.yml` "it once shipped without them"), which the CI guard for it could
    not catch because that job self-skips on runners without podman. The
    Containerfile must COPY the schema dir alongside `hub/`; this changes the
    image bytes, so `execution-profiles.json` + the template digest are
    re-pinned together on the next (fleet, publish-gated) rebuild.
