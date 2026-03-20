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
_INVALID_CSV = _TEST_DATA / "invalid.csv"

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


def _open_sidebar(page: Page) -> None:
    """Open the sidebar if it is collapsed."""
    btn = page.locator("[data-testid='stSidebarCollapsedControl']").first
    if btn.is_visible():
        btn.click()
        page.wait_for_timeout(1000)


# ---------------------------------------------------------------------------
# 1. Page Load (6 tests)
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

    def test_empty_state_message(self, page: Page) -> None:
        expect(page.locator("text=No simulation results yet")).to_be_visible()

    def test_seed_input_visible(self, page: Page) -> None:
        seed = page.locator("[data-testid='stNumberInput']").first
        expect(seed).to_be_visible()


# ---------------------------------------------------------------------------
# 2. Upload & Configure (6 tests)
# ---------------------------------------------------------------------------


class TestUploadAndConfigure:

    def test_upload_player_csv(self, page: Page) -> None:
        inputs = page.locator("input[type='file']")
        inputs.first.set_input_files(str(_INPUT_CSV))
        page.locator("[data-testid='stAlert']").first.wait_for(timeout=10000)

    def test_upload_both_shows_ready(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)

    def test_upload_both_enables_run(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)
        run_btn = page.locator("button:has-text('Run Simulation')")
        expect(run_btn).to_be_enabled()

    def test_upload_invalid_csv_shows_error(self, page: Page) -> None:
        inputs = page.locator("input[type='file']")
        inputs.first.set_input_files(str(_INVALID_CSV))
        page.wait_for_timeout(3000)
        # Should show validation error for missing columns
        error = page.locator("[data-testid='stAlert']").first
        error.wait_for(timeout=10000)
        expect(error).to_be_visible()

    def test_upload_only_player_warns(self, page: Page) -> None:
        inputs = page.locator("input[type='file']")
        inputs.first.set_input_files(str(_INPUT_CSV))
        page.wait_for_timeout(3000)
        expect(page.locator("text=Upload config to continue")).to_be_visible()

    def test_upload_only_config_warns(self, page: Page) -> None:
        inputs = page.locator("input[type='file']")
        inputs.nth(1).set_input_files(str(_CONFIG_CSV))
        page.wait_for_timeout(3000)
        expect(page.locator("text=Upload player data to continue")).to_be_visible()


# ---------------------------------------------------------------------------
# 3. Config Editor (3 tests)
# ---------------------------------------------------------------------------


class TestConfigEditor:

    def test_config_editor_appears_after_upload(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)
        # Config editor expander should be present
        expect(page.locator("text=Edit Config...")).to_be_visible()

    def test_config_editor_opens(self, page: Page) -> None:
        _upload_both(page)
        page.locator("text=Ready to simulate").wait_for(timeout=15000)
        page.locator("text=Edit Config...").click()
        page.wait_for_timeout(1000)
        # Should show number inputs for config params
        number_inputs = page.locator("[data-testid='stNumberInput']")
        assert number_inputs.count() >= 2  # At least max_successes + point values

    def test_config_change_warning_after_run(self, page: Page) -> None:
        _run_simulation(page)
        # Open config editor
        page.locator("text=Edit Config...").click()
        page.wait_for_timeout(1000)
        # Change a number input value
        number_inputs = page.locator(
            "[data-testid='stNumberInput'] input[type='number']"
        )
        if number_inputs.count() > 0:
            number_inputs.first.fill("999")
            number_inputs.first.press("Enter")
            page.wait_for_timeout(2000)
            # Should show stale config warning
            expect(
                page.locator("text=Config changed since last run")
            ).to_be_visible()


# ---------------------------------------------------------------------------
# 4. Run Simulation (7 tests)
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

    def test_run_shows_churn_analysis_tab(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_role("tab", name="Churn Analysis")).to_be_visible()

    def test_run_shows_data_table_tab(self, page: Page) -> None:
        _run_simulation(page)
        expect(page.get_by_role("tab", name="Data Table")).to_be_visible()


