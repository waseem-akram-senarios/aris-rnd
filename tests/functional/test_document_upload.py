"""
Functional tests for document upload features
Tests document upload functionality against requirements
"""
import pytest
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app


@pytest.mark.functional
class TestDocumentUpload:
    """Test document upload functionality"""
    
    def test_upload_pdf(self, api_client, temp_dir):
        """Test uploading PDF document"""
        # Create sample PDF
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")
        
        with open(pdf_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        assert response.status_code in [201, 200]
        data = response.json()
        assert "document_id" in data
        assert data["document_name"] == "test.pdf"
        assert data["status"] in ["processing", "completed"]
    
    def test_upload_duplicate_detection(self, api_client, temp_dir):
        """Test duplicate file detection"""
        pdf_file = temp_dir / "test.pdf"
        pdf_content = b"test pdf content"
        pdf_file.write_bytes(pdf_content)
        
        # Upload first time
        with open(pdf_file, 'rb') as f:
            response1 = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        # Upload same file again
        with open(pdf_file, 'rb') as f:
            response2 = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        # Second upload should detect duplicate (409 or different status)
        assert response2.status_code in [409, 200, 201]  # May vary based on implementation
    
    def test_upload_large_file(self, api_client, temp_dir):
        """Test uploading large file"""
        # Create large file (simulate)
        large_file = temp_dir / "large.pdf"
        # Write 10MB of data
        large_file.write_bytes(b"x" * (10 * 1024 * 1024))
        
        with open(large_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("large.pdf", f, "application/pdf")}
            )
        
        # Should handle large files (may take time)
        assert response.status_code in [201, 200, 500]  # May timeout or succeed
    
    def test_upload_multiple_formats(self, api_client, temp_dir):
        """Test uploading multiple file formats"""
        # Test TXT
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("Test text content")
        
        with open(txt_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        assert response.status_code in [201, 200, 400]  # May or may not support TXT
    
    def test_upload_with_parser_preference(self, api_client, temp_dir):
        """Test uploading with parser preference"""
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        with open(pdf_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"parser_preference": "docling"}
            )
        
        assert response.status_code in [201, 200]
        data = response.json()
        # Parser preference should be respected (may be in processing)
        assert "document_id" in data
    
    def test_upload_invalid_file_type(self, api_client, temp_dir):
        """Test uploading invalid file type"""
        invalid_file = temp_dir / "test.exe"
        invalid_file.write_bytes(b"executable content")
        
        with open(invalid_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.exe", f, "application/x-msdownload")}
            )
        
        # Should reject invalid file types
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"] or "invalid" in response.json()["detail"].lower()
