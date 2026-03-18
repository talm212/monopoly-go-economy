"""Tests for LocalDataReader — CSV ingestion using Polars.

Covers:
- read_players() with valid CSV returns correct Polars DataFrame schema
- read_players() with missing required columns returns validation errors
- read_players() with the actual coin-flip-assignment/input_table.csv
- read_config() with valid config CSV returns dict with parsed values
- read_config() with the actual coin-flip-assignment/config_table.csv
- validate_players() required columns check and null handling
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
import pytest

from src.infrastructure.readers.local_reader import LocalDataReader

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ASSIGNMENT_DIR = Path(__file__).resolve().parents[2] / "coin-flip-assignment"


@pytest.fixture
def reader() -> LocalDataReader:
    return LocalDataReader()


@pytest.fixture
def valid_player_csv(tmp_path: Path) -> str:
    """Write a valid player CSV and return the path."""
    path = tmp_path / "players.csv"
    df = pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "rolls_sink": [100, 200, 50],
            "avg_multiplier": [10, 20, 5],
            "about_to_churn": [False, False, True],
        }
    )
    df.write_csv(str(path))
    return str(path)


@pytest.fixture
def missing_columns_csv(tmp_path: Path) -> str:
    """CSV missing the required 'rolls_sink' column."""
    path = tmp_path / "bad_players.csv"
    df = pl.DataFrame(
        {
            "user_id": [1, 2],
            "avg_multiplier": [10, 20],
        }
    )
    df.write_csv(str(path))
    return str(path)


@pytest.fixture
def no_churn_column_csv(tmp_path: Path) -> str:
    """CSV without optional about_to_churn column."""
    path = tmp_path / "no_churn.csv"
    df = pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "rolls_sink": [100, 200, 50],
            "avg_multiplier": [10, 20, 5],
        }
    )
    df.write_csv(str(path))
    return str(path)


@pytest.fixture
def null_values_csv(tmp_path: Path) -> str:
    """CSV with null values in required columns."""
    path = tmp_path / "nulls.csv"
    path.write_text(
        "user_id,rolls_sink,avg_multiplier,about_to_churn\n"
        "1,100,10,false\n"
        ",200,20,false\n"
        "3,,5,true\n"
    )
    return str(path)


@pytest.fixture
def valid_config_csv(tmp_path: Path) -> str:
    """Write a valid config CSV (Input/Value format) and return the path."""
    path = tmp_path / "config.csv"
    df = pl.DataFrame(
        {
            "Input": [
                "p_success_1",
                "p_success_2",
                "max_successes",
                "points_success_1",
                "points_success_2",
            ],
            "Value": ["60%", "50%", "5", "1", "2"],
        }
    )
    df.write_csv(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# read_players — valid CSV
# ---------------------------------------------------------------------------


class TestReadPlayers:
    """Tests for LocalDataReader.read_players()."""

    def test_returns_polars_dataframe(
        self, reader: LocalDataReader, valid_player_csv: str
    ) -> None:
        result = reader.read_players(valid_player_csv)
        assert isinstance(result, pl.DataFrame)

    def test_correct_schema_columns(
        self, reader: LocalDataReader, valid_player_csv: str
    ) -> None:
        result = reader.read_players(valid_player_csv)
        assert "user_id" in result.columns
        assert "rolls_sink" in result.columns
        assert "avg_multiplier" in result.columns
        assert "about_to_churn" in result.columns

    def test_correct_row_count(
        self, reader: LocalDataReader, valid_player_csv: str
    ) -> None:
        result = reader.read_players(valid_player_csv)
        assert len(result) == 3

    def test_about_to_churn_is_boolean(
        self, reader: LocalDataReader, valid_player_csv: str
    ) -> None:
        result = reader.read_players(valid_player_csv)
        assert result["about_to_churn"].dtype == pl.Boolean

    def test_defaults_about_to_churn_when_missing(
        self, reader: LocalDataReader, no_churn_column_csv: str
    ) -> None:
        result = reader.read_players(no_churn_column_csv)
        assert "about_to_churn" in result.columns
        assert result["about_to_churn"].dtype == pl.Boolean
        assert result["about_to_churn"].to_list() == [False, False, False]

    @pytest.mark.integration
    def test_read_actual_input_table(self, reader: LocalDataReader) -> None:
        """Read the real assignment CSV and verify basic properties."""
        path = str(ASSIGNMENT_DIR / "input_table.csv")
        result = reader.read_players(path)
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 10000
        assert "user_id" in result.columns
        assert "rolls_sink" in result.columns
        assert "avg_multiplier" in result.columns
        assert "about_to_churn" in result.columns
        assert result["about_to_churn"].dtype == pl.Boolean
        # Spot-check: there should be some churners
        churn_count = result["about_to_churn"].sum()
        assert churn_count > 0


# ---------------------------------------------------------------------------
# validate_players
# ---------------------------------------------------------------------------


class TestValidatePlayers:
    """Tests for LocalDataReader.validate_players()."""

    def test_valid_df_returns_no_errors(
        self, reader: LocalDataReader, sample_players_df: pl.DataFrame
    ) -> None:
        errors = reader.validate_players(sample_players_df)
        assert errors == []

    def test_missing_required_column_returns_error(
        self, reader: LocalDataReader
    ) -> None:
        df = pl.DataFrame({"user_id": [1], "avg_multiplier": [10]})
        errors = reader.validate_players(df)
        assert len(errors) > 0
        assert any("rolls_sink" in e for e in errors)

    def test_missing_multiple_columns_returns_multiple_errors(
        self, reader: LocalDataReader
    ) -> None:
        df = pl.DataFrame({"some_col": [1]})
        errors = reader.validate_players(df)
        assert any("user_id" in e for e in errors)
        assert any("rolls_sink" in e for e in errors)
        assert any("avg_multiplier" in e for e in errors)

    def test_null_values_in_user_id_returns_error(
        self, reader: LocalDataReader
    ) -> None:
        df = pl.DataFrame(
            {
                "user_id": [1, None, 3],
                "rolls_sink": [100, 200, 50],
                "avg_multiplier": [10, 20, 5],
                "about_to_churn": [False, False, True],
            }
        )
        errors = reader.validate_players(df)
        assert len(errors) > 0
        assert any("null" in e.lower() for e in errors)

    def test_null_values_in_rolls_sink_returns_error(
        self, reader: LocalDataReader
    ) -> None:
        df = pl.DataFrame(
            {
                "user_id": [1, 2, 3],
                "rolls_sink": [100, None, 50],
                "avg_multiplier": [10, 20, 5],
                "about_to_churn": [False, False, True],
            }
        )
        errors = reader.validate_players(df)
        assert len(errors) > 0
        assert any("null" in e.lower() for e in errors)

    def test_read_players_with_missing_columns_raises(
        self, reader: LocalDataReader, missing_columns_csv: str
    ) -> None:
        """read_players should raise ValueError for missing required columns."""
        with pytest.raises(ValueError, match="rolls_sink"):
            reader.read_players(missing_columns_csv)

    def test_read_players_with_nulls_raises(
        self, reader: LocalDataReader, null_values_csv: str
    ) -> None:
        """read_players should raise ValueError when required columns have nulls."""
        with pytest.raises(ValueError, match="(?i)null"):
            reader.read_players(null_values_csv)


# ---------------------------------------------------------------------------
# read_config
# ---------------------------------------------------------------------------


class TestReadConfig:
    """Tests for LocalDataReader.read_config()."""

    def test_returns_dict(
        self, reader: LocalDataReader, valid_config_csv: str
    ) -> None:
        result = reader.read_config(valid_config_csv)
        assert isinstance(result, dict)

    def test_parses_percentage_to_float(
        self, reader: LocalDataReader, valid_config_csv: str
    ) -> None:
        result = reader.read_config(valid_config_csv)
        assert result["p_success_1"] == pytest.approx(0.60)
        assert result["p_success_2"] == pytest.approx(0.50)

    def test_parses_integer_string(
        self, reader: LocalDataReader, valid_config_csv: str
    ) -> None:
        result = reader.read_config(valid_config_csv)
        assert result["max_successes"] == 5
        assert isinstance(result["max_successes"], int)

    def test_parses_point_values_as_numeric(
        self, reader: LocalDataReader, valid_config_csv: str
    ) -> None:
        result = reader.read_config(valid_config_csv)
        assert result["points_success_1"] == 1
        assert result["points_success_2"] == 2

    def test_all_keys_present(
        self, reader: LocalDataReader, valid_config_csv: str
    ) -> None:
        result = reader.read_config(valid_config_csv)
        assert "p_success_1" in result
        assert "p_success_2" in result
        assert "max_successes" in result
        assert "points_success_1" in result
        assert "points_success_2" in result

    @pytest.mark.integration
    def test_read_actual_config_table(self, reader: LocalDataReader) -> None:
        """Read the real assignment config CSV."""
        path = str(ASSIGNMENT_DIR / "config_table.csv")
        result = reader.read_config(path)
        assert isinstance(result, dict)
        # Known values from the assignment
        assert result["p_success_1"] == pytest.approx(0.60)
        assert result["p_success_2"] == pytest.approx(0.50)
        assert result["max_successes"] == 5
        assert result["points_success_1"] == 1
        assert result["points_success_5"] == 16

    def test_float_value_parsed(self, reader: LocalDataReader, tmp_path: Path) -> None:
        """Config with a float value like '2.5' should be parsed as float."""
        path = tmp_path / "float_config.csv"
        path.write_text("Input,Value\nsome_rate,2.5\n")
        result = reader.read_config(str(path))
        assert result["some_rate"] == pytest.approx(2.5)
        assert isinstance(result["some_rate"], float)
