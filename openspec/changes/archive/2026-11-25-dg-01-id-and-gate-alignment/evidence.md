# DG-01 verification

Eight IDs were added without changing any earlier requirement ID or text.
Repository-wide history, source, test, and archive searches found no prior
reference to the assigned IDs.

| Capability | New IDs |
|---|---|
| adapters-and-loops | `adapter-01`, `adapter-02` |
| reviewer-surfaces | `reviewer-01`, `reviewer-02`, `reviewer-03` |
| traceability-and-drift | `trace-01`, `trace-02`, `trace-03` |

Thirteen focused tests passed. They cover canonical markers and headings,
malformed and unclosed markers, duplicate and extra IDs, drafts, fenced
examples, and parity with the shared traceability parser. The CI gate uses
the exact locally installed OpenSpec CLI 1.14.3.

The committed-tree state gate reconciled both the historical
`479b609` comparison and the current `fd2c11f` baseline comparison.
The three unsupported-format findings are resolved without changing
ledger state. The former parser failure is recorded as `FAIL-508da106`.
