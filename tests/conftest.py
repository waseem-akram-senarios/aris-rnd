"""
Pytest configuration and fixtures
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
project_root_str = str(project_root)

# Ensure project root is in path (at the beginning)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Also add current directory
if '.' not in sys.path:
    sys.path.insert(0, '.')

# Change to project root directory for tests
os.chdir(project_root_str)

