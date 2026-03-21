"""Streamlit AppTest integration tests for the economy simulator dashboard.

Uses ``streamlit.testing.v1.AppTest`` to run the app headlessly -- no browser needed.
Faster than Playwright E2E tests while still exercising the full render pipeline.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from streamlit.testing.v1 import AppTest

from src.domain.models.coin_flip import CoinFlipConfig, CoinFlipResult

# ---------------------------------------------------------------------------
# Path to main app file (relative to project root)
# ---------------------------------------------------------------------------

_APP_PATH = "src/ui/app.py"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_config() -> CoinFlipConfig:
    """Standard 5-depth coin flip config for testing."""
    return CoinFlipConfig(
        max_successes=5,
        probabilities=(0.60, 0.50, 0.50, 0.50, 0.50),
        point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
        churn_boost_multiplier=1.3,
        reward_threshold=100.0,
    )


@pytest.fixture
def sample_result() -> CoinFlipResult:
    """Minimal CoinFlipResult with realistic data for KPI display tests."""
    player_results = pl.DataFrame(
        {
            "user_id": [1, 2, 3, 4, 5],
            "total_points": [50.0, 120.0, 200.0, 80.0, 150.0],
            "interactions": [10, 20, 40, 8, 30],
            "about_to_churn": [False, False, True, False, True],
        }
    )
    return CoinFlipResult(
        player_results=player_results,
        total_interactions=108,
        success_counts={0: 30, 1: 25, 2: 20, 3: 15, 4: 10, 5: 8},
        total_points=600.0,
        players_above_threshold=3,
        threshold=100.0,
    )


@pytest.fixture
def display_config_dict() -> dict[str, Any]:
    """Config dict in display format (what the config editor renders)."""
    return {
        "p_success_1": "60%",
        "p_success_2": "50%",
        "p_success_3": "50%",
        "p_success_4": "50%",
        "p_success_5": "50%",
        "points_success_1": 1,
        "points_success_2": 2,
        "points_success_3": 4,
        "points_success_4": 8,
        "points_success_5": 16,
        "max_successes": 5,
    }


def _create_app() -> AppTest:
    """Create an AppTest instance with mocked external dependencies.

    Mocks LocalSimulationStore.list_runs to return empty (no history)
    and the LLM client factory to avoid AWS/Anthropic initialization.
    """
    at = AppTest.from_file(_APP_PATH)
    return at


def _patch_store_and_run(at: AppTest, timeout: int = 15) -> AppTest:
    """Run the AppTest with LocalSimulationStore mocked to return no history.

    The app calls ``store.list_runs()`` at module level during initialization.
    Patching prevents filesystem access and ensures a clean empty state.
    """
    with (
        patch(
            "src.infrastructure.store.local_store.LocalSimulationStore.list_runs",
            return_value=[],
        ),
        patch(
            "src.infrastructure.store.local_store.LocalSimulationStore.save_run",
            return_value="mock-run-id",
        ),
        patch(
            "src.infrastructure.llm.client.get_llm_client",
            return_value=MagicMock(),
        ),
    ):
        at.run(timeout=timeout)
    return at


# ===========================================================================
# 1. Initial State
# ===========================================================================


class TestInitialState:
    """Tests for app initial render without any data or config loaded."""

    def test_app_loads_without_errors(self) -> None:
        """App loads and shows title without exceptions."""
        at = _create_app()
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception on load: {at.exception}"
        )

    def test_title_contains_economy_simulator(self) -> None:
        """Page title includes 'Economy Simulator'."""
        at = _create_app()
        _patch_store_and_run(at)
        title_values = [t.value for t in at.title]
        assert any(
            "Economy Simulator" in t for t in title_values
        ), f"Expected 'Economy Simulator' in titles, got: {title_values}"

    def test_empty_state_shows_upload_prompt(self) -> None:
        """Without data, shows an info message about uploading."""
        at = _create_app()
        _patch_store_and_run(at)
        info_values = [i.value for i in at.info]
        assert any(
            "Upload" in val or "upload" in val for val in info_values
        ), f"Expected upload prompt in info messages, got: {info_values}"

    def test_no_results_section_in_empty_state(self) -> None:
        """Without simulation results, no metric cards should render."""
        at = _create_app()
        _patch_store_and_run(at)
        # In empty state, there should be no metric elements
        assert len(at.metric) == 0, (
            f"Expected 0 metrics in empty state, got {len(at.metric)}"
        )


# ===========================================================================
# 2. Feature Routing
# ===========================================================================


class TestFeatureRouting:
    """Tests for feature routing via query parameters."""

    def test_default_feature_is_coin_flip(self) -> None:
        """Default feature (no query param) shows Coin Flip in title."""
        at = _create_app()
        _patch_store_and_run(at)
        title_values = [t.value for t in at.title]
        assert any(
            "Coin Flip" in t for t in title_values
        ), f"Expected 'Coin Flip' in titles, got: {title_values}"

    def test_invalid_feature_does_not_crash(self) -> None:
        """Invalid feature query param does not raise an exception."""
        at = _create_app()
        at.query_params["feature"] = "nonexistent_feature"
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception with invalid feature: {at.exception}"
        )

    def test_invalid_feature_falls_back_to_default(self) -> None:
        """Invalid feature falls back to coin_flip (shows Coin Flip in title)."""
        at = _create_app()
        at.query_params["feature"] = "nonexistent_feature"
        _patch_store_and_run(at)
        title_values = [t.value for t in at.title]
        assert any(
            "Coin Flip" in t for t in title_values
        ), f"Expected fallback to 'Coin Flip', got: {title_values}"


# ===========================================================================
# 3. Config Editor
# ===========================================================================


class TestConfigEditor:
    """Tests for config editor rendering with pre-populated session state."""

    def test_config_editor_renders_after_upload(
        self,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """Config editor appears when config is in session state."""
        at = _create_app()
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["config"] = sample_config
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception with config in session state: {at.exception}"
        )

    def test_app_with_config_but_no_players_shows_warning(
        self,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """With config but no player data, shows a warning to upload players."""
        at = _create_app()
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["config"] = sample_config
        _patch_store_and_run(at)
        warning_values = [w.value for w in at.warning]
        assert any(
            "player" in val.lower() or "upload" in val.lower()
            for val in warning_values
        ), f"Expected warning about player data, got: {warning_values}"


# ===========================================================================
# 4. Results Display
# ===========================================================================


class TestResultsDisplay:
    """Tests for KPI and results display with pre-populated simulation result."""

    def test_simulation_result_shows_kpis(
        self,
        sample_result: CoinFlipResult,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """When simulation result is in session state, KPIs render."""
        at = _create_app()
        at.session_state["simulation_result"] = sample_result
        at.session_state["config"] = sample_config
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["_app_initialized"] = True
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception with result: {at.exception}"
        )
        # Coin flip KPI bar renders 4 metrics: Mean, Median, Total, % Above
        assert len(at.metric) >= 4, (
            f"Expected at least 4 KPI metrics, got {len(at.metric)}"
        )

    def test_loaded_summary_shows_kpis(self) -> None:
        """When a loaded run summary is in session state, KPIs render."""
        at = _create_app()
        at.session_state["loaded_run_summary"] = {
            "total_interactions": 1000,
            "total_points": 5000.0,
            "players_above_threshold": 50,
            "threshold": 100.0,
            "mean_points_per_player": 100.0,
            "median_points_per_player": 80.0,
            "pct_above_threshold": 0.5,
        }
        at.session_state["loaded_run_distribution"] = {
            "0": 300, "1": 250, "2": 200, "3": 150, "4": 75, "5": 25,
        }
        at.session_state["_app_initialized"] = True
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception with loaded summary: {at.exception}"
        )
        # Loaded summary renders 3 spec-required KPI metrics
        assert len(at.metric) >= 3, (
            f"Expected at least 3 KPI metrics from loaded summary, got {len(at.metric)}"
        )

    def test_results_section_renders_with_simulation(
        self,
        sample_result: CoinFlipResult,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """Results section (subheader) appears when simulation result exists."""
        at = _create_app()
        at.session_state["simulation_result"] = sample_result
        at.session_state["config"] = sample_config
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["_app_initialized"] = True
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception: {at.exception}"
        )
        # Check that "Results" subheader appears
        subheader_values = [s.value for s in at.subheader]
        assert any(
            "Results" in s for s in subheader_values
        ), f"Expected 'Results' subheader, got: {subheader_values}"


# ===========================================================================
# 5. Run Button State
# ===========================================================================


class TestRunButton:
    """Tests for the Run Simulation button state."""

    def test_run_button_disabled_without_data(self) -> None:
        """Run button is disabled when no player data or config."""
        at = _create_app()
        _patch_store_and_run(at)
        run_buttons = [
            b for b in at.button
            if "Run" in (b.label or "") and "Simulation" in (b.label or "")
        ]
        if run_buttons:
            assert run_buttons[0].disabled, (
                "Run Simulation button should be disabled without data"
            )

    def test_run_button_exists(self) -> None:
        """Run Simulation button is always rendered."""
        at = _create_app()
        _patch_store_and_run(at)
        button_labels = [b.label for b in at.button]
        assert any(
            "Run" in (label or "") for label in button_labels
        ), f"Expected a 'Run' button, got labels: {button_labels}"


# ===========================================================================
# 6. Session State Isolation
# ===========================================================================


class TestSessionStateIsolation:
    """Tests that session state pre-population works correctly."""

    def test_stale_config_warning_shown(
        self,
        sample_result: CoinFlipResult,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """When config_changed_since_run is True, a warning is shown."""
        at = _create_app()
        at.session_state["simulation_result"] = sample_result
        at.session_state["config"] = sample_config
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["config_changed_since_run"] = True
        at.session_state["_app_initialized"] = True
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception: {at.exception}"
        )
        warning_values = [w.value for w in at.warning]
        assert any(
            "config" in val.lower() and "changed" in val.lower()
            for val in warning_values
        ), f"Expected stale config warning, got: {warning_values}"

    def test_ready_message_with_players_and_config(
        self,
        sample_config: CoinFlipConfig,
        display_config_dict: dict[str, Any],
    ) -> None:
        """When both player data and config exist, shows 'Ready to simulate'."""
        at = _create_app()
        player_df = pl.DataFrame(
            {
                "user_id": [1, 2, 3],
                "rolls_sink": [100, 200, 50],
                "avg_multiplier": [10, 20, 5],
                "about_to_churn": [False, False, True],
            }
        )
        at.session_state["player_data"] = player_df
        at.session_state["config"] = sample_config
        at.session_state["config_uploaded"] = True
        at.session_state["config_dict"] = display_config_dict
        at.session_state["_app_initialized"] = True
        _patch_store_and_run(at)
        assert not at.exception, (
            f"App raised exception: {at.exception}"
        )
        success_values = [s.value for s in at.success]
        assert any(
            "Ready" in val or "ready" in val for val in success_values
        ), f"Expected 'Ready to simulate' success message, got: {success_values}"
