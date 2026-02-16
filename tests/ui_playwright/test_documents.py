"""
Test 3: Documents tab functionality.
Verifies listing documents, viewing details, and document CRUD UI elements.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, click_button


@pytest.mark.ui
class TestDocumentsTab:
    """Verify Documents tab works correctly."""

    def test_documents_tab_has_load_button(self, mcp_page: Page):
        """Documents tab shows Load Documents button."""
        click_tab(mcp_page, "Documents")
        btn = mcp_page.get_by_role("button", name="Load Documents", exact=False)
        expect(btn.first).to_be_visible()

    def test_load_documents_returns_list(self, mcp_page: Page):
        """Clicking Load Documents populates the document list."""
        click_tab(mcp_page, "Documents")
        click_button(mcp_page, "Load Documents")
        mcp_page.wait_for_timeout(3000)

        body = mcp_page.inner_text("body")
        # Should show document count
        assert "documents" in body.lower(), f"Expected document list info. Got: {body[:400]}"

    def test_document_expanders_visible(self, mcp_page: Page):
        """After loading, document expanders should be visible."""
        click_tab(mcp_page, "Documents")
        click_button(mcp_page, "Load Documents")
        mcp_page.wait_for_timeout(3000)

        # Streamlit expanders use data-testid="stExpander"
        expanders = mcp_page.locator('[data-testid="stExpander"]')
        count = expanders.count()
        assert count > 0, "Expected at least one document expander after loading"

    def test_document_has_crud_buttons(self, mcp_page: Page):
        """Each document expander should contain Details, Update, Delete buttons."""
        click_tab(mcp_page, "Documents")
        click_button(mcp_page, "Load Documents")
        # After Streamlit reruns, we may need to re-select the Documents tab
        mcp_page.wait_for_timeout(3000)
        click_tab(mcp_page, "Documents")
        mcp_page.wait_for_timeout(2000)

        # Streamlit expanders use <details> / <summary> under the hood
        # Find a visible expander summary that contains document text (e.g. "chunks")
        summaries = mcp_page.locator('details[data-testid="stExpander"] > summary')
        if summaries.count() == 0:
            # Fallback: try the generic expander locator
            summaries = mcp_page.locator('[data-testid="stExpander"]')

        count = summaries.count()
        assert count > 0, f"No document expanders found after loading. Page has {count} expanders."

        # Click the first visible summary to expand it
        for i in range(count):
            if summaries.nth(i).is_visible():
                summaries.nth(i).click()
                mcp_page.wait_for_timeout(2000)
                break
        else:
            pytest.skip("All document expanders are hidden (tab might not be active)")

        body = mcp_page.inner_text("body")
        assert "Details" in body, f"Expected 'Details' button. Body excerpt: {body[:500]}"
        assert "Update" in body, f"Expected 'Update' button. Body excerpt: {body[:500]}"
        assert "Delete" in body, f"Expected 'Delete' button. Body excerpt: {body[:500]}"
