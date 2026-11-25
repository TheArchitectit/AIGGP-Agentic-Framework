# Spec Delta

## Purpose

Record owner decisions about optional GitLab instance adoption without treating a deferral as proof of a live server or exposing private connection details.

## ADDED Requirements

### Requirement: GitLab instance adoption review records a bounded owner decision
<!-- id: glf-oi-001 -->
An overdue GitLab instance deferral SHALL have an owner decision record stating whether the instance work remains dormant or is explicitly activated and identifying the next authorized trigger. The record SHALL preserve historical source dates and SHALL NOT include private endpoints, aliases, credentials, or unverified live-server claims.

#### Scenario: owner reviews the expired instance deferral
- **WHEN** an authorized owner records the current OI-001 adoption decision
- **THEN** the record states the dormant or explicitly activated outcome and next authorized trigger, leaves the source dates unchanged, and contains no private connection details
