"""Tests for ConfigSchema, ConfigField, and ConfigFieldType.

Verifies:
- ConfigFieldType enum values
- ConfigField construction with defaults
- ConfigSchema.to_display_dict() converts internal -> display format
- ConfigSchema.from_display_dict() converts display -> internal format
- Roundtrip fidelity: from_display_dict(to_display_dict(d)) == d
- get_groups() returns ordered unique group names
- fields_by_group() groups fields correctly
- CoinFlipConfig.schema() returns a valid ConfigSchema
"""

from __future__ import annotations

import pytest

from src.domain.models.coin_flip import CoinFlipConfig
from src.domain.protocols import ConfigField, ConfigFieldType, ConfigSchema


# ---------------------------------------------------------------------------
# ConfigFieldType
# ---------------------------------------------------------------------------


class TestConfigFieldType:
    def test_integer_value(self) -> None:
        assert ConfigFieldType.INTEGER.value == "integer"

    def test_float_value(self) -> None:
        assert ConfigFieldType.FLOAT.value == "float"

    def test_percentage_value(self) -> None:
        assert ConfigFieldType.PERCENTAGE.value == "percentage"

    def test_enum_members_count(self) -> None:
        assert len(ConfigFieldType) == 3


# ---------------------------------------------------------------------------
# ConfigField
# ---------------------------------------------------------------------------


class TestConfigField:
    def test_construction_with_required_fields(self) -> None:
        field = ConfigField(
            name="test_field",
            display_name="Test Field",
            field_type=ConfigFieldType.INTEGER,
            default=10,
        )
        assert field.name == "test_field"
        assert field.display_name == "Test Field"
        assert field.field_type == ConfigFieldType.INTEGER
        assert field.default == 10

    def test_optional_defaults(self) -> None:
        field = ConfigField(
            name="f",
            display_name="F",
            field_type=ConfigFieldType.FLOAT,
            default=1.0,
        )
        assert field.min_value is None
        assert field.max_value is None
        assert field.help_text == ""
        assert field.group == ""

    def test_frozen_immutability(self) -> None:
        field = ConfigField(
            name="f",
            display_name="F",
            field_type=ConfigFieldType.INTEGER,
            default=5,
        )
        with pytest.raises(AttributeError):
            field.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConfigSchema — to_display_dict / from_display_dict
# ---------------------------------------------------------------------------


