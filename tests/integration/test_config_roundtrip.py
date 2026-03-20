"""Integration tests for config format roundtrips.

Validates that config data survives all three representation conversions
without corruption:

1. CSV dict  (str keys, str values — as parsed from CSV file)
2. CoinFlipConfig  (domain model with typed tuples)
3. Display dict  (str keys, mixed values — as shown in the Streamlit editor)

These tests import the *actual* conversion helpers from app.py rather than
copying them, so they catch regressions when the real helpers change.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.application.config_conversion import (
    config_obj_to_display as _config_obj_to_display,
    display_dict_to_raw as _display_dict_to_raw,
    raw_dict_to_display as _raw_dict_to_display,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CSV_DICT_5_DEPTHS: dict[str, str] = {
    "p_success_1": "60%",
    "p_success_2": "50%",
    "p_success_3": "40%",
    "p_success_4": "30%",
    "p_success_5": "20%",
    "points_success_1": "1",
    "points_success_2": "2",
    "points_success_3": "4",
    "points_success_4": "8",
    "points_success_5": "16",
    "max_successes": "5",
}

EXPECTED_PROBABILITIES = (0.6, 0.5, 0.4, 0.3, 0.2)
EXPECTED_POINT_VALUES = (1.0, 2.0, 4.0, 8.0, 16.0)


@pytest.fixture()
def csv_dict() -> dict[str, str]:
    """CSV string dict with 5 flip depths."""
    return dict(CSV_DICT_5_DEPTHS)


@pytest.fixture()
def config_from_csv(csv_dict: dict[str, str]) -> CoinFlipConfig:
    """CoinFlipConfig built from the CSV dict fixture."""
    return CoinFlipConfig.from_csv_dict(csv_dict)


# ---------------------------------------------------------------------------
# 1. CSV -> CoinFlipConfig -> to_dict() -> from_dict() roundtrip
# ---------------------------------------------------------------------------


class TestCsvToConfigToDict:
    """CSV string dict -> CoinFlipConfig -> to_dict -> from_dict roundtrip."""

    def test_csv_parses_to_correct_config(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        assert config_from_csv.max_successes == 5
        assert config_from_csv.probabilities == EXPECTED_PROBABILITIES
        assert config_from_csv.point_values == EXPECTED_POINT_VALUES

    def test_to_dict_from_dict_roundtrip(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        serialized = config_from_csv.to_dict()
        restored = CoinFlipConfig.from_dict(serialized)
        assert restored == config_from_csv

    def test_to_dict_keys_are_complete(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        serialized = config_from_csv.to_dict()
        expected_keys = {
            "max_successes",
            "probabilities",
            "point_values",
            "churn_boost_multiplier",
            "reward_threshold",
        }
        assert set(serialized.keys()) == expected_keys

    def test_double_roundtrip(self, config_from_csv: CoinFlipConfig) -> None:
        """Serialize -> deserialize -> serialize -> deserialize stays stable."""
        first = CoinFlipConfig.from_dict(config_from_csv.to_dict())
        second = CoinFlipConfig.from_dict(first.to_dict())
        assert second == config_from_csv


# ---------------------------------------------------------------------------
# 2. CoinFlipConfig -> display dict -> raw dict -> CoinFlipConfig roundtrip
# ---------------------------------------------------------------------------


class TestConfigDisplayRawRoundtrip:
    """CoinFlipConfig -> display -> raw -> from_csv_dict roundtrip."""

    def test_config_to_display_to_raw_to_config(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config_from_csv.reward_threshold,
            churn_boost=config_from_csv.churn_boost_multiplier,
        )
        assert restored == config_from_csv

    def test_display_dict_has_all_keys(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        for i in range(1, 6):
            assert f"p_success_{i}" in display
            assert f"points_success_{i}" in display
        assert "max_successes" in display

    def test_raw_dict_values_are_strings(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        raw = _display_dict_to_raw(display)
        for value in raw.values():
            assert isinstance(value, str), f"Expected str, got {type(value)}: {value}"

    def test_raw_dict_to_display_to_raw_is_stable(
        self, csv_dict: dict[str, str]
    ) -> None:
        """raw -> display -> raw should produce identical strings."""
        display = _raw_dict_to_display(csv_dict)
        raw_again = _display_dict_to_raw(display)
        assert raw_again == csv_dict


# ---------------------------------------------------------------------------
# 3. Float precision edge case  (IEEE 754: 0.6 * 100 = 60.00000000000001)
# ---------------------------------------------------------------------------


class TestFloatPrecision:
    """Verify that IEEE 754 artifacts don't leak into display strings."""

    @pytest.mark.parametrize(
        ("probability", "expected_display"),
        [
            (0.6, "60%"),
            (0.5, "50%"),
            (0.1, "10%"),
            (0.33, "33%"),
            (0.99, "99%"),
            (1.0, "100%"),
        ],
    )
    def test_probability_displays_as_clean_percentage(
        self, probability: float, expected_display: str
    ) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(probability,),
            point_values=(1.0,),
        )
        display = _config_obj_to_display(config)
        assert display["p_success_1"] == expected_display, (
            f"p={probability} displayed as {display['p_success_1']!r}, "
            f"expected {expected_display!r}"
        )

    def test_0_6_never_shows_floating_point_noise(self) -> None:
        """Explicit guard against the 0.6 * 100 = 60.00000000000001 bug."""
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.6,),
            point_values=(1.0,),
        )
        display = _config_obj_to_display(config)
        assert "60.0" not in str(display["p_success_1"])
        assert display["p_success_1"] == "60%"

    def test_precision_survives_full_roundtrip(self) -> None:
        """0.6 -> '60%' -> 0.6 must not drift."""
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.6,),
            point_values=(1.0,),
        )
        display = _config_obj_to_display(config)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.probabilities[0] == 0.6


