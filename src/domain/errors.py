"""Domain-specific exception types."""


class SimulationError(Exception):
    """Base exception for simulation errors."""


class InvalidConfigError(SimulationError, ValueError):
    """Raised when a simulator configuration is invalid."""


class InvalidPlayerDataError(SimulationError, ValueError):
    """Raised when player data fails validation."""