# ---------------------------------------------------------------------------
# 5. Results Tabs (6 tests)
# ---------------------------------------------------------------------------


class TestResultsTabs:

    def test_charts_tab_shows_distribution(self, page: Page) -> None:
        _run_simulation(page)
        charts_tab = page.get_by_role("tab", name="Charts")
        charts_tab.click()
        page.wait_for_timeout(1000)
        # Charts should render via Altair / Vega
        charts = page.locator("[data-testid='stVegaLiteChart']")
        assert charts.count() >= 1

    def test_charts_tab_shows_captions(self, page: Page) -> None:
        _run_simulation(page)
        charts_tab = page.get_by_role("tab", name="Charts")
        charts_tab.click()
        page.wait_for_timeout(1000)
        # Should show chart explanation captions
        expect(page.locator("text=X-axis:").first).to_be_visible()

    def test_churn_tab_shows_two_columns(self, page: Page) -> None:
        _run_simulation(page)
        churn_tab = page.get_by_role("tab", name="Churn Analysis")
        churn_tab.click()
        page.wait_for_timeout(1000)
        expect(page.locator("text=About-to-Churn Players")).to_be_visible()
        expect(page.locator("text=Non-Churn Players")).to_be_visible()

    def test_churn_tab_shows_segment_metrics(self, page: Page) -> None:
        _run_simulation(page)
        churn_tab = page.get_by_role("tab", name="Churn Analysis")
        churn_tab.click()
        page.wait_for_timeout(1000)
        # Should show Player Count metric for each segment
        expect(page.locator("text=Player Count").first).to_be_visible()

    def test_data_table_tab_shows_dataframe(self, page: Page) -> None:
        _run_simulation(page)
        data_tab = page.get_by_role("tab", name="Data Table")
        data_tab.click()
        page.wait_for_timeout(1000)
        # Should show a dataframe
        df = page.locator("[data-testid='stDataFrame']")
        expect(df.first).to_be_visible()

    def test_data_table_tab_has_download_button(self, page: Page) -> None:
        _run_simulation(page)
        data_tab = page.get_by_role("tab", name="Data Table")
        data_tab.click()
        page.wait_for_timeout(1000)
        expect(page.locator("button:has-text('Download Results CSV')")).to_be_visible()


# ---------------------------------------------------------------------------
# 6. AI Features UI (6 tests)
# ---------------------------------------------------------------------------


class TestAIFeaturesUI:

    def test_insights_tab_has_generate_button(self, page: Page) -> None:
        _run_simulation(page)
        insights_tab = page.get_by_role("tab", name="Insights")
        insights_tab.click()
        page.wait_for_timeout(1000)
        btn = page.locator("button:has-text('Generate Insights')")
        expect(btn).to_be_visible()

    def test_insights_tab_has_severity_explanation(self, page: Page) -> None:
        _run_simulation(page)
        insights_tab = page.get_by_role("tab", name="Insights")
        insights_tab.click()
        page.wait_for_timeout(1000)
        expect(page.locator("text=INFO")).to_be_visible()

    def test_chat_tab_has_input(self, page: Page) -> None:
        _run_simulation(page)
        chat_tab = page.get_by_role("tab", name="Ask a Question")
        chat_tab.click()
        page.wait_for_timeout(1000)
        # Chat should have a text input
        chat_input = page.locator("[data-testid='stChatInput'] textarea")
        expect(chat_input).to_be_visible()

    def test_optimizer_tab_has_controls(self, page: Page) -> None:
        _run_simulation(page)
        opt_tab = page.get_by_role("tab", name="Optimizer")
        opt_tab.click()
        page.wait_for_timeout(1000)
        expect(page.locator("text=Target metric")).to_be_visible()
        expect(page.locator("text=Direction")).to_be_visible()
        expect(page.locator("button:has-text('Run Optimizer')")).to_be_visible()

    def test_optimizer_tab_has_metric_options(self, page: Page) -> None:
        _run_simulation(page)
        opt_tab = page.get_by_role("tab", name="Optimizer")
        opt_tab.click()
        page.wait_for_timeout(1000)
        # The target metric selectbox should have options
        expect(page.locator("text=pct_above_threshold")).to_be_visible()

    def test_ai_section_has_explanation_caption(self, page: Page) -> None:
        _run_simulation(page)
        expect(
            page.locator("text=AI-powered analysis of your simulation results")
        ).to_be_visible()


