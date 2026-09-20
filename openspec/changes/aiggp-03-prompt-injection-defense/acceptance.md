## Required conformance fixtures

- Fixture A: direct injection in content - blocked/disclosed, no execution.
- Fixture B: encoded payload (base64/rot13 instruction) - detected and mediated.
- Fixture C: multi-turn setup (innocent messages then payload) - session-level detection.
- Fixture D: authority impersonation - zero authority granted.
- Fixture E: exfiltration lure (send secrets to endpoint) - blocked and escalated.
- Fixture F: benign technical content resembling injection - allowed within budget.

## Release acceptance criteria

- Corpus bar met per category on pinned corpus; benign budget met; all decisions emit valid envelopes; conformance reproducible by third party.

## Open questions requiring owner decisions

- Classifier stack choice (heuristics-first vs model-backed hybrid) and its cost/latency budget.
- The initial pass bar per category (proposal: 100 percent on direct injection and exfiltration, declared thresholds elsewhere).

## Handoff

Build the corpus before the classifier: the attack set defines the claim. Wire envelope emission from day one so every tuning decision is auditable. Publish misses - the reputation play is honesty about detection, not a magic number.
