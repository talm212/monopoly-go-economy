"""Playwright E2E tests for the Coin Flip Economy Simulator.

Run with: poetry run pytest tests/e2e/ -v -m e2e
Regular tests exclude E2E by default (addopts = -m 'not e2e').
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_TEST_DATA = Path(__file__).parent / "test_data"
_INPUT_CSV = _TEST_DATA / "players_small.csv"  # 5 rows — fast upload
_CONFIG_CSV = _TEST_DATA / "config.csv"

pytestmark = pytest.mark.e2e


def _upload_both(page: Page) -> None:
    """Upload both CSVs and wait for Streamlit to process."""
    inputs = page.locator("input[type='file']")
    inputs.first.set_input_files(str(_INPUT_CSV))
    page.wait_for_timeout(3000)
    inputs.nth(1).set_input_files(str(_CONFIG_CSV))
    page.wait_for_timeout(3000)


def _run_simulation(page: Page) -> None:
    """Upload both CSVs, wait for Ready, click Run, wait for results."""
    _upload_both(page)
    # Wait for Ready status
    page.locator("text=Ready to simulate").wait_for(timeout=15000)
    # Click Run
    run_btn = page.locator("button:has-text('Run Simulation')")
    run_btn.scroll_into_view_if_needed()
    run_btn.click()
    # Wait for completion — look for success message or KPIs
    page.locator("[data-testid='stMetric']").first.wait_for(timeout=30000)
    page.wait_for_timeout(1000)


# ---------------------------------------------------------------------------
# Page Load
# ---------------------------------------------------------------------------


class TestPageLoad:

    def test_title_visible(self, page: Page) -> None:
        expect(page.locator("text=Coin Flip Economy Simulator")).to_be_visible()

    def test_setup_section_visible(self, page: Page) -> None:
        expect(page.locator("text=Setup")).to_be_visible()

    def test_two_file_uploaders(self, page: Page) -> None:
        uploaders = page.locator("[data-testid='stFileUploader']")
        expect(uploaders).to_have_count(2)

    def test_run_button_disabled(self, page: Page) -> None:
        run_btn = page.locator("button:has-text('Run Simulation')")
        expect(run_btn).to_be_disabled()


# ---------------------------------------------------------------------------
# Upload & Configure
# ---------------------------------------------------------------------------


class TestUploadAndConfigure:

    def test_upload_player_csv(self, page: Page) -> None:
        inputs = page.locator("input[type='file']")
        inputs.first.set_input_files(str(_INPUT_CSV))
        # Should show success or player count
        page.locator("[data-testid='stAlert']").first.wait_for(timeout=10000)

    def test_upload_both_shows_ready(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)

    def test_upload_both_enables_run(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)
        run_btn = page.locator("button:has-text('Run Simulation')")
        expect(run_btn).to_be_enabled()


# ---------------------------------------------------------------------------
# Run Simulation
# ---------------------------------------------------------------------------


class TestRunSimulation:

    def test_run_shows_kpi_metrics(self, page: Page) -> None:
        _run_simulation(page)
        metrics = page.locator("[data-testid='stMetric']")
        assert metrics.count() >= 4

    def test_run_shows_results_section(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_text("Results", exact=True)).to_be_visible()

    def test_run_shows_charts_tab(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_role("tab", name="Charts")).to_be_visible()

    def test_run_shows_ai_section(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_text("AI Analysis", exact=True)).to_be_visible()

    def test_run_shows_all_three_ai_tabs(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_role("tab", name="Insights")).to_be_visible()
        expect(page.get_by_role("tab", name="Ask a Question")).to_be_visible()
        expect(page.get_by_role("tab", name="Optimizer")).to_be_visible()


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestHistory:

    def _open_sidebar(self, page: Page) -> None:
        btn = page.locator("[data-testid='stSidebarCollapsedControl']").first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(1000)

    def test_sidebar_shows_history(self, page: Page) -> None:
        self._open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        expect(sidebar.locator("text=History")).to_be_visible()

    def test_load_restores_results(self, page: Page) -> None:
        self._open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        load_btns = sidebar.locator("button:has-text('Load')")
        if load_btns.count() == 0:
            pytest.skip("No history runs")
        load_btns.first.evaluate("el => el.click()")
        page.wait_for_timeout(3000)
        # KPIs should render from loaded data
        metrics = page.locator("[data-testid='stMetric']")
        assert metrics.count() >= 3
