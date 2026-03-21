"""Tests for the ConfigOptimizer engine.

Validates that ConfigOptimizer correctly orchestrates the simulation-LLM
feedback loop, applies guardrails to LLM suggestions, tracks the best
config across iterations, and handles edge cases gracefully.
All tests use mocked LLM client and simulate_fn -- no real API calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest

from src.application.optimize_config import OPTIMIZER_SYSTEM_PROMPT, ConfigOptimizer
from src.domain.models.optimization import (
    OptimizationDirection,
    OptimizationStep,
    OptimizationTarget,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> AsyncMock:
    """AsyncMock that satisfies the LLMClient protocol."""
    return AsyncMock()


@pytest.fixture
def mock_simulate_fn() -> MagicMock:
    """Mock simulation callable: (config_dict, players_df) -> summary_dict."""
    return MagicMock()


@pytest.fixture
def optimizer(mock_llm: AsyncMock) -> ConfigOptimizer:
    """ConfigOptimizer wired with a mocked LLM client, max 5 iterations."""
    return ConfigOptimizer(llm_client=mock_llm, max_iterations=5)


@pytest.fixture
def small_players_df() -> pl.DataFrame:
    """Tiny player DataFrame for optimizer tests."""
    return pl.DataFrame(
        {
            "user_id": [1, 2, 3],
            "rolls_sink": [100, 200, 50],
            "avg_multiplier": [10, 20, 5],
            "about_to_churn": [False, False, True],
        }
    )


@pytest.fixture
def base_config() -> dict[str, Any]:
    """Starting config for optimization."""
    return {
        "max_successes": 5,
        "probabilities": [0.60, 0.50, 0.50, 0.50, 0.50],
        "point_values": [1.0, 2.0, 4.0, 8.0, 16.0],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture
def target_500() -> OptimizationTarget:
    """Optimization target: get players_above_threshold to 500."""
    return OptimizationTarget(
        metric="players_above_threshold",
        target_value=500.0,
        direction=OptimizationDirection.TARGET,
        tolerance=0.05,
    )


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOptimizationTarget:
    """OptimizationTarget creation and defaults."""

    def test_create_target(self) -> None:
        """Can create an OptimizationTarget with all fields."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=100_000.0,
            direction=OptimizationDirection.MAXIMIZE,
            tolerance=0.10,
        )
        assert target.metric == "total_points"
        assert target.target_value == 100_000.0
        assert target.direction == OptimizationDirection.MAXIMIZE
        assert target.tolerance == 0.10

    def test_tolerance_default(self) -> None:
        """Default tolerance is 0.05 (5%)."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=100_000.0,
            direction=OptimizationDirection.TARGET,
        )
        assert target.tolerance == 0.05

    def test_target_is_frozen(self) -> None:
        """OptimizationTarget is immutable."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=100_000.0,
            direction=OptimizationDirection.TARGET,
        )
        with pytest.raises(AttributeError):
            target.metric = "changed"  # type: ignore[misc]

    def test_direction_enum_values(self) -> None:
        """All three direction enum values exist."""
        assert OptimizationDirection.MAXIMIZE.value == "maximize"
        assert OptimizationDirection.MINIMIZE.value == "minimize"
        assert OptimizationDirection.TARGET.value == "target"