# ---------------------------------------------------------------------------
# 7. History (5 tests)
# ---------------------------------------------------------------------------


class TestHistory:

    def test_sidebar_shows_history(self, page: Page) -> None:
        _open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        expect(sidebar.locator("text=History")).to_be_visible()

    def test_load_restores_results(self, page: Page) -> None:
        _open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        load_btns = sidebar.locator("button:has-text('Load')")
        if load_btns.count() == 0:
            pytest.skip("No history runs")
        load_btns.first.scroll_into_view_if_needed()
        load_btns.first.click()
        page.wait_for_timeout(3000)
        # KPIs should render from loaded data
        metrics = page.locator("[data-testid='stMetric']")
        assert metrics.count() >= 3

    def test_load_hides_empty_state(self, page: Page) -> None:
        _open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        load_btns = sidebar.locator("button:has-text('Load')")
        if load_btns.count() == 0:
            pytest.skip("No history runs")
        load_btns.first.scroll_into_view_if_needed()
        load_btns.first.click()
        page.wait_for_timeout(3000)
        # "No simulation results" should NOT be visible
        expect(page.locator("text=No simulation results yet")).not_to_be_visible()

    def test_delete_button_exists(self, page: Page) -> None:
        _open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        delete_btns = sidebar.locator("button:has-text('Delete')")
        if delete_btns.count() == 0:
            pytest.skip("No history runs")
        expect(delete_btns.first).to_be_visible()

    def test_compare_section_exists(self, page: Page) -> None:
        _open_sidebar(page)
        sidebar = page.locator("[data-testid='stSidebar']")
        expect(sidebar.locator("text=Compare Runs")).to_be_visible()


# ---------------------------------------------------------------------------
# 8. Tooltips & Info Icons (4 tests)
# ---------------------------------------------------------------------------


class TestTooltips:

    def test_kpi_metrics_have_help_icons(self, page: Page) -> None:
        _run_simulation(page)
        # Streamlit renders help as a tooltip div inside each metric
        help_icons = page.locator(
            "[data-testid='stMetric'] [data-testid='stTooltipIcon']"
        )
        assert help_icons.count() >= 4

    def test_seed_input_has_help(self, page: Page) -> None:
        # Seed input should have a help tooltip
        help_icon = page.locator(
            "[data-testid='stNumberInput'] [data-testid='stTooltipIcon']"
        )
        expect(help_icon.first).to_be_visible()

    def test_churn_metrics_have_help(self, page: Page) -> None:
        _run_simulation(page)
        churn_tab = page.get_by_role("tab", name="Churn Analysis")
        churn_tab.click()
        page.wait_for_timeout(1000)
        help_icons = page.locator(
            "[data-testid='stMetric'] [data-testid='stTooltipIcon']"
        )
        # KPI metrics (4) + churn segment metrics (at least 4 per segment)
        assert help_icons.count() >= 8

    def test_optimizer_inputs_have_help(self, page: Page) -> None:
        _run_simulation(page)
        opt_tab = page.get_by_role("tab", name="Optimizer")
        opt_tab.click()
        page.wait_for_timeout(1000)
        help_icons = page.locator("[data-testid='stTooltipIcon']")
        # At least target metric, target value, direction, max iterations
        assert help_icons.count() >= 4
