"""
Playwright fixtures for ARIS MCP Client UI testing.

Target: http://44.221.84.58/MCP_Client  (Streamlit app)
"""

import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("MCP_UI_URL", "http://44.221.84.58")
MCP_PAGE = f"{BASE_URL}/MCP_Client"

# Streamlit takes time to render; generous but realistic timeouts
LOAD_TIMEOUT = 30_000   # initial page load
ACTION_TIMEOUT = 60_000  # after clicking a button that hits an API


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Override default context args for all tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "ignore_https_errors": True,
    }


@pytest.fixture()
def mcp_page(page: Page) -> Page:
    """Navigate to MCP Client page and wait until Streamlit finishes loading."""
    page.goto(MCP_PAGE, wait_until="networkidle", timeout=LOAD_TIMEOUT)
    # Streamlit renders inside iframes; wait for the main app container
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=LOAD_TIMEOUT)
    # Give extra time for Streamlit widgets to hydrate
    page.wait_for_timeout(2000)
    return page


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TAB_LABELS = {
    "Search":    "🔍 Search",
    "Ingest":    "📥 Add Documents",
    "Documents": "📄 Documents",
    "Indexes":   "🗂️ Indexes",
    "Chunks":    "🧩 Chunks",
    "System":    "📊 System",
    "History":   "📜 History",
}


def click_tab(page: Page, short_label: str):
    """Click a Streamlit tab by its short label (e.g. 'Documents')."""
    full = TAB_LABELS.get(short_label, short_label)
    tab = page.get_by_role("tab", name=full, exact=True)
    tab.click()
    page.wait_for_timeout(500)


def click_button(page: Page, label: str, timeout: int = ACTION_TIMEOUT):
    """Click a Streamlit button and wait for network to settle."""
    btn = page.get_by_role("button", name=label, exact=False).first
    btn.scroll_into_view_if_needed()
    btn.click()
    # Wait for Streamlit to process (spinner appears/disappears)
    try:
        page.wait_for_selector('[data-testid="stSpinner"]', state="attached", timeout=3000)
        page.wait_for_selector('[data-testid="stSpinner"]', state="detached", timeout=timeout)
    except Exception:
        # Some buttons don't show a spinner; just wait a bit
        page.wait_for_timeout(2000)


def get_visible_text(page: Page) -> str:
    """Return all visible text on the page (for assertion debugging)."""
    return page.inner_text("body")
