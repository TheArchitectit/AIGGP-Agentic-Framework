## Requirement: provenance at ingestion

Every external content input crossing a mediation boundary SHALL carry a provenance record, or SHALL be classed unverifiable. Content claims SHALL NOT modify their own class.

### Scenario: self-vouching email

Given an email whose body claims it is from the owner, when provenance is assigned, then the class SHALL derive from the channel facts, and the body claim SHALL be ignored for classification.

### Scenario: missing provenance

Given content arriving through an uninstrumented path, when it reaches a boundary, then it SHALL be classed unverifiable and the gap SHALL be logged.

## Requirement: append-only chains

Transformations SHALL append to the chain with content digests. Modification or removal of chain entries SHALL be detectable by the verifier.

### Scenario: substituted intermediate

Given a chain where one transformation output was replaced, when the verifier runs, then it SHALL reject the chain naming the broken link.

## Requirement: provenance inheritance

Derived content SHALL reference its parents and SHALL NOT exceed the minimum parent class unless an authorized, recorded transformation raises it.

### Scenario: summary of third-party page

Given a summary generated from a third-party webpage, when the summary justifies an action, then the action's evidence SHALL link the page's provenance, and the justification SHALL be classed third-party.
