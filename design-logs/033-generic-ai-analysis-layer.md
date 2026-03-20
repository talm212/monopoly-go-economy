# 033 — Generic AI Analysis Layer

**Date:** 2026-03-21
**Status:** Complete
**Feature:** #46 — Generic AI analysis layer, reusable across features

## Context

The AI analysis section (insights, chat, optimizer) was tightly coupled to `CoinFlipResult` through manual context-building logic scattered across `ai_analysis.py` and `app.py`. Each consumer (InsightsAnalyst, ChatAssistant, ConfigOptimizer) accepted the same four dicts (`result_summary`, `distribution`, `config`, `kpi_metrics`) separately, with no shared abstraction.

As the platform grows to support additional features (loot tables, reward distributions), every new feature would need to replicate the same manual context-building and churn-segment computation in the UI layer.

## Decision

Introduce `FeatureAnalysisContext` as a frozen dataclass in `protocols.py` that packages all AI-relevant data into a single object. Each feature's result model (e.g., `CoinFlipResult`) provides a `to_analysis_context()` method that encapsulates its domain-specific logic (KPI merging, churn segment breakdown).

## Changes

1. **`src/domain/protocols.py`** — Added `FeatureAnalysisContext` dataclass with fields: `feature_name`, `result_summary`, `distribution`, `config`, `kpi_metrics`, `segment_data`.

2. **`src/domain/models/coin_flip.py`** — Added `CoinFlipResult.to_analysis_context(config)` method that builds a complete `FeatureAnalysisContext` including churn segment data when available.

3. **`src/ui/sections/ai_analysis.py`** — Refactored `_build_ai_context()` to return a `FeatureAnalysisContext` instead of a 4-tuple. When a fresh `CoinFlipResult` is available, delegates to `to_analysis_context()`. Updated `render_ai_analysis()` to unpack fields from the context object and pass `feature_name` through to the insights tab.

4. **`tests/domain/test_coin_flip_model.py`** — Added 9 tests for `to_analysis_context()` covering: return type, feature name, config matching, KPI presence, string-keyed distribution, summary enrichment, churn segment population, no-churn fallback, and frozen immutability.

## Key Principles

- **Domain owns its context**: Coin-flip-specific logic (churn segment breakdown) lives in `CoinFlipResult`, not the UI layer.
- **Feature-agnostic AI layer**: InsightsAnalyst, ChatAssistant, ConfigOptimizer internal signatures unchanged — they still accept dicts. The context just provides them.
- **Backward compatible**: `render_ai_analysis()` public signature unchanged. Loaded-from-history path still works via fallback context construction.

## Outcome

All 408 tests pass. AI analysis functionality preserved exactly as before, but the context-building logic is now encapsulated in the domain layer and reusable for future features.
