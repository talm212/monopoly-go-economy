"""Pure unit tests for UI helper functions.

Tests render_severity_badge() and _build_sweepable_params() without
requiring a running Streamlit server. These are pure functions that
return strings/dicts, so no mocking of st.* is needed.
"""

from __future__ import annotations

import pytest

from src.domain.models.insight import Severity
from src.ui.components.insight_cards import (
    SEVERITY_COLORS,
    SEVERITY_LABELS,
    render_severity_badge,
)
from src.ui.sections.parameter_sweep import _build_sweepable_params

# ---------------------------------------------------------------------------
# render_severity_badge tests
# ---------------------------------------------------------------------------


class TestRenderSeverityBadge:
    """Tests for the HTML badge rendering helper."""

    def test_info_badge_has_correct_color(self) -> None:
        """INFO severity badge uses color #1E88E5."""
        html = render_severity_badge(Severity.INFO)
        assert "#1E88E5" in html

    def test_info_badge_has_label(self) -> None:
        """INFO severity badge displays 'INFO' label."""
        html = render_severity_badge(Severity.INFO)
        assert "INFO" in html

    def test_warning_badge_has_correct_color(self) -> None:
        """WARNING severity badge uses color #FB8C00."""
        html = render_severity_badge(Severity.WARNING)
        assert "#FB8C00" in html

    def test_warning_badge_has_label(self) -> None:
        """WARNING severity badge displays 'WARNING' label."""
        html = render_severity_badge(Severity.WARNING)
        assert "WARNING" in html

    def test_critical_badge_has_correct_color(self) -> None:
        """CRITICAL severity badge uses color #E53935."""
        html = render_severity_badge(Severity.CRITICAL)
        assert "#E53935" in html

    def test_critical_badge_has_label(self) -> None:
        """CRITICAL severity badge displays 'CRITICAL' label."""
        html = render_severity_badge(Severity.CRITICAL)
        assert "CRITICAL" in html

    def test_badge_is_html_span(self) -> None:
        """Badge output is an HTML span element."""
        html = render_severity_badge(Severity.INFO)
        assert html.startswith("<span")
        assert html.endswith("</span>")

    def test_badge_has_white_text(self) -> None:
        """Badge text is white for contrast."""
        html = render_severity_badge(Severity.INFO)
        assert "color:white" in html

    def test_all_severities_have_colors(self) -> None:
        """Every Severity enum member is mapped in SEVERITY_COLORS."""
        for severity in Severity:
            assert severity in SEVERITY_COLORS

    def test_all_severities_have_labels(self) -> None:
        """Every Severity enum member is mapped in SEVERITY_LABELS."""
        for severity in Severity:
            assert severity in SEVERITY_LABELS


# ---------------------------------------------------------------------------
# _build_sweepable_params tests
# ---------------------------------------------------------------------------


class TestBuildSweepableParams:
    """Tests for the sweepable parameter metadata builder."""

    def test_max_successes_3_generates_correct_count(self) -> None:
        """max_successes=3 produces 3 probability + 3 point params + 1 threshold = 7."""
        params = _build_sweepable_params(max_successes=3)
        assert len(params) == 7  # 3 + 3 + 1 (reward_threshold)

    def test_max_successes_1_generates_correct_count(self) -> None:
        """max_successes=1 produces 1 probability + 1 point param + 1 threshold = 3."""
        params = _build_sweepable_params(max_successes=1)
        assert len(params) == 3  # 1 + 1 + 1

    def test_max_successes_5_generates_correct_count(self) -> None:
        """max_successes=5 produces 5 probability + 5 point params + 1 threshold = 11."""
        params = _build_sweepable_params(max_successes=5)
        assert len(params) == 11  # 5 + 5 + 1

    def test_probability_params_have_correct_keys(self) -> None:
        """Probability params are named p_success_1 through p_success_N."""
        params = _build_sweepable_params(max_successes=3)
        assert "p_success_1" in params
        assert "p_success_2" in params
        assert "p_success_3" in params

    def test_point_params_have_correct_keys(self) -> None:
        """Point params are named points_success_1 through points_success_N."""
        params = _build_sweepable_params(max_successes=3)
        assert "points_success_1" in params
        assert "points_success_2" in params
        assert "points_success_3" in params

    def test_reward_threshold_always_present(self) -> None:
        """reward_threshold is always included regardless of max_successes."""
        params = _build_sweepable_params(max_successes=1)
        assert "reward_threshold" in params

    def test_probability_params_map_to_correct_sweep_names(self) -> None:
        """Probability params map to 'probabilities.N' format."""
        params = _build_sweepable_params(max_successes=2)
        assert params["p_success_1"]["param_name"] == "probabilities.0"
        assert params["p_success_2"]["param_name"] == "probabilities.1"

    def test_point_params_map_to_correct_sweep_names(self) -> None:
        """Point params map to 'point_values.N' format."""
        params = _build_sweepable_params(max_successes=2)
        assert params["points_success_1"]["param_name"] == "point_values.0"
        assert params["points_success_2"]["param_name"] == "point_values.1"

    def test_probability_params_have_valid_range(self) -> None:
        """Probability params have min=0.0 and max=1.0."""
        params = _build_sweepable_params(max_successes=1)
        p = params["p_success_1"]
        assert p["min"] == 0.0
        assert p["max"] == 1.0

    def test_threshold_param_has_correct_sweep_name(self) -> None:
        """reward_threshold maps to 'reward_threshold' (flat param, not indexed)."""
        params = _build_sweepable_params(max_successes=1)
        assert params["reward_threshold"]["param_name"] == "reward_threshold"
