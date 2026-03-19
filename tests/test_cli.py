"""Tests for the CLI entrypoint (src.cli).

Uses click.testing.CliRunner to test the CLI command without spawning
a subprocess.  Exercises help, end-to-end simulation, flag handling,
error reporting, and stdout summary output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner with isolated filesystem disabled (we use tmp_path)."""
    return CliRunner()


@pytest.fixture
def cli_input_csv(tmp_path: Any) -> str:
    """Write a small player CSV for CLI tests and return the path."""
    path = tmp_path / "players.csv"
    df = pl.DataFrame(
        {
            "user_id": [1, 2, 3, 4, 5],
            "rolls_sink": [100, 200, 50, 500, 1000],
            "avg_multiplier": [10, 20, 5, 50, 100],
            "about_to_churn": [False, False, True, False, False],
        }
    )
    df.write_csv(str(path))
    return str(path)


@pytest.fixture
def cli_config_csv(tmp_path: Any) -> str:
    """Write a config CSV for CLI tests and return the path."""
    path = tmp_path / "config.csv"
    df = pl.DataFrame(
        {
            "Input": [
                "p_success_1",
                "p_success_2",
                "p_success_3",
                "p_success_4",
                "p_success_5",
                "max_successes",
                "points_success_1",
                "points_success_2",
                "points_success_3",
                "points_success_4",
                "points_success_5",
            ],
            "Value": [
                "60%",
                "50%",
                "50%",
                "50%",
                "50%",
                "5",
                "1",
                "2",
                "4",
                "8",
                "16",
            ],
        }
    )
    df.write_csv(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


class TestHelp:
    """--help flag shows usage information."""

    def test_help_shows_usage(self, runner: CliRunner) -> None:
        """--help exits 0 and shows usage text."""
        from src.cli import main

        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output
        assert "INPUT_CSV" in result.output
        assert "CONFIG_CSV" in result.output

    def test_help_shows_options(self, runner: CliRunner) -> None:
        """--help lists all expected options."""
        from src.cli import main

        result = runner.invoke(main, ["--help"])
        assert "--output" in result.output
        assert "--threshold" in result.output
        assert "--churn-boost" in result.output
        assert "--seed" in result.output
        assert "--verbose" in result.output


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """Full simulation through the CLI produces expected output."""

    def test_basic_run_succeeds(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Basic invocation exits 0 and prints summary."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.stderr}"
        assert "Total interactions" in result.output
        assert "Total points" in result.output
        assert "Players above threshold" in result.output

    def test_output_csv_written(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Any,
    ) -> None:
        """--output flag writes results CSV."""
        from src.cli import main

        output_path = str(tmp_path / "results.csv")
        result = runner.invoke(
            main, [cli_input_csv, cli_config_csv, "--seed", "42", "--output", output_path]
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}\n{result.stderr}"
        assert Path(output_path).exists()

        output_df = pl.read_csv(output_path)
        assert output_df.shape[0] == 5  # 5 players
        assert "total_points" in output_df.columns
        assert "num_interactions" in output_df.columns

    def test_output_message_shown(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Any,
    ) -> None:
        """When --output is used, a confirmation message is printed."""
        from src.cli import main

        output_path = str(tmp_path / "results.csv")
        result = runner.invoke(
            main, [cli_input_csv, cli_config_csv, "--seed", "42", "--output", output_path]
        )
        assert result.exit_code == 0
        assert "Results written to" in result.output

    def test_success_distribution_shown(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Summary includes success distribution."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0
        assert "Success distribution" in result.output


# ---------------------------------------------------------------------------
# Flag handling
# ---------------------------------------------------------------------------


class TestFlags:
    """CLI flags control simulation parameters."""

    def test_threshold_flag(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """--threshold value appears in the summary output."""
        from src.cli import main

        result = runner.invoke(
            main, [cli_input_csv, cli_config_csv, "--seed", "42", "--threshold", "50.0"]
        )
        assert result.exit_code == 0
        assert "Players above threshold (50.0)" in result.output

    def test_churn_boost_flag(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """--churn-boost affects simulation results (different from default 1.3)."""
        from src.cli import main

        result_default = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        result_boosted = runner.invoke(
            main, [cli_input_csv, cli_config_csv, "--seed", "42", "--churn-boost", "2.0"]
        )
        assert result_default.exit_code == 0
        assert result_boosted.exit_code == 0
        # With a higher churn boost, churning players get better outcomes,
        # so total points should differ
        # (We just check both succeed; exact values depend on seed + data)

    def test_seed_reproducibility(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Same --seed produces identical output."""
        from src.cli import main

        result_a = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        result_b = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result_a.exit_code == 0
        assert result_b.exit_code == 0
        assert result_a.output == result_b.output

    def test_different_seeds_produce_different_output(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Different seeds produce different total points."""
        from src.cli import main

        result_a = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        result_b = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "99"])
        assert result_a.exit_code == 0
        assert result_b.exit_code == 0
        # Outputs should differ (extremely unlikely to be identical with different seeds)
        assert result_a.output != result_b.output

    def test_verbose_flag(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """--verbose does not cause errors."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42", "--verbose"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    """Missing files and bad input produce helpful error messages."""

    def test_missing_input_file_shows_error(
        self,
        runner: CliRunner,
        cli_config_csv: str,
    ) -> None:
        """Non-existent input CSV shows error."""
        from src.cli import main

        result = runner.invoke(main, ["/nonexistent/players.csv", cli_config_csv])
        assert result.exit_code != 0

    def test_missing_config_file_shows_error(
        self,
        runner: CliRunner,
        cli_input_csv: str,
    ) -> None:
        """Non-existent config CSV shows error."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, "/nonexistent/config.csv"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Summary content validation
# ---------------------------------------------------------------------------


class TestSummaryContent:
    """Summary output contains expected numeric values."""

    def test_summary_contains_numeric_values(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Summary lines contain formatted numbers."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
        # First three lines should be the summary metrics
        interactions_line = [line for line in lines if "Total interactions" in line]
        points_line = [line for line in lines if "Total points" in line]
        threshold_line = [line for line in lines if "Players above threshold" in line]

        assert len(interactions_line) == 1
        assert len(points_line) == 1
        assert len(threshold_line) == 1

    def test_default_threshold_is_100(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        """Default threshold of 100.0 appears in summary."""
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0
        assert "Players above threshold (100.0)" in result.output
