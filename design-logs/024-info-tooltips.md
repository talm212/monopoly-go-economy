# Design Log 024 — Info Tooltips for UI Elements

## Date: 2026-03-20
## Status: Complete

## Goal
Add contextual help tooltips and info captions to all metrics, charts, and sections so users understand what each element means.

## Decisions
- Use `st.metric(help=...)` for KPI metrics — renders native ℹ️ icon on hover
- Use `st.caption()` for chart and section explanations — visible inline
- Use `help=` on `st.selectbox` / `st.number_input` for optimizer and seed inputs
- Help text uses plain English with game-domain terms (flip depth, churn boost, threshold)
- Added to: KPI cards, churn segment metrics, comparison view, charts, AI tabs, optimizer inputs, seed input

## Files Changed
- `src/ui/components/kpi_cards.py` — added `help_texts` parameter to `render_kpi_cards()`
- `src/ui/components/comparison_view.py` — added help to comparison metrics
- `src/ui/app.py` — supplied help texts across all sections
