# Design Log 028 — Auto-Generate AI Insights

## Date: 2026-03-20
## Status: Complete

## Goal
Auto-trigger AI insight generation after simulation completes instead of requiring manual click.

## Approach
- After simulation run + auto-save, call `InsightsAnalyst.generate_insights()` in a try/except
- Store results in `session_state["ai_insights"]`
- On failure: log warning, never block results display
- Info banner near KPIs: "N insight(s) ready — scroll down to AI Analysis to view"
- Insights tab shows pre-generated insights immediately; "Regenerate" button for manual refresh
- Updated empty-state text to mention auto-generation

## Files Changed
- `src/ui/app.py` — added auto-insight call after simulation, notification banner, updated empty state text
