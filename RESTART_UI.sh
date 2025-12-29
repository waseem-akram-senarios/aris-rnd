#!/bin/bash
# Script to restart Streamlit UI with cache cleared

echo "=========================================="
echo "Restarting Streamlit UI"
echo "=========================================="
echo ""

# Stop any running Streamlit instances
echo "Stopping any running Streamlit instances..."
pkill -f "streamlit run" 2>/dev/null
sleep 2

# Clear Streamlit cache
echo "Clearing Streamlit cache..."
rm -rf .streamlit/cache
rm -rf ~/.streamlit/cache

# Clear Python cache
echo "Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo ""
echo "✅ Cache cleared"
echo ""
echo "Starting Streamlit UI..."
echo "UI will open at: http://localhost:8501"
echo ""
echo "To see OCR options:"
echo "  1. Look in the LEFT SIDEBAR"
echo "  2. Find '🔧 Parser Settings' section"
echo "  3. Click the 'Choose Parser:' dropdown"
echo "  4. Select 'OCRmyPDF'"
echo "  5. OCR settings panel will appear below"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start Streamlit
streamlit run api/app.py
