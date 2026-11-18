# GitHub App token for fleet CI — the canonical step shape

One App, one token path. This file is the copy-visible source of the shape; it
first landed in `.github/workflows/spec-fleet.yml` (the highest-calling
workflow), and the sibling AIGGP workflows carry the same block.

Change of record: `missioncontrol/openspec/changes/2026-11-15-fleet-ci-github-app-auth/`.

## Why this exists (measured 2026-11-18)

- `gh api rate_limit` on the operator workstation returned `core` `limit=5000,
  remaining=0` for the **user** identity, and `gh api user` answered
  `HTTP 403: API rate limit exceeded for user ID 241862351`. The user budget is
  5,000/hour shared by every tool and agent on that account.
- `github.token` inside CI is the Actions app's installation token: 1,000
  requests/hour **per repository**, and scoped to that repository. A job that
  has to read *other* repos in the fleet cannot do it on that token.
- An App installation token has its own budget — 5,000/hour per installation,
  separate from the user's. That is the budget this shape spends.

## Canonical names

| What | Kind | Name |
|---|---|---|
| App ID | repository **variable** | `DEVGATE_SWEEP_APP_ID` |
| App private key | repository **secret** | `DEVGATE_SWEEP_APP_PRIVATE_KEY` |

One spelling fleet-wide: `vars.DEVGATE_SWEEP_APP_ID` and
`secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY`.

Why reuse the existing names instead of renaming them to something that says
"App" rather than "sweep":

- The pair already exists and is proven in this repository. The
  `secret-fleet.yml` live run of 2026-09-30 recorded `token_mode=app`
  (`docs/qa/2026-09-29-fleet-sweep-live.md`).
- A secret cannot be read back. Renaming it means **re-provisioning the private
  key**, and the existing key was streamed to GitHub without ever touching local
  disk. A rename is therefore a credential-availability risk, not a `sed`.
- Renaming buys clarity and costs an outage; the cost is not worth paying
  today. **When the key is next rotated, rename both then** — a rotation is the
  only moment a rename is free. Record that in the rotation entry when it
  happens.

Do not use a `GITHUB_` prefix for either name: GitHub rejects variable and
secret names that start with `GITHUB_`.

## Configuration (no values in any file)

Per repository that mints a token, an owner with admin rights sets:

```
gh variable set DEVGATE_SWEEP_APP_ID --repo <owner>/<repo> --body <app-id>
gh secret   set DEVGATE_SWEEP_APP_PRIVATE_KEY --repo <owner>/<repo> < key.pem
```

The App is the program's existing App ("Mission Control CI/CD"), installed
All-repositories. The App ID is an identifier, not a credential. The **private
key is a credential**: it is never committed, echoed, logged, or written to a
file in any repository, public or private.

## The steps to copy

Three steps. Put them after `actions/checkout` (the mint does not need the
checkout, but every caller has one).

```yaml
      # --- Fleet GitHub App token: canonical shape, docs/GITHUB-APP-TOKEN.md ---
      # 1. Fail closed and named when half the pair is configured. The action
      #    would also fail on a missing private-key input, but its message does
      #    not name the secret a reader has to go and set.
      - name: Check the App credential pair (fail closed, named)
        id: app-cred
        env:
          APP_ID: ${{ vars.DEVGATE_SWEEP_APP_ID }}
          APP_KEY: ${{ secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY }}
        run: |
          set -eu
          if [ -n "$APP_ID" ] && [ -z "$APP_KEY" ]; then
            echo "::error::vars.DEVGATE_SWEEP_APP_ID is set but secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY is missing."
            echo "::error::Failing closed: a configured App never falls through to a wider identity."
            exit 1
          fi
          echo "[auth] app id variable: $([ -n "$APP_ID" ] && echo set || echo unset)"

      # 2. Mint the installation token. Skipped only when the variable is unset;
      #    the pin is a full SHA, never a tag.
      - name: Mint the fleet App token
        id: app-token
        if: ${{ vars.DEVGATE_SWEEP_APP_ID != '' }}
        uses: actions/create-github-app-token@fee1f7d63c2ff003460e3d139729b119787bc349 # v2
        with:
          app-id: ${{ vars.DEVGATE_SWEEP_APP_ID }}
          private-key: ${{ secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY }}
          owner: TheArchitectit   # owner scope: jobs that read other fleet repos

      # 3. Resolve the mode once, announce it, and publish one token output for
      #    the call sites. The fallback is never silent.
      - name: Resolve and announce the token mode
        id: auth
        env:
          APP_TOKEN: ${{ steps.app-token.outputs.token }}
          WORKFLOW_TOKEN: ${{ github.token }}
        run: |
          set -eu
          if [ -n "$APP_TOKEN" ]; then
            MODE=app
            echo "[auth] token mode: app — program GitHub App installation, 5,000 req/h (separate from the user budget)"
            TOKEN="$APP_TOKEN"
          else
            MODE=workflow
            TOKEN="$WORKFLOW_TOKEN"
            echo "::warning::[auth] token mode: workflow — vars.DEVGATE_SWEEP_APP_ID is unset on this repository. Falling back to github.token: 1,000 req/h, scoped to this repository only."
          fi
          [ -z "$APP_TOKEN" ] || echo "::add-mask::$APP_TOKEN"
          printf 'token=%s\n' "$TOKEN" >> "$GITHUB_OUTPUT"
          printf 'token_mode=%s\n' "$MODE" >> "$GITHUB_OUTPUT"
```

