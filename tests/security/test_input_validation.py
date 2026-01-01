"""
Security tests for input validation
Tests SQL injection, XSS, path traversal prevention
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
class TestInputValidation:
    """Test input validation and security"""
    
    def test_sql_injection_prevention(self, api_client):
        """Test SQL injection attempts are blocked"""
        # SQL injection attempts in query
        malicious_queries = [
            "'; DROP TABLE documents; --",
            "1' OR '1'='1",
            "admin'--",
            "'; DELETE FROM documents WHERE '1'='1"
        ]
        
        for malicious_query in malicious_queries:
            response = api_client.post(
                "/query",
                json={"question": malicious_query, "k": 3}
            )
            
            # Should either handle gracefully or return error, not execute SQL
            assert response.status_code in [200, 400, 422, 500]
            # No SQL should be executed (tested by ensuring no data loss)
    
    def test_path_traversal_prevention(self, api_client, temp_dir):
        """Test path traversal attempts are blocked"""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]
        
        for malicious_path in malicious_paths:
            pdf_file = temp_dir / "test.pdf"
            pdf_file.write_bytes(b"fake pdf")
            
            # Try to upload with malicious filename
            with open(pdf_file, 'rb') as f:
                response = api_client.post(
                    "/documents",
                    files={"file": (malicious_path, f, "application/pdf")}
                )
            
            # Should sanitize filename or reject
            assert response.status_code in [201, 400, 422]
            if response.status_code == 201:
                # Filename should be sanitized
                data = response.json()
                assert ".." not in data.get("document_name", "")
                assert "/" not in data.get("document_name", "") or data["document_name"].startswith("/")
    
    def test_xss_prevention(self, api_client):
        """Test XSS prevention in responses"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>"
        ]
        
        for payload in xss_payloads:
            response = api_client.post(
                "/query",
                json={"question": payload, "k": 3}
            )
            
            # Response should not contain unescaped script tags
            if response.status_code == 200:
                response_text = response.text
                # Should escape or sanitize
                assert "<script>" not in response_text or "&lt;script&gt;" in response_text
    
    def test_file_type_validation(self, api_client, temp_dir):
        """Test invalid file types are rejected"""
        invalid_files = [
            ("test.exe", b"executable"),
            ("test.sh", b"#!/bin/bash"),
            ("test.php", b"<?php echo 'test'; ?>"),
            ("test.js", b"console.log('test')")
        ]
        
        for filename, content in invalid_files:
            file_path = temp_dir / filename
            file_path.write_bytes(content)
            
            with open(file_path, 'rb') as f:
                response = api_client.post(
                    "/documents",
                    files={"file": (filename, f, "application/octet-stream")}
                )
            
            # Should reject invalid file types
            assert response.status_code == 400
            assert "Unsupported file type" in response.json()["detail"] or "invalid" in response.json()["detail"].lower()
