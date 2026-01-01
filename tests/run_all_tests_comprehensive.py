#!/usr/bin/env python3
"""
Comprehensive test runner
Runs all test types with reporting
"""
import sys
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

def run_tests_by_marker(marker, test_dir=None):
    """Run tests by marker"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "-m", marker,
        "-v",
        "--tb=short",
        "--junitxml", f"reports/junit_{marker}.xml"
    ]
    
    if test_dir:
        cmd.insert(2, test_dir)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "marker": marker,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

def main():
    """Run all test suites"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Create reports directory
    reports_dir = project_root / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print("ARIS RAG System - Comprehensive Test Suite")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    test_markers = [
        ("unit", "tests/unit/"),
        ("integration", "tests/integration/"),
        ("functional", "tests/functional/"),
        ("api", "tests/api/"),
        ("regression", "tests/regression/"),
        ("smoke", "tests/smoke/"),
        ("sanity", "tests/sanity/"),
        ("performance", "tests/performance/"),
        ("security", "tests/security/"),
        ("e2e", "tests/e2e/")
    ]
    
    results = {}
    start_time = time.time()
    
    for marker, test_dir in test_markers:
        print(f"\n{'=' * 80}")
        print(f"Running {marker} tests...")
        print(f"{'=' * 80}\n")
        
        result = run_tests_by_marker(marker, test_dir)
        results[marker] = result
        
        if result["returncode"] == 0:
            print(f"✅ {marker} tests passed")
        else:
            print(f"❌ {marker} tests failed")
    
    elapsed = time.time() - start_time
    
    # Generate summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results.values() if r["returncode"] == 0)
    failed = len(results) - passed
    
    print(f"Total test suites: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total time: {elapsed:.2f}s")
    
    # Save results
    results_file = reports_dir / "test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "results": results,
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": failed
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_file}")
    
    # Exit with error if any failed
    sys.exit(1 if failed > 0 else 0)

if __name__ == "__main__":
    import os
    main()
