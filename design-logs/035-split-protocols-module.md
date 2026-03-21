# 035 — Split protocols.py God Module into Focused Sub-Modules

## Status: Complete

## Context
`src/domain/protocols.py` has grown into a God module with 8+ distinct concerns:
- Simulation protocols (SimulatorConfig, SimulationResult, Simulator)
- Display protocols (ConfigFieldType, ConfigField, ConfigSchema, ResultsDisplay)
- Analysis data class (FeatureAnalysisContext)
- LLM protocol (LLMClient)

This violates the Single Responsibility Principle. Each concern should live in its own module within a `protocols` package.

## Decision
Split `protocols.py` into a package with focused sub-modules:
- `protocols/simulation.py` — SimulatorConfig, SimulationResult, Simulator
- `protocols/display.py` — ConfigFieldType, ConfigField, ConfigSchema, ResultsDisplay
- `protocols/analysis.py` — FeatureAnalysisContext
- `protocols/llm.py` — LLMClient
- `protocols/__init__.py` — re-exports everything for backward compatibility

## Key Considerations
- **Backward compatibility**: All existing `from src.domain.protocols import X` imports must continue to work via `__init__.py` re-exports.
- **Cross-references**: `Simulator` references `SimulatorConfig` and `SimulationResult`. Keep them in the same `simulation.py` module to avoid circular imports.
- **TypeVars**: `TConfig` and `TResult` are only used locally; keep them in `simulation.py`.
- **Note**: `SimulatorRegistry` is NOT in protocols.py — it's in `src/domain/simulators/registry.py`. The task description mentioned it but it doesn't exist in the source file.

## Outcome
Split successfully. All 562 tests pass. No import changes required in any consumer
because `__init__.py` re-exports everything for backward compatibility.
