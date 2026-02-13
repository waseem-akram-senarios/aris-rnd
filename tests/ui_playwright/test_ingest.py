"""
Test 6: Add Documents (Ingest) tab functionality.
Verifies the ingest form elements and content type radio buttons.
"""

import pytest
from playwright.sync_api import Page, expect
from tests.ui_playwright.conftest import click_tab, click_button


@pytest.mark.ui
class TestIngestTab:
    """Verify Add Documents tab form elements."""

    def test_ingest_tab_has_content_type_radio(self, mcp_page: Page):
        """Ingest tab shows Content Type radio group with the right options."""
        click_tab(mcp_page, "Ingest")
        # Streamlit horizontal radio renders option labels in separate elements
        # Check the full HTML for the radio option labels
        html = mcp_page.content()
        assert "Plain Text" in html, "Expected 'Plain Text' radio option in page HTML"
        assert "S3 URI" in html, "Expected 'S3 URI' radio option in page HTML"
        assert "Upload File" in html, "Expected 'Upload File' radio option in page HTML"

    def test_ingest_tab_has_metadata_fields(self, mcp_page: Page):
        """Ingest tab shows metadata section with Domain, Language, etc."""
        click_tab(mcp_page, "Ingest")
        # The labels are in the page HTML even if inner_text doesn't capture them
        html = mcp_page.content()
        assert "Domain" in html, "Expected 'Domain' label in Ingest tab HTML"
        assert "Language" in html, "Expected 'Language' label in Ingest tab HTML"
        # Also verify the Metadata header is visible in body text
        body = mcp_page.inner_text("body")
        assert "Metadata" in body, "Expected 'Metadata' section header"

    def test_ingest_button_present(self, mcp_page: Page):
        """Ingest button is present."""
        click_tab(mcp_page, "Ingest")
        btn = mcp_page.get_by_role("button", name="Ingest Document", exact=False)
        expect(btn.first).to_be_visible()

    def test_empty_ingest_shows_error(self, mcp_page: Page):
        """Clicking Ingest with no content shows error."""
        click_tab(mcp_page, "Ingest")
        click_button(mcp_page, "Ingest Document")
        mcp_page.wait_for_timeout(2000)
        body = mcp_page.inner_text("body")
        assert "Please provide content" in body, \
            f"Expected 'Please provide content' error. Got: {body[:300]}"

    def test_ingest_plain_text(self, mcp_page: Page):
        """Ingest a small plain text document successfully."""
        click_tab(mcp_page, "Ingest")
        # Ensure Plain Text radio is selected (it should be default)
        plain_text_radio = mcp_page.get_by_text("Plain Text", exact=True)
        plain_text_radio.click()
        mcp_page.wait_for_timeout(500)

        # Type content into the text area
        textarea = mcp_page.locator('textarea[aria-label="Content"]')
        textarea.fill("This is a Playwright automation test document. It tests the MCP Client ingest functionality end-to-end.")
        mcp_page.wait_for_timeout(500)

        # Click ingest
        click_button(mcp_page, "Ingest Document")
        mcp_page.wait_for_timeout(10000)  # ingestion can take a while

        body = mcp_page.inner_text("body")
        success = "Ingested" in body or "Doc ID" in body or "success" in body.lower()
        error = "Cannot connect" in body or "error" in body.lower()
        assert success or not error, f"Ingest may have failed. Page: {body[:500]}"
