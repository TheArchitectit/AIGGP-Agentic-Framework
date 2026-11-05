# Secret Fleet D4 — per-repo findings triage, first pass (2026-11-05)

Disposition 4 of
[`2026-10-11-secret-fleet-sweep-triage.md`](./2026-10-11-secret-fleet-sweep-triage.md):
*"Per-repo findings triage across the 54 repos — separate workstream; the monitor
is correctly naming a large backlog, not a single defect."*

**No allowlist entry was written and no coverage was narrowed.** This is a triage
record: it classifies the backlog and names what needs a decision. Dispositions
are recorded here; applying them is a separate step, and one item below must not
be dispositioned at all until it is rotated.

Measured against `docs/qa/fleet-sweeps/2026-11-05.json` (the live sweep).

## The backlog is not one number

The report carries two different quantities that both use the word *finding*,
and they are not interchangeable.

| Quantity | Meaning | 2026-11-05 |
|---|---|---|
| `findings` (per repo) | every location the gate wrote to its report — **allowlisted and not** | 504,052 |
| `uncovered` (per repo) | locations with no disposition — **this is what exits non-zero** | 503,839 |
| `states.findings` | repos whose gate exited 1, i.e. repos with `uncovered > 0` | **55** |

`scripts/secret-scan.sh` exits 1 only when `uncovered` is non-empty, and
`scripts/secret-scan-fleet.sh` sets `state=findings` only on that exit code. So
`states.findings: 55` is the **actionable** population and is correct.

Three repos are `state=clean` while `findings > 0`. They are not hidden — every
one of their findings is allowlisted:

| Repo | findings | uncovered | state |
|---|---|---|---|
| NeonDash | 31 | 0 | clean |
| vbrainstorm | 23 | 0 | clean |
| radicalopenmcpplatform | 19 | 0 | clean |

That is **73 dispositioned findings** the summary tally does not surface. Reading
`findings` as "work remaining" overstates the backlog by exactly this amount.

### One repo is the backlog

| | uncovered | share |
|---|---|---|
| `openclaw` (upstream fork, D1) | 502,513 | 99.7% |
| everything else | **1,326** | 0.3% |

D4's real workload is **1,326 uncovered findings across 54 repos**. D1 (owner
call) would remove the 502,513. Until then the monitor's magnitude is measuring
one upstream fork, not our leak surface.

Largest of the remainder: `R.A.D.1.C.A.1` 188, `AIREPO01` 118,
`openagentplatform` 84, `claw-code` 69, `plexus` 63, `GlitchDungeon` 62,
`RSON` 62, `AIGGP-Agentic-Framework` 42, `radcode` 40.

## Where the signal is concentrated

Across the 1,326 (openclaw excluded), by rule:

| rule | count | reading |
|---|---|---|
| `generic-api-key` | 703 | the catch-all; mostly fixtures and docs |
| `curl-auth-header` | 283 | mostly walkthrough/lab examples |
| `stripe-access-token` | 57 | **one documentation example, copied 12+ times** |
| `private-key` | 31 | mostly vendored crate sources |
| `jwt` | 27 | one real candidate; the rest fixtures |
| `curl-auth-user` | 20 | one lab walkthrough |
| `slack-app-token` / `github-pat` / `discord-client-secret` / `gcp-api-key` | 10 | all classified below |

By top-level path: `docs` 318, `guardrails-template` 131 (a copied tree), root 71,
`crates` 65, `mcp-server` 56, `src` 52, `05-workloads` 50 (vendored),
`data` 49, `.guardrails` 43, `tests` 34.

Four noise classes account for nearly all of it, each identified by inspection
rather than assumed:

1. **Template doc residue.** `docs/MCP_TOOLS_REFERENCE.md:216` (or under
   `guardrails-template/`) is the guardrails-template's own *"Example Usage"*
   block for its Secret Detection tool, which shows
   `const apiKey = '…'` as sample input. It appears at the **same line** in
   `claw-code`, `datacenterbreakout`, `GlitchDungeon`, `openagentplatform`,
   `OpenRawFlow`, `pi-provider-resume-public`, `radredeye`,
   `radredeye-vision-review`, `RSON`, `swordofhope`, `SynthGrid`. The template
   already documents this class in its own `.gitleaksignore`. Copies inherit the
   finding and not the disposition.
