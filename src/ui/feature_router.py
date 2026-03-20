"""Feature routing — maps feature names to their UI configurations.

Provides a registry of available game mechanic features with display
metadata. Used by the Streamlit app to render the correct UI based
on the ``?feature=`` query parameter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureUIConfig:
    """Display metadata for a simulator feature in the dashboard.

    Attributes:
        name: Internal identifier matching the simulator registry key.
        display_name: Human-readable name shown in the UI.
        icon: Emoji icon for visual identification.
        description: Short description shown in the feature selector.
    """

    name: str
    display_name: str
    icon: str
    description: str


# ---------------------------------------------------------------------------
# Feature registry — add new features here as they are implemented
# ---------------------------------------------------------------------------

FEATURE_REGISTRY: dict[str, FeatureUIConfig] = {
    "coin_flip": FeatureUIConfig(
        name="coin_flip",
        display_name="Coin Flip",
        icon="\U0001f3b2",
        description="Sequential coin-flip chain simulation",
    ),
    "loot_table": FeatureUIConfig(
        name="loot_table",
        display_name="Loot Table",
        icon="\U0001f381",
        description="Weighted loot pool simulation with rarity tiers and pity system",
    ),
}

DEFAULT_FEATURE = "coin_flip"


def get_feature_config(feature_name: str) -> FeatureUIConfig | None:
    """Look up a feature's UI config by name.

    Returns None if the feature is not registered.
    """
    return FEATURE_REGISTRY.get(feature_name)


def list_feature_names() -> list[str]:
    """Return all registered feature names in insertion order."""
    return list(FEATURE_REGISTRY.keys())


def is_valid_feature(feature_name: str) -> bool:
    """Return True if the feature name is registered."""
    return feature_name in FEATURE_REGISTRY
