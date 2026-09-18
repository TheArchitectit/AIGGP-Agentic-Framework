# New Repository Onboarding

> How to wire DevGate into a **new or existing repository** so the gates actually
> execute, the overlay stays clean, and OpenSpec packages carry verifiable identity.

**Related:** [RELEASE_GATE.md](./RELEASE_GATE.md) | [WRITE_AUDIT_REVIEW.md](./WRITE_AUDIT_REVIEW.md) | [AGENTS.md](../AGENTS.md)

---

## The one rule that breaks onboarding

**The submodule MUST live at `.devgate/`.**

Every gate resolves the project root as *the parent directory of `.devgate/`*.
A submodule checked out at `devgate/`, `vendor/devgate/`, or any other name makes
every gate scan the wrong tree (or walk upward into a sibling project). Several
scripts fail closed on this; the semantic scanner silently resolves to the parent
repo — see `known-gate-defects.md`. There is no config that fixes a wrong path.

```bash
# correct
git submodule add <devgate-url> .devgate

# wrong — gates will not find your project
git submodule add <devgate-url> devgate
```

---

## Layout

```
<project>/
├── <your source>              ← any language, any structure
├── package.json|Cargo.toml|pyproject.toml|go.mod|project.godot
├── .devgate/                  ← the submodule (fixed name)
└── .guardrails/               ← THIS project's overlay (never inside .devgate/)
    ├── failure-registry.jsonl
    ├── prevention-rules/
    │   └── pattern-rules.json
    └── openspec/
        ├── gate-config.json
        └── changes/<change-id>/
            ├── spec.md
            ├── tasks.md
            ├── package.json          ← identity (see below)
            └── specs/<capability>.md
```

The overlay is merged **over** the bundled baseline by `scripts/gate_overlay.py`;
the overlay wins on `rule_id` / `failure_id` collision. Never edit files inside
`.devgate/` to customize behavior — that is what the overlay is for
(`gate-configuration-contract` / `rule-config-01`, `doc-truth` / `doc-overlay-01`).

---

## Step 1 — Add the submodule and the overlay

```bash
git submodule add <devgate-url> .devgate
mkdir -p .guardrails/prevention-rules
mkdir -p .guardrails/openspec/changes
touch .guardrails/failure-registry.jsonl
```

Add the secrets ignore patterns **before** the first gate run — the forbidden-file
check will otherwise block on a stray `.env` (and it should):

```gitignore
.env
.env.*
!.env.example
*.pem
*.key
```

---

## Step 2 — Verify the gates run against *your* tree

```bash
node .devgate/scripts/guardrails-scan.mjs
node .devgate/scripts/semantic-scan.mjs
python3 .devgate/scripts/regression_check.py --all --pre-commit
bash .devgate/scripts/silent-success-scan.sh
```

Confirm each reports **your** file paths. A gate that scans a sibling repository
is not passing — it is not running (`gate-execution-contract` / `gate-root-01`).

A gate that evaluated zero inputs is **not** green (`gate-vacuous-01`). On a clean
tree `regression_check.py --staged` reports *NOTHING SCANNED*; that is no evidence.
Use `--all` or `--base <ref>`, and `--fail-if-empty` in CI.

---

## Step 3 — OpenSpec package identity (checksums)

Specs are only enforceable when their identity is verifiable. Follow the
canonical-identity contract of the spec-coherence service
(`openspec/specs/.../canonical-identity`, ids `coh-id-01`…`coh-id-05`).

**Two files per change package:**

`specs/<capability>.md` — requirements carry `<!-- id: ... -->` markers so
`spec_traceability.py` can find them:

```markdown
## Requirement: Blitz ends at 30 seconds
<!-- id: mode-end-01 -->
...
```

`package.json` — declares which files are **normative** (part of the contract)
and which are **informative** (record-keeping only):

```json
{
  "schema_version": "devgate.openspec.package/v1",
  "package_id": "myproject.change-id",
  "package_version": "1.0.0",
  "normative_inventory": [
    { "path": "specs/capability.md", "kind": "normative", "digest": "sha256:<64 hex>" },
    { "path": "tasks.md",            "kind": "informative", "digest": "sha256:<64 hex>" }
  ],
  "imports": []
}
```

Digests are **raw-byte SHA-256**:

```bash
sha256sum specs/capability.md | cut -d' ' -f1
```