2. **Vendored dependency trees.** `AIREPO01`'s 118 are almost entirely
   `.cargo/registry/src/…/{pem-rfc7468,pkcs1,pkcs8,rsa,rustls-pemfile,sqlx-*}`
   sources and READMEs — crates.io content, not repository content.
3. **Test fixtures.** `mcp-server/internal/**/secrets_scanner_test.go:60` and
   friends, `scanner/tests/secrets/key_detection.py`,
   `test/onboard.test.ts`, `src/worker/utils/scrubber.test.ts`. Deliberately
   planted fake tokens to assert a redaction path.
4. **Sprint/study material.** `docs/sprints/WEEK_08.md` at identical lines
   3777/4129/4136 in four repos, and
   `studyguides/NCM-MCI-LAB-WALKTHROUGH.md` (`curl-auth-user` × 10) in
   `radicaltrainingplatform`.

## High-severity rules — every location inspected

145 locations across the 1,326 carry a rule other than `generic-api-key`. Each was
opened and classified by **shape** — token length, charset class, placeholder
markers, PEM structure, surrounding context — never by value. No secret is
quoted anywhere in this document.

### Escalate — 1 item, do not disposition

**E1. `photography-website` `.env` at `b7309b181f8c` line 2 — `jwt`.**
A 208-character, three-segment, JWT-shaped value with full charset variety and
**no placeholder marker**, in a **tracked `.env`**. The file is gone from HEAD
but the blob is in history and is recoverable by anyone who can clone.

**It is unexpired.** Decoded to *timestamps only* — no claim, no header field
beyond `alg`, and no part of the token is reproduced here or anywhere in this
repository:

| | |
|---|---|
| `alg` | `HS256` |
| `iat` | 2025-12-20T23:39:01Z |
| `exp` | 2035-12-21T11:39:01Z |
| verdict | **UNEXPIRED — 3,332 days remaining** |

A **ten-year** HMAC-signed bearer token, not expired, sitting in the history of
a repository anyone with clone access can read. What is *not* established is
whether the issuer still accepts it — the signing secret may have rotated or
the token may be revoked server-side — and that does not change the action
either. Treat it as live until the issuer says otherwise. Whether that
repository is public or private is likewise not established here.

This is not an allowlist candidate. It needs the credential **revoked or rotated
now**, and then a decision about history. A disposition entry would only tell
the monitor to stop looking at a live secret.

(`photography-website/.env.production` is still tracked and holds one
`VITE_`-prefixed URL key — a 46-character URL-shaped value, not a token. Classed
benign, but `VITE_` values are bundled into client JS, so anything ever added
there is public by construction.)

### Retracted — 1 item, was escalated in an earlier draft of this record

**E2. `missioncontrol` `docs/GITHUB_APP_CONFIG_IN_D1.md:25` at `ee51590c` —
`private-key`. NOT A LEAK.**

An earlier draft of this record escalated this on a one-line shape check that
matched `-----BEGIN … PRIVATE KEY-----`. That was wrong. The line is **SQL
comment prose inside a setup walkthrough**:

> `-- - Generate or download the private key (starts with "-----BEGIN RSA
> PRIVATE KEY-----")`

It *quotes* the header so a reader knows what to look for in GitHub's UI. There
is **no key body** — the file contains zero long base64 lines. The only other
reference in the document is the explicit elision `MIIEp...full_private_key...`
inside a JSON example of the field's shape.

Disposition: **justify — documentation of a configuration format**. Same class
as the template's "Example Usage" block.

