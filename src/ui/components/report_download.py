"""Download Report button component for the simulation dashboard.

Generates a PDF report on-demand when the user clicks the button.
Data is prepared eagerly but the PDF is only written when requested.
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
    """Render a Download Report button that generates a PDF on click.

    The PDF is only generated when the user clicks the button, not on
    every page render. Data is prepared eagerly but file writing is lazy.
    """
    display_name = feature_name.replace("_", " ").title()

    if st.button(
        f"Generate {display_name} Report (PDF)",
        key="generate_report_pdf",
        use_container_width=True,
        help="Generate a PDF report with config, KPIs, distribution, churn segments, and AI insights (if generated).",
    ):
        try:
            with st.spinner("Generating PDF report..."):
                pdf_bytes = _generator.generate(
                    config=config,
                    kpi_metrics=kpi_metrics,
                    distribution=distribution,
                    segments=segments,
                    insights=insights,
                    feature_name=feature_name,
                )
            st.session_state["_report_pdf_bytes"] = pdf_bytes
        except Exception:
            logger.exception("Failed to generate PDF report")
            st.error("Failed to generate PDF report.")
            return

    # Show download button only after PDF is generated
    pdf_bytes: bytes | None = st.session_state.get("_report_pdf_bytes")
    if pdf_bytes is not None:
        st.download_button(
            label=f"Download {display_name} Report (PDF)",
            data=pdf_bytes,
            file_name=f"{feature_name}_simulation_report.pdf",
            mime="application/pdf",
            key="download_report_pdf",
            help="Download the generated PDF report.",
        )
