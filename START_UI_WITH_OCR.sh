#!/bin/bash
# Start Streamlit UI with OCR Integration

echo "=========================================="
echo "Starting ARIS UI with OCR Integration"
echo "=========================================="
echo ""

# Check if Streamlit is installed
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "⚠️  Streamlit not found. Installing..."
    pip install streamlit>=1.31.0
fi

# Navigate to project directory
cd "$(dirname "$0")"

echo "✅ OCR Integration Features:"
echo "   - OCRmyPDF parser in dropdown"
echo "   - OCR settings panel (languages, DPI)"
echo "   - Real-time progress tracking"
echo ""

echo "Starting Streamlit UI..."
echo "UI will open at: http://localhost:8501"
echo ""
echo "To see OCR options:"
echo "  1. Look for 'Parser Settings' in the sidebar"
echo "  2. Select 'OCRmyPDF' from the dropdown"
echo "  3. OCR settings panel will appear"
echo ""

# Start Streamlit
streamlit run api/app.py
