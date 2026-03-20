# 032 — Generic Config Editor (Reusable Across Features)

## Status: Complete

## Context
The current config editor (`src/ui/components/config_editor.py`) renders form fields from a raw dict by inspecting value types at runtime. This works but is entirely untyped — it has no knowledge of what a field represents (probability vs. integer vs. percentage). As we add more simulators beyond coin flip, each feature needs a structured way to declare its config schema so the UI can render appropriate widgets with validation, grouping, and display formatting.

## Decision
Introduce a `ConfigSchema` / `ConfigField` abstraction in the domain layer (`protocols.py`) that:
1. Defines field metadata (type, bounds, display name, grouping) as explicit domain objects
2. Handles conversion between internal representation and display format (e.g., 0.6 -> "60%")
3. Provides a `schema()` classmethod on `CoinFlipConfig` as the first adopter
4. Powers a new `generic_config_editor.py` UI component that renders widgets from schema metadata

This is an **addition** — the existing `config_editor.py` remains untouched for backwards compatibility.

## Approach
1. Add `ConfigFieldType`, `ConfigField`, `ConfigSchema` dataclasses to `src/domain/protocols.py`
2. Add `schema()` classmethod to `CoinFlipConfig`
3. Create `src/ui/components/generic_config_editor.py` rendering function
4. Write tests for schema conversion logic and CoinFlipConfig.schema()
5. All existing tests must continue to pass

## Risks
- `ConfigSchema.to_display_dict` / `from_display_dict` must be exact inverses (roundtrip fidelity)
- Percentage fields store as decimal internally but display as "X%" — must handle edge cases (0%, 100%)

## Outcome
All three steps implemented successfully. 32 new tests pass, 408 total tests pass (0 failures).

### Files changed
- `src/domain/protocols.py` — Added `ConfigFieldType` enum, `ConfigField` frozen dataclass, `ConfigSchema` dataclass with `to_display_dict`, `from_display_dict`, `get_groups`, `fields_by_group`
- `src/domain/models/coin_flip.py` — Added `schema()` classmethod to `CoinFlipConfig`
- `src/ui/components/generic_config_editor.py` — New schema-driven editor with `render_schema_editor()`, per-type rendering helpers
- `tests/domain/test_config_schema.py` — 32 tests covering field types, schema conversion, grouping, roundtrips, and CoinFlipConfig.schema()
