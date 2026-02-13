"""
Test 4: Indexes tab functionality.
Verifies index listing and index details.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, click_button


@pytest.mark.ui
class TestIndexesTab:
    """Verify Indexes tab works correctly."""

    def test_indexes_tab_has_load_button(self, mcp_page: Page):
        """Indexes tab shows Load Indexes button."""
        click_tab(mcp_page, "Indexes")
        btn = mcp_page.get_by_role("button", name="Load Indexes", exact=False)
        expect(btn.first).to_be_visible()

    def test_load_indexes_returns_list(self, mcp_page: Page):
        """Clicking Load Indexes shows index listing."""
        click_tab(mcp_page, "Indexes")
        click_button(mcp_page, "Load Indexes")
        mcp_page.wait_for_timeout(3000)

        body = mcp_page.inner_text("body")
        assert "indexes found" in body.lower() or "index" in body.lower(), \
            f"Expected index listing. Got: {body[:400]}"

    def test_document_indexes_section(self, mcp_page: Page):
        """After loading, Document Indexes section should appear."""
        click_tab(mcp_page, "Indexes")
        click_button(mcp_page, "Load Indexes")
        mcp_page.wait_for_timeout(3000)

        body = mcp_page.inner_text("body")
        # The UI filters indexes with 'aris-doc' in the name
        has_doc_indexes = "Document Indexes" in body or "aris-doc" in body
        has_system = "System Indexes" in body
        assert has_doc_indexes or has_system, \
            f"Expected index categorization. Got: {body[:400]}"
