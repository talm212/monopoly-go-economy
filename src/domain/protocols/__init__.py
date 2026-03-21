"""Domain protocols package — re-exports all protocols for backward compatibility."""

from src.domain.protocols.analysis import FeatureAnalysisContext
from src.domain.protocols.display import ConfigField, ConfigFieldType, ConfigSchema, ResultsDisplay
from src.domain.protocols.llm import LLMClient
from src.domain.protocols.simulation import Simulator, SimulatorConfig, SimulationResult

__all__ = [
    "ConfigField",
    "ConfigFieldType",
    "ConfigSchema",
    "FeatureAnalysisContext",
    "LLMClient",
    "ResultsDisplay",
    "Simulator",
    "SimulatorConfig",
    "SimulationResult",
]
