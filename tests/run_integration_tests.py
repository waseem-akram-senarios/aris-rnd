#!/usr/bin/env python3
"""
Integration test runner
Runs all integration tests
"""
import sys
import subprocess
from pathlib import Path

def main():
    """Run integration tests"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/integration/",
        "-m", "integration",
        "-v",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    import os
    main()
