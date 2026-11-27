# Qualify hub and integration evidence gaps

## Why

The DG-02 batch 007 review found that `HUB_BIND_HOST=0.0.0.0` is accepted by hub configuration and passed to the server bind. The existing `mon-local-01` requirement calls for loopback or LAN listeners only. The same review identified missing end-to-end controls across hub deployment, monitoring, and integration contracts. Current test results and source markers do not establish the historical closure of rows 073–084.

## What Changes

- Define an enforceable listener boundary and fail closed on wildcard or public addresses, including resolved names and IPv4 and IPv6. Preserve explicitly approved local network use through a documented configuration contract.
- Add behavioral controls for the hub and integration proof gaps listed in the tasks, then produce independently validated requirement-specific evidence.
- Keep DG-02 rows UNPROVEN until each historical claim has the required accepted evidence and any transition passes the state gate.

## Impact

Hub configuration and startup, deployment documentation, test fixtures, and coherence integration evidence. The change does not assert a live deployment or create a ledger transition.
