#!/usr/bin/env python3
"""
ARIS Test Dashboard Launcher
Start the test monitoring dashboard
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Launch the test dashboard"""
    # Get dashboard directory
    dashboard_dir = Path(__file__).parent
    os.chdir(dashboard_dir)
    
    # Check if requirements are installed
    try:
        import streamlit
        import pandas
        import plotly
        print("✅ All dependencies available")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("📦 Installing requirements...")
        
        # Install requirements
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        
        print("✅ Dependencies installed")
    
    # Launch Streamlit dashboard
    print("🚀 Starting ARIS Test Dashboard...")
    print("🌐 Dashboard will open in your browser")
    print("📍 URL: http://localhost:8501")
    print("\n📋 Available Test Categories:")
    print("   • E2E Tests - End-to-end testing")
    print("   • MCP Tests - Model Context Protocol testing")
    print("   • Unit Tests - Component unit testing")
    print("   • Integration Tests - Service integration")
    print("   • All Tests - Complete test suite")
    
    # Run streamlit
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0",
        "--browser.gatherUsageStats", "false"
    ])

if __name__ == "__main__":
    main()
