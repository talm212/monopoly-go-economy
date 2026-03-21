"""Parameter sweep use case: run simulations across a range of config values.

Iterates over a list of parameter values, overrides the base config for each,
runs the simulation, and collects KPI metrics into a unified SweepResult.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any

import polars as pl

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.protocols import Simulator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known parameter keys for validation
# ---------------------------------------------------------------------------

# Flat (scalar) parameters that can be swept directly
_FLAT_PARAMS = {"reward_threshold", "churn_boost_multiplier"}

# List parameters that use dotted index notation (e.g. "probabilities.0")
_LIST_PARAMS = {"probabilities", "point_values"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SweepPoint:
    """Result from one sweep configuration.

    Attributes:
        param_value: The parameter value used for this simulation.
        config: The full config dict used for this simulation.
        kpi_metrics: KPI metrics from the simulation result.
    """

    param_value: float
    config: dict[str, Any]
    kpi_metrics: dict[str, float]


@dataclass
class SweepResult:
    """Full parameter sweep results.

    Attributes:
        param_name: The parameter that was swept.
        sweep_points: List of results, one per swept value.
    """

    param_name: str
    sweep_points: list[SweepPoint]

    def to_dataframe(self) -> pl.DataFrame:
        """Convert sweep results to a Polars DataFrame for charting.

        Returns:
            DataFrame with columns: param_value + all KPI metric keys.
        """
        if not self.sweep_points:
            return pl.DataFrame()

        rows: list[dict[str, float]] = []
        for sp in self.sweep_points:
            row: dict[str, float] = {"param_value": sp.param_value}
            row.update(sp.kpi_metrics)
            rows.append(row)

        return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Parameter override helpers
# ---------------------------------------------------------------------------


def _parse_param_name(param_name: str) -> tuple[str, int | None]:
    """Parse a parameter name into (base_key, optional_index).

    Args:
        param_name: Either a flat name like "reward_threshold" or
            an indexed name like "probabilities.0".

    Returns:
        Tuple of (base_key, index) where index is None for flat params.

    Raises:
        ValueError: If the parameter name is not recognized.
    """
    if "." in param_name:
        parts = param_name.split(".", 1)
        base_key = parts[0]
        if base_key not in _LIST_PARAMS:
            raise ValueError(
                f"Unknown parameter '{param_name}'. "
                f"List parameters: {sorted(_LIST_PARAMS)}"
            )
        try:
            index = int(parts[1])
        except ValueError:
            raise ValueError(
                f"Invalid index in '{param_name}': '{parts[1]}' is not an integer"
            ) from None
        return base_key, index

    if param_name in _FLAT_PARAMS:
        return param_name, None

    raise ValueError(
        f"Unknown parameter '{param_name}'. "
        f"Flat parameters: {sorted(_FLAT_PARAMS)}. "
        f"List parameters (use dotted index): {sorted(_LIST_PARAMS)}"
    )


def _apply_override(
    config_dict: dict[str, Any],
    base_key: str,
    index: int | None,
    value: float,
) -> dict[str, Any]:
    """Apply a parameter override to a config dict (returns a new copy).

    Args:
        config_dict: Base configuration dictionary.
        base_key: The top-level key to override.
        index: If not None, override config_dict[base_key][index].
        value: The new value to set.

    Returns:
        A new config dict with the override applied.

    Raises:
        ValueError: If the index is out of range.
    """
    modified = copy.deepcopy(config_dict)

    if index is not None:
        lst = modified[base_key]
        if not isinstance(lst, list):
            raise ValueError(
                f"Expected '{base_key}' to be a list, got {type(lst).__name__}"
            )
        if index < 0 or index >= len(lst):
            raise ValueError(
                f"Index {index} out of range for '{base_key}' "
                f"(length {len(lst)})"
            )
        lst[index] = value
    else:
        modified[base_key] = value

    return modified


# ---------------------------------------------------------------------------
# Main use case
# ---------------------------------------------------------------------------


class ParameterSweep:
    """Runs a simulation for each value in a parameter range.

    Args:
        simulator: A simulator instance with a .simulate() method
            (e.g. CoinFlipSimulator).
    """

    def __init__(self, simulator: Simulator) -> None:
        self._simulator = simulator

    def run(
        self,
        players: pl.DataFrame,
        base_config: dict[str, Any],
        param_name: str,
        values: list[float],
        seed: int | None = None,
    ) -> SweepResult:
        """Run simulation for each parameter value.

        For each value:
        1. Copy base_config
        2. Override param_name with the value
        3. Build CoinFlipConfig from the modified dict
        4. Run simulation
        5. Collect KPI metrics

        Args:
            players: Polars DataFrame with player data.
            base_config: Base configuration dict (serialized CoinFlipConfig).
            param_name: Parameter to sweep. Flat params use plain names
                (e.g. "reward_threshold"). List params use dotted index
                notation (e.g. "probabilities.0" for the first probability).
            values: List of values to sweep over.
            seed: Optional RNG seed. Each sweep point uses seed + i for
                reproducibility while varying the parameter, not the randomness.

        Returns:
            SweepResult containing all sweep points.

        Raises:
            ValueError: If param_name is invalid or index is out of range.
        """
        base_key, index = _parse_param_name(param_name)

        # Validate index against actual config before starting sweep
        if index is not None:
            lst = base_config.get(base_key)
            if not isinstance(lst, list):
                raise ValueError(
                    f"Expected '{base_key}' to be a list in base_config"
                )
            if index < 0 or index >= len(lst):
                raise ValueError(
                    f"Index {index} out of range for '{base_key}' "
                    f"(length {len(lst)})"
                )

        sweep_points: list[SweepPoint] = []

        for i, value in enumerate(values):
            # 1-2. Copy and override
            modified_dict = _apply_override(base_config, base_key, index, value)

            # 3. Build config
            config = CoinFlipConfig.from_dict(modified_dict)

            # 4. Run simulation — use seed + i so each point is deterministic
            # but independent from the others
            point_seed = (seed + i) if seed is not None else None
            result = self._simulator.simulate(players, config, seed=point_seed)

            # 5. Collect KPIs
            kpi_metrics = result.get_kpi_metrics()

            sweep_points.append(
                SweepPoint(
                    param_value=value,
                    config=modified_dict,
                    kpi_metrics=kpi_metrics,
                )
            )

            logger.info(
                "Sweep point %d/%d: %s=%.4f -> mean_points=%.2f",
                i + 1,
                len(values),
                param_name,
                value,
                kpi_metrics.get("mean_points_per_player", 0.0),
            )

        return SweepResult(param_name=param_name, sweep_points=sweep_points)
