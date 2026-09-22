---
name: False positive report
about: A DevGate gate flagged code that is actually fine — enough detail to write a regression fixture
labels: false-positive
---

**Gate:** guardrails-scan / semantic-scan / silent-success / regression-check

**Rule / family id:** PREVENT-___ or family name

**Language + file type:**

**The flagged line (verbatim):**

```text
paste the exact line here
```

**Why this is correct code (one paragraph):**

**Suggested disposition:** new exclude_glob / allowlist pending upstream fix / rule regex fix

> Maintainers: a regression fixture (file + line + rule) must be derivable
> from this report alone. If it cannot be, ask for the missing piece.
