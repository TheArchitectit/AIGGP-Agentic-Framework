# Monitor state recovery design

## State boundary

The recovery set covers the configured runner registry, service map, and daily
alert records. These filenames identify candidate inputs. Their contents still
need qualification before backup. The [source inventory](state-inventory.md)
records which inputs can carry pending enrollment credentials, instance
addresses, or free text. The private archive must exclude environment secrets,
plaintext bearer tokens, machine-specific endpoints and deployment
configuration. Keep instance backups and receipts in private storage.

Reject an ineligible generation before writing an archive or issuing a receipt.
Leave the source state intact. In particular, an outstanding one-time enrollment
credential is a reason to defer a raw registry backup. Complete or explicitly
retire that enrollment through the normal lifecycle before retrying. Keep the
registry salt with the heartbeat verifiers needed for recovery. Define any
normalized backup representation, its schema version and its restore behavior
before enabling backup of a generation that needs field-level transformation.

The registry schema is versioned JSON and the service map has its own JSON schema.
The runner registry is written with a same-directory temporary file followed by
`os.replace`; alert history is append-only JSONL. A backup must capture these files
as one declared generation. It records a normalized relative path, size, schema
version where applicable, and SHA-256 for each included file, plus a digest of the
complete archive. A detached manifest digest covers canonical manifest content
with its digest field omitted, avoiding a self-referential checksum.
Unknown files, unsafe paths, duplicate paths, missing
required state, or a mismatched digest fail the backup or restore closed.

## Controlled restore

Restore first stages the archive in a fresh temporary directory. It verifies the
manifest, path containment, every file digest, JSON/JSONL parsing, and the current
registry and service-map schemas before replacing any live state. The verified
staged generation is installed as a unit while the writer lock is held. If any
check fails, the prior live files remain byte-for-byte unchanged and the monitor
does not start against a partially restored generation.

The backup preserves only the registry's stored token hashes; it never writes
plaintext tokens or environment secrets into the archive or receipt. After startup,
each restored runner remains unknown until a valid heartbeat is received using its
preserved credential. If a credential is unavailable or rejected, the receipt marks
that runner as requiring explicit re-enrollment with a newly issued token. The
recovery process does not mint or disclose enrollment tokens automatically.

## Single-writer fencing and receipts

The existing one-monitor requirement remains authoritative. The monitor process
must acquire and hold an exclusive lock for the configured state directory before
it loads or writes state. Backup obtains a consistent generation while the writer
is quiesced; restore requires the prior writer to be stopped and fenced. Recovery
must abort if it cannot prove exclusive ownership. It advances the durable writer
generation before serving requests, so a stale process cannot continue writing a
generation that recovery has replaced. This is local writer fencing, not a lease
between hosts, high availability, or automatic failover.

A state-restored receipt records the backup/manifest digest, schema version,
restored file digests, writer generation, and counts of preserved and
re-enrollment-required runner records. It contains no token, endpoint, or host
address. A separate convergence receipt is issued only after every non-deferred,
enrolled runner
has either sent an authenticated heartbeat using restored state or completed
explicit re-enrollment, and alert deduplication has been reconciled against open
issues. Until then, missing or stale runners and unresolved alert state remain
unknown; they are not reported as healthy. A restore receipt alone never claims
operational convergence.

## Verification

Use disposable local state directories and fake spokes/notifiers. Positive fixtures
prove a complete manifest, digest-verified restore, monotonic writer generation,
and a convergence receipt after all non-deferred, enrolled runners reconcile.
Negative fixtures
corrupt or omit a file, provide an unsupported schema or unsafe archive path,
attempt restore while a writer lock is held, or leave a runner unreconciled. Each
negative case must preserve the original live state, produce no convergence
receipt, and avoid emitting secrets or private instance values. No live deployment
or failover exercise is part of this change.
