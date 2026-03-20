"""Core simulator protocols defining the contracts every simulator must implement.

These are the foundational abstractions for the economy simulation platform.
All simulator implementations (coin flip, loot tables, etc.) conform to these
protocols, enabling a uniform interface for orchestration, UI, and testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable

import polars as pl

TConfig = TypeVar("TConfig", bound="SimulatorConfig")
TResult = TypeVar("TResult", bound="SimulationResult")


# ---------------------------------------------------------------------------
# Config schema — reusable metadata for building UI editors
# ---------------------------------------------------------------------------


class ConfigFieldType(Enum):
    """Supported field types for config editor rendering."""

    INTEGER = "integer"
    FLOAT = "float"
    PERCENTAGE = "percentage"  # stored as decimal (0.6), displayed as "60%"


@dataclass(frozen=True)
class ConfigField:
    """Metadata for a single configuration field.

    Attributes:
        name: Internal key name (e.g., "p_success_1").
        display_name: Human-readable label (e.g., "P(Success 1)").
        field_type: Determines widget rendering and conversion logic.
        default: Default value in internal representation.
        min_value: Optional lower bound for validation/widget constraints.
        max_value: Optional upper bound for validation/widget constraints.
        help_text: Tooltip or description shown in the UI.
        group: Logical grouping key (e.g., "probabilities", "points").
    """

    name: str
    display_name: str
    field_type: ConfigFieldType
    default: float | int
    min_value: float | int | None = None
    max_value: float | int | None = None
    help_text: str = ""
    group: str = ""


@dataclass
class ConfigSchema:
    """Describes the full set of configurable fields for a simulator feature.

    Provides conversion between internal config dicts (domain representation)
    and display dicts (UI-friendly representation with formatted percentages).
    """

    fields: list[ConfigField] = field(default_factory=list)

    def to_display_dict(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Convert an internal config dict to display format.

        PERCENTAGE fields are converted from decimal (0.6) to percentage
        string ("60%").  Other field types are passed through unchanged.
        """
        display: dict[str, Any] = {}
        field_map = {f.name: f for f in self.fields}
        for key, value in config_dict.items():
            schema_field = field_map.get(key)
            if schema_field is not None and schema_field.field_type == ConfigFieldType.PERCENTAGE:
                display[key] = f"{round(float(value) * 100):.0f}%"
            elif schema_field is not None and schema_field.field_type == ConfigFieldType.INTEGER:
                display[key] = int(value)
            else:
                display[key] = value
        return display

    def from_display_dict(self, display_dict: dict[str, Any]) -> dict[str, Any]:
        """Convert a display dict back to internal config format.

        Percentage strings ("60%") are converted to decimals (0.6).
        INTEGER display values are kept as int.
        """
        internal: dict[str, Any] = {}
        field_map = {f.name: f for f in self.fields}
        for key, value in display_dict.items():
            schema_field = field_map.get(key)
            if schema_field is not None and schema_field.field_type == ConfigFieldType.PERCENTAGE:
                if isinstance(value, str) and value.endswith("%"):
                    internal[key] = float(value[:-1]) / 100.0
                else:
                    internal[key] = float(value)
            elif schema_field is not None and schema_field.field_type == ConfigFieldType.INTEGER:
                internal[key] = int(value)
            else:
                internal[key] = value
        return internal

    def get_groups(self) -> list[str]:
        """Return ordered unique group names, preserving first-seen order."""
        seen: set[str] = set()
        groups: list[str] = []
        for f in self.fields:
            if f.group and f.group not in seen:
                seen.add(f.group)
                groups.append(f.group)
        return groups

    def fields_by_group(self) -> dict[str, list[ConfigField]]:
        """Return fields organized by group name.

        Ungrouped fields (empty group string) are collected under the "" key.
        """
        result: dict[str, list[ConfigField]] = {}
        for f in self.fields:
            result.setdefault(f.group, []).append(f)
        return result


