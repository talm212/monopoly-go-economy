# 023 — AI-Powered Config Optimizer

## Status: Complete
## Date: 2026-03-19

## Context
The economy team needs to iteratively tune simulation parameters (probabilities, point values) to hit specific KPI targets. Manually adjusting configs and re-running simulations is slow. An AI-powered optimizer can automate this loop: run simulation, evaluate results against a target, ask the LLM for a better config, repeat until convergence.

## Decision
Build a `ConfigOptimizer` in the application layer that:
1. Takes a simulation callable, current config, an optimization target, and player data
2. Iteratively runs simulation → evaluates → asks LLM for suggestions → applies guardrails
3. Tracks all optimization steps for UI display
4. Returns the best config found (closest to target)

### Key Design Choices
- **Callable simulate_fn** instead of Simulator protocol — keeps optimizer feature-agnostic
- **Guardrails on LLM output** — cap probabilities at [0,1], ensure positive point values, protect max_successes
- **Best-tracking** — always returns the best config seen, even if LLM suggests worse ones later
- **Convergence check** — stops early when within tolerance of the target
- **OptimizationDirection enum** — supports maximize, minimize, and target-seeking

### Domain Model
- `OptimizationDirection` — enum for maximize/minimize/target
- `OptimizationTarget` — frozen dataclass with metric, target_value, direction, tolerance
- `OptimizationStep` — mutable dataclass tracking each iteration

### Architecture
- Domain model in `src/domain/models/optimization.py`
- Application service in `src/application/optimize_config.py`
- Follows same pattern as `InsightsAnalyst` — DI of LLMClient, JSON parsing, error handling

## Testing Strategy
- TDD: tests written first
- Mock both LLM client and simulate_fn
- Test convergence, max iterations, guardrails, error handling
- All tests seeded/deterministic

## Risks
- LLM might suggest invalid configs — mitigated by guardrails
- LLM might oscillate — mitigated by best-tracking and max iterations
- JSON parsing failures — mitigated by error handling (break loop on failure)
