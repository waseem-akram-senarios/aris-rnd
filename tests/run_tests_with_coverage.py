#!/usr/bin/env python3
"""
Test runner with coverage reporting
Runs tests and generates coverage reports
"""
import sys
import subprocess
from pathlib import Path

def main():
    """Run tests with coverage"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--cov=api",
        "--cov=parsers",
        "--cov=vectorstores",
        "--cov=ingestion",
        "--cov=rag",
        "--cov=config",
        "--cov=storage",
        "--cov=utils",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=json:reports/coverage.json",
        "-v"
    ]
    
    result = subprocess.run(cmd)
    
    print("\n" + "=" * 80)
    print("Coverage report generated:")
    print("  HTML: htmlcov/index.html")
    print("  JSON: reports/coverage.json")
    print("=" * 80)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    import os
    main()
