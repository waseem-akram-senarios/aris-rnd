#!/usr/bin/env python3
"""
Performance test runner
Runs performance tests with benchmarking
"""
import sys
import subprocess
from pathlib import Path

def main():
    """Run performance tests"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/performance/",
        "-m", "performance",
        "--benchmark-only",
        "--benchmark-json", "reports/benchmark_results.json",
        "-v"
    ]
    
    result = subprocess.run(cmd)
    
    print("\n" + "=" * 80)
    print("Performance benchmark results saved to:")
    print("  reports/benchmark_results.json")
    print("=" * 80)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    import os
    main()
