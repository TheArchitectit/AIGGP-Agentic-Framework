# // spec: mon-hub-01
"""hub.request_limits — the transport boundary's exception types and caps.

Extracted from `hub/server.py` for its 500-line source hard limit (508 on
2026-11-08, when the Windows-spoke enrollment landed). This is a MOVE: the
constants and the two exception types are verbatim what lived in `server.py`,
and `server.py` imports every name back, so `hub.server.FIELD_CAPS`,
`hub.server.PayloadTooLarge` and the rest resolve exactly as before.

What stayed behind is the pair of predicates that USE these caps
(`_labels_ok`, `_scan_state_ok`), because they are validation logic rather than
boundary data, and the tests that exercise them import them from `hub.server`.
"""

from __future__ import annotations


class PayloadTooLarge(Exception):
    """Content-Length over MAX_BODY_BYTES — raised before the body is read."""


class InvalidContentLength(Exception):
    """Content-Length < 0 — refused BEFORE any read, answered as 400 by do_POST.

    BufferedReader.read(n) with a negative n reads until EOF: on a socket that
    is "hang until the client hangs up", so one unauthenticated connection
    pins a request thread forever. A hub's spokes page on /health staleness;
    enough pinned threads and the page fires while the hub is merely wedged.
    Live-verified 2026-09-27 — the cap above only bounded the positive side.
    """


# Per-field caps: the body cap bounds the REQUEST, not what one field can do
# to an issue body or a fleet table later. A 60 KB image_reason belongs in no
# GitHub issue; labels are names, not payloads.
FIELD_CAPS = {"image_digest": 512, "image_reason": 1024,
              "image_pin_divergence": 1024, "last_job_seen": 256,
              # mon-tc-05: the lane's own image digest, free text from an
              # untrusted-as-input host. Capped like the evaluator's, because
              # fulfillment compares it byte for byte and an unbounded field
              # that takes part in a comparison is a storage-cost problem
              # waiting for someone to notice it.
              "lane_image_digest": 512}
MAX_LABELS = 64
MAX_LABEL_LEN = 128
MAX_SCAN_REPOS = 256
MAX_SCAN_REPO_NAME = 256
MAX_SCAN_FIELD_LEN = 64