**Method caveat, recorded because it cost a false alarm.** The first pass
classified the 145 high-severity locations partly by a one-line shape probe
(does this line contain a PEM header / a long token / a placeholder marker?).
That probe cannot distinguish a *quoted* header from a *real* one, and it
reported "no placeholder marker" because the elision sits on a different line.
Every escalation must be confirmed against surrounding context and, where the
claim is consequential, by decoding structure — as E1 was, and as E2 now has
been. Every other location was read with its surrounding lines; this one alone
was taken on the probe, and it is the one that turned out wrong.

### Classed false positive / fixture — 144 locations

| Class | Evidence | Disposition |
|---|---|---|
| Template doc example (`MCP_TOOLS_REFERENCE.md:216`, `stripe-access-token`) | sits under a heading literally titled **"Example Usage"**, inside a JSON body showing `const apiKey = '…'` as the *input* to a secret-detection tool | **justify** — doc residue; template already names it |
| `missioncontrol` `docs/GITHUB_APP_CONFIG_IN_D1.md:25` (`private-key`) | SQL-comment prose quoting what a PEM header looks like; **zero** base64 body lines; the JSON example value carries the explicit elision `MIIEp...full_private_key...`. History-only (`d3cac6ae` removed it) | **justify** — doc example; was E2, retracted |
| `AIREPO01` `.cargo/registry/**` (`private-key` × 11) | crates.io sources: `pem-rfc7468`, `pkcs1`, `pkcs8`, `rsa`, `rustls-pemfile`, `sqlx-*`. Vendored tree | **justify** — out of repository content |
| `secrets_scanner_test.go:60` and siblings (`jwt`) | redaction tests with planted fakes, in 6 repos | **justify** — fixture |
| `radcode` / `RADICAL-CODE` `crates/cli/src/support/redaction/keys.rs:29,43` (`private-key`) | a redaction library's own test keys | **justify** — fixture |
| `NemoClaw` `.github/workflows/nightly-e2e.yaml:336-343` (`discord-client-secret` × 2, `slack-app-token`) | `*_TOKEN_A` / `*_TOKEN_B` pairs feeding a "Run token rotation E2E test" step. Every value carries `test`/`fake`, 13–15 unique characters across 24–32, Shannon 3.4–3.7 — synthetic | **justify** — fixture; see promotion debt 4 |
| `NemoClaw` `src/lib/sandbox-channels.ts:72` (`slack-app-token`) | a `tokenFormatHint` help string: *"Slack app tokens start with 'xapp-' (e.g. …)"* | **justify** — UI example |
| `datacenterbreakout` `src/terminal/VirtualFilesystem.ts:354` and its `archive/` twin (`private-key`) | an in-game virtual filesystem returning a fake OpenSSH key, next to a faked syslog (`Apr  1 00:25:12 … sshd`). Game content | **justify** — artifact |
| `plexus` `scripts/default-populate.json:8`, `scripts/build-populate.ts:10` (`jwt`) | 236-char JWT shape but **placeholder marker present**; both files deleted at HEAD | **justify** — fixture, history-only |
| `missioncontrol` `src/worker/utils/scrubber.test.ts:26` (`github-pat`) | `scrubSecrets('token ghp_… leaked')` — a scrubber test asserting the fake is redacted. Relocated to `src/server/utils/scrubber.test.ts`, same fixture | **justify** — fixture |
| `AIGGP` `fleet-manager/tests/test_operations_v1.py:164` (`github-pat`) | a credential-shaped literal planted to assert the refusal path does **not** echo it (`assertNotIn`). AIGGP is public | **justify** — fixture, but see promotion debt 3 |
| `radicaltrainingplatform` `studyguides/…:794-935` (`curl-auth-user` × 10) | a lab walkthrough's example `curl -u` lines | **justify** — study material |

Every one of these is the kind of thing a scanner should surface and a human
should be able to dismiss in seconds. None of them is a leak.

## Named defects (recorded, not applied)

### D4-a. The fleet's gate cannot see the dispositions the template wrote

`scripts/secret-scan.sh` reads **exactly one** disposition file:
`.guardrails/secret-allowlist.json`, matching an entry on `rule` + `path`.

