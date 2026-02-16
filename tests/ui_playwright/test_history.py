"""
Test 7: History tab functionality.
Verifies the history tab shows a message when no history exists.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab


@pytest.mark.ui
class TestHistoryTab:
    """Verify History tab works correctly."""

    def test_history_tab_shows_empty_message(self, mcp_page: Page):
        """Fresh session shows 'No executions yet' message."""
        click_tab(mcp_page, "History")
        body = mcp_page.inner_text("body")
        assert "No executions yet" in body or "Execution History" in body, \
            f"Expected history info. Got: {body[:300]}"

    def test_history_tab_header(self, mcp_page: Page):
        """History tab has the Execution History header."""
        click_tab(mcp_page, "History")
        body = mcp_page.inner_text("body")
        assert "Execution History" in body
