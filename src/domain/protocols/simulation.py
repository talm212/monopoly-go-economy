"""Simulation protocols — contracts for simulator engines, configs, and results.

These protocols define the foundational abstractions that every simulator
implementation (coin flip, loot table, etc.) must conform to.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

import polars as pl

TConfig = TypeVar("TConfig", bound="SimulatorConfig")
TResult = TypeVar("TResult", bound="SimulationResult")


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
