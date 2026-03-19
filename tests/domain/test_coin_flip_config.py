"""Tests for CoinFlipConfig domain model.

Verifies:
- validate() passes for valid config, rejects mismatched lengths, invalid probabilities
- to_dict() / from_dict() roundtrip serialization
- from_csv_dict() parses config_table.csv percentage-string format
- get_boosted_probabilities() applies churn boost capped at 1.0
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.protocols import SimulatorConfig


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------


class TestCoinFlipConfigValidation:
    """Validate that CoinFlipConfig enforces business rules."""

    def test_valid_config_passes_validation(self, sample_config_dict: dict[str, Any]) -> None:
        config = CoinFlipConfig.from_dict(sample_config_dict)
        config.validate()  # should not raise

    def test_mismatched_probabilities_length_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=(0.6, 0.5, 0.5),  # only 3 instead of 5
            point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
        )
        with pytest.raises(ValueError, match="probabilities"):
            config.validate()

    def test_mismatched_point_values_length_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=(0.6, 0.5, 0.5, 0.5, 0.5),
            point_values=(1.0, 2.0),  # only 2 instead of 5
        )
        with pytest.raises(ValueError, match="point_values"):
            config.validate()

    def test_probability_below_zero_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(-0.1, 0.5),
            point_values=(1.0, 2.0),
        )
        with pytest.raises(ValueError, match="probability"):
            config.validate()

    def test_probability_above_one_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 1.1),
            point_values=(1.0, 2.0),
        )
        with pytest.raises(ValueError, match="probability"):
            config.validate()

    def test_max_successes_zero_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=0,
            probabilities=(),
            point_values=(),
        )
        with pytest.raises(ValueError, match="max_successes"):
            config.validate()

    def test_negative_point_value_raises(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.0, -2.0),
        )
        with pytest.raises(ValueError, match="point_values"):
            config.validate()

    def test_boundary_probability_zero_is_valid(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.0,),
            point_values=(1.0,),
        )
        config.validate()  # 0.0 is within [0, 1]

    def test_boundary_probability_one_is_valid(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(1.0,),
            point_values=(1.0,),
        )
        config.validate()  # 1.0 is within [0, 1]


# ---------------------------------------------------------------------------
# Serialization roundtrip
# ---------------------------------------------------------------------------


class TestCoinFlipConfigSerialization:
    """Verify to_dict / from_dict roundtrip fidelity."""

    def test_to_dict_contains_all_fields(self, sample_config_dict: dict[str, Any]) -> None:
        config = CoinFlipConfig.from_dict(sample_config_dict)
        result = config.to_dict()
        assert set(result.keys()) == {
            "max_successes",
            "probabilities",
            "point_values",
            "churn_boost_multiplier",
            "reward_threshold",
        }

    def test_roundtrip_preserves_values(self, sample_config_dict: dict[str, Any]) -> None:
        original = CoinFlipConfig.from_dict(sample_config_dict)
        restored = CoinFlipConfig.from_dict(original.to_dict())
        assert restored.max_successes == original.max_successes
        assert restored.probabilities == original.probabilities
        assert restored.point_values == original.point_values
        assert restored.churn_boost_multiplier == original.churn_boost_multiplier
        assert restored.reward_threshold == original.reward_threshold

    def test_from_dict_with_defaults(self) -> None:
        data: dict[str, Any] = {
            "max_successes": 3,
            "probabilities": [0.5, 0.5, 0.5],
            "point_values": [1.0, 2.0, 4.0],
        }
        config = CoinFlipConfig.from_dict(data)
        assert config.churn_boost_multiplier == 1.3
        assert config.reward_threshold == 100.0


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


class TestCoinFlipConfigFromCsv:
    """Verify parsing from config_table.csv key-value format."""

    def test_from_csv_dict_parses_percentages(self) -> None:
        csv_data: dict[str, str] = {
            "p_success_1": "60%",
            "p_success_2": "50%",
            "p_success_3": "50%",
            "p_success_4": "50%",
            "p_success_5": "50%",
            "max_successes": "5",
            "points_success_1": "1",
            "points_success_2": "2",
            "points_success_3": "4",
            "points_success_4": "8",
            "points_success_5": "16",
        }
        config = CoinFlipConfig.from_csv_dict(csv_data)
        assert config.max_successes == 5
        assert config.probabilities == (0.60, 0.50, 0.50, 0.50, 0.50)
        assert config.point_values == (1.0, 2.0, 4.0, 8.0, 16.0)

    def test_from_csv_dict_respects_threshold_arg(self) -> None:
        csv_data: dict[str, str] = {
            "p_success_1": "60%",
            "max_successes": "1",
            "points_success_1": "5",
        }
        config = CoinFlipConfig.from_csv_dict(csv_data, threshold=200.0)
        assert config.reward_threshold == 200.0

    def test_from_csv_dict_respects_churn_boost_arg(self) -> None:
        csv_data: dict[str, str] = {
            "p_success_1": "60%",
            "max_successes": "1",
            "points_success_1": "5",
        }
        config = CoinFlipConfig.from_csv_dict(csv_data, churn_boost=1.5)
        assert config.churn_boost_multiplier == 1.5

    def test_from_csv_dict_handles_decimal_probabilities(self) -> None:
        """CSV values can also be plain decimals, not just percentages."""
        csv_data: dict[str, str] = {
            "p_success_1": "0.6",
            "max_successes": "1",
            "points_success_1": "5",
        }
        config = CoinFlipConfig.from_csv_dict(csv_data)
        assert config.probabilities == (0.6,)


# ---------------------------------------------------------------------------
# Churn boost
# ---------------------------------------------------------------------------


class TestCoinFlipConfigChurnBoost:
    """Verify churn probability boosting with cap at 1.0."""

    def test_boosted_probabilities_applies_multiplier(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.0, 2.0),
            churn_boost_multiplier=1.3,
        )
        boosted = config.get_boosted_probabilities()
        assert boosted == [0.65, 0.65]

    def test_boosted_probabilities_capped_at_one(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.8, 0.9),
            point_values=(1.0, 2.0),
            churn_boost_multiplier=1.3,
        )
        boosted = config.get_boosted_probabilities()
        # 0.8 * 1.3 = 1.04 → capped at 1.0
        # 0.9 * 1.3 = 1.17 → capped at 1.0
        assert boosted == [1.0, 1.0]

    def test_boosted_probabilities_mixed_capping(self) -> None:
        config = CoinFlipConfig(
            max_successes=3,
            probabilities=(0.5, 0.8, 0.6),
            point_values=(1.0, 2.0, 4.0),
            churn_boost_multiplier=1.3,
        )
        boosted = config.get_boosted_probabilities()
        assert boosted[0] == pytest.approx(0.65)
        assert boosted[1] == 1.0  # 0.8 * 1.3 = 1.04 → capped
        assert boosted[2] == pytest.approx(0.78)

    def test_boosted_probabilities_with_no_boost(self) -> None:
        config = CoinFlipConfig(
            max_successes=2,
            probabilities=(0.5, 0.5),
            point_values=(1.0, 2.0),
            churn_boost_multiplier=1.0,
        )
        boosted = config.get_boosted_probabilities()
        assert boosted == [0.5, 0.5]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestCoinFlipConfigProtocol:
    """Verify CoinFlipConfig satisfies SimulatorConfig protocol."""

    def test_is_instance_of_simulator_config(self) -> None:
        config = CoinFlipConfig(
            max_successes=1,
            probabilities=(0.5,),
            point_values=(1.0,),
        )
        assert isinstance(config, SimulatorConfig)
