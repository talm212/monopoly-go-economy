"""Tests for LocalDataWriter — CSV output using Polars.

Covers:
- write_results() creates a CSV file at the given path
- Written CSV is readable by Polars and has expected columns
- Uses tmp_path fixture for file output
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src.infrastructure.writers.local_writer import LocalDataWriter


@pytest.fixture
def writer() -> LocalDataWriter:
    return LocalDataWriter()


@pytest.fixture
def sample_results_df() -> pl.DataFrame:
    """Small results DataFrame for testing writes."""
    return pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "total_points": [10.0, 25.5, 0.0],
            "num_flips": [3, 5, 0],
            "won": [True, True, False],
        }
    )


class TestWriteResults:
    """Tests for LocalDataWriter.write_results()."""

    def test_creates_csv_file(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        writer.write_results(sample_results_df, dest)
        assert Path(dest).exists()

    def test_written_csv_is_readable_by_polars(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        writer.write_results(sample_results_df, dest)
        loaded = pl.read_csv(dest)
        assert isinstance(loaded, pl.DataFrame)

    def test_written_csv_has_expected_columns(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        writer.write_results(sample_results_df, dest)
        loaded = pl.read_csv(dest)
        assert set(loaded.columns) == {"user_id", "total_points", "num_flips", "won"}

    def test_written_csv_has_correct_row_count(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        writer.write_results(sample_results_df, dest)
        loaded = pl.read_csv(dest)
        assert len(loaded) == 3

    def test_written_csv_preserves_data(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        writer.write_results(sample_results_df, dest)
        loaded = pl.read_csv(dest)
        assert loaded["user_id"].to_list() == [1, 2, 3]
        assert loaded["total_points"].to_list() == pytest.approx([10.0, 25.5, 0.0])

    def test_creates_parent_directories(
        self,
        writer: LocalDataWriter,
        sample_results_df: pl.DataFrame,
        tmp_path: Path,
    ) -> None:
        """write_results should create parent directories if they don't exist."""
        dest = str(tmp_path / "nested" / "dir" / "output.csv")
        writer.write_results(sample_results_df, dest)
        assert Path(dest).exists()

    def test_overwrites_existing_file(
        self,
        writer: LocalDataWriter,
        tmp_path: Path,
    ) -> None:
        dest = str(tmp_path / "output.csv")
        first_df = pl.DataFrame({"a": [1]})
        second_df = pl.DataFrame({"b": [2, 3]})
        writer.write_results(first_df, dest)
        writer.write_results(second_df, dest)
        loaded = pl.read_csv(dest)
        assert loaded.columns == ["b"]
        assert len(loaded) == 2
