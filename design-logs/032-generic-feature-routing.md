# 032 — Generic Feature Routing

## Status: Done
## Date: 2026-03-21

## Context

The app is hardcoded for the coin_flip feature. We need URL-based routing so each
game mechanic (coin flip, loot tables, reward distributions) gets its own page/section.
This is a prerequisite for adding any new simulator feature to the dashboard.

## Decision

Use `st.query_params` (Streamlit 1.55+) for routing:
- `?feature=coin_flip` selects the coin flip simulator
- A `FeatureUIConfig` registry maps feature names to display metadata
- Feature selector in the sidebar or top of page syncs with URL
- Sidebar history filters by the currently selected feature
- All existing coin_flip functionality remains untouched

## Approach

1. Create `src/ui/feature_router.py` with `FeatureUIConfig` dataclass and `FEATURE_REGISTRY`
2. Add feature selector to `app.py` using `st.query_params`
3. Wrap coin_flip-specific code in a feature check; other features show "Coming soon"
4. Update sidebar history to filter by current feature
5. Add tests for the feature router module

## Outcome

Implemented successfully. All 367 tests pass (17 new feature router tests).

### Files created:
- `src/ui/feature_router.py` — `FeatureUIConfig` dataclass, `FEATURE_REGISTRY`, and helper functions
- `tests/ui/test_feature_router.py` — 17 unit tests covering registry, config lookup, validation

### Files modified:
- `src/ui/app.py` — Integrated feature routing via `st.query_params["feature"]`, dynamic page title, feature guard with "Coming soon" placeholder for unimplemented features, feature-filtered history loading on startup
- `src/ui/sections/sidebar_history.py` — `render_sidebar_history()` now accepts optional `feature` parameter to filter history runs

### Key decisions:
- Feature selector only shown when >1 feature is registered (avoids UI clutter)
- Invalid `?feature=` values silently reset to the default (coin_flip)
- `st.stop()` used to halt rendering for unimplemented features after showing placeholder
- Sidebar history filtered by current feature so each feature sees only its own runs
- Backward-compatible: `render_sidebar_history(store)` still works without feature param
