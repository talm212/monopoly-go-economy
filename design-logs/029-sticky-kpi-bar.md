# Design Log 029 — Sticky KPI Bar

## Date: 2026-03-20
## Status: Complete

## Goal
Make KPI metrics bar sticky at top of viewport while user scrolls through results and AI sections.

## Approach
- CSS `position: sticky` via `st.markdown` injection (no JavaScript)
- Hidden marker div `data-testid="sticky-kpi-bar"` inside the KPI container
- CSS `:has()` selector targets the parent wrapper when the marker is present
- `z-index: 999` keeps it above scrolling content
- `box-shadow` provides visual separation from content below
- Uses `var(--background-color, white)` for theme compatibility

## Files Changed
- `src/ui/app.py` — added CSS rule and marker div inside KPI container
