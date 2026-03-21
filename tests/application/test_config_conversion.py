"""Unit tests for config format conversion helpers.

Tests all four functions from src/application/config_conversion.py:
- config_df_to_raw_dict
- raw_dict_to_display
- display_dict_to_raw
- config_obj_to_display

Covers valid inputs, empty DataFrames, edge values, precision behavior,
and identity roundtrips.
"""

from __future__ import annotations

from typing import Any

import polars as pl
import pytest

from src.application.config_conversion import (
    config_df_to_raw_dict,
    config_obj_to_display,
    display_dict_to_raw,
    raw_dict_to_display,
)
from src.domain.models.coin_flip import CoinFlipConfig

# ---------------------------------------------------------------------------
# config_df_to_raw_dict
# ---------------------------------------------------------------------------


class TestConfigDfToRawDict:
    """Tests for converting a config CSV DataFrame to a raw string dict."""

    def test_valid_dataframe(self) -> None:
        """Standard config CSV DataFrame converts to correct dict."""
        df = pl.DataFrame(
            {
                "Input": ["p_success_1", "points_success_1", "max_successes"],
                "Value": ["60%", "1", "5"],
            }
        )
        result = config_df_to_raw_dict(df)
        assert result == {
            "p_success_1": "60%",
            "points_success_1": "1",
            "max_successes": "5",
        }

    def test_empty_dataframe(self) -> None:
        """Empty DataFrame produces an empty dict."""
        df = pl.DataFrame({"Input": [], "Value": []}).cast({"Input": pl.Utf8, "Value": pl.Utf8})
        result = config_df_to_raw_dict(df)
        assert result == {}

    def test_values_are_strings(self) -> None:
        """All values in the result dict are strings."""
        df = pl.DataFrame(
            {
                "Input": ["max_successes"],
                "Value": [5],
            }
        )
        result = config_df_to_raw_dict(df)
        assert isinstance(result["max_successes"], str)
        assert result["max_successes"] == "5"


# ---------------------------------------------------------------------------
# raw_dict_to_display
# ---------------------------------------------------------------------------


class TestRawDictToDisplay:
    """Tests for converting raw CSV string dict to display-friendly types."""

    def test_percentage_values_kept_as_strings(self) -> None:
        """Values ending with '%' stay as percentage strings."""
        raw = {"p_success_1": "60%", "p_success_2": "33%"}
        display = raw_dict_to_display(raw)
        assert display["p_success_1"] == "60%"
        assert display["p_success_2"] == "33%"

    def test_integer_values_converted(self) -> None:
        """Whole number strings become ints."""
        raw = {"max_successes": "5", "points_success_1": "16"}
        display = raw_dict_to_display(raw)
        assert display["max_successes"] == 5
        assert isinstance(display["max_successes"], int)
        assert display["points_success_1"] == 16
        assert isinstance(display["points_success_1"], int)

    def test_float_values_converted(self) -> None:
        """Decimal number strings become floats."""
        raw = {"churn_boost": "1.3", "reward_threshold": "100.5"}
        display = raw_dict_to_display(raw)
        assert display["churn_boost"] == pytest.approx(1.3)
        assert isinstance(display["churn_boost"], float)

    def test_non_numeric_values_kept_as_strings(self) -> None:
        """Strings that are neither numbers nor percentages stay as-is."""
        raw = {"feature_name": "coin_flip"}
        display = raw_dict_to_display(raw)
        assert display["feature_name"] == "coin_flip"

    def test_edge_zero_value(self) -> None:
        """Zero is parsed as an integer."""
        raw = {"min_val": "0"}
        display = raw_dict_to_display(raw)
        assert display["min_val"] == 0
        assert isinstance(display["min_val"], int)


# ---------------------------------------------------------------------------
# display_dict_to_raw
# ---------------------------------------------------------------------------