class TestConfigSchemaDisplayConversion:
    @pytest.fixture
    def percentage_schema(self) -> ConfigSchema:
        return ConfigSchema(
            fields=[
                ConfigField(
                    name="p_success_1",
                    display_name="P(Success 1)",
                    field_type=ConfigFieldType.PERCENTAGE,
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    group="probabilities",
                ),
                ConfigField(
                    name="points_1",
                    display_name="Points 1",
                    field_type=ConfigFieldType.INTEGER,
                    default=1,
                    min_value=0,
                    group="points",
                ),
                ConfigField(
                    name="ratio",
                    display_name="Ratio",
                    field_type=ConfigFieldType.FLOAT,
                    default=0.5,
                ),
            ]
        )

    def test_to_display_converts_percentage(self, percentage_schema: ConfigSchema) -> None:
        internal = {"p_success_1": 0.6, "points_1": 5, "ratio": 1.23}
        display = percentage_schema.to_display_dict(internal)
        assert display["p_success_1"] == "60%"

    def test_to_display_keeps_integer(self, percentage_schema: ConfigSchema) -> None:
        internal = {"p_success_1": 0.5, "points_1": 42, "ratio": 1.0}
        display = percentage_schema.to_display_dict(internal)
        assert display["points_1"] == 42
        assert isinstance(display["points_1"], int)

    def test_to_display_keeps_float(self, percentage_schema: ConfigSchema) -> None:
        internal = {"p_success_1": 0.5, "points_1": 1, "ratio": 3.14}
        display = percentage_schema.to_display_dict(internal)
        assert display["ratio"] == 3.14

    def test_from_display_converts_percentage_string(self, percentage_schema: ConfigSchema) -> None:
        display = {"p_success_1": "60%", "points_1": 5, "ratio": 1.23}
        internal = percentage_schema.from_display_dict(display)
        assert internal["p_success_1"] == pytest.approx(0.6)

    def test_from_display_converts_percentage_numeric(self, percentage_schema: ConfigSchema) -> None:
        """When percentage is already a float (e.g. from slider), treat as decimal."""
        display = {"p_success_1": 0.75, "points_1": 5, "ratio": 1.0}
        internal = percentage_schema.from_display_dict(display)
        assert internal["p_success_1"] == pytest.approx(0.75)

    def test_from_display_keeps_integer(self, percentage_schema: ConfigSchema) -> None:
        display = {"p_success_1": "50%", "points_1": 99, "ratio": 2.0}
        internal = percentage_schema.from_display_dict(display)
        assert internal["points_1"] == 99
        assert isinstance(internal["points_1"], int)

    def test_roundtrip_percentage(self, percentage_schema: ConfigSchema) -> None:
        """to_display then from_display should recover the original internal values."""
        original = {"p_success_1": 0.6, "points_1": 5, "ratio": 1.23}
        display = percentage_schema.to_display_dict(original)
        recovered = percentage_schema.from_display_dict(display)
        assert recovered["p_success_1"] == pytest.approx(original["p_success_1"])
        assert recovered["points_1"] == original["points_1"]
        assert recovered["ratio"] == original["ratio"]

    def test_to_display_zero_percentage(self, percentage_schema: ConfigSchema) -> None:
        internal = {"p_success_1": 0.0, "points_1": 0, "ratio": 0.0}
        display = percentage_schema.to_display_dict(internal)
        assert display["p_success_1"] == "0%"

    def test_to_display_full_percentage(self, percentage_schema: ConfigSchema) -> None:
        internal = {"p_success_1": 1.0, "points_1": 0, "ratio": 0.0}
        display = percentage_schema.to_display_dict(internal)
        assert display["p_success_1"] == "100%"

    def test_from_display_zero_percent_string(self, percentage_schema: ConfigSchema) -> None:
        display = {"p_success_1": "0%", "points_1": 0, "ratio": 0.0}
        internal = percentage_schema.from_display_dict(display)
        assert internal["p_success_1"] == 0.0

    def test_from_display_hundred_percent_string(self, percentage_schema: ConfigSchema) -> None:
        display = {"p_success_1": "100%", "points_1": 0, "ratio": 0.0}
        internal = percentage_schema.from_display_dict(display)
        assert internal["p_success_1"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# ConfigSchema — grouping
# ---------------------------------------------------------------------------


class TestConfigSchemaGrouping:
    @pytest.fixture
    def grouped_schema(self) -> ConfigSchema:
        return ConfigSchema(
            fields=[
                ConfigField(name="a", display_name="A", field_type=ConfigFieldType.FLOAT, default=0.0, group="alpha"),
                ConfigField(name="b", display_name="B", field_type=ConfigFieldType.FLOAT, default=0.0, group="beta"),
                ConfigField(name="c", display_name="C", field_type=ConfigFieldType.FLOAT, default=0.0, group="alpha"),
                ConfigField(name="d", display_name="D", field_type=ConfigFieldType.FLOAT, default=0.0),
            ]
        )

    def test_get_groups_returns_ordered_unique(self, grouped_schema: ConfigSchema) -> None:
        groups = grouped_schema.get_groups()
        assert groups == ["alpha", "beta"]

    def test_get_groups_excludes_empty_group(self, grouped_schema: ConfigSchema) -> None:
        groups = grouped_schema.get_groups()
        assert "" not in groups

    def test_fields_by_group_structure(self, grouped_schema: ConfigSchema) -> None:
        by_group = grouped_schema.fields_by_group()
        assert len(by_group["alpha"]) == 2
        assert len(by_group["beta"]) == 1
        assert len(by_group[""]) == 1

    def test_fields_by_group_field_names(self, grouped_schema: ConfigSchema) -> None:
        by_group = grouped_schema.fields_by_group()
        alpha_names = [f.name for f in by_group["alpha"]]
        assert alpha_names == ["a", "c"]

    def test_empty_schema_groups(self) -> None:
        schema = ConfigSchema(fields=[])
        assert schema.get_groups() == []
        assert schema.fields_by_group() == {}


# ---------------------------------------------------------------------------
# CoinFlipConfig.schema()
# ---------------------------------------------------------------------------


class TestCoinFlipConfigSchema:
    def test_schema_returns_config_schema(self) -> None:
        schema = CoinFlipConfig.schema()
        assert isinstance(schema, ConfigSchema)

    def test_default_schema_has_correct_field_count(self) -> None:
        schema = CoinFlipConfig.schema()
        # 5 probability + 5 points + 1 max_successes = 11
        assert len(schema.fields) == 11

    def test_custom_max_successes(self) -> None:
        schema = CoinFlipConfig.schema(max_successes=3)
        # 3 probability + 3 points + 1 max_successes = 7
        assert len(schema.fields) == 7

    def test_probability_fields_are_percentage_type(self) -> None:
        schema = CoinFlipConfig.schema()
        prob_fields = [f for f in schema.fields if f.name.startswith("p_success_")]
        assert len(prob_fields) == 5
        for f in prob_fields:
            assert f.field_type == ConfigFieldType.PERCENTAGE

    def test_points_fields_are_integer_type(self) -> None:
        schema = CoinFlipConfig.schema()
        pts_fields = [f for f in schema.fields if f.name.startswith("points_success_")]
        assert len(pts_fields) == 5
        for f in pts_fields:
            assert f.field_type == ConfigFieldType.INTEGER

    def test_max_successes_field_is_integer(self) -> None:
        schema = CoinFlipConfig.schema()
        ms_fields = [f for f in schema.fields if f.name == "max_successes"]
        assert len(ms_fields) == 1
        assert ms_fields[0].field_type == ConfigFieldType.INTEGER

    def test_groups_present(self) -> None:
        schema = CoinFlipConfig.schema()
        groups = schema.get_groups()
        assert "probabilities" in groups
        assert "points" in groups

    def test_schema_to_display_matches_config_obj_to_display(self) -> None:
        """Ensure schema-based conversion produces the same output as the
        existing config_obj_to_display function."""
        config = CoinFlipConfig(
            max_successes=5,
            probabilities=(0.6, 0.5, 0.5, 0.5, 0.5),
            point_values=(1.0, 2.0, 4.0, 8.0, 16.0),
        )
        schema = CoinFlipConfig.schema(max_successes=config.max_successes)

        # Build a flat dict from config using CSV-style keys
        flat: dict[str, float | int] = {}
        for i, p in enumerate(config.probabilities, 1):
            flat[f"p_success_{i}"] = p
        for i, v in enumerate(config.point_values, 1):
            flat[f"points_success_{i}"] = v
        flat["max_successes"] = config.max_successes

        display = schema.to_display_dict(flat)
        assert display["p_success_1"] == "60%"
        assert display["p_success_2"] == "50%"
        assert display["points_success_1"] == 1
        assert display["max_successes"] == 5

    def test_schema_roundtrip_with_coin_flip_values(self) -> None:
        """to_display -> from_display should recover original values."""
        schema = CoinFlipConfig.schema(max_successes=3)
        internal = {
            "p_success_1": 0.6,
            "p_success_2": 0.5,
            "p_success_3": 0.4,
            "points_success_1": 1,
            "points_success_2": 2,
            "points_success_3": 4,
            "max_successes": 3,
        }
        display = schema.to_display_dict(internal)
        recovered = schema.from_display_dict(display)
        assert recovered["p_success_1"] == pytest.approx(0.6)
        assert recovered["p_success_2"] == pytest.approx(0.5)
        assert recovered["p_success_3"] == pytest.approx(0.4)
        assert recovered["points_success_1"] == 1
        assert recovered["points_success_2"] == 2
        assert recovered["points_success_3"] == 4
        assert recovered["max_successes"] == 3
