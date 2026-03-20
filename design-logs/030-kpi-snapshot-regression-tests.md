# 030 — KPI Snapshot Regression Tests

**Date**: 2026-03-21
**Status**: Done
**Feature**: #32

## Context

The simulation engine produces numerical KPIs (total points, mean/median per player, success distribution, churn segmentation). Any code change that silently alters these outputs could go undetected by the existing property-based and invariant tests.

## Decision

Add deterministic snapshot tests that run the simulator with a fixed seed (42) and a known 5-player dataset, then assert **exact** KPI values. This creates a hard regression barrier — any change to simulation logic that changes numerical output will immediately break CI.

## Tests Added

File: `tests/domain/test_kpi_snapshots.py`

1. **test_kpi_snapshot_total_points** — asserts total_points == 2540.0
2. **test_kpi_snapshot_mean_median** — asserts mean == 508.0, median == 350.0
3. **test_kpi_snapshot_pct_above_threshold** — asserts pct == 1.0 (all 5 players above 100)
4. **test_kpi_snapshot_distribution** — asserts exact success_counts dict {0:23, 1:12, 2:8, 3:0, 4:3, 5:4}
5. **test_kpi_snapshot_churn_vs_non_churn** — asserts churn mean == 720.0, non-churn mean == 455.0
6. **test_kpi_snapshot_total_interactions** — asserts total_interactions == 50

## Design Choices

- **Module-scoped fixture**: The simulation runs once and is shared across all 6 tests via `pytest.fixture(scope="module")`. This avoids redundant computation while keeping tests isolated and independently reportable.
- **No pytest.approx**: Values are exact floats (no floating-point fuzz) because the simulation with integer multipliers and small interaction counts produces clean float results.
- **Separate from existing tests**: New file rather than extending `test_coin_flip_simulator.py` — these are a different category of test (regression snapshots vs. property/invariant tests).

## Outcome

All 345 tests pass (6 new + 339 existing). The snapshot tests will catch any regression in the simulation engine's numerical output.
