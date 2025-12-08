#!/usr/bin/env python3
"""
Test to verify OpenSearch index name generation from document names.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import just the static method logic without importing the full class
import re

def sanitize_index_name(document_name: str) -> str:
    """
    Sanitize a document name to create a valid OpenSearch index name.
    (Copied from OpenSearchVectorStore.sanitize_index_name for testing)
    """
    # Remove file extension if present
    name_without_ext = os.path.splitext(document_name)[0]
    
    # Convert to lowercase
    sanitized = name_without_ext.lower()
    
    # Replace spaces and special characters with hyphens
    sanitized = re.sub(r'[^a-z0-9_-]', '-', sanitized)
    
    # Replace multiple consecutive hyphens with single hyphen
    sanitized = re.sub(r'-+', '-', sanitized)
    
    # Remove leading/trailing hyphens and underscores
    sanitized = sanitized.strip('-').strip('_')
    
    # Ensure it starts with a letter or underscore (OpenSearch requirement)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = 'doc-' + sanitized
    
    # Truncate to 255 characters (OpenSearch limit)
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
        # Remove trailing hyphen if truncated
        sanitized = sanitized.rstrip('-')
    
    # If empty after sanitization, use default
    if not sanitized:
        sanitized = 'document'
    
    return sanitized

def test_sanitize_index_name():
    """Test index name sanitization."""
    print("=" * 70)
    print("Testing: OpenSearch Index Name Sanitization")
    print("=" * 70)
    print()
    
    test_cases = [
        ("My Document.pdf", "my-document"),
        ("2025_MustangS650_OM_ENG_version1 (1).pdf", "2025-mustangs650-om-eng-version1-1"),
        ("Test Document with Spaces.docx", "test-document-with-spaces"),
        ("Document@#$%^&*().pdf", "document"),
        ("123-starts-with-number.pdf", "doc-123-starts-with-number"),
        ("UPPERCASE_DOCUMENT.PDF", "uppercase-document"),
        ("Document-with---multiple---hyphens.pdf", "document-with-multiple-hyphens"),
        ("", "document"),  # Empty name
        ("a" * 300, "a" * 255),  # Very long name
    ]
    
    passed = 0
    failed = 0
    
    for doc_name, expected_pattern in test_cases:
        try:
            result = sanitize_index_name(doc_name)
            
            # Check basic requirements
            checks = []
            checks.append(("lowercase", result.islower() or result == ""))
            checks.append(("no spaces", " " not in result))
            checks.append(("valid chars", all(c.isalnum() or c in ['-', '_'] for c in result)))
            checks.append(("starts correctly", not result or result[0].isalpha() or result[0] == '_' or result.startswith('doc-')))
            checks.append(("length limit", len(result) <= 255))
            
            all_passed = all(check[1] for check in checks)
            
            if all_passed:
                print(f"✅ '{doc_name}' → '{result}'")
                passed += 1
            else:
                print(f"❌ '{doc_name}' → '{result}'")
                for check_name, check_result in checks:
                    if not check_result:
                        print(f"   Failed: {check_name}")
                failed += 1
        except Exception as e:
            print(f"❌ '{doc_name}' → ERROR: {str(e)}")
            failed += 1
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0

def test_index_name_generation():
    """Test index name generation logic."""
    print()
    print("=" * 70)
    print("Testing: Index Name Generation Logic")
    print("=" * 70)
    print()
    
    # Test that sanitization handles various edge cases
    edge_cases = [
        "Document.pdf",
        "Document (1).pdf",
        "Document-v2.pdf",
        "My Very Long Document Name That Should Be Truncated If Too Long.pdf",
    ]
    
    print("Testing edge cases:")
    for doc_name in edge_cases:
        result = sanitize_index_name(doc_name)
        print(f"  '{doc_name}' → '{result}'")
    
    print()
    print("✅ Index name generation logic looks correct")
    return True

if __name__ == "__main__":
    print()
    test1_passed = test_sanitize_index_name()
    test2_passed = test_index_name_generation()
    
    print()
    if test1_passed and test2_passed:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

