#!/usr/bin/env python3
"""
Clean up obsolete test scripts for ARIS microservices architecture
Removes old test files that are no longer relevant for current system
"""
import os
import shutil
from pathlib import Path
import argparse


# Obsolete test files that can be removed
OBSOLETE_TESTS = [
    # Legacy comprehensive tests (old monolithic architecture)
    "comprehensive_api_test.py",
    "test_all.py", 
    "test_all_apis.py",
    "test_all_endpoints_comprehensive.py",
    "test_all_endpoints_detailed.py",
    "test_all_endpoints_with_document.py",
    "test_all_endpoints_with_responses.py",
    "test_all_parsers_server.py",
    "test_comprehensive_all.py",
    "test_comprehensive_e2e.py",
    "test_automated_comprehensive.py",
    "test_full_in_depth_with_logs.py",
    "test_full_system_optimization.py",
    
    # Server-based tests (now microservices)
    "test_server_*.py",
    "test_gateway_minimal_api.py",
    "test_fastapi_integration_comprehensive.py",
    "test_fastapi_rag_e2e.py",
    "test_server_comprehensive.py",
    "test_server_image_extraction.py",
    "test_server_in_depth.py",
    "test_server_parsers.py",
    "test_server_spanish_ocr.py",
    
    # Postman tests (use FastAPI TestClient instead)
    "test_postman_*.py",
    
    # Individual component tests (now integrated)
    "test_ocr_*.py",
    "test_spanish_*.py", 
    "test_image_*.py",
    "test_parser_*.py",
    "test_citation_*.py",
    
    # Language-specific tests (now integrated)
    "test_cross_language_*.py",
    "test_multilingual_*.py",
    "test_client_spanish_*.py",
    
    # Diagnostic/debugging tests (not needed for CI)
    "test_diagnostic_*.py",
    "test_debug_*.py",
    "test_verify_*.py",
    
    # Manual testing scripts
    "manual_*.py",
    "check_*.py",
    "diagnose_*.py",
    "extract_*.py",
    "force_*.py",
    "parse_*.py",
    "verify_*.py",
    
    # Performance comparison tests (use dedicated performance tests)
    "benchmark_*.py",
    "test_ocr_accuracy_comparison.py",
    "test_similarity_percentage_accuracy.py",
    
    # Test result files (can be regenerated)
    "*_results.json",
    "*_results.log",
    "*_output.log",
    "test_output.txt",
    "curl_*.txt",
    
    # Documentation files (move to docs/)
    "README_*.md",
    "TESTING_*.md",
    "MANUAL_*.md",
    "MOCK_*.md",
    "CHUNKING_*.md",
    "CITATION_*.md",
    "TEST_*.md",
]

# Files to keep (still relevant)
KEEP_FILES = [
    "conftest.py",
    "run_*.py",
    "generate_*.py",
    "quick_*.py",
    "test_language_detection.py",  # Simple utility test
    "test_s3_*.py",  # S3 integration tests
    "test_accuracy_checking.py",  # Accuracy validation
]

# Directories to keep
KEEP_DIRS = [
    "unit/",
    "integration/", 
    "e2e/",
    "api/",
    "functional/",
    "regression/",
    "smoke/",
    "sanity/",
    "performance/",
    "security/",
    "fixtures/",
    "utils/",
    "parser_test_results/",
    "server_ocr_results/",
    "spanish_ocr_results/",
    "ocr_test_results/",
]

def is_obsolete_file(filepath: Path) -> bool:
    """Check if a file is obsolete"""
    filename = filepath.name
    
    # Keep essential files
    if filename in KEEP_FILES:
        return False
    
    # Keep directories
    if filepath.is_dir() and filename.endswith('/'):
        return False
    
    # Check against obsolete patterns
    for pattern in OBSOLETE_TESTS:
        if filepath.match(pattern):
            return True
    
    return False

def cleanup_tests(test_dir: Path, dry_run: bool = False) -> dict:
    """Clean up obsolete test files"""
    results = {
        'removed': [],
        'kept': [],
        'errors': []
    }
    
    if not test_dir.exists():
        results['errors'].append(f"Test directory {test_dir} does not exist")
        return results
    
    print(f"Scanning {test_dir} for obsolete test files...")
    
    for item in test_dir.iterdir():
        if item.name in ['.', '..']:
            continue
            
        # Keep essential directories
        if item.is_dir() and item.name in [d.rstrip('/') for d in KEEP_DIRS]:
            results['kept'].append(str(item))
            continue
            
        # Check if file is obsolete
        if is_obsolete_file(item):
            if dry_run:
                results['removed'].append(f"[DRY RUN] Would remove: {item}")
            else:
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                        results['removed'].append(f"Removed directory: {item}")
                    else:
                        item.unlink()
                        results['removed'].append(f"Removed file: {item}")
                except Exception as e:
                    results['errors'].append(f"Error removing {item}: {e}")
        else:
            results['kept'].append(str(item))
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Clean up obsolete ARIS test files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without actually removing")
    parser.add_argument("--test-dir", default="tests", help="Test directory path")
    
    args = parser.parse_args()
    
    test_dir = Path(args.test_dir)
    results = cleanup_tests(test_dir, args.dry_run)
    
    print("\n" + "="*60)
    print("CLEANUP RESULTS")
    print("="*60)
    
    if results['removed']:
        print(f"\nFiles/Directories Removed ({len(results['removed'])}):")
        for item in results['removed']:
            print(f"  {item}")
    
    if results['kept']:
        print(f"\nFiles/Directories Kept ({len(results['kept'])}):")
        for item in results['kept']:
            print(f"  {item}")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  ERROR: {error}")
    
    print(f"\nSummary:")
    print(f"  Removed: {len(results['removed'])}")
    print(f"  Kept: {len(results['kept'])}")
    print(f"  Errors: {len(results['errors'])}")
    
    if not args.dry_run and results['removed']:
        print(f"\n✅ Cleanup completed! {len(results['removed'])} obsolete files removed.")
    elif args.dry_run:
        print(f"\n🔍 Dry run completed! Would remove {len(results['removed'])} files.")

if __name__ == "__main__":
    main()