class TestDisplayDictToRaw:
    """Tests for converting display dict back to raw string form."""

    def test_percentage_string_passthrough(self) -> None:
        """Percentage strings in display pass through unchanged."""
        display: dict[str, Any] = {"p_success_1": "33%"}
        raw = display_dict_to_raw(display)
        assert raw["p_success_1"] == "33%"

    def test_integer_to_string(self) -> None:
        """Integers convert to string representation."""
        display: dict[str, Any] = {"max_successes": 5}
        raw = display_dict_to_raw(display)
        assert raw["max_successes"] == "5"

    def test_whole_float_to_int_string(self) -> None:
        """Whole-number floats (e.g. 16.0) convert to int strings (e.g. '16')."""
        display: dict[str, Any] = {"points_success_1": 16.0}
        raw = display_dict_to_raw(display)
        assert raw["points_success_1"] == "16"

    def test_fractional_float_to_string(self) -> None:
        """Fractional floats convert to their float string representation."""
        display: dict[str, Any] = {"churn_boost": 1.3}
        raw = display_dict_to_raw(display)
        assert raw["churn_boost"] == "1.3"

    def test_reverse_conversion_percentage(self) -> None:
        """'33%' should round-trip through display_dict_to_raw."""
        display: dict[str, Any] = {"p_success_1": "33%"}
        raw = display_dict_to_raw(display)
        assert raw["p_success_1"] == "33%"


# ---------------------------------------------------------------------------
# config_obj_to_display
# ---------------------------------------------------------------------------


class TestConfigObjToDisplay:
    """Tests for converting CoinFlipConfig to display dict format."""

    def test_probabilities_formatted_as_percentage(self) -> None:
        """Probabilities should display as percentage strings (e.g. '60%')."""
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=(0.6, 0.5, 0.4),
            point_values=(1.0, 2.0, 4.0),
        )
        display = config_obj_to_display(config)
        assert display["p_success_1"] == "60%"
        assert display["p_success_2"] == "50%"
        assert display["p_success_3"] == "40%"

    def test_point_values_as_integers(self) -> None:
        """Whole-number point values display as int."""
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.0, 2.0),
        )
        display = config_obj_to_display(config)
        assert display["points_success_1"] == 1
        assert isinstance(display["points_success_1"], int)
        assert display["points_success_2"] == 2

    def test_max_successes_present(self) -> None:
        """Display dict includes max_successes."""
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=(0.6, 0.5, 0.5, 0.5, 0.5),
            point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
        )
        display = config_obj_to_display(config)
        assert display["max_successes"] == 5

    def test_reward_threshold_and_churn_boost(self) -> None:
        """Display dict includes reward_threshold and churn_boost_multiplier."""
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.5,),
            point_values=(1.0,),
            reward_threshold=200.0,
            churn_boost_multiplier=1.5,
        )
        display = config_obj_to_display(config)
        assert display["reward_threshold"] == 200.0
        assert display["churn_boost_multiplier"] == 1.5

    def test_precision_0_333_probability(self) -> None:
        """Document behavior: 0.333 -> round(33.3) = 33 -> '33%'."""
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.333,),
            point_values=(1.0,),
        )
        display = config_obj_to_display(config)
        # round(0.333 * 100) = round(33.3) = 33
        assert display["p_success_1"] == "33%"

    def test_precision_0_335_probability(self) -> None:
        """Document behavior: 0.335 -> round(33.5) = 34 -> '34%'."""
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.335,),
            point_values=(1.0,),
        )
        display = config_obj_to_display(config)
        # round(0.335 * 100) = round(33.5) = 34 (banker's rounding)
        assert display["p_success_1"] == "34%"


# ---------------------------------------------------------------------------
# Identity roundtrip: config -> display -> raw -> config
# ---------------------------------------------------------------------------


class TestIdentityRoundtrip:
    """config -> display -> raw -> CoinFlipConfig.from_csv_dict should be identity."""

    def test_standard_config_roundtrip(self) -> None:
        """Standard config survives config -> display -> raw -> config."""
        original = CoinFlipConfig(
            max_successes=5,
            probabilities=(0.6, 0.5, 0.4, 0.3, 0.2),
            point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
            churn_boost_multiplier=1.3,
            reward_threshold=100.0,
        )
        display = config_obj_to_display(original)
        raw = display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=original.reward_threshold,
            churn_boost=original.churn_boost_multiplier,
        )
        assert restored.max_successes == original.max_successes
        assert restored.probabilities == original.probabilities
        assert restored.point_values == original.point_values

    def test_single_depth_roundtrip(self) -> None:
        """Single-depth config roundtrips cleanly."""
        original = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.7,),
            point_values=(10.0,),
        )
        display = config_obj_to_display(original)
        raw = display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=original.reward_threshold,
            churn_boost=original.churn_boost_multiplier,
        )
        assert restored.probabilities == original.probabilities
        assert restored.point_values == original.point_values
