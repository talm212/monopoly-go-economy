"""Schema-driven configuration editor for any simulator feature.

Renders Streamlit widgets based on ConfigSchema metadata, handling type
conversion, grouping, and validation constraints automatically.  This is
an addition to — not a replacement for — the existing dict-based
``config_editor.render_config_editor`` component.
"""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from src.domain.protocols import ConfigField, ConfigFieldType, ConfigSchema

logger = logging.getLogger(__name__)


def render_schema_editor(
    schema: ConfigSchema,
    values: dict[str, Any],
    key_prefix: str,
) -> dict[str, Any]:
    """Render editable form fields driven by a ConfigSchema.

    Widgets are selected based on each field's ``ConfigFieldType``:
    - PERCENTAGE -> slider (0-100) with ``%.1f%%`` format
    - INTEGER -> number input with step=1
    - FLOAT -> number input with step=0.01

    Fields are grouped by their ``group`` attribute; each group gets a
    subheader.  Ungrouped fields render at the end under "General".

    Args:
        schema: The ConfigSchema defining field metadata.
        values: Current display-format values (keys matching field names).
        key_prefix: Prefix added to Streamlit widget keys for uniqueness.

    Returns:
        A new dict with the same keys and user-edited display values.
    """
    edited: dict[str, Any] = {}
    grouped = schema.fields_by_group()
    group_order = schema.get_groups()

    # Render grouped fields first
    for group_name in group_order:
        group_fields = grouped[group_name]
        st.subheader(group_name.replace("_", " ").title())
        for cfg_field in group_fields:
            edited[cfg_field.name] = _render_field(cfg_field, values, key_prefix)

    # Render ungrouped fields
    ungrouped = grouped.get("", [])
    if ungrouped:
        if group_order:
            st.subheader("General")
        for cfg_field in ungrouped:
            edited[cfg_field.name] = _render_field(cfg_field, values, key_prefix)

    return edited


def _render_field(
    cfg_field: ConfigField,
    values: dict[str, Any],
    key_prefix: str,
) -> Any:
    """Render a single config field and return its display value."""
    widget_key = f"{key_prefix}_{cfg_field.name}"
    current = values.get(cfg_field.name, cfg_field.default)

    if cfg_field.field_type == ConfigFieldType.PERCENTAGE:
        return _render_percentage(cfg_field, current, widget_key)

    if cfg_field.field_type == ConfigFieldType.INTEGER:
        return _render_integer(cfg_field, current, widget_key)

    if cfg_field.field_type == ConfigFieldType.FLOAT:
        return _render_float(cfg_field, current, widget_key)

    # Fallback — should not happen with current enum, but defensive
    logger.warning(
        "Unknown ConfigFieldType %s for field '%s'; rendering as text",
        cfg_field.field_type,
        cfg_field.name,
    )
    return st.text_input(cfg_field.display_name, value=str(current), key=widget_key)


def _render_percentage(
    cfg_field: ConfigField,
    current: Any,
    widget_key: str,
) -> str:
    """Render a PERCENTAGE field as a slider returning a display string like '60%'."""
    # Parse current display value to a numeric percentage
    if isinstance(current, str) and current.endswith("%"):
        pct_value = float(current[:-1])
    elif isinstance(current, (int, float)):
        # If the value looks like a raw decimal (<=1.0), convert to percentage
        pct_value = float(current) * 100.0 if float(current) <= 1.0 else float(current)
    else:
        pct_value = float(cfg_field.default) * 100.0

    min_pct = float(cfg_field.min_value) * 100.0 if cfg_field.min_value is not None else 0.0
    max_pct = float(cfg_field.max_value) * 100.0 if cfg_field.max_value is not None else 100.0

    slider_result: float = st.slider(
        cfg_field.display_name,
        min_value=min_pct,
        max_value=max_pct,
        value=pct_value,
        step=0.5,
        format="%.1f%%",
        key=widget_key,
        help=cfg_field.help_text or None,
    )
    return f"{slider_result}%"


def _render_integer(
    cfg_field: ConfigField,
    current: Any,
    widget_key: str,
) -> int:
    """Render an INTEGER field as a number input with step=1."""
    int_value = int(current) if current is not None else int(cfg_field.default)

    kwargs: dict[str, Any] = {
        "label": cfg_field.display_name,
        "value": int_value,
        "step": 1,
        "key": widget_key,
    }
    if cfg_field.min_value is not None:
        kwargs["min_value"] = int(cfg_field.min_value)
    if cfg_field.max_value is not None:
        kwargs["max_value"] = int(cfg_field.max_value)
    if cfg_field.help_text:
        kwargs["help"] = cfg_field.help_text

    return int(st.number_input(**kwargs))


def _render_float(
    cfg_field: ConfigField,
    current: Any,
    widget_key: str,
) -> float:
    """Render a FLOAT field as a number input with step=0.01."""
    float_value = float(current) if current is not None else float(cfg_field.default)

    kwargs: dict[str, Any] = {
        "label": cfg_field.display_name,
        "value": float_value,
        "step": 0.01,
        "format": "%.4f",
        "key": widget_key,
    }
    if cfg_field.min_value is not None:
        kwargs["min_value"] = float(cfg_field.min_value)
    if cfg_field.max_value is not None:
        kwargs["max_value"] = float(cfg_field.max_value)
    if cfg_field.help_text:
        kwargs["help"] = cfg_field.help_text

    return float(st.number_input(**kwargs))
