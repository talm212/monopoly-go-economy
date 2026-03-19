"""AI-powered config optimizer for game economy simulations.

Uses an LLM in a feedback loop with a simulator to iteratively tune
configuration parameters toward a specified optimization target.
Feature-agnostic -- works with any simulation callable that returns
a summary dictionary.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import polars as pl

from src.domain.models.optimization import (
    OptimizationDirection,
    OptimizationStep,
    OptimizationTarget,
)
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.llm.utils import strip_markdown_fences

logger = logging.getLogger(__name__)

OPTIMIZER_SYSTEM_PROMPT = """You are an optimizer for Monopoly Go game economy parameters.
Given current config, simulation results, and a target, suggest modified config parameters.

Rules:
- Return ONLY valid JSON with the modified config parameters
- Only modify probabilities (0.0-1.0) and point_values (positive numbers)
- Do NOT modify max_successes
- Make incremental changes (don't change everything at once)
- Consider the relationship: higher probabilities = more points distributed"""


class ConfigOptimizer:
    """Iteratively optimizes simulation config using LLM suggestions.

    Orchestrates a loop: simulate -> evaluate -> ask LLM -> apply guardrails -> repeat.
    Tracks the best config found across all iterations and returns it along with
    the full optimization history.
    """

    def __init__(self, llm_client: LLMClient, max_iterations: int = 10) -> None:
        self._llm = llm_client
        self._max_iterations = max_iterations

    async def optimize(
        self,
        simulate_fn: Callable[[dict[str, Any], pl.DataFrame], dict[str, Any]],
        current_config: dict[str, Any],
        target: OptimizationTarget,
        players: pl.DataFrame,
    ) -> tuple[dict[str, Any], list[OptimizationStep]]:
        """Run the optimization loop until convergence or max iterations.

        Args:
            simulate_fn: Callable taking (config_dict, players_df) and returning
                a summary dict with metric values.
            current_config: Starting configuration dictionary.
            target: The optimization target specifying metric, value, and direction.
            players: Player DataFrame to pass to the simulation callable.

        Returns:
            Tuple of (best_config_dict, list_of_optimization_steps).
        """
        original_max_successes = current_config.get("max_successes")
        best_config = dict(current_config)
        best_distance = float("inf")
        steps: list[OptimizationStep] = []

        for i in range(self._max_iterations):
            result_summary = simulate_fn(current_config, players)
            current_value = float(result_summary.get(target.metric, 0.0))
            distance = abs(current_value - target.target_value)

            steps.append(
                OptimizationStep(
                    iteration=i + 1,
                    config=dict(current_config),
                    result_metric=current_value,
                    distance_to_target=distance,
                )
            )

            if distance < best_distance:
                best_distance = distance
                best_config = dict(current_config)

            if self._is_converged(current_value, target):
                logger.info("Converged at iteration %d", i + 1)
                break

            try:
                suggestion = await self._get_suggestion(
                    current_config, result_summary, target, current_value
                )
                current_config = self._apply_guardrails(
                    suggestion, original_max_successes, current_config
                )
            except Exception:
                logger.exception("LLM suggestion failed at iteration %d", i + 1)
                break

        return best_config, steps

    def _is_converged(self, current_value: float, target: OptimizationTarget) -> bool:
        """Check whether the current value satisfies the target within tolerance."""
        if target.direction == OptimizationDirection.TARGET:
            if target.target_value == 0.0:
                return abs(current_value) <= target.tolerance
            return (
                abs(current_value - target.target_value) / abs(target.target_value)
                <= target.tolerance
            )

        if target.direction == OptimizationDirection.MAXIMIZE:
            return current_value >= target.target_value

        # MINIMIZE
        return current_value <= target.target_value

    def _apply_guardrails(
        self,
        config: dict[str, Any],
        original_max_successes: Any,
        current_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Sanitize an LLM-suggested config to enforce invariants.

        - Required keys must exist; falls back to current_config if missing.
        - Probabilities are clamped to [0.0, 1.0].
        - Point values are clamped to >= 0.0.
        - max_successes is restored to its original value.
        """
        # Ensure required keys exist
        for key in ("probabilities", "point_values", "max_successes"):
            if key not in config:
                logger.warning("LLM suggestion missing key: %s", key)
                if current_config is not None:
                    return current_config  # fall back to current
                break

        result = dict(config)

        if original_max_successes is not None:
            result["max_successes"] = original_max_successes

        if "probabilities" in result:
            result["probabilities"] = [
                max(0.0, min(float(p), 1.0)) for p in result["probabilities"]
            ]

        if "point_values" in result:
            result["point_values"] = [max(0.0, float(v)) for v in result["point_values"]]

        return result

    async def _get_suggestion(
        self,
        config: dict[str, Any],
        result_summary: dict[str, Any],
        target: OptimizationTarget,
        current_value: float,
    ) -> dict[str, Any]:
        """Ask the LLM for a new config suggestion and parse the JSON response."""
        prompt = self._build_prompt(config, result_summary, target, current_value)
        response = await self._llm.complete(prompt, system=OPTIMIZER_SYSTEM_PROMPT)
        cleaned = strip_markdown_fences(response)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("LLM returned invalid JSON: %s", exc)
            raise

        if not isinstance(parsed, dict):
            msg = f"LLM response is not a JSON object: {type(parsed).__name__}"
            logger.error(msg)
            raise ValueError(msg)

        return parsed

    def _build_prompt(
        self,
        config: dict[str, Any],
        result_summary: dict[str, Any],
        target: OptimizationTarget,
        current_value: float,
    ) -> str:
        """Build the user prompt with current state and target."""
        return (
            f"Current config:\n{json.dumps(config, indent=2)}\n\n"
            f"Simulation results:\n{json.dumps(result_summary, indent=2)}\n\n"
            f"Target: {target.metric} = {target.target_value} "
            f"(direction: {target.direction.value})\n"
            f"Current value: {current_value}\n"
            f"Distance to target: {abs(current_value - target.target_value)}\n\n"
            "Suggest a modified config as JSON to move closer to the target."
        )
