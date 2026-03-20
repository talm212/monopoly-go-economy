"""Playwright E2E test fixtures — starts Streamlit server for browser testing."""

from __future__ import annotations

import subprocess
import time
from typing import Generator

import pytest
import urllib.request
from playwright.sync_api import Page, sync_playwright

_STREAMLIT_PORT = 8599  # Use non-default port to avoid conflicts
_STREAMLIT_URL = f"http://localhost:{_STREAMLIT_PORT}"
_STARTUP_TIMEOUT = 30  # seconds


def _wait_for_server(url: str, timeout: int = _STARTUP_TIMEOUT) -> bool:
    """Poll the server until it responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/_stcore/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def streamlit_server() -> Generator[str, None, None]:
    """Start a Streamlit server for the test session, yield the URL, then stop."""
    proc = subprocess.Popen(
        [
            "poetry", "run", "streamlit", "run", "src/ui/app.py",
            "--server.port", str(_STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not _wait_for_server(_STREAMLIT_URL):
        proc.terminate()
        raise RuntimeError(
            f"Streamlit server failed to start within {_STARTUP_TIMEOUT}s"
        )

    yield _STREAMLIT_URL

    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser_context(streamlit_server: str):
    """Create a Playwright browser context for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context, streamlit_server: str) -> Generator[Page, None, None]:
    """Create a fresh page for each test, navigated to the Streamlit app."""
    pg = browser_context.new_page()
    pg.goto(streamlit_server, wait_until="networkidle")
    # Wait for Streamlit to fully render
    pg.wait_for_selector("[data-testid='stAppViewContainer']", timeout=10000)
    yield pg
    pg.close()
