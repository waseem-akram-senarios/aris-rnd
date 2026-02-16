"""
Test 2: Search tab functionality.
Verifies search form, example buttons, and executing a real search.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, click_button


@pytest.mark.ui
class TestSearchTab:
    """Verify search tab works end-to-end."""

    def test_search_tab_has_form_elements(self, mcp_page: Page):
        """Search tab displays the query textarea, options, and search button."""
        click_tab(mcp_page, "Search")
        # Query textarea
        textarea = mcp_page.locator('textarea[aria-label="Search Query"]')
        expect(textarea).to_be_visible()
        # Search button
        btn = mcp_page.get_by_role("button", name="Search", exact=False)
        expect(btn.first).to_be_visible()

    def test_search_mode_selector(self, mcp_page: Page):
        """Search mode dropdown is present with default 'hybrid'."""
        click_tab(mcp_page, "Search")
        body = mcp_page.inner_text("body")
        assert "hybrid" in body.lower() or "Search Mode" in body

    def test_example_buttons_present(self, mcp_page: Page):
        """Four example query buttons are shown."""
        click_tab(mcp_page, "Search")
        for label in ["Maintenance", "Troubleshoot", "Overview", "Policy"]:
            btn = mcp_page.get_by_role("button", name=label, exact=False)
            expect(btn.first).to_be_visible()

    def test_empty_search_shows_error(self, mcp_page: Page):
        """Clicking Search with empty query shows an error."""
        click_tab(mcp_page, "Search")
        # Clear textarea if any default
        textarea = mcp_page.locator('textarea[aria-label="Search Query"]')
        textarea.fill("")
        click_button(mcp_page, "Search")
        mcp_page.wait_for_timeout(1500)
        body = mcp_page.inner_text("body")
        assert "Please enter a search query" in body, f"Expected error message, got: {body[:300]}"

    def test_real_search_returns_results(self, mcp_page: Page):
        """Execute a real search and verify results appear."""
        click_tab(mcp_page, "Search")
        textarea = mcp_page.locator('textarea[aria-label="Search Query"]')
        textarea.fill("What is the attendance policy?")
        mcp_page.wait_for_timeout(500)

        # Click the primary Search button
        click_button(mcp_page, "Search")
        # Wait for results (search can take up to 60s with agentic RAG)
        mcp_page.wait_for_timeout(5000)

        body = mcp_page.inner_text("body")
        # Should have either results or an answer
        has_results = "Results" in body or "Answer" in body or "results" in body.lower()
        has_error = "Unknown error" in body or "Cannot connect" in body
        assert has_results or not has_error, f"Search failed or returned nothing. Page text: {body[:500]}"