# ---------------------------------------------------------------------------
# 4. All 5 probability values survive roundtrip
# ---------------------------------------------------------------------------


class TestAllDepthsSurviveRoundtrip:
    """Verify every probability and point value at all 5 depths survives."""

    def test_all_probabilities_survive_csv_roundtrip(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config_from_csv.reward_threshold,
            churn_boost=config_from_csv.churn_boost_multiplier,
        )
        for i in range(5):
            assert restored.probabilities[i] == pytest.approx(
                config_from_csv.probabilities[i]
            ), f"Probability at depth {i + 1} drifted"

    def test_all_point_values_survive_csv_roundtrip(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config_from_csv.reward_threshold,
            churn_boost=config_from_csv.churn_boost_multiplier,
        )
        for i in range(5):
            assert restored.point_values[i] == pytest.approx(
                config_from_csv.point_values[i]
            ), f"Point value at depth {i + 1} drifted"

    def test_all_depths_survive_to_dict_from_dict(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        restored = CoinFlipConfig.from_dict(config_from_csv.to_dict())
        assert restored.probabilities == config_from_csv.probabilities
        assert restored.point_values == config_from_csv.point_values


# ---------------------------------------------------------------------------
# 5. Integer vs float values survive roundtrip
# ---------------------------------------------------------------------------


class TestIntegerFloatPreservation:
    """Point values that are whole numbers should remain usable as integers."""

    def test_whole_number_point_values_display_as_int(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        for i in range(1, 6):
            val = display[f"points_success_{i}"]
            assert isinstance(val, int), (
                f"points_success_{i} is {type(val).__name__}, expected int"
            )

    def test_fractional_point_value_stays_float(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.5, 2.5),
        )
        display = _config_obj_to_display(config)
        assert isinstance(display["points_success_1"], float)
        assert display["points_success_1"] == 1.5

    def test_int_point_values_survive_display_raw_roundtrip(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        raw = _display_dict_to_raw(display)
        # Raw dict should have "1", "2", etc. — not "1.0"
        assert raw["points_success_1"] == "1"
        assert raw["points_success_2"] == "2"
        assert raw["points_success_3"] == "4"
        assert raw["points_success_4"] == "8"
        assert raw["points_success_5"] == "16"

    def test_float_point_values_survive_full_roundtrip(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.5, 3.7),
        )
        display = _config_obj_to_display(config)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.point_values == pytest.approx(config.point_values)

    def test_max_successes_stays_integer_through_roundtrip(
        self, config_from_csv: CoinFlipConfig
    ) -> None:
        display = _config_obj_to_display(config_from_csv)
        assert isinstance(display["max_successes"], int)
        raw = _display_dict_to_raw(display)
        assert raw["max_successes"] == "5"
        display2 = _raw_dict_to_display(raw)
        assert isinstance(display2["max_successes"], int)
        assert display2["max_successes"] == 5
