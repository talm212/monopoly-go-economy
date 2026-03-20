"""PDF report generator for simulation results.

Produces a clean, formatted PDF containing configuration, KPIs,
distribution data, optional segment comparison, and AI insights.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_MARGIN = 20 * mm
_SPACER_HEIGHT = 6 * mm
_SECTION_SPACER_HEIGHT = 12 * mm

_HEADER_BG = colors.HexColor("#2C3E50")
_HEADER_FG = colors.white
_ALT_ROW_BG = colors.HexColor("#F5F6FA")
_GRID_COLOR = colors.HexColor("#D5D8DC")

_SEVERITY_COLORS: dict[str, colors.Color] = {
    "critical": colors.HexColor("#E74C3C"),
    "warning": colors.HexColor("#F39C12"),
    "info": colors.HexColor("#3498DB"),
    "positive": colors.HexColor("#27AE60"),
}


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


class SimulationReportGenerator:
    """Generates PDF reports from simulation results."""

    def generate(
        self,
        config: dict[str, Any],
        kpi_metrics: dict[str, float],
        distribution: dict[str, int],
        segments: dict[str, dict[str, float]] | None = None,
        insights: list[dict[str, Any]] | None = None,
        feature_name: str = "coin_flip",
        *,
        _compress: bool = True,
    ) -> bytes:
        """Generate a PDF report and return as bytes.

        Args:
            config: Simulation configuration key-value pairs.
            kpi_metrics: KPI metric name to numeric value mapping.
            distribution: Success depth to interaction count mapping.
            segments: Optional churn vs non-churn segment metrics.
            insights: Optional AI-generated insights with severity.
            feature_name: Name of the simulated feature.

        Returns:
            PDF file content as bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=_PAGE_MARGIN,
            rightMargin=_PAGE_MARGIN,
            topMargin=_PAGE_MARGIN,
            bottomMargin=_PAGE_MARGIN,
            pageCompression=1 if _compress else 0,
        )

        styles = getSampleStyleSheet()
        elements: list[Any] = []

        # -- Header --
        elements.extend(self._build_header(styles, feature_name))
        elements.append(Spacer(1, _SECTION_SPACER_HEIGHT))

        # -- Configuration table --
        elements.extend(self._build_config_section(styles, config))
        elements.append(Spacer(1, _SECTION_SPACER_HEIGHT))

        # -- KPI summary table --
        elements.extend(self._build_kpi_section(styles, kpi_metrics))
        elements.append(Spacer(1, _SECTION_SPACER_HEIGHT))

        # -- Distribution table --
        elements.extend(self._build_distribution_section(styles, distribution))

        # -- Segment comparison (optional) --
        if segments:
            elements.append(Spacer(1, _SECTION_SPACER_HEIGHT))
            elements.extend(self._build_segments_section(styles, segments))

        # -- AI Insights (optional) --
        if insights:
            elements.append(Spacer(1, _SECTION_SPACER_HEIGHT))
            elements.extend(self._build_insights_section(styles, insights))

        doc.build(elements)
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_header(
        self,
        styles: Any,
        feature_name: str,
    ) -> list[Any]:
        """Build the report title and timestamp."""
        display_name = feature_name.replace("_", " ").title()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=20,
            spaceAfter=4 * mm,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.grey,
        )
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return [
            Paragraph(f"Economy Simulation Report — {display_name}", title_style),
            Paragraph(f"Generated: {timestamp}", subtitle_style),
        ]

    def _build_config_section(
        self,
        styles: Any,
        config: dict[str, Any],
    ) -> list[Any]:
        """Build the configuration key-value table."""
        heading = Paragraph("Configuration", styles["Heading2"])
        data = [["Parameter", "Value"]]
        for key, value in config.items():
            data.append([str(key), self._format_value(value)])
        table = self._styled_table(data)
        return [heading, Spacer(1, _SPACER_HEIGHT), table]

    def _build_kpi_section(
        self,
        styles: Any,
        kpi_metrics: dict[str, float],
    ) -> list[Any]:
        """Build the KPI summary table."""
        heading = Paragraph("KPI Summary", styles["Heading2"])
        data = [["Metric", "Value"]]
        for metric, value in kpi_metrics.items():
            data.append([str(metric), self._format_value(value)])
        table = self._styled_table(data)
        return [heading, Spacer(1, _SPACER_HEIGHT), table]

    def _build_distribution_section(
        self,
        styles: Any,
        distribution: dict[str, int],
    ) -> list[Any]:
        """Build the distribution table (depth -> count)."""
        heading = Paragraph("Success Depth Distribution", styles["Heading2"])
        data = [["Depth", "Count"]]
        for depth, count in sorted(distribution.items(), key=lambda x: int(x[0])):
            data.append([str(depth), f"{count:,}"])
        table = self._styled_table(data)
        return [heading, Spacer(1, _SPACER_HEIGHT), table]

    def _build_segments_section(
        self,
        styles: Any,
        segments: dict[str, dict[str, float]],
    ) -> list[Any]:
        """Build the segment comparison table."""
        heading = Paragraph("Segment Comparison", styles["Heading2"])

        # Collect all metric names across segments
        all_metrics: list[str] = []
        for seg_data in segments.values():
            for metric in seg_data:
                if metric not in all_metrics:
                    all_metrics.append(metric)

        segment_names = list(segments.keys())
        header_row = ["Metric"] + [
            name.replace("_", " ").replace("-", " ").title() for name in segment_names
        ]
        data = [header_row]
        for metric in all_metrics:
            row = [metric]
            for seg_name in segment_names:
                val = segments[seg_name].get(metric, 0.0)
                row.append(self._format_value(val))
            data.append(row)

        table = self._styled_table(data)
        return [heading, Spacer(1, _SPACER_HEIGHT), table]

    def _build_insights_section(
        self,
        styles: Any,
        insights: list[dict[str, Any]],
    ) -> list[Any]:
        """Build the AI insights as bullet points with severity."""
        heading = Paragraph("AI Insights", styles["Heading2"])
        elements: list[Any] = [heading, Spacer(1, _SPACER_HEIGHT)]

        bullet_style = ParagraphStyle(
            "InsightBullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=10,
            spaceAfter=3 * mm,
        )

        for insight in insights:
            title = insight.get("title", "")
            description = insight.get("description", "")
            severity = insight.get("severity", "info")
            color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["info"])
            hex_color = color.hexval() if hasattr(color, "hexval") else "#3498DB"

            text = (
                f'<font color="{hex_color}"><b>[{severity.upper()}]</b></font> '
                f"<b>{title}</b> — {description}"
            )
            elements.append(Paragraph(text, bullet_style))

        return elements

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a value for display in the PDF."""
        if isinstance(value, float):
            if value == int(value) and abs(value) < 1e15:
                return f"{int(value):,}"
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, (list, tuple)):
            return ", ".join(str(v) for v in value)
        return str(value)

    @staticmethod
    def _styled_table(data: list[list[str]]) -> Table:
        """Create a Table with alternating row colors and clean styling."""
        page_width = A4[0] - 2 * _PAGE_MARGIN
        col_count = len(data[0]) if data else 1
        col_widths = [page_width / col_count] * col_count

        table = Table(data, colWidths=col_widths, repeatRows=1)

        style_commands: list[Any] = [
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_FG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            # Body rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.5, _GRID_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]

        # Alternating row backgrounds for body rows
        for row_idx in range(1, len(data)):
            if row_idx % 2 == 0:
                style_commands.append(
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), _ALT_ROW_BG)
                )

        table.setStyle(TableStyle(style_commands))
        return table
