# Game Regression Tracking

Status: Proposed. Enforcement layer invoked by game-type-phase-matrix.

## Registry
Append-only `.guardrails/failure-registry.jsonl` — one JSON object per bug/failure.
Never edit existing entries; append only via `scripts/log_failure.py`.

Game-class patterns tracked (beyond generic DevGate):
- NULL_DEREF / NPE at runtime
- SCENE_LOAD_FAIL — scene fails to instantiate
- SAVE_CORRUPT — save/load round-trip breaks
- SCRIPT_ERROR — engine script runtime error
- ORPHAN_SIGNAL — button/signal with no handler
- DETERMINISM_BREAK — seeded run diverges
- PERF_REGRESSION — frame time / memory exceeds budget

## Regression scanner
`scripts/game_regression_check.py` — scans staged/unstaged changes against the registry
patterns + file-size limits + prevention rules. `--pre-commit` exits nonzero on blockers.
Soft-as-hard headroom: promote soft violations to blocking for files changed since prior
release tag (mirror DevGate regression_check.py).

## Determinism accommodation
A gameplay run is only a regression candidate if seed + input trace are logged. Gate requires
seed-logged replay for any gameplay-crash entry.

## Seeding
Port from reference: Sword of Hope `scripts/regression_check.py`, `.guardrails/failure-registry.jsonl`,
`prevention-rules`, `b8_polish_verify.py`. Generic byte/file-size logic stays in DevGate; this
module adds the game-class patterns and screen/save/determinism hooks.
