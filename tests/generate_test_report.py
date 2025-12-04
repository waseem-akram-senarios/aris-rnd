"""
Generate comprehensive test report
"""
import sys
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_pytest_with_json(test_file):
    """Run pytest and capture JSON output"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "--json-report", "--json-report-file=-"],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def generate_report():
    """Generate comprehensive test report"""
    print("Generating test report...")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "test_suites": [],
        "summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0
        }
    }
    
    # Test files to include
    test_files = [
        "tests/test_config.py",
        "tests/test_document_registry.py",
        "tests/test_service_container.py",
        "tests/api/test_sync_endpoints.py",
        "tests/api/test_document_crud_sync.py",
        "tests/test_vectorstore_sync.py",
        "tests/test_metadata_sync.py",
        "tests/test_config_sync.py",
        "tests/test_conflict_resolution.py",
        "tests/test_full_sync_workflow.py",
        "tests/test_cross_system_access.py",
    ]
    
    # Run tests and collect results
    for test_file in test_files:
        if not Path(test_file).exists():
            continue
        
        print(f"Running {test_file}...")
        success, stdout, stderr = run_pytest_with_json(test_file)
        
        suite_result = {
            "file": test_file,
            "status": "passed" if success else "failed",
            "output": stdout,
            "errors": stderr
        }
        
        report["test_suites"].append(suite_result)
        
        if success:
            report["summary"]["passed"] += 1
        else:
            report["summary"]["failed"] += 1
        
        report["summary"]["total_tests"] += 1
    
    # Calculate success rate
    if report["summary"]["total_tests"] > 0:
        report["summary"]["success_rate"] = (
            report["summary"]["passed"] / report["summary"]["total_tests"] * 100
        )
    else:
        report["summary"]["success_rate"] = 0
    
    # Save report
    report_file = project_root / "tests" / "test_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST REPORT SUMMARY")
    print("="*80)
    print(f"Total Test Suites: {report['summary']['total_tests']}")
    print(f"Passed: {report['summary']['passed']}")
    print(f"Failed: {report['summary']['failed']}")
    print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
    print(f"\nReport saved to: {report_file}")
    print("="*80)
    
    return report


if __name__ == "__main__":
    report = generate_report()
    sys.exit(0 if report["summary"]["failed"] == 0 else 1)

