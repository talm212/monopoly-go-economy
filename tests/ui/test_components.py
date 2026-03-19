"""Unit tests for pure helper functions in UI components (no Streamlit needed)."""

from __future__ import annotations

from src.ui.components.kpi_cards import _format_value
from src.ui.components.config_editor import _is_percentage, _parse_percentage


# ---------------------------------------------------------------------------
# _format_value (kpi_cards)
# ---------------------------------------------------------------------------


class TestFormatValue:
    def test_integer(self) -> None:
        assert _format_value(1000) == "1,000"

    def test_float_whole(self) -> None:
        assert _format_value(1000.0) == "1,000"

    def test_float_decimal(self) -> None:
        assert _format_value(1234.56) == "1,234.56"

    def test_zero_int(self) -> None:
        assert _format_value(0) == "0"

    def test_zero_float(self) -> None:
        assert _format_value(0.0) == "0"

    def test_large_number(self) -> None:
        assert _format_value(1_000_000) == "1,000,000"


# ---------------------------------------------------------------------------
# _is_percentage (config_editor)
# ---------------------------------------------------------------------------


class TestIsPercentage:
    def test_valid_percentage(self) -> None:
        assert _is_percentage("60%") is True

    def test_decimal_percentage(self) -> None:
        assert _is_percentage("99.5%") is True

    def test_plain_number(self) -> None:
        assert _is_percentage("60") is False

    def test_non_string(self) -> None:
        assert _is_percentage(60) is False

    def test_empty_string(self) -> None:
        assert _is_percentage("") is False


# ---------------------------------------------------------------------------
# _parse_percentage (config_editor)
# ---------------------------------------------------------------------------


class TestParsePercentage:
    def test_integer_percentage(self) -> None:
        assert _parse_percentage("60%") == 60.0

    def test_decimal_percentage(self) -> None:
        assert _parse_percentage("99.5%") == 99.5

    def test_invalid_string(self) -> None:
        assert _parse_percentage("hello") == 0.0
