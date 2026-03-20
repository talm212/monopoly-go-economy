# Design Log 026 — Fix CSS History Label

## Date: 2026-03-20
## Status: Complete

## Problem
The CSS `::after` pseudo-element approach for adding "History" text next to the sidebar toggle relied on Streamlit-internal `data-testid` selectors that change between versions.

## Solution
Replaced fragile `::after` CSS with a fixed-position `<div class="history-label">` element:
- Uses `position: fixed` at `top: 12px; left: 48px` — appears next to the sidebar arrow
- `pointer-events: none` so it doesn't interfere with clicks
- No dependency on Streamlit internal selectors — works across versions

## Files Changed
- `src/ui/app.py` — replaced CSS `::after` with positioned div
