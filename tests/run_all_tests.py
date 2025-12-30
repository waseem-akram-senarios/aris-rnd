"""
Test runner script for comprehensive E2E tests
"""
import sys
import subprocess
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests(test_files, test_name):
    """Run a set of test files"""
    print(f"\n{'='*80}")
    print(f"Running {test_name}")
    print(f"{'='*80}\n")
    
    results = []
    for test_file in test_files:
        print(f"Running {test_file}...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test file
            )
            success = result.returncode == 0
            results.append((test_file, success, result.stdout, result.stderr))
            
            if success:
                print(f"✅ {test_file} PASSED")
            else:
                print(f"❌ {test_file} FAILED")
                print(result.stdout)
                print(result.stderr)
        except subprocess.TimeoutExpired:
            results.append((test_file, False, "", "Test timed out"))
            print(f"⏱️ {test_file} TIMED OUT")
        except Exception as e:
            results.append((test_file, False, "", str(e)))
            print(f"❌ {test_file} ERROR: {e}")
    
    return results


def main():
    """Run all test suites"""
    print("="*80)
    print("ARIS RAG System - Comprehensive E2E Test Suite")
    print("="*80)
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Define test phases
    test_phases = {
        "Phase 1: Unit Tests": [
            "tests/test_config.py",
            "tests/test_document_registry.py",
            "tests/test_service_container.py",
        ],
        "Phase 2: Integration Tests": [
            "tests/api/test_sync_endpoints.py",
            "tests/api/test_document_crud_sync.py",
        ],
        "Phase 3: E2E Sync Tests": [
            "tests/test_vectorstore_sync.py",
            "tests/test_metadata_sync.py",
            "tests/test_config_sync.py",
            "tests/test_conflict_resolution.py",
        ],
        "Phase 4: Full Workflow Tests": [
            "tests/test_full_sync_workflow.py",
            "tests/test_cross_system_access.py",
        ],
    }
    
    all_results = {}
    total_passed = 0
    total_failed = 0
    
    # Run each phase
    for phase_name, test_files in test_phases.items():
        # Filter to only existing files
        existing_files = [f for f in test_files if Path(f).exists()]
        
        if not existing_files:
            print(f"\n⚠️ {phase_name}: No test files found, skipping...")
            continue
        
        results = run_tests(existing_files, phase_name)
        all_results[phase_name] = results
        
        # Count results
        phase_passed = sum(1 for _, success, _, _ in results if success)
        phase_failed = len(results) - phase_passed
        total_passed += phase_passed
        total_failed += phase_failed
        
        print(f"\n{phase_name} Summary: {phase_passed} passed, {phase_failed} failed")
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    for phase_name, results in all_results.items():
        print(f"\n{phase_name}:")
        for test_file, success, _, _ in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {status}: {test_file}")
    
    print(f"\n{'='*80}")
    print(f"Total: {total_passed} passed, {total_failed} failed")
    print(f"Success Rate: {(total_passed/(total_passed+total_failed)*100):.1f}%" if (total_passed+total_failed) > 0 else "N/A")
    print(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Exit with appropriate code
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

