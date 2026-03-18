"""Generic simulation orchestrator: read → validate → simulate → write → store.

Works with ANY simulator via protocol interfaces. No feature-specific
imports — all dependencies are injected through the constructor.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import polars as pl

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols (structural subtyping contracts for DI)
# ---------------------------------------------------------------------------


class DataReaderProtocol(Protocol):
    """Contract for reading player data from a source."""

    def read_players(self, source: str) -> pl.DataFrame: ...
    def read_config(self, source: str) -> dict[str, Any]: ...
    def validate_players(self, df: pl.DataFrame) -> list[str]: ...


class DataWriterProtocol(Protocol):
    """Contract for writing simulation results to a destination."""

    def write_results(self, df: pl.DataFrame, destination: str) -> None: ...


class SimulationStoreProtocol(Protocol):
    """Contract for persisting simulation run metadata."""

    def save_run(self, run: dict[str, Any]) -> str: ...


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class RunSimulationUseCase:
    """Generic orchestrator: read → validate → simulate → write → store.

    Works with ANY simulator via protocol interfaces.
    Dependency injection via constructor.
    """

    def __init__(
        self,
        reader: DataReaderProtocol,
        simulator: Any,  # Simulator protocol
        writer: DataWriterProtocol | None = None,
        store: SimulationStoreProtocol | None = None,
    ) -> None:
        self._reader = reader
        self._simulator = simulator
        self._writer = writer
        self._store = store

    def execute(
        self,
        player_source: str,
        config: Any,  # SimulatorConfig
        output_destination: str | None = None,
        seed: int | None = None,
    ) -> Any:  # SimulationResult
        """Run the full simulation pipeline.

        Steps:
            1. Read player data from source
            2. Validate input via simulator's validator
            3. Run simulation
            4. Write output (if destination and writer provided)
            5. Store run metadata (if store provided)
            6. Return result

        Args:
            player_source: Path or URI to the player data.
            config: Feature-specific configuration satisfying SimulatorConfig.
            output_destination: Optional path for writing result CSV.
            seed: Optional RNG seed for reproducibility.

        Returns:
            SimulationResult from the simulator.

        Raises:
            ValueError: If input validation fails.
            FileNotFoundError: If the player source does not exist.
        """
        # 1. Read players
        players = self._reader.read_players(player_source)

        # 2. Validate input via the simulator's domain-level validator
        errors = self._simulator.validate_input(players)
        if errors:
            raise ValueError(f"Input validation failed: {'; '.join(errors)}")

        # 3. Simulate
        logger.info("Running simulation with %d players", players.shape[0])
        result = self._simulator.simulate(players, config, seed=seed)
        logger.info(
            "Simulation complete: %d interactions",
            result.to_summary_dict().get("total_interactions", 0),
        )

        # 4. Write output (only when both destination and writer are present)
        if output_destination and self._writer:
            self._writer.write_results(result.to_dataframe(), output_destination)
            logger.info("Results written to %s", output_destination)

        # 5. Store run metadata
        if self._store:
            run_data = {
                "config": config.to_dict(),
                "result_summary": result.to_summary_dict(),
            }
            run_id = self._store.save_run(run_data)
            logger.info("Run stored with ID: %s", run_id)

        return result
