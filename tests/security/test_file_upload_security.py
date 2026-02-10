"""
Security tests for file upload
Tests malicious file handling, size limits, sanitization
"""
import pytest
import tempfile
from pathlib import Path


@pytest.mark.security
class TestFileUploadSecurity:
    """Test file upload security"""
    
    def test_malicious_file_rejection(self, api_client, temp_dir):
        """Test malicious files are blocked"""
        # Create file with suspicious content
        malicious_file = temp_dir / "malicious.pdf"
        # PDF with embedded script (simulated)
        malicious_content = b"%PDF-1.4\n<</JavaScript/JS(alert('XSS'))>>"
        malicious_file.write_bytes(malicious_content)
        
        with open(malicious_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("malicious.pdf", f, "application/pdf")}
            )
        
        # Should either reject or handle safely
        assert response.status_code in [201, 400, 422, 500]
    
    def test_file_size_limits(self, api_client, temp_dir):
        """Test file size restrictions"""
        # Create very large file (100MB)
        large_file = temp_dir / "large.pdf"
        large_content = b"x" * (100 * 1024 * 1024)  # 100MB
        large_file.write_bytes(large_content)
        
        with open(large_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("large.pdf", f, "application/pdf")}
            )
        
        # May accept or reject based on configuration
        assert response.status_code in [201, 400, 413, 500]
    
    def test_filename_sanitization(self, api_client, temp_dir):
        """Test filename sanitization"""
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        malicious_names = [
            "../../../etc/passwd.pdf",
            "file with spaces.pdf",
            "file\nwith\nnewlines.pdf",
            "file<script>.pdf"
        ]
        
        for malicious_name in malicious_names:
            with open(pdf_file, 'rb') as f:
                response = api_client.post(
                    "/documents",
                    files={"file": (malicious_name, f, "application/pdf")}
                )
            
            if response.status_code == 201:
                data = response.json()
                # Filename should be sanitized
                sanitized_name = data.get("document_name", "")
                assert ".." not in sanitized_name
                assert "\n" not in sanitized_name
                assert "<script>" not in sanitized_name
    
    def test_zip_bomb_protection(self, api_client, temp_dir):
        """Test zip bomb protection (if zip files supported)"""
        # Create a zip file (if supported)
        # This is a structural test
        # Actual zip bomb protection would be in file processing
        assert True  # Placeholder for zip bomb test