## The call-site pattern

Every step that spends GitHub API budget gets both variables and prints the
mode as its first line. Nothing is ambient.

```yaml
        env:
          GH_TOKEN: ${{ steps.auth.outputs.token }}
          TOKEN_MODE: ${{ steps.auth.outputs.token_mode }}
        run: |
          set -eu
          echo "[auth] this step spends the $TOKEN_MODE budget"
          # ... gh / curl calls follow
```

For a step that must run even after an earlier failure (`if: always()`), keep
the fallback but keep it honest — when the resolver did not run at all, the
identity really is the workflow token:

```yaml
        env:
          GH_TOKEN: ${{ steps.auth.outputs.token || github.token }}
          TOKEN_MODE: ${{ steps.auth.outputs.token_mode || 'workflow' }}
```

## The log shape

Configured repository, `app` mode:

```
[auth] app id variable: set
[auth] token mode: app — program GitHub App installation, 5,000 req/h (separate from the user budget)
[auth] this step spends the app budget
```

Not configured, fallback:

```
[auth] app id variable: unset
::warning::[auth] token mode: workflow — vars.DEVGATE_SWEEP_APP_ID is unset on this repository. Falling back to github.token: 1,000 req/h, scoped to this repository only.
[auth] this step spends the workflow budget
```

The warning is the signal that distinguishes a fallback from a deliberate
workflow-token choice.

## Authenticated clones for the curated private set (spec-fleet)

API budget is not the only thing the App is for. The nightly **Spec Fleet
Sweep** (`.github/workflows/spec-fleet.yml`) also *clones* what it scans, and
some of the curated fleet lives in private repositories that only the App can
read. The shape there, in order:

1. **The curated owner is the App-installed owner.** `fleet-sweep-include.txt`
   lists the same content under `TheArchitectit`, where the App installation
   (101651861) is, rather than under the collaborator account where those
   copies are also private. Scanning both owners would double-count the
   trend line; scanning the unreadable owner reds every night as
   `unscannable`.
2. **Re-admission, in `app` mode only.** The declaration step still drops
   every *generated* owner-scope private repository — the unauthenticated
   clone cannot read it, and `unscannable` is a RED. But a dropped-as-private
   URL that a human wrote in `fleet-sweep-include.txt` is re-admitted when
   the token mode is `app`, and the step prints the re-admitted repos by name.
   In `workflow` mode nothing is re-admitted: `github.token` cannot read
   another owner's private repos, so re-admitting would only move the red.
3. **The token reaches the walk as an environment variable.**
   `scripts/spec-fleet-walk.sh` reads `SPEC_FLEET_CLONE_TOKEN` (empty means the
   historical unauthenticated path, byte for byte). It writes a `GIT_ASKPASS`
   helper into its work temp dir at mode `700`; the helper reads the secret
   from its own environment at prompt time, so the file itself carries no
   credential. The clone also gets `credential.username=x-access-token`,
   `credential.helper=` (so a runner credential store never caches it), and
   `GIT_TERMINAL_PROMPT=0`. **The token is never on git's argv.**
4. **Redaction before storage.** The report is committed to
   `docs/qa/spec-sweeps/` in this public repository. Anything captured from a
   failed clone is passed through a redactor (the token itself,
   credential-shaped literals, and URL userinfo) before it becomes a report
   `reason` or a log line.
5. **A positive control, before the walk.** Immediately after the mode
   resolver, an `app`-only step runs `git ls-remote` against
   `https://github.com/TheArchitectit/rad-gateway` with the same askpass
   mechanism. It fails loudly, naming the repository and the installation, if
   the App cannot read it — so a mis-scoped installation is diagnosed at the
   top of the run rather than as four `unscannable` repos at the bottom.

The positive control and the clone-token plumbing are **spec-fleet-specific**:
they belong only in a workflow that clones private fleet repos. Do not copy
them into a workflow that only reads the API — it would spend budget and prove
nothing. The three-step token shape above remains the copyable unit for
everything else.

## Rules for adopters

- The private key is read from `secrets.*` at run time only. Never echo it,
  never write `run: echo "${{ secrets.<NAME> }}"` anywhere, never write it to a
  file, never pass it to a non-minting step.
- Keep the mint action SHA-pinned. Refresh the pin by reading the release tag's
  commit SHA, not by trusting a floating tag.
- Keep the fallback. An unconfigured repository must still run.
- Do not add a fourth step that re-implements the choice; copy these three.
- A reusable workflow (`workflow_call`) is the wrong shape here: the token is
  needed by later steps **in the same job**, and a called workflow cannot hand
  a token back into the caller's steps. The step shape is the unit of reuse.
