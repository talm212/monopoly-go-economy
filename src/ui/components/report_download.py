"""Download Report button component for the simulation dashboard.

Generates a PDF report from simulation results and provides a Streamlit
download button for the user.
"""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from src.application.report_generator import SimulationReportGenerator

logger = logging.getLogger(__name__)

# Singleton generator — stateless, safe to reuse
_generator = SimulationReportGenerator()


def render_report_download(
    config: dict[str, Any],
    kpi_metrics: dict[str, float],
    distribution: dict[str, int],
    segments: dict[str, dict[str, float]] | None = None,
    insights: list[dict[str, Any]] | None = None,
    feature_name: str = "coin_flip",
) -> None:
    """Render a Download Report button that generates and downloads a PDF.

    Args:
        config: Simulation configuration key-value pairs.
        kpi_metrics: KPI metric name to numeric value mapping.
        distribution: Success depth to interaction count mapping.
        segments: Optional churn vs non-churn segment metrics.
        insights: Optional AI-generated insights with severity.
        feature_name: Name of the simulated feature.
    """
    try:
        pdf_bytes = _generator.generate(
            config=config,
            kpi_metrics=kpi_metrics,
            distribution=distribution,
            segments=segments,
            insights=insights,
            feature_name=feature_name,
        )
    except Exception:
        logger.exception("Failed to generate PDF report")
        st.error("Failed to generate PDF report.")
        return

    display_name = feature_name.replace("_", " ").title()
    st.download_button(
        label=f"Download {display_name} Report (PDF)",
        data=pdf_bytes,
        file_name=f"{feature_name}_simulation_report.pdf",
        mime="application/pdf",
        key="download_report_pdf",
    )
