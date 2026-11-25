# Design

## Context

The workflow checks for the App ID and private key before requesting an
installation token. The later resolver accepts an empty token result and
selects the repository workflow token. It then writes the selected value
into a shell-authored runner output. The reconciler already accepts the
installation token and private key as environment variables.

## Decisions

Remove the fallback and redundant credential output in the workflow. Keep the
enrollment job gated on a verified, nonempty installation token and give the
reconciler the value through its existing environment contract. Preserve the
mint action's reviewed pin, automatic revocation behavior, workflow triggers,
job permissions, and input names when the chosen issuer transport satisfies
the file-handling requirement.

Review the exact pinned issuer action and its runner-managed output separately
before marking the file-handling requirement verified. If the issuer transport
places a raw credential in a file covered by `fleet-app-08`, use a handoff
that keeps the credential in process memory or keep that acceptance item open
with the recorded observation. Test missing configuration and token outcomes
by executing the authored shell or process boundary with disposable synthetic
credentials. Do not contact enrolled repositories during local verification.

## Risks / Trade-offs

An authentication failure stops enrollment and should name the missing input
or missing minted token without including credential values. Keep evidence
limited to evaluated paths, exit statuses, and controlled log checks.
