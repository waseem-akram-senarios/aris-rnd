#!/usr/bin/env python3
"""
Quick test runner
Runs fast tests (smoke, sanity, unit)
"""
import sys
import subprocess
from pathlib import Path

def main():
    """Run quick tests"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/smoke/",
        "tests/sanity/",
        "tests/unit/",
        "-m", "smoke or sanity or unit",
        "-v",
        "--tb=short"
    ]
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    import os
    main()
