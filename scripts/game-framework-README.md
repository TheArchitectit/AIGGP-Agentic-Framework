# devgate-game-framework

Game-development quality gates for AI-assisted game builds, pulled into DevGate-Agentic-Framework as a git submodule.

## Modules
- **Game-Type Phase Matrix** — minimum required features/screens/verification per game type × phase (Prototype→Alpha→Beta→Release→Post-release)
- **Per-Screen Feature Tracking + Button Validation** — scene inventory, node/button registry, scene-load smoke, orphaned-signal detection
- **Game Regression Tracking** — failure-registry + regression scanner scaled to gameplay/crash/save-corruption patterns

## Attach
```bash
git submodule add git@github.com:TheArchitectit/devgate-game-framework.git game-framework
```

Reference implementation: Sword of Hope (`scene_load_check.gd`, `automated_gameplay_test.gd`, `integration_runner.gd`, `.guardrails/failure-registry.jsonl`, `regression_check.py`).
