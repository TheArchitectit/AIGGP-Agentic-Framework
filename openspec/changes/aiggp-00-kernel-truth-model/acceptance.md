## Required conformance fixtures

- Fixture A: valid bundle, valid envelopes, passing aggregation - full green path.
- Fixture B: zero-discovery run - must not pass.
- Fixture C: expired waiver over a FAIL - must remain FAIL.
- Fixture D: tampered envelope - must be rejected with named check.
- Fixture E: tampered ledger - verifier names the chain break.
- Fixture F: nondeterministic bundle source (embedded timestamp) - build must fail or normalize deterministically.

## Release acceptance criteria

- All fixtures pass on the kernel; both shadow adapters emit valid fixtures; verifier runs offline; document regeneration is byte-identical.

## Open questions requiring owner decisions

### Q1 — Signature algorithm and key custody for envelope signing

**ANSWERED 2026-10-01 (owner).**

**Algorithm: Ed25519.** 32-byte keys, 64-byte signatures, deterministic (no
per-signature RNG footgun), stdlib-backed in Python / Rust / Go. Fits the
kernel's "auditable by one person in a sitting" principle
(`design.md:3`). Post-quantum deferred to a future schema version; ES256 and
HMAC rejected on "no gain for this kernel" and "wrong trust model" grounds
respectively.

**Custody: hybrid — per-install Ed25519 keys optionally signed by an org CA.**

Default shape (v1, no org CA required):
- Each install generates its own Ed25519 keypair at first boot; the private
  half is held in the install's custody path (doc named in
  `design.md: "evidence envelope: signed"`).
- An envelope's signature binds it to the signer's identity; the
  `provenance chain` field already carries the signer's public-key hash,
  so a fleet-wide verifier can accept-or-reject on an allowlist of
  install key hashes at the *trust* layer without any CA.

Opt-in "trust-via-org-CA" mode (envelope shape must SUPPORT this, enforcement
is opt-in):
- An org CA (also Ed25519) signs each install's public key during enrollment.
- The envelope MAY carry a CA signature over the signer's public key.
- A verifier opts in to CA-checked trust by requiring that extra field.
  Without opt-in, envelopes with and without the CA signature both verify
  on the base path.

**Invariant — anything with org-wide blast radius is opt-in.**
Owner clarification 2026-10-01, correcting the scope of the Q1 opt-in
requirement. The original Q1 note mis-expanded "env" as *envelope* — it
means **environment**. The class is: any default whose wrong or uninformed
use can break an entire org — *"environment breaking, meaning that if you do
it and don't understand what you're doing you break your entire org."* The
invariant is about blast radius at the org scale; it is **not** narrowly
about envelope validity. The envelope case is the sharpest instance (it
travels fleet-wide the moment it flips), but the rule covers the whole
class.

Named instances of the class (non-exhaustive):
- **Envelope trust-model changes** — a required CA signature, a new required
  field, or an algorithm migration all turn previously valid envelopes
  invalid across the fleet in one flip.
- **Ledger format / chain-schema changes** that make existing chain history
  unverifiable on the reads every downstream consumer already runs.
- **Key / CA revocation semantics** that revoke retroactively (invalidating
  already-signed evidence) rather than cutover at a recorded boundary.
- **Install-level destruction or migration paths** — anything that can lose
  a watcher's ledger or key material if run by someone who does not
  understand the blast radius.

Every such change MUST be gated behind an opt-in flag on the
verifier/consumer (a schema-version bump for anything that touches the wire
shape), never default-on. The blast radius *is* the reason for the rule: a
default flip travels the whole org with no review step; an opt-in forces
the understanding *before* the org sees the new behavior. Same
defensive-positive shape the audit's core-gate rule uses — the truth unit and
its storage are owned by the org, so reshaping their validity domain is a
runtime decision, never a silent upgrade.

**Rotation note (stated assumption SA-4):** per-install key rotation is
local to the affected install. Old envelopes signed by a rotated-away key
remain valid for evidence produced during that key's lifetime (bound by the
envelope's `issued_at` and the ledger's chain), but new envelopes must use
the current key. A CA-signed cross-install trust path is rotated by
re-issuing the CA-signed key inventory; the CA's own rotation is a fleet
equivalent of the above and does not retroactively invalidate envelopes.

### Q2 — Ledger storage backend for local-first installs

**ANSWERED 2026-10-01 (owner).**

**Backend: append-only file + hash chain** (JSONL). Every line is
`{prev_hash, entry_hash, entry}` — the hash chain *is* the append-only
enforcement: a tampered entry breaks the chain at the point of tamper and
the verifier names the break. Export is `cp`. Backup is `cp`. This matches
design.md's "append-only, hash-chained, exportable. The verifier is a
standalone binary/script with no module imports."

For local-first installs there is no separate DB tier. Waivers, exceptions,
and revoke-tombstones are chain entries (design.md: *Waivers exist as ledger
entries, not config*), so a query need is a *read* need — the verifier walks
the chain; an operator greps the file. If a fleet-outgrowing-the-file
moment ever arrives, the escalation path is a later question (an indexed
materialized view is possible), but **v1 ships the file as the ledger's
only store**, and it is the source of truth in either case.

**Why not SQLite:** the kernel's "one person in a sitting" auditability +
"standalone verifier with no module imports" is the whole point. A JSONL
file with a visible `prev_hash` chain is readable by an auditor without a
Python module tree or a DB driver; the file format *is* the threat model.
Concurrent appends serialize on a per-ledger write lock (atomic append via
file-lock + append-only create), never a shared mutable node.

Said v1: **one `ledger.ndjson` file per install, append-only by hash chain,
append enforced by file-lock, export is `cp`.** Any future DB-like
escalation is a Q-style owner decision under the org-wide-blast-radius
invariant above (see: the invariant), not a silent upgrade.

## Handoff

Build the schema library and fixtures first; nothing else in AIGGP should block on full verifier polish. The conformance kit is the public face of the kernel: treat its clarity as a launch feature, not an afterthought.
