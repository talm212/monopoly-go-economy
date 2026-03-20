"""Tests for normalize_churn_column — shared data normalization utility.

Verifies:
- Missing about_to_churn column gets default False
- String "true"/"false" (case-insensitive) converts to boolean
- Integer 0/1 column casts to boolean
- Already-boolean column is a no-op
- Empty DataFrame handling
"""

from __future__ import annotations

import polars as pl
import pytest

from src.infrastructure.readers.normalize import normalize_churn_column

# ---------------------------------------------------------------------------
# Missing column
# ---------------------------------------------------------------------------


class TestNormalizeMissingColumn:
    """When about_to_churn is absent, add it with default False."""

    def test_missing_column_adds_default_false(self) -> None:
        df = pl.DataFrame({"user_id": [1, 2, 3], "rolls_sink": [100, 200, 50]})
        result = normalize_churn_column(df)

        assert "about_to_churn" in result.columns
        assert result["about_to_churn"].dtype == pl.Boolean
        assert result["about_to_churn"].to_list() == [False, False, False]

    def test_missing_column_preserves_existing_columns(self) -> None:
        df = pl.DataFrame({"user_id": [1, 2], "rolls_sink": [100, 200]})
        result = normalize_churn_column(df)

        assert result["user_id"].to_list() == [1, 2]
        assert result["rolls_sink"].to_list() == [100, 200]


# ---------------------------------------------------------------------------
# String column conversion
# ---------------------------------------------------------------------------


class TestNormalizeStringColumn:
    """String "true"/"false" (case-insensitive) converts to boolean."""

    @pytest.mark.parametrize(
        ("input_vals", "expected"),
        [
            (["true", "false", "true"], [True, False, True]),
            (["True", "False", "True"], [True, False, True]),
            (["TRUE", "FALSE", "TRUE"], [True, False, True]),
            (["tRuE", "fAlSe"], [True, False]),
        ],
        ids=["lowercase", "titlecase", "uppercase", "mixedcase"],
    )
    def test_string_values_convert_to_boolean(
        self, input_vals: list[str], expected: list[bool]
    ) -> None:
        df = pl.DataFrame({"about_to_churn": input_vals})
        result = normalize_churn_column(df)

        assert result["about_to_churn"].dtype == pl.Boolean
        assert result["about_to_churn"].to_list() == expected

    def test_string_non_true_treated_as_false(self) -> None:
        df = pl.DataFrame({"about_to_churn": ["yes", "no", "1"]})
        result = normalize_churn_column(df)

        assert result["about_to_churn"].dtype == pl.Boolean
        # Only "true" (case-insensitive) maps to True; everything else is False
        assert result["about_to_churn"].to_list() == [False, False, False]


# ---------------------------------------------------------------------------
# Integer column conversion
# ---------------------------------------------------------------------------


class TestNormalizeIntegerColumn:
    """Integer 0/1 column casts to boolean."""

    def test_integer_zero_one_casts_to_boolean(self) -> None:
        df = pl.DataFrame({"about_to_churn": [0, 1, 0, 1]})
        result = normalize_churn_column(df)

        assert result["about_to_churn"].dtype == pl.Boolean
        assert result["about_to_churn"].to_list() == [False, True, False, True]

    def test_all_zeros_cast_to_false(self) -> None:
        df = pl.DataFrame({"about_to_churn": [0, 0, 0]})
        result = normalize_churn_column(df)

        assert result["about_to_churn"].to_list() == [False, False, False]


# ---------------------------------------------------------------------------
# Already-boolean column
# ---------------------------------------------------------------------------


class TestNormalizeBooleanColumn:
    """Already-boolean column is a no-op."""

    def test_boolean_column_unchanged(self) -> None:
        df = pl.DataFrame({"about_to_churn": [True, False, True]})
        result = normalize_churn_column(df)

        assert result["about_to_churn"].dtype == pl.Boolean
        assert result["about_to_churn"].to_list() == [True, False, True]


# ---------------------------------------------------------------------------
# Empty DataFrame
# ---------------------------------------------------------------------------


class TestNormalizeEmptyDataFrame:
    """Edge case: empty DataFrames."""

    def test_empty_df_without_column_adds_column(self) -> None:
        df = pl.DataFrame({"user_id": pl.Series([], dtype=pl.Int64)})
        result = normalize_churn_column(df)

        assert "about_to_churn" in result.columns
        assert len(result) == 0

    def test_empty_df_with_boolean_column_is_noop(self) -> None:
        df = pl.DataFrame(
            {
                "user_id": pl.Series([], dtype=pl.Int64),
                "about_to_churn": pl.Series([], dtype=pl.Boolean),
            }
        )
        result = normalize_churn_column(df)

        assert result["about_to_churn"].dtype == pl.Boolean
        assert len(result) == 0
