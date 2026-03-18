"""Simulator registry for looking up simulator implementations by name.

Provides a central registry where each simulator feature (coin flip,
loot table, etc.) registers itself so the application layer and UI
can discover and invoke simulators dynamically.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.protocols import Simulator

logger = logging.getLogger(__name__)


class SimulatorRegistry:
    """Registry mapping string names to Simulator instances.

    Usage::

        registry = SimulatorRegistry()
        registry.register("coin_flip", CoinFlipSimulator())
        sim = registry.get("coin_flip")
    """

    def __init__(self) -> None:
        self._simulators: dict[str, Simulator] = {}

    def register(self, name: str, simulator: Simulator) -> None:
        """Register a simulator under the given name.

        If a simulator is already registered with the same name it will
        be overwritten.

        Args:
            name: Unique string identifier for the simulator.
            simulator: An object conforming to the Simulator protocol.
        """
        logger.info("Registering simulator: %s", name)
        self._simulators[name] = simulator

    def get(self, name: str) -> Simulator:
        """Retrieve a simulator by name.

        Args:
            name: The registered name of the simulator.

        Returns:
            The Simulator instance.

        Raises:
            KeyError: If no simulator is registered under the given name.
        """
        if name not in self._simulators:
            raise KeyError(
                f"Unknown simulator '{name}'. "
                f"Available: {self.list_simulators()}"
            )
        return self._simulators[name]

    def list_simulators(self) -> list[str]:
        """Return a sorted list of all registered simulator names."""
        return sorted(self._simulators.keys())
