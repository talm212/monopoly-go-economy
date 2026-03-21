"""Display protocols — config schema metadata and result rendering contracts.

Defines the data structures for building UI config editors (ConfigFieldType,
ConfigField, ConfigSchema) and the protocol for rendering simulation results
in the dashboard (ResultsDisplay).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import polars as pl


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
