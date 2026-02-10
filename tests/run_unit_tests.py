#!/usr/bin/env python3
"""
Unit test runner
Runs all unit tests
"""
import sys
import subprocess
from pathlib import Path

def main():
    """Run unit tests"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/unit/",
        "-m", "unit",
        "-v",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    import os
    main()
