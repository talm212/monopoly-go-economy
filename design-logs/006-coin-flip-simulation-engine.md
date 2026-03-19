# 006 — Coin Flip Domain Models & Simulation Engine

**Date**: 2026-03-19
**Status**: Complete
**Feature**: #6 — Core coin flip simulation engine

## Context

The coin flip is the first and primary game mechanic to simulate. Players trigger coin-flip chains by landing on tiles. Each chain is up to `max_successes` sequential flips with independent probabilities. Points accumulate per flip depth and are multiplied by the player's `avg_multiplier`. Churn-risk players get a 1.3x probability boost (capped at 1.0).

## Decision: Fully Vectorized NumPy Strategy

**Why not loop per player?** With 1M+ players and potentially 10M+ interactions, Python for-loops would take minutes. Instead:

1. Compute interactions per player via Polars integer division
2. Flatten all interactions into a single NumPy array using `np.repeat`
3. Generate ALL random numbers in one `rng.random((N, max_successes))` call
4. Use `np.where` broadcasting to assign normal vs boosted probabilities per interaction
5. Boolean comparison + `np.cumprod` to find first failure per chain
6. Lookup table for cumulative points by depth
7. Polars `group_by` for final player-level aggregation

**Result**: 100K players completes in ~2 seconds. Scales linearly with total interactions.

## Files Created

- `src/domain/models/coin_flip.py` — `CoinFlipConfig` (frozen dataclass) + `CoinFlipResult` (dataclass)
- `src/domain/simulators/coin_flip.py` — `CoinFlipSimulator` with fully vectorized `simulate()` method
- `tests/domain/test_coin_flip_config.py` — 21 tests for config validation, serialization, CSV parsing, churn boost
- `tests/domain/test_coin_flip_simulator.py` — 28 tests for determinism, invariants, edge cases, performance, protocol conformance

## Key Design Choices

| Choice | Rationale |
|---|---|
| `CoinFlipConfig` is `frozen=True` dataclass | Immutable config prevents accidental mutation during simulation |
| `CoinFlipResult` is mutable dataclass | Needs to be constructed field-by-field during simulation |
| `np.cumprod` on int8 success matrix | Efficiently finds first failure without branching |
| Points lookup table `points_lookup[depth]` | O(1) vectorized mapping from depth to cumulative points |
| Module-level registry registration | Enables auto-discovery when the module is imported |
| Both models implement protocol contracts | `SimulatorConfig`, `SimulationResult`, `Simulator` — verified by isinstance tests |

## Testing

- 49 new tests, all passing
- 107 total tests, zero regressions
- TDD: tests written first, confirmed import failure, then implementation
- All tests deterministic via seeded RNG (seed=42)
- Performance test: 100K players < 5 seconds (marked `@pytest.mark.slow`)