@dataclass(frozen=True)
class FeatureAnalysisContext:
    """Generic AI analysis context that any feature simulator can produce.

    Encapsulates all the data needed by InsightsAnalyst, ChatAssistant,
    and ConfigOptimizer so the AI layer is feature-agnostic.

    Attributes:
        feature_name: Identifier for the simulation feature (e.g. "coin_flip").
        result_summary: High-level summary from SimulationResult.to_summary_dict().
        distribution: Outcome distribution from SimulationResult.get_distribution().
        config: Configuration dict from SimulatorConfig.to_dict().
        kpi_metrics: Key performance indicators from SimulationResult.get_kpi_metrics().
        segment_data: Optional breakdown by player segment (e.g. churn vs non-churn).
    """

    feature_name: str
    result_summary: dict[str, Any]
    distribution: dict[str, int]
    config: dict[str, Any]
    kpi_metrics: dict[str, float]
    segment_data: dict[str, Any] | None = field(default=None)


@runtime_checkable
class SimulatorConfig(Protocol):
    """Contract for simulator configuration objects.

    Implementations should be dataclasses or pydantic models holding
    all tunable parameters for a specific simulation feature.
    """

    def validate(self) -> None:
        """Raise ValueError if the configuration is invalid."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a plain dictionary."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulatorConfig:
        """Construct a configuration instance from a plain dictionary."""
        ...


@runtime_checkable
class SimulationResult(Protocol):
    """Contract for simulation result objects.

    Wraps the raw output of a simulation run and provides
    standard accessors for summaries, distributions, and KPIs.
    """

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a high-level summary as a dictionary."""
        ...

    def to_dataframe(self) -> pl.DataFrame:
        """Return the full result data as a Polars DataFrame."""
        ...

    def get_distribution(self) -> dict[str, int]:
        """Return a distribution of results bucketed by string keys."""
        ...

    def get_kpi_metrics(self) -> dict[str, float]:
        """Return key performance indicators as metric-name to float-value."""
        ...


@runtime_checkable
class Simulator(Protocol):
    """Contract for simulator engines.

    Each game feature (coin flip, loot table, etc.) implements this
    protocol to provide a consistent simulate-and-validate interface.
    """

    def simulate(
        self,
        players: pl.DataFrame,
        config: SimulatorConfig,
        seed: int | None = None,
    ) -> SimulationResult:
        """Run the simulation for all players with the given config.

        Args:
            players: Polars DataFrame with at least a ``user_id`` column.
            config: Feature-specific configuration satisfying SimulatorConfig.
            seed: Optional RNG seed for reproducibility.

        Returns:
            A SimulationResult wrapping the per-player outcomes.
        """
        ...

    def validate_input(self, players: pl.DataFrame) -> list[str]:
        """Validate the player DataFrame and return a list of error messages.

        Returns an empty list when the input is valid.
        """
        ...


@runtime_checkable
class ResultsDisplay(Protocol):
    """Contract for rendering simulation results in the UI.

    Each simulator's result type implements this protocol so that
    the UI layer can render KPI cards, distribution charts, segment
    breakdowns, and downloadable DataFrames generically — without
    coupling to a specific feature's result model.
    """

    def get_kpi_cards(self) -> dict[str, tuple[float | int, str]]:
        """Return KPI card data as ``{label: (value, help_text)}``.

        Each entry becomes one metric card in the dashboard.
        """
        ...

    def get_distribution(self) -> dict[str, int]:
        """Return distribution data for charting (string-keyed counts)."""
        ...

    def get_segments(self) -> dict[str, dict[str, float]] | None:
        """Return optional segment breakdowns.

        Returns ``None`` when no segmentation is available.
        Keys are segment names (e.g. ``"churn"``, ``"non-churn"``);
        values map metric labels to numeric values.
        """
        ...

    def get_dataframe(self) -> pl.DataFrame:
        """Return the full result DataFrame for download / display."""
        ...


@runtime_checkable
class LLMClient(Protocol):
    """Contract for LLM client adapters.

    All adapters (Anthropic direct, Bedrock, etc.) implement this
    protocol to provide a uniform interface for text completion.
    """

    async def complete(self, prompt: str, system: str = "") -> str:
        """Send a prompt to the LLM and return the text response.

        Args:
            prompt: The user message to send.
            system: Optional system prompt. Defaults to a generic assistant prompt.

        Returns:
            The model's text response.
        """
        ...
