"""API tests package"""
# Prevent Python from treating this as the api module
import sys
from pathlib import Path

# Ensure we're not conflicting with the api package
if 'api' in sys.modules:
    # Clear any cached api module that might conflict
    pass