@pytest.mark.unit
class TestOptimizationStep:
    """OptimizationStep creation and mutability."""

    def test_create_step(self) -> None:
        """Can create an OptimizationStep."""
        step = OptimizationStep(
            iteration=1,
            config={"max_successes": 5},
            result_metric=350.0,
            distance_to_target=150.0,
        )
        assert step.iteration == 1
        assert step.result_metric == 350.0
        assert step.distance_to_target == 150.0

    def test_step_is_frozen(self) -> None:
        """OptimizationStep is a frozen (immutable) dataclass."""
        step = OptimizationStep(
            iteration=1,
            config={},
            result_metric=0.0,
            distance_to_target=100.0,
        )
        with pytest.raises(AttributeError):
            step.result_metric = 42.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConfigOptimizer: happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfigOptimizer:
    """ConfigOptimizer orchestrates the simulate-evaluate-suggest loop."""

    @pytest.mark.asyncio
    async def test_optimize_returns_best_config(
        self,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        small_players_df: pl.DataFrame,
    ) -> None:
        """Optimizer returns the config that got closest to the target."""
        # Use tight (1%) tolerance so 450 doesn't converge (450 vs 500 = 10%)
        target = OptimizationTarget(
            metric="players_above_threshold",
            target_value=500.0,
            direction=OptimizationDirection.TARGET,
            tolerance=0.01,
        )
        optimizer = ConfigOptimizer(llm_client=mock_llm, max_iterations=3)

        # Iteration 1: far from target (300)
        # Iteration 2: closest (480, distance=20) — best
        # Iteration 3: worse again (450, distance=50)
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 480.0},
            {"players_above_threshold": 450.0},
        ]

        improved_config = dict(base_config)
        improved_config["probabilities"] = [0.70, 0.60, 0.55, 0.50, 0.50]
        worse_config = dict(base_config)
        worse_config["probabilities"] = [0.65, 0.55, 0.50, 0.50, 0.50]

        mock_llm.complete.side_effect = [
            json.dumps(improved_config),
            json.dumps(worse_config),
        ]

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        # Best was iteration 2 (distance=20), not iteration 3 (distance=50)
        assert best_config["probabilities"] == [0.70, 0.60, 0.55, 0.50, 0.50]
        assert len(steps) == 3

    @pytest.mark.asyncio
    async def test_stops_on_convergence(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        small_players_df: pl.DataFrame,
    ) -> None:
        """Optimizer stops iterating when result is within tolerance of target."""
        target = OptimizationTarget(
            metric="players_above_threshold",
            target_value=500.0,
            direction=OptimizationDirection.TARGET,
            tolerance=0.05,
        )

        # First result is within 5% of 500 (490 -> distance=10, 10/500=2%)
        mock_simulate_fn.return_value = {"players_above_threshold": 490.0}

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        # Should stop after 1 iteration — no LLM call needed
        assert len(steps) == 1
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_stops_at_max_iterations(
        self,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Optimizer stops after max_iterations even if not converged."""
        optimizer = ConfigOptimizer(llm_client=mock_llm, max_iterations=3)

        # Never converges — always far from target
        mock_simulate_fn.return_value = {"players_above_threshold": 100.0}
        mock_llm.complete.return_value = json.dumps(base_config)

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        assert len(steps) == 3

    @pytest.mark.asyncio
    async def test_returns_optimization_steps(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Each iteration produces an OptimizationStep with correct fields."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 400.0},
        ]
        mock_llm.complete.side_effect = [
            json.dumps(base_config),
        ]

        # Second iteration converges close enough? No, 400 vs 500 = 20% off.
        # But only 2 simulate calls means LLM is called once then it runs again.
        # Let's allow convergence on 2nd: set tolerance high
        target = OptimizationTarget(
            metric="players_above_threshold",
            target_value=500.0,
            direction=OptimizationDirection.TARGET,
            tolerance=0.25,  # 25% tolerance — 400 is within 20%
        )

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        assert len(steps) == 2
        assert steps[0].iteration == 1
        assert steps[0].result_metric == 300.0
        assert steps[0].distance_to_target == 200.0
        assert steps[1].iteration == 2
        assert steps[1].result_metric == 400.0
        assert steps[1].distance_to_target == 100.0

    @pytest.mark.asyncio
    async def test_handles_invalid_llm_suggestion(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Invalid JSON from LLM causes optimizer to break and return best so far."""
        mock_simulate_fn.return_value = {"players_above_threshold": 300.0}
        mock_llm.complete.return_value = "This is not valid JSON {{"

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        # Should have 1 step, then break on invalid LLM response
        assert len(steps) == 1
        assert best_config == base_config

    @pytest.mark.asyncio
    async def test_caps_probabilities_at_one(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Guardrails cap probability values at 1.0."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 490.0},  # converges
        ]

        bad_config = dict(base_config)
        bad_config["probabilities"] = [1.5, 0.60, 1.2, 0.50, 0.50]
        mock_llm.complete.return_value = json.dumps(bad_config)

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        # The second iteration used the guardrailed config
        # Check the config passed to simulate_fn on the 2nd call
        second_call_config = mock_simulate_fn.call_args_list[1][0][0]
        for p in second_call_config["probabilities"]:
            assert p <= 1.0

    @pytest.mark.asyncio
    async def test_ensures_positive_point_values(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Guardrails ensure point values are non-negative."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 490.0},  # converges
        ]

        bad_config = dict(base_config)
        bad_config["point_values"] = [-5.0, 2.0, -1.0, 8.0, 16.0]
        mock_llm.complete.return_value = json.dumps(bad_config)

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        second_call_config = mock_simulate_fn.call_args_list[1][0][0]
        for pv in second_call_config["point_values"]:
            assert pv >= 0.0

    @pytest.mark.asyncio
    async def test_preserves_max_successes(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Guardrails prevent LLM from modifying max_successes."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 490.0},  # converges
        ]

        bad_config = dict(base_config)
        bad_config["max_successes"] = 10  # LLM tries to change it
        mock_llm.complete.return_value = json.dumps(bad_config)

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        second_call_config = mock_simulate_fn.call_args_list[1][0][0]
        assert second_call_config["max_successes"] == 5

    @pytest.mark.asyncio
    async def test_llm_exception_breaks_loop(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """LLM client raising an exception causes the loop to break gracefully."""
        mock_simulate_fn.return_value = {"players_above_threshold": 300.0}
        mock_llm.complete.side_effect = RuntimeError("API timeout")

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        assert len(steps) == 1
        assert best_config == base_config

    @pytest.mark.asyncio
    async def test_caps_probabilities_at_zero(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """Guardrails cap negative probabilities at 0.0."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 490.0},
        ]

        bad_config = dict(base_config)
        bad_config["probabilities"] = [-0.1, 0.50, 0.50, 0.50, 0.50]
        mock_llm.complete.return_value = json.dumps(bad_config)

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        second_call_config = mock_simulate_fn.call_args_list[1][0][0]
        for p in second_call_config["probabilities"]:
            assert 0.0 <= p <= 1.0

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(
        self,
        optimizer: ConfigOptimizer,
        mock_llm: AsyncMock,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        target_500: OptimizationTarget,
        small_players_df: pl.DataFrame,
    ) -> None:
        """LLM wrapping JSON in markdown fences is still parsed."""
        mock_simulate_fn.side_effect = [
            {"players_above_threshold": 300.0},
            {"players_above_threshold": 490.0},
        ]

        config_json = json.dumps(base_config)
        mock_llm.complete.return_value = f"```json\n{config_json}\n```"

        best_config, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target_500,
            players=small_players_df,
        )

        # Should have parsed successfully and run 2 iterations
        assert len(steps) == 2


# ---------------------------------------------------------------------------
# Convergence logic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConvergenceLogic:
    """Tests for the _is_converged helper in different directions."""

    @pytest.mark.asyncio
    async def test_target_direction_converged_within_tolerance(
        self,
        optimizer: ConfigOptimizer,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        small_players_df: pl.DataFrame,
    ) -> None:
        """TARGET direction converges when within tolerance of target_value."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=1000.0,
            direction=OptimizationDirection.TARGET,
            tolerance=0.05,
        )
        # 970 is within 3% of 1000 — should converge
        mock_simulate_fn.return_value = {"total_points": 970.0}

        _, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_maximize_direction_converged(
        self,
        optimizer: ConfigOptimizer,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        small_players_df: pl.DataFrame,
    ) -> None:
        """MAXIMIZE direction converges when value >= target_value."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=1000.0,
            direction=OptimizationDirection.MAXIMIZE,
            tolerance=0.05,
        )
        mock_simulate_fn.return_value = {"total_points": 1050.0}

        _, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_minimize_direction_converged(
        self,
        optimizer: ConfigOptimizer,
        mock_simulate_fn: MagicMock,
        base_config: dict[str, Any],
        small_players_df: pl.DataFrame,
    ) -> None:
        """MINIMIZE direction converges when value <= target_value."""
        target = OptimizationTarget(
            metric="total_points",
            target_value=1000.0,
            direction=OptimizationDirection.MINIMIZE,
            tolerance=0.05,
        )
        mock_simulate_fn.return_value = {"total_points": 950.0}

        _, steps = await optimizer.optimize(
            simulate_fn=mock_simulate_fn,
            current_config=dict(base_config),
            target=target,
            players=small_players_df,
        )

        assert len(steps) == 1


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOptimizerSystemPrompt:
    """System prompt guides the LLM correctly."""

    def test_system_prompt_mentions_json(self) -> None:
        """System prompt tells LLM to return JSON."""
        assert "JSON" in OPTIMIZER_SYSTEM_PROMPT

    def test_system_prompt_mentions_probabilities(self) -> None:
        """System prompt mentions probability constraints."""
        assert "probabilities" in OPTIMIZER_SYSTEM_PROMPT

    def test_system_prompt_prohibits_max_successes_change(self) -> None:
        """System prompt tells LLM not to modify max_successes."""
        assert "max_successes" in OPTIMIZER_SYSTEM_PROMPT
