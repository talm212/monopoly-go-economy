"""Unit tests for the feature router module."""

from __future__ import annotations

from src.ui.feature_router import (
    DEFAULT_FEATURE,
    FEATURE_REGISTRY,
    FeatureUIConfig,
    get_feature_config,
    is_valid_feature,
    list_feature_names,
)


class TestFeatureUIConfig:
    """Tests for the FeatureUIConfig dataclass."""

    def test_frozen_dataclass(self) -> None:
        cfg = FeatureUIConfig(
            name="test",
            display_name="Test Feature",
            icon="T",
            description="A test feature",
        )
        assert cfg.name == "test"
        assert cfg.display_name == "Test Feature"
        assert cfg.icon == "T"
        assert cfg.description == "A test feature"

    def test_immutable(self) -> None:
        cfg = FeatureUIConfig(
            name="test",
            display_name="Test",
            icon="T",
            description="desc",
        )
        try:
            cfg.name = "changed"  # type: ignore[misc]
            raise AssertionError("Expected FrozenInstanceError")
        except AttributeError:
            pass  # Expected — frozen dataclass

    def test_equality(self) -> None:
        a = FeatureUIConfig(name="x", display_name="X", icon="!", description="d")
        b = FeatureUIConfig(name="x", display_name="X", icon="!", description="d")
        assert a == b


class TestFeatureRegistry:
    """Tests for the FEATURE_REGISTRY and helper functions."""

    def test_coin_flip_registered(self) -> None:
        assert "coin_flip" in FEATURE_REGISTRY

    def test_coin_flip_config_values(self) -> None:
        cfg = FEATURE_REGISTRY["coin_flip"]
        assert cfg.name == "coin_flip"
        assert cfg.display_name == "Coin Flip"
        assert len(cfg.icon) > 0
        assert len(cfg.description) > 0

    def test_default_feature_is_coin_flip(self) -> None:
        assert DEFAULT_FEATURE == "coin_flip"

    def test_default_feature_is_registered(self) -> None:
        assert DEFAULT_FEATURE in FEATURE_REGISTRY


class TestGetFeatureConfig:
    """Tests for get_feature_config()."""

    def test_existing_feature(self) -> None:
        cfg = get_feature_config("coin_flip")
        assert cfg is not None
        assert cfg.name == "coin_flip"

    def test_unknown_feature_returns_none(self) -> None:
        assert get_feature_config("nonexistent_feature") is None

    def test_empty_string_returns_none(self) -> None:
        assert get_feature_config("") is None


class TestListFeatureNames:
    """Tests for list_feature_names()."""

    def test_returns_list(self) -> None:
        names = list_feature_names()
        assert isinstance(names, list)

    def test_contains_coin_flip(self) -> None:
        assert "coin_flip" in list_feature_names()

    def test_preserves_insertion_order(self) -> None:
        names = list_feature_names()
        registry_keys = list(FEATURE_REGISTRY.keys())
        assert names == registry_keys


class TestIsValidFeature:
    """Tests for is_valid_feature()."""

    def test_valid_feature(self) -> None:
        assert is_valid_feature("coin_flip") is True

    def test_invalid_feature(self) -> None:
        assert is_valid_feature("nonexistent") is False

    def test_empty_string(self) -> None:
        assert is_valid_feature("") is False

    def test_case_sensitive(self) -> None:
        assert is_valid_feature("Coin_Flip") is False
        assert is_valid_feature("COIN_FLIP") is False
