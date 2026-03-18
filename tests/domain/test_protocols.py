"""Tests for simulator protocols and registry.

Verifies that:
- SimulatorConfig protocol is @runtime_checkable and enforces validate(), to_dict(), from_dict()
- SimulationResult protocol is @runtime_checkable and enforces to_summary_dict(), to_dataframe(),
  get_distribution(), get_kpi_metrics()
- Simulator protocol is @runtime_checkable and enforces simulate(), validate_input()
- SimulatorRegistry can register, retrieve by name, and list all registered simulators
- SimulatorRegistry raises KeyError for unknown simulator names
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl
import pytest

from src.domain.protocols import (
    SimulationResult,
    Simulator,
    SimulatorConfig,
)
from src.domain.simulators.registry import SimulatorRegistry


# ---------------------------------------------------------------------------
# Stub implementations for protocol conformance testing
# ---------------------------------------------------------------------------


@dataclass
class StubConfig:
    """Minimal concrete implementation of SimulatorConfig."""

    max_successes: int = 5
    probabilities: list[float] = field(default_factory=lambda: [0.5, 0.5])

    def validate(self) -> None:
        if self.max_successes <= 0:
            raise ValueError("max_successes must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_successes": self.max_successes,
            "probabilities": self.probabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StubConfig:
        return cls(
            max_successes=data["max_successes"],
            probabilities=data["probabilities"],
        )


@dataclass
class StubResult:
    """Minimal concrete implementation of SimulationResult."""

    total_points: float = 100.0

    def to_summary_dict(self) -> dict[str, Any]:
        return {"total_points": self.total_points}

    def to_dataframe(self) -> pl.DataFrame:
        return pl.DataFrame({"points": [self.total_points]})

    def get_distribution(self) -> dict[str, int]:
        return {"0-100": 50, "100-200": 30, "200+": 20}

    def get_kpi_metrics(self) -> dict[str, float]:
        return {"mean_points": self.total_points, "median_points": 90.0}


class StubSimulator:
    """Minimal concrete implementation of Simulator."""

    def simulate(
        self,
        players: pl.DataFrame,
        config: SimulatorConfig,
        seed: int | None = None,
    ) -> SimulationResult:
        return StubResult(total_points=float(len(players)))

    def validate_input(self, players: pl.DataFrame) -> list[str]:
        errors: list[str] = []
        if "user_id" not in players.columns:
            errors.append("Missing required column: user_id")
        return errors


# ---------------------------------------------------------------------------
# Non-conforming classes (missing methods) for negative protocol checks
# ---------------------------------------------------------------------------


class NotAConfig:
    """Deliberately missing protocol methods."""

    pass


class NotAResult:
    """Deliberately missing protocol methods."""

    pass


class NotASimulator:
    """Deliberately missing protocol methods."""

    pass


# ---------------------------------------------------------------------------
# Protocol conformance tests — SimulatorConfig
# ---------------------------------------------------------------------------


class TestSimulatorConfigProtocol:
    """Verify SimulatorConfig protocol is @runtime_checkable and contract works."""

    def test_stub_config_is_instance_of_protocol(self) -> None:
        config = StubConfig()
        assert isinstance(config, SimulatorConfig)

    def test_non_conforming_class_is_not_instance(self) -> None:
        obj = NotAConfig()
        assert not isinstance(obj, SimulatorConfig)

    def test_validate_raises_on_invalid(self) -> None:
        config = StubConfig(max_successes=-1)
        with pytest.raises(ValueError, match="max_successes must be positive"):
            config.validate()

    def test_validate_passes_on_valid(self) -> None:
        config = StubConfig(max_successes=5)
        config.validate()  # should not raise

    def test_to_dict_returns_expected_keys(self) -> None:
        config = StubConfig(max_successes=3, probabilities=[0.6, 0.4])
        result = config.to_dict()
        assert result == {"max_successes": 3, "probabilities": [0.6, 0.4]}

    def test_from_dict_roundtrip(self) -> None:
        original = StubConfig(max_successes=7, probabilities=[0.1, 0.2, 0.3])
        data = original.to_dict()
        restored = StubConfig.from_dict(data)
        assert restored.max_successes == original.max_successes
        assert restored.probabilities == original.probabilities


# ---------------------------------------------------------------------------
# Protocol conformance tests — SimulationResult
# ---------------------------------------------------------------------------


class TestSimulationResultProtocol:
    """Verify SimulationResult protocol is @runtime_checkable and contract works."""

    def test_stub_result_is_instance_of_protocol(self) -> None:
        result = StubResult()
        assert isinstance(result, SimulationResult)

    def test_non_conforming_class_is_not_instance(self) -> None:
        obj = NotAResult()
        assert not isinstance(obj, SimulationResult)

    def test_to_summary_dict_returns_dict(self) -> None:
        result = StubResult(total_points=42.0)
        summary = result.to_summary_dict()
        assert isinstance(summary, dict)
        assert summary["total_points"] == 42.0

    def test_to_dataframe_returns_polars_dataframe(self) -> None:
        result = StubResult(total_points=99.0)
        df = result.to_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert df["points"][0] == 99.0

    def test_get_distribution_returns_str_int_dict(self) -> None:
        result = StubResult()
        dist = result.get_distribution()
        assert isinstance(dist, dict)
        assert all(isinstance(k, str) for k in dist)
        assert all(isinstance(v, int) for v in dist.values())

    def test_get_kpi_metrics_returns_str_float_dict(self) -> None:
        result = StubResult()
        kpis = result.get_kpi_metrics()
        assert isinstance(kpis, dict)
        assert "mean_points" in kpis
        assert all(isinstance(v, float) for v in kpis.values())


# ---------------------------------------------------------------------------
# Protocol conformance tests — Simulator
# ---------------------------------------------------------------------------


class TestSimulatorProtocol:
    """Verify Simulator protocol is @runtime_checkable and contract works."""

    def test_stub_simulator_is_instance_of_protocol(self) -> None:
        sim = StubSimulator()
        assert isinstance(sim, Simulator)

    def test_non_conforming_class_is_not_instance(self) -> None:
        obj = NotASimulator()
        assert not isinstance(obj, Simulator)

    def test_simulate_returns_simulation_result(self) -> None:
        sim = StubSimulator()
        players = pl.DataFrame({"user_id": [1, 2, 3]})
        config = StubConfig()
        result = sim.simulate(players, config, seed=42)
        assert isinstance(result, SimulationResult)

    def test_simulate_uses_player_count(self) -> None:
        sim = StubSimulator()
        players = pl.DataFrame({"user_id": [1, 2, 3, 4, 5]})
        config = StubConfig()
        result = sim.simulate(players, config)
        summary = result.to_summary_dict()
        assert summary["total_points"] == 5.0

    def test_validate_input_returns_empty_list_for_valid(self) -> None:
        sim = StubSimulator()
        players = pl.DataFrame({"user_id": [1, 2]})
        errors = sim.validate_input(players)
        assert errors == []

    def test_validate_input_returns_errors_for_invalid(self) -> None:
        sim = StubSimulator()
        players = pl.DataFrame({"not_user_id": [1, 2]})
        errors = sim.validate_input(players)
        assert len(errors) == 1
        assert "user_id" in errors[0]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestSimulatorRegistry:
    """Verify SimulatorRegistry can register, get, and list simulators."""

    def test_register_and_get(self) -> None:
        registry = SimulatorRegistry()
        sim = StubSimulator()
        registry.register("coin_flip", sim)
        assert registry.get("coin_flip") is sim

    def test_get_raises_key_error_for_unknown(self) -> None:
        registry = SimulatorRegistry()
        with pytest.raises(KeyError, match="no_such_simulator"):
            registry.get("no_such_simulator")

    def test_list_simulators_empty(self) -> None:
        registry = SimulatorRegistry()
        assert registry.list_simulators() == []

    def test_list_simulators_returns_registered_names(self) -> None:
        registry = SimulatorRegistry()
        registry.register("coin_flip", StubSimulator())
        registry.register("loot_table", StubSimulator())
        names = registry.list_simulators()
        assert sorted(names) == ["coin_flip", "loot_table"]

    def test_register_overwrites_existing(self) -> None:
        registry = SimulatorRegistry()
        sim1 = StubSimulator()
        sim2 = StubSimulator()
        registry.register("coin_flip", sim1)
        registry.register("coin_flip", sim2)
        assert registry.get("coin_flip") is sim2

    def test_list_simulators_returns_sorted(self) -> None:
        registry = SimulatorRegistry()
        registry.register("zebra_sim", StubSimulator())
        registry.register("alpha_sim", StubSimulator())
        names = registry.list_simulators()
        assert names == sorted(names)
