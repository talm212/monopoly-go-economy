"""Tests for SimulationReportGenerator PDF generation."""

from __future__ import annotations

import re

import pytest

from src.application.report_generator import SimulationReportGenerator


# ---------------------------------------------------------------------------
# PDF text extraction helper (for uncompressed PDFs)
# ---------------------------------------------------------------------------


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract readable text from an uncompressed PDF.

    Parses reportlab text-drawing operators ``(text) Tj`` and ``[(text)] TJ``
    from the raw PDF bytes.  Works only when the PDF is generated with
    ``_compress=False``.
    """
    raw = pdf_bytes.decode("latin-1", errors="replace")
    # Match text inside parentheses from Tj/TJ operators
    texts = re.findall(r"\(([^)]*)\)", raw)
    return " ".join(texts)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def generator() -> SimulationReportGenerator:
    return SimulationReportGenerator()


@pytest.fixture()
def sample_config() -> dict[str, object]:
    return {
        "max_successes": 5,
        "probabilities": [0.6, 0.5, 0.4, 0.3, 0.2],
        "point_values": [1, 2, 5, 10, 50],
        "churn_boost_multiplier": 1.3,
        "reward_threshold": 100.0,
    }


@pytest.fixture()
def sample_kpis() -> dict[str, float]:
    return {
        "Mean Points / Player": 42.5,
        "Median Points / Player": 35.0,
        "Total Points": 4250000.0,
        "% Above Threshold": 18.75,
    }


@pytest.fixture()
def sample_distribution() -> dict[str, int]:
    return {
        "0": 400000,
        "1": 300000,
        "2": 180000,
        "3": 80000,
        "4": 30000,
        "5": 10000,
    }


@pytest.fixture()
def sample_segments() -> dict[str, dict[str, float]]:
    return {
        "churn": {
            "Player Count": 2000.0,
            "Avg Points / Player": 55.0,
            "Median Points / Player": 48.0,
            "Total Points": 110000.0,
        },
        "non-churn": {
            "Player Count": 8000.0,
            "Avg Points / Player": 39.5,
            "Median Points / Player": 32.0,
            "Total Points": 316000.0,
        },
    }


@pytest.fixture()
def sample_insights() -> list[dict[str, object]]:
    return [
        {
            "title": "High churn boost impact",
            "description": "Churn players earn 39% more on average.",
            "severity": "warning",
        },
        {
            "title": "Distribution skew detected",
            "description": "Mean is 21% higher than median, indicating right skew.",
            "severity": "info",
        },
        {
            "title": "Threshold coverage low",
            "description": "Only 18.75% of players exceed the reward threshold.",
            "severity": "critical",
        },
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimulationReportGenerator:
    """Tests for PDF report generation."""

    def test_generate_full_report_returns_valid_pdf(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
        sample_segments: dict[str, dict[str, float]],
        sample_insights: list[dict[str, object]],
    ) -> None:
        """Full report with all sections produces non-empty PDF bytes."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            segments=sample_segments,
            insights=sample_insights,
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_generate_minimal_report_no_segments_no_insights(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """Report with only required sections (no segments, no insights) is valid."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_kpi_values_appear_in_pdf_text(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """All KPI metric names appear in the PDF content."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)

        for metric_name in sample_kpis:
            assert metric_name in pdf_text, (
                f"KPI metric '{metric_name}' not found in PDF content"
            )

    def test_config_values_appear_in_pdf_text(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """Configuration parameter names appear in the PDF content."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)

        for param_name in sample_config:
            assert param_name in pdf_text, (
                f"Config parameter '{param_name}' not found in PDF content"
            )

    def test_distribution_heading_in_pdf(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """Distribution section heading appears in the PDF content."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)
        assert "Distribution" in pdf_text

    def test_segments_appear_in_pdf_text(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
        sample_segments: dict[str, dict[str, float]],
    ) -> None:
        """Segment comparison data appears in the PDF when provided."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            segments=sample_segments,
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)
        assert "Segment Comparison" in pdf_text

    def test_insights_appear_in_pdf_text(
        self,
        generator: SimulationReportGenerator,
        sample_config: dict[str, object],
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
        sample_insights: list[dict[str, object]],
    ) -> None:
        """AI insights section appears in the PDF when provided."""
        pdf_bytes = generator.generate(
            config=sample_config,
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            insights=sample_insights,
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)
        assert "AI Insights" in pdf_text
        assert "High churn boost impact" in pdf_text

    def test_custom_feature_name_in_header(
        self,
        generator: SimulationReportGenerator,
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """Custom feature name appears in the report header."""
        pdf_bytes = generator.generate(
            config={},
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
            feature_name="loot_table",
            _compress=False,
        )

        pdf_text = _extract_pdf_text(pdf_bytes)
        assert "Loot Table" in pdf_text

    def test_empty_config_produces_valid_pdf(
        self,
        generator: SimulationReportGenerator,
        sample_kpis: dict[str, float],
        sample_distribution: dict[str, int],
    ) -> None:
        """Empty config dict still produces a valid PDF."""
        pdf_bytes = generator.generate(
            config={},
            kpi_metrics=sample_kpis,
            distribution=sample_distribution,
        )

        assert pdf_bytes[:5] == b"%PDF-"

    def test_format_value_integers(
        self,
        generator: SimulationReportGenerator,
    ) -> None:
        """_format_value handles int, float, list, and string values."""
        assert generator._format_value(1000) == "1,000"
        assert generator._format_value(42.0) == "42"
        assert generator._format_value(3.14) == "3.14"
        assert generator._format_value([0.5, 0.3]) == "0.5, 0.3"
        assert generator._format_value("hello") == "hello"
