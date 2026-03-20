"""TDD tests for config format roundtrips.

These test the exact data flow that happens when:
1. A run is loaded from history (stored format → display format)
2. The config editor renders and saves (display format → raw format)
3. CoinFlipConfig is built from the editor output (raw format → CoinFlipConfig)

Each step must preserve the config values without error.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.domain.models.coin_flip import CoinFlipConfig


# ---------------------------------------------------------------------------
# Helpers (copied from app.py to test in isolation)
# ---------------------------------------------------------------------------


def _config_obj_to_display(config: CoinFlipConfig) -> dict[str, Any]:
    """Convert a CoinFlipConfig to the display dict format the editor expects."""
    display: dict[str, Any] = {}
    for i, p in enumerate(config.probabilities, 1):
        display[f"p_success_{i}"] = f"{p:.0%}" if p * 100 == int(p * 100) else str(p)
    for i, v in enumerate(config.point_values, 1):
        display[f"points_success_{i}"] = int(v) if v == int(v) else v
    display["max_successes"] = config.max_successes
    return display


def _display_dict_to_raw(display: dict[str, Any]) -> dict[str, str]:
    """Convert the editor's display dict back to raw string form."""
    raw: dict[str, str] = {}
    for key, value in display.items():
        if isinstance(value, str):
            raw[key] = value
        elif isinstance(value, float) and not isinstance(value, bool):
            if value == int(value):
                raw[key] = str(int(value))
            else:
                raw[key] = str(value)
        else:
            raw[key] = str(value)
    return raw


def _raw_dict_to_display(raw: dict[str, str]) -> dict[str, Any]:
    """Convert raw CSV string dict to display-friendly types for the editor."""
    display: dict[str, Any] = {}
    for key, value in raw.items():
        if value.endswith("%"):
            display[key] = value
        else:
            try:
                display[key] = int(value)
            except ValueError:
                try:
                    display[key] = float(value)
                except ValueError:
                    display[key] = value
    return display


# ---------------------------------------------------------------------------
# The stored config format (what LocalSimulationStore saves)
# ---------------------------------------------------------------------------

STORED_CONFIG: dict[str, Any] = {
    "max_successes": 5,
    "probabilities": [0.6, 0.5, 0.5, 0.5, 0.5],
    "point_values": [1.0, 2.0, 4.0, 8.0, 16.0],
    "churn_boost_multiplier": 1.3,
    "reward_threshold": 100.0,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadFromHistory:
    """Test the flow: stored config → from_dict → CoinFlipConfig."""

    def test_from_dict_succeeds(self) -> None:
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        assert config.max_successes == 5
        assert config.probabilities == (0.6, 0.5, 0.5, 0.5, 0.5)

    def test_from_dict_to_display_succeeds(self) -> None:
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)
        assert "p_success_1" in display
        assert "points_success_1" in display
        assert "max_successes" in display

    def test_display_has_correct_values(self) -> None:
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)
        assert display["p_success_1"] == "60%"
        assert display["p_success_2"] == "50%"
        assert display["points_success_1"] == 1
        assert display["points_success_5"] == 16
        assert display["max_successes"] == 5


class TestDisplayToRawRoundtrip:
    """Test: display dict → raw dict → from_csv_dict → CoinFlipConfig."""

    def test_display_to_raw_succeeds(self) -> None:
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)
        raw = _display_dict_to_raw(display)
        assert raw["p_success_1"] == "60%"
        assert raw["max_successes"] == "5"

    def test_raw_to_from_csv_dict_succeeds(self) -> None:
        """THIS IS THE CRITICAL TEST — this is where the bug was."""
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.probabilities == config.probabilities
        assert restored.point_values == config.point_values
        assert restored.max_successes == config.max_successes

    def test_full_roundtrip_preserves_all_values(self) -> None:
        """stored → from_dict → display → raw → from_csv_dict → compare."""
        original = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(original)
        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=original.reward_threshold,
            churn_boost=original.churn_boost_multiplier,
        )
        assert restored == original


class TestEditorSimulation:
    """Simulate what the Streamlit config editor does to the display dict.

    The editor may change types (e.g., percentage slider returns float,
    number_input returns int/float). Test that the roundtrip survives.
    """

    def test_editor_changes_percentage_to_different_value(self) -> None:
        """User changes p_success_1 from 60% to 70% via slider."""
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)

        # Simulate editor changing a percentage
        display["p_success_1"] = "70%"

        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.probabilities[0] == pytest.approx(0.7)

    def test_editor_changes_point_value(self) -> None:
        """User changes points_success_1 from 1 to 5."""
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)

        # Simulate editor changing a point value (number_input returns int)
        display["points_success_1"] = 5

        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.point_values[0] == 5.0

    def test_editor_returns_float_for_point_value(self) -> None:
        """number_input might return 2.0 instead of 2 for an integer value."""
        config = CoinFlipConfig.from_dict(STORED_CONFIG)
        display = _config_obj_to_display(config)

        # Simulate number_input returning float
        display["points_success_1"] = 2.0

        raw = _display_dict_to_raw(display)
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )
        assert restored.point_values[0] == 2.0


class TestLoadFromHistoryStore:
    """Integration test with actual LocalSimulationStore."""

    def test_load_from_store_roundtrip(self) -> None:
        """If history has runs, load the first one and verify roundtrip."""
        from src.infrastructure.store.local_store import LocalSimulationStore

        store = LocalSimulationStore()
        runs = store.list_runs(limit=1)
        if not runs:
            pytest.skip("No runs in history store")

        run = runs[0]
        config_data = run.get("config", {})
        assert config_data, "Run has no config data"

        # Step 1: from_dict
        config = CoinFlipConfig.from_dict(config_data)

        # Step 2: to display
        display = _config_obj_to_display(config)

        # Step 3: to raw
        raw = _display_dict_to_raw(display)

        # Step 4: from_csv_dict
        restored = CoinFlipConfig.from_csv_dict(
            raw,
            threshold=config.reward_threshold,
            churn_boost=config.churn_boost_multiplier,
        )

        assert restored.probabilities == config.probabilities
        assert restored.point_values == config.point_values
        assert restored.max_successes == config.max_successes

    def test_load_from_store_has_summary_and_distribution(self) -> None:
        """Verify stored runs have result_summary and distribution for display."""
        from src.infrastructure.store.local_store import LocalSimulationStore

        store = LocalSimulationStore()
        runs = store.list_runs(limit=1)
        if not runs:
            pytest.skip("No runs in history store")

        run = runs[0]

        # Result summary must have these keys
        summary = run.get("result_summary", {})
        assert "total_interactions" in summary, "Missing total_interactions"
        assert "total_points" in summary, "Missing total_points"
        assert "players_above_threshold" in summary, "Missing players_above_threshold"

        # Distribution must exist and be non-empty
        dist = run.get("distribution", {})
        assert dist, "Distribution is empty"
        assert all(isinstance(v, (int, float)) for v in dist.values()), "Distribution values must be numeric"

    def test_loaded_distribution_can_render(self) -> None:
        """Verify loaded distribution can be converted to the format render_distribution_chart expects."""
        from src.infrastructure.store.local_store import LocalSimulationStore

        store = LocalSimulationStore()
        runs = store.list_runs(limit=1)
        if not runs:
            pytest.skip("No runs in history store")

        dist = runs[0].get("distribution", {})
        # Convert to string keys (what render_distribution_chart expects)
        display_dist = {str(k): int(v) for k, v in dist.items()}
        assert all(isinstance(k, str) for k in display_dist)
        assert all(isinstance(v, int) for v in display_dist.values())
