# 034 — Generic KPI and Results Display Protocol

**Date:** 2026-03-21
**Status:** Complete
**Feature:** #48 — Generic KPI and results display, reusable across features

## Context

The UI layer (app.py, results_section.py) was tightly coupled to CoinFlipResult.
KPI help texts lived in app.py, segment rendering was hard-coded to filter by
`about_to_churn`, and the results section accepted `CoinFlipResult` directly.
Adding a second feature (e.g. loot tables) would require duplicating all this
rendering logic.

## Decision

Introduce a `ResultsDisplay` protocol in `src/domain/protocols.py` that any
simulator result can implement. The protocol provides four methods:

- `get_kpi_cards()` — returns `{label: (value, help_text)}` for metric cards
- `get_distribution()` — returns string-keyed count dict for charts
- `get_segments()` — returns optional segment breakdowns (or None)
- `get_dataframe()` — returns the full result DataFrame

## Changes

1. **protocols.py** — Added `ResultsDisplay` protocol (runtime_checkable)
2. **coin_flip.py** — Added `_KPI_HELP` constant and three new methods
   (`get_kpi_cards`, `get_segments`, `get_dataframe`) to `CoinFlipResult`.
   KPI help text is now co-located with the domain model instead of app.py.
3. **results_section.py** — Changed `render_results()` to accept
   `ResultsDisplay | None` instead of `CoinFlipResult | None`. Charts tab
   uses `get_dataframe()`, churn tab uses `get_segments()`.
4. **app.py** — KPI bar now uses `sim_result.get_kpi_cards()` for fresh
   results. `_KPI_HELP` imports from the domain model and only extends it
   with fallback keys for loaded summaries.

## Testing

- Added `TestResultsDisplayProtocol` in test_protocols.py (stub + negative
  check + CoinFlipResult conformance check)
- Added `TestCoinFlipResultsDisplay` in test_coin_flip_model.py (11 tests
  covering get_kpi_cards, get_segments, get_dataframe, empty/edge cases)
- All 424 tests pass.

## Outcome

The results section is now feature-agnostic. Any future simulator result that
implements `ResultsDisplay` will render KPIs, charts, segments, and data
tables automatically without touching the UI code.
