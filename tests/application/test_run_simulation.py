"""Tests for the generic RunSimulationUseCase orchestrator.

Validates read → validate → simulate → write → store pipeline using
CoinFlipSimulator as the concrete simulator implementation for DI wiring.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

from src.application.run_simulation import RunSimulationUseCase
from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult
from src.domain.simulators.coin_flip import CoinFlipSimulator
from src.infrastructure.readers.local_reader import LocalDataReader
from src.infrastructure.writers.local_writer import LocalDataWriter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def coin_flip_config() -> CoinFlipConfig:
    """Standard 5-flip config for testing."""
    return CoinFlipConfig(
        max_successes=5,
        probabilities=[0.60, 0.50, 0.50, 0.50, 0.50],
        point_values=[1.0, 2.0, 4.0, 8.0, 16.0],
        churn_boost_multiplier=1.3,
        reward_threshold=100.0,
    )


@pytest.fixture
def reader() -> LocalDataReader:
    return LocalDataReader()


@pytest.fixture
def writer() -> LocalDataWriter:
    return LocalDataWriter()


@pytest.fixture
def simulator() -> CoinFlipSimulator:
    return CoinFlipSimulator()


@pytest.fixture
def mock_store() -> MagicMock:
    """Mock SimulationStoreProtocol."""
    store = MagicMock()
    store.save_run.return_value = "run-abc-123"
    return store


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """RunSimulationUseCase correctly reads, simulates, and returns results."""

    def test_execute_returns_result(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """Execute returns a CoinFlipResult with expected structure."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator)
        result = use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            seed=42,
        )

        assert isinstance(result, CoinFlipResult)
        assert result.total_interactions > 0
        assert result.player_results.shape[0] == 3  # 3 players in fixture

    def test_execute_deterministic_with_seed(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """Same seed produces identical results."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator)

        result_a = use_case.execute(
            player_source=sample_input_csv, config=coin_flip_config, seed=42
        )
        result_b = use_case.execute(
            player_source=sample_input_csv, config=coin_flip_config, seed=42
        )

        assert result_a.total_points == result_b.total_points
        assert result_a.total_interactions == result_b.total_interactions

    def test_result_has_expected_columns(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """Player results DataFrame contains total_points and num_interactions."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator)
        result = use_case.execute(player_source=sample_input_csv, config=coin_flip_config, seed=42)

        assert "total_points" in result.player_results.columns
        assert "num_interactions" in result.player_results.columns
        assert "user_id" in result.player_results.columns


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


class TestOutputWriting:
    """Results are written to file only when a destination is provided."""

    def test_output_file_written_when_destination_provided(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
        writer: LocalDataWriter,
        tmp_path: Any,
    ) -> None:
        """A CSV file is created at the output destination."""
        output_path = str(tmp_path / "output.csv")
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, writer=writer)
        use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            output_destination=output_path,
            seed=42,
        )

        output_df = pl.read_csv(output_path)
        assert output_df.shape[0] == 3
        assert "total_points" in output_df.columns

    def test_no_output_file_when_destination_is_none(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
        writer: LocalDataWriter,
        tmp_path: Any,
    ) -> None:
        """No file is created when output_destination is None."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, writer=writer)
        result = use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            output_destination=None,
            seed=42,
        )

        assert isinstance(result, CoinFlipResult)
        # tmp_path should remain empty (only the input CSV in parent)
        output_files = list(tmp_path.glob("output*"))
        assert len(output_files) == 0

    def test_no_write_when_writer_is_none(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
        tmp_path: Any,
    ) -> None:
        """No error even when writer is None and destination is provided."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, writer=None)
        # Should not raise even though destination is given but writer is None
        result = use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            output_destination=str(tmp_path / "output.csv"),
            seed=42,
        )

        assert isinstance(result, CoinFlipResult)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Validation failures raise ValueError with descriptive messages."""

    def test_missing_column_raises_value_error(
        self,
        tmp_path: Any,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """Missing required column triggers ValueError from validator."""
        bad_csv = tmp_path / "bad_players.csv"
        # Missing rolls_sink and avg_multiplier columns
        pl.DataFrame(
            {
                "user_id": [1, 2],
                "about_to_churn": [False, True],
            }
        ).write_csv(str(bad_csv))

        use_case = RunSimulationUseCase(reader=reader, simulator=simulator)

        with pytest.raises(ValueError, match="Missing required column"):
            use_case.execute(
                player_source=str(bad_csv),
                config=coin_flip_config,
                seed=42,
            )

    def test_validation_error_message_includes_all_errors(
        self,
        tmp_path: Any,
        coin_flip_config: CoinFlipConfig,
        simulator: CoinFlipSimulator,
    ) -> None:
        """Multiple validation errors are joined into one message."""
        bad_csv = tmp_path / "bad_players.csv"
        # Missing both rolls_sink and avg_multiplier
        pl.DataFrame(
            {
                "user_id": [1, 2],
                "about_to_churn": [False, True],
            }
        ).write_csv(str(bad_csv))

        # Use a reader that does NOT raise on its own validation,
        # so the use case's simulator validation can catch the errors.
        # LocalDataReader.read_players raises on missing columns itself,
        # so we use a minimal reader that skips its own validation.
        class PassThroughReader:
            def read_players(self, source: str) -> pl.DataFrame:
                return pl.read_csv(source)

            def read_config(self, source: str) -> dict[str, Any]:
                return {}

            def validate_players(self, df: pl.DataFrame) -> list[str]:
                return []

        use_case = RunSimulationUseCase(reader=PassThroughReader(), simulator=simulator)

        with pytest.raises(ValueError, match="Input validation failed") as exc_info:
            use_case.execute(
                player_source=str(bad_csv),
                config=coin_flip_config,
                seed=42,
            )

        error_msg = str(exc_info.value)
        assert "rolls_sink" in error_msg
        assert "avg_multiplier" in error_msg


# ---------------------------------------------------------------------------
# SimulationStore integration
# ---------------------------------------------------------------------------


class TestSimulationStore:
    """Optional store is called with run data when provided."""

    def test_store_save_run_called(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
        mock_store: MagicMock,
    ) -> None:
        """store.save_run is invoked with config and result summary."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, store=mock_store)
        use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            seed=42,
        )

        mock_store.save_run.assert_called_once()
        call_args = mock_store.save_run.call_args[0][0]
        assert "config" in call_args
        assert "result_summary" in call_args
        assert call_args["config"]["max_successes"] == 5

    def test_store_not_called_when_none(
        self,
        sample_input_csv: str,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """No error when store is None."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, store=None)
        # Should complete without error
        result = use_case.execute(
            player_source=sample_input_csv,
            config=coin_flip_config,
            seed=42,
        )
        assert isinstance(result, CoinFlipResult)


# ---------------------------------------------------------------------------
# Reader error propagation
# ---------------------------------------------------------------------------


class TestReaderErrors:
    """Errors from the reader propagate correctly."""

    def test_file_not_found_propagates(
        self,
        coin_flip_config: CoinFlipConfig,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
    ) -> None:
        """FileNotFoundError from reader propagates to caller."""
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator)

        with pytest.raises((FileNotFoundError, OSError)):
            use_case.execute(
                player_source="/nonexistent/path/players.csv",
                config=coin_flip_config,
                seed=42,
            )


# ---------------------------------------------------------------------------
# Generic: use case has no coin-flip imports
# ---------------------------------------------------------------------------


class TestGenericDesign:
    """RunSimulationUseCase itself imports NO coin-flip specific types."""

    def test_use_case_module_has_no_coin_flip_imports(self) -> None:
        """The run_simulation module does not import any coin-flip classes."""
        import inspect

        import src.application.run_simulation as mod

        source = inspect.getsource(mod)
        assert "CoinFlip" not in source
        assert "coin_flip" not in source.lower().replace("# ", "")  # ignore comments if structured

    def test_use_case_accepts_any_simulator_protocol(self) -> None:
        """RunSimulationUseCase can be instantiated with mock protocols."""
        mock_reader = MagicMock()
        mock_simulator = MagicMock()
        mock_writer = MagicMock()

        # Should not raise
        use_case = RunSimulationUseCase(
            reader=mock_reader,
            simulator=mock_simulator,
            writer=mock_writer,
        )
        assert use_case is not None


# ---------------------------------------------------------------------------
# Integration: works with actual CSV files from conftest
# ---------------------------------------------------------------------------


class TestIntegrationWithCSVFiles:
    """End-to-end with sample CSV fixtures from conftest."""

    def test_full_pipeline_with_csv_fixtures(
        self,
        sample_input_csv: str,
        sample_config_csv: str,
        reader: LocalDataReader,
        simulator: CoinFlipSimulator,
        writer: LocalDataWriter,
        tmp_path: Any,
    ) -> None:
        """Full pipeline: read CSV → parse config → simulate → write output."""
        # Read config CSV and build CoinFlipConfig
        config_dict = reader.read_config(sample_config_csv)
        config = CoinFlipConfig.from_csv_dict({k: str(v) for k, v in config_dict.items()})

        output_path = str(tmp_path / "results.csv")
        use_case = RunSimulationUseCase(reader=reader, simulator=simulator, writer=writer)
        result = use_case.execute(
            player_source=sample_input_csv,
            config=config,
            output_destination=output_path,
            seed=42,
        )

        assert isinstance(result, CoinFlipResult)
        assert result.total_interactions > 0

        # Verify output file
        output_df = pl.read_csv(output_path)
        assert output_df.shape[0] == 3
        assert "total_points" in output_df.columns
        assert "num_interactions" in output_df.columns
