"""
Test 1: MCP Client page loads correctly.
Verifies header, server connection status, all 7 tabs, and tool count.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, TAB_LABELS


@pytest.mark.ui
class TestPageLoad:
    """Verify the MCP Client page renders correctly."""

    def test_page_title(self, mcp_page: Page):
        """Page title contains MCP Client."""
        expect(mcp_page).to_have_title("MCP Client - ARIS RAG")

    def test_header_visible(self, mcp_page: Page):
        """Header shows MCP Client branding."""
        header = mcp_page.locator(".mcp-header")
        expect(header).to_be_visible()
        expect(header).to_contain_text("MCP Client")

    def test_server_connected(self, mcp_page: Page):
        """Status card shows server is connected with 4 tools."""
        # The connected status card has class 'connected'
        card = mcp_page.locator(".status-card.connected").first
        expect(card).to_be_visible()
        expect(card).to_contain_text("Connected")
        expect(card).to_contain_text("4 tools")

    def test_tool_categories_shown(self, mcp_page: Page):
        """Tool categories card lists all categories."""
        body_text = mcp_page.inner_text("body")
        assert "Query" in body_text
        assert "Documents" in body_text
        assert "Indexes" in body_text
        assert "System" in body_text

    def test_feature_badges(self, mcp_page: Page):
        """Feature badges are displayed."""
        badges = mcp_page.locator(".feature-badge")
        assert badges.count() >= 4, f"Expected at least 4 feature badges, got {badges.count()}"

    @pytest.mark.parametrize("tab_name", list(TAB_LABELS.keys()))
    def test_tab_exists_and_clickable(self, mcp_page: Page, tab_name: str):
        """Each tab exists and can be clicked."""
        click_tab(mcp_page, tab_name)
        # After clicking, the tab should be selected (aria-selected=true)
        full = TAB_LABELS[tab_name]
        tab = mcp_page.get_by_role("tab", name=full, exact=True)
        expect(tab).to_have_attribute("aria-selected", "true")

    def test_footer_visible(self, mcp_page: Page):
        """Footer with server URL is visible."""
        body_text = mcp_page.inner_text("body")
        assert "MCP Client for ARIS RAG System" in body_text
        assert "4 consolidated tools" in body_text