The guardrails template ships **`.gitleaksignore`** (17 entries,
`commit:path:rule:line`) and `.gitleaks.toml`, and **no**
`.guardrails/secret-allowlist.json`. So the template's written reasons are
invisible to the scanner that grades it: it reports 20 findings / 20 uncovered,
having already documented a disposition for some of them.

Matching the template's 20 reported locations against its own `.gitleaksignore`:

| | count |
|---|---|
| exact `path`+`rule`+`line` match | 6 / 20 |
| `path`+`rule` match (the gate's own semantics) | 7 / 20 |
| no entry at all | 13 / 20 |

So it is **two** problems, not one: a **mechanism mismatch** (two disjoint
allowlist formats; the fleet reads the wrong one) and **staleness** (the 13
unmatched include every `cpofopencode` location and `STATUS.md:68`, plus
`_test.go` fixtures added after the entries were written).

A repo that does the right thing — writes a reasoned disposition in the file the
template ships — is still counted as uncovered.

**Why not fixed here:** teaching the gate to honour `.gitleaksignore` would turn
existing written reasons into "covered" and make the fleet read greener. That is
a coverage change of exactly the kind the triage record reserves for owner
sign-off, and it would need a decision on which format is canonical. Proposed
for owner call.

### D4-b. `states.findings` silently excludes fully-allowlisted repos

Named in the table above. Not a defect in the gate's verdict — the verdict is
right — but a report-reader trap: `findings` and `states.findings` mean different
things and nothing in the report says so. A one-line note in the report schema
would close it.

## Promotion debts named while classifying

1. **Template doc example.** Fixing `docs/MCP_TOOLS_REFERENCE.md` in the template
   (mask the sample `apiKey`) stops every *future* copy from inheriting the
   finding. Existing copies still need their own entry or a re-sync.
2. **Vendored trees.** `AIREPO01`'s `.cargo/registry` is the textbook case for
   a scope skip; the gate already skips some build trees and this is the same
   class.
3. **Credential-shaped test literals.** `test_operations_v1.py` and the
   template's `*_test.go` files plant values that *look* real to a scanner and to
   a `.pyc`/bytecode reader. AIGGP is public. Worth a standing rule that test
   literals be constructed at run time rather than written as source literals.
4. **NemoClaw's rotation fixture is hardcoded in the workflow.** It is honestly
   fake today. Inline literals in a workflow file invite a later paste of a real
   value; generating the A/B pair at run time would remove the temptation.

## What this does not do

- **No allowlist entry, no exclusion, no scope change.** Nothing here makes the
  fleet read greener.
- **E1 is not dispositioned.** It needs the credential revoked or rotated first.
- **D1** (exclude `openclaw`) and **D2** (two-owner token scope) are unchanged —
  both are owner decisions.
- **D3** is closed and untouched by this record.
- Nothing in `RADICAL-CODE` (out of scope). The `radcode` / `RADICAL-CODE`
  `redaction/keys.rs` class above is named for completeness only.

## Bottom line

The monitor is naming a real backlog and it is mostly what it looks like:
documentation examples, vendored sources, and test fixtures. Of 504,052 reported
locations, **502,513 are one upstream fork** and roughly **1,326** are ours to
look at; of those, the overwhelming majority class out on inspection.

**One does not class out.** `photography-website` `.env` at `b7309b181f8c`
holds an **HS256 bearer token that does not expire until 2035-12-21** — issued
2025-12-20, unexpired, recoverable from history. Treat it as live until the
issuer says otherwise. It is the reason this pass stopped at triage and the
reason the next action is **revocation, not a disposition entry**.

A second item (`missioncontrol` `docs/GITHUB_APP_CONFIG_IN_D1.md` at
`ee51590c`) was escalated in an earlier draft and has been **retracted**: it is
documentation prose quoting a PEM header, with no key body. The retraction and
the method caveat that produced the false alarm are recorded above, so the
record is self-auditing.
