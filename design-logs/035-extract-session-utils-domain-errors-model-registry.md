# 035 — Extract Session Utils, Domain Exceptions, Model Registry

**Date:** 2026-03-21
**Status:** Complete

## Context

Three architecture improvements to reduce duplication and improve type safety:
1. `_clear_stale_ai_data` was copy-pasted across 3 files with different key sets
2. Domain validation used generic `ValueError` with no hierarchy
3. Bedrock model IDs were hardcoded in the adapter with no central registry

## Decisions

### Task 1: Session Utils (#58)
- Created `src/ui/session_utils.py` with canonical `clear_stale_ai_data()` and `config_changed_since_last_run()`
- Used ai_analysis.py version as canonical (most complete, includes optimizer keys)
- Replaced all 3 duplicates in app.py, ai_analysis.py, sidebar_history.py
- Removed backward-compat aliases in app.py (no tests depended on them)
- Dropped underscore prefix since these are now public module-level functions

### Task 2: Domain Exceptions (#63)
- Created `src/domain/errors.py` with `SimulationError`, `InvalidConfigError`, `InvalidPlayerDataError`
- Made `InvalidConfigError` and `InvalidPlayerDataError` inherit from both `SimulationError` AND `ValueError` for backward compatibility
- This ensures existing `except ValueError` blocks and `pytest.raises(ValueError)` continue to work
- Updated coin_flip.py, loot_table.py, local_reader.py to raise domain-specific exceptions
- Updated UI catch blocks to explicitly list domain exception types alongside ValueError

### Task 3: Model Registry (#64)
- Created `src/infrastructure/llm/registry.py` with `AVAILABLE_MODELS` dict and `DEFAULT_MODEL_LABEL`
- Updated `BedrockAdapter.__init__` to import defaults from registry
- Registry is provider-agnostic; can be used by UI model selector in future

## Outcome

All 562 tests pass. Zero breaking changes thanks to multiple inheritance for backward compat.
