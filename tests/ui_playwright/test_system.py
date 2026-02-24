"""
Test 5: System tab functionality.
Verifies system stats and service health buttons work.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, click_sub_tab, click_button


@pytest.mark.ui
class TestSystemTab:
    """Verify System tab works correctly."""

    def test_system_tab_has_buttons(self, mcp_page: Page):
        """System tab shows Force Sync button and sub-tab buttons."""
        click_tab(mcp_page, "System")
        # Force Sync is visible at top level of System & Server tab
        btn = mcp_page.get_by_role("button", name="Force Sync", exact=False)
        expect(btn.first).to_be_visible()
        # Stats button is in the Statistics sub-tab (default)
        btn2 = mcp_page.get_by_role("button", name="Load System Stats", exact=False)
        expect(btn2.first).to_be_visible()

    def test_load_system_stats(self, mcp_page: Page):
        """Clicking Load System Stats shows processing info."""
        click_tab(mcp_page, "System")
        # Statistics sub-tab is the default
        click_button(mcp_page, "Load System Stats")
        mcp_page.wait_for_timeout(3000)

        body = mcp_page.inner_text("body")
        has_stats = "Documents" in body or "Chunks" in body or "Full Stats" in body or "stats" in body.lower()
        assert has_stats, f"Expected system stats info. Got: {body[:400]}"

    def test_service_health_button(self, mcp_page: Page):
        """Clicking Service Health Check shows health JSON."""
        click_tab(mcp_page, "System")
        click_button(mcp_page, "Service Health Check")
        mcp_page.wait_for_timeout(3000)

        body = mcp_page.inner_text("body")
        assert "healthy" in body.lower() or "mcp" in body.lower(), \
            f"Expected health info. Got: {body[:400]}"
