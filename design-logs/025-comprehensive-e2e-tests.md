# Design Log 025 — Comprehensive E2E Tests

## Date: 2026-03-20
## Status: Complete

## Goal
Expand Playwright E2E test suite from 14 to 40+ tests covering all user journeys.

## Result: 43 tests across 8 test classes

## Test Classes
1. **TestPageLoad** (6) — title, setup section, uploaders, run button disabled, empty state, seed input
2. **TestUploadAndConfigure** (6) — valid upload, ready state, enabled run, invalid CSV error, partial upload warnings
3. **TestConfigEditor** (3) — appears after upload, opens expander, config change warning after run
4. **TestRunSimulation** (7) — KPIs, results section, charts/churn/data tabs, AI section + tabs
5. **TestResultsTabs** (6) — distribution chart, captions, churn two-column, segment metrics, dataframe, download button
6. **TestAIFeaturesUI** (6) — generate button, severity explanation, chat input, optimizer controls, metric options, caption
7. **TestHistory** (5) — sidebar history, load restores, load hides empty state, delete button, compare section
8. **TestTooltips** (4) — KPI help icons, seed help, churn metric help, optimizer input help

## Files Changed
- `tests/e2e/test_app.py` — expanded from 14 to 43 tests
- `tests/e2e/test_data/invalid.csv` — test data for error state testing