**Rules that matter:**

- A `kind: normative` file changing by **one byte** invalidates the package's
  approval and changes the package digest (`coh-id-03`). Update the digest in the
  same commit that changes the spec, or the gate fails.
- `tasks.md` is *informative* — checkboxes flip constantly, so it digests
  separately and does not gate anything.
- `imports` carry the resolved digest of a superseded package. A placeholder
  digest (`sha256:000…0`) is reported **UNRESOLVED**, never as verified.
- Approval is **detached** — the package carries no self-referential
  `approved_revision` field (`coh-pkg-03`, `coh-pkg-05`).

### Reference implementation

`.guardrails/scripts/verify-package.py` implements the canonical profile
(sorted-key RFC 8785 JSON, domain-separated `package/v1` + `subject-manifest/v1`
prefixes) and exits `0` verified / `1` violated / `2` malformed. Copy it into a
new repo's `.guardrails/scripts/` and wire `verify-all-packages.sh` into CI.

---

## Step 4 — Traceability gate

Create an `openspec/` symlink at the project root so the traceability gate finds
the standard layout while specs still live in the overlay:

```bash
ln -s .guardrails/openspec openspec
```

Requirement IDs are only **covered** when a source file carries a marker in its
own comment syntax (`rule-coverage-truth` / `rule-marker-01`):

```javascript
// spec: mode-end-01 — enforced in update.js game-over path
if (shouldEndGame()) { ... }
```

```python
# spec: score-san-01
```

```sql
-- spec: score-migrate-01
```

Set enforcement in `.guardrails/openspec/gate-config.json`:

```json
{ "specs": { "my-capability": "blocking" } }
```

Advisory is for adoption. A capability with an owner and a deadline should be
`blocking` — an advisory finding with no promotion rule becomes permanent bypass.

---

## Step 5 — CI wiring

Run the gates **before** the test job so a spec/pattern violation fails fast.
Self-hosted runners are the fleet standard where the account has no hosted
minutes (`runs-on: [self-hosted, devgate]`); see the runner template under
`templates/runner/`.

Ordering that works:

1. `verify-all-packages.sh` — identity (fast, fails on stale digest)
2. `spec_traceability.py` — coverage (fails on a claimed-but-unmarked requirement)
3. `guardrails-scan.mjs` + `regression_check.py --all --pre-commit`
4. project build + tests
5. Playwright / visual gates

**CI secrets never live in any repo.** A Cloudflare/registry deploy token belongs
in the hosting platform's secret store or the operator's on-box drop-in — not in
`.github/workflows/`, not in `.guardrails/`, not in `.devgate/`. Machine-specific
topology (hosts, tailnet IPs, token drop-in paths) belongs in the operator's
private infra records, never in this framework.

---

## Step 6 — Failure registry

When you fix a bug, append with the helper — it writes the **project overlay** by
default, not the shared baseline (`baseline-ownership` / `base-write-01`):

```bash
python3 .devgate/scripts/log_failure.py \
  --error-message "..." --category runtime --severity high \
  --root-cause "..." --affected-files path/to/file.js \
  --regression-pattern 'the_signature_that_must_not_return' \
  --prevention-rule "..."
```

The `regression_pattern` is the load-bearing field: `regression_check.py` compiles
it and fails the build when it reappears in **added** lines. Use `--upstream` only
when the bug is genuinely generic to the framework. Entries are append-only.

---

## Onboarding checklist

- [ ] Submodule at `.devgate/` (exact name)
- [ ] `.guardrails/` overlay exists; baseline untouched
- [ ] Secret ignore patterns added before first gate run
- [ ] Every gate reports **this** project's paths
- [ ] No gate reported green with zero inputs
- [ ] `openspec` symlink → `.guardrails/openspec`
- [ ] Each change package has `package.json` with raw-byte SHA-256 digests
- [ ] Normative vs informative classification is deliberate
- [ ] `verify-package.py` exits 0; tamper test exits 1
- [ ] `gate-config.json` sets owned capabilities to `blocking`
- [ ] Source markers use the file's own comment syntax
- [ ] CI runs identity → traceability → pattern → build → test
- [ ] No secrets, tokens, host names, or IPs in any tracked file
- [ ] `failure-registry.jsonl` overlay receives project bugs (not the baseline)
