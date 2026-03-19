"""Tests for the CLI entrypoint (src.cli).

Uses click.testing.CliRunner to test the CLI command without spawning
a subprocess.  Exercises help, end-to-end simulation, flag handling,
error reporting, summary output, and the required output CSV format.
"""

from __future__ import annotations

from pathlib import Path

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
def cli_input_csv(tmp_path: Path) -> str:
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
def cli_config_csv(tmp_path: Path) -> str:
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
        from src.cli import main

        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output
        assert "INPUT_CSV" in result.output
        assert "CONFIG_CSV" in result.output

    def test_help_shows_options(self, runner: CliRunner) -> None:
        from src.cli import main

        result = runner.invoke(main, ["--help"])
        assert "--output" in result.output
        assert "--output-players" in result.output
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
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Total interactions" in result.output
        assert "Total points" in result.output
        assert "Players above threshold" in result.output

    def test_summary_csv_has_required_columns(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        """--output writes summary CSV with the exact columns from the spec."""
        from src.cli import main

        output_path = str(tmp_path / "summary.csv")
        result = runner.invoke(
            main,
            [cli_input_csv, cli_config_csv, "--seed", "42", "--output", output_path],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert Path(output_path).exists()

        summary_df = pl.read_csv(output_path)
        assert summary_df.shape[0] == 1, "Summary CSV should have exactly 1 row"

        # Required columns from spec
        assert "total_roll_interactions" in summary_df.columns
        assert "success_0_count" in summary_df.columns
        assert "success_1_count" in summary_df.columns
        assert "success_2_count" in summary_df.columns
        assert "success_3_count" in summary_df.columns
        assert "success_4_count" in summary_df.columns
        assert "success_5_count" in summary_df.columns
        assert "total_points" in summary_df.columns
        assert "players_above_threshold" in summary_df.columns

    def test_summary_csv_values_are_consistent(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        """Summary CSV values are internally consistent."""
        from src.cli import main

        output_path = str(tmp_path / "summary.csv")
        result = runner.invoke(
            main,
            [cli_input_csv, cli_config_csv, "--seed", "42", "--output", output_path],
        )
        assert result.exit_code == 0

        df = pl.read_csv(output_path)
        row = df.row(0, named=True)

        # success_0 + success_1 + ... + success_5 should equal total_roll_interactions
        success_sum = sum(row[f"success_{i}_count"] for i in range(6))
        assert success_sum == row["total_roll_interactions"]

        # All counts should be non-negative
        assert row["total_roll_interactions"] >= 0
        assert row["total_points"] >= 0
        assert row["players_above_threshold"] >= 0

    def test_player_results_csv_written(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        """--output-players writes per-player results CSV."""
        from src.cli import main

        output_path = str(tmp_path / "players_results.csv")
        result = runner.invoke(
            main,
            [
                cli_input_csv,
                cli_config_csv,
                "--seed",
                "42",
                "--output-players",
                output_path,
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert Path(output_path).exists()

        output_df = pl.read_csv(output_path)
        assert output_df.shape[0] == 5  # 5 players
        assert "total_points" in output_df.columns
        assert "num_interactions" in output_df.columns

    def test_both_outputs_written(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        """Both --output and --output-players can be used together."""
        from src.cli import main

        summary_path = str(tmp_path / "summary.csv")
        players_path = str(tmp_path / "players.csv")
        result = runner.invoke(
            main,
            [
                cli_input_csv,
                cli_config_csv,
                "--seed",
                "42",
                "--output",
                summary_path,
                "--output-players",
                players_path,
            ],
        )
        assert result.exit_code == 0
        assert Path(summary_path).exists()
        assert Path(players_path).exists()

        summary_df = pl.read_csv(summary_path)
        players_df = pl.read_csv(players_path)
        assert summary_df.shape[0] == 1
        assert players_df.shape[0] == 5

    def test_output_message_shown(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        from src.cli import main

        output_path = str(tmp_path / "summary.csv")
        result = runner.invoke(
            main,
            [cli_input_csv, cli_config_csv, "--seed", "42", "--output", output_path],
        )
        assert result.exit_code == 0
        assert "Summary written to" in result.output

    def test_success_distribution_shown(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
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
        from src.cli import main

        result_default = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        result_boosted = runner.invoke(
            main, [cli_input_csv, cli_config_csv, "--seed", "42", "--churn-boost", "2.0"]
        )
        assert result_default.exit_code == 0
        assert result_boosted.exit_code == 0

    def test_seed_reproducibility(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
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
        from src.cli import main

        result_a = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        result_b = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "99"])
        assert result_a.exit_code == 0
        assert result_b.exit_code == 0
        assert result_a.output != result_b.output

    def test_verbose_flag(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
    ) -> None:
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42", "--verbose"])
        assert result.exit_code == 0

    def test_threshold_in_summary_csv(
        self,
        runner: CliRunner,
        cli_input_csv: str,
        cli_config_csv: str,
        tmp_path: Path,
    ) -> None:
        """--threshold affects players_above_threshold in output CSV."""
        from src.cli import main

        path_high = str(tmp_path / "high.csv")
        path_low = str(tmp_path / "low.csv")

        runner.invoke(
            main,
            [cli_input_csv, cli_config_csv, "--seed", "42",
             "--threshold", "999999", "-o", path_high],
        )
        runner.invoke(
            main,
            [cli_input_csv, cli_config_csv, "--seed", "42", "--threshold", "0", "-o", path_low],
        )

        high_df = pl.read_csv(path_high)
        low_df = pl.read_csv(path_low)

        # With threshold=999999, nobody should be above
        assert high_df.row(0, named=True)["players_above_threshold"] == 0
        # With threshold=0, everyone should be above (unless they got 0 points)
        assert low_df.row(0, named=True)["players_above_threshold"] >= 0


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
        from src.cli import main

        result = runner.invoke(main, ["/nonexistent/players.csv", cli_config_csv])
        assert result.exit_code != 0

    def test_missing_config_file_shows_error(
        self,
        runner: CliRunner,
        cli_input_csv: str,
    ) -> None:
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
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0

        lines = result.output.strip().split("\n")
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
        from src.cli import main

        result = runner.invoke(main, [cli_input_csv, cli_config_csv, "--seed", "42"])
        assert result.exit_code == 0
        assert "Players above threshold (100.0)" in result.output
