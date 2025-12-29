#!/bin/bash
# Run Streamlit locally to see OCR integration

echo "=========================================="
echo "Starting Streamlit UI Locally"
echo "=========================================="
echo ""

# Stop any running instances
pkill -f "streamlit run" 2>/dev/null
sleep 2

# Clear cache
echo "Clearing cache..."
rm -rf .streamlit/cache ~/.streamlit/cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo ""
echo "✅ Cache cleared"
echo ""
echo "Starting Streamlit..."
echo "UI will open at: http://localhost:8501"
echo ""
echo "═══════════════════════════════════════════"
echo "WHERE TO FIND OCR:"
echo "═══════════════════════════════════════════"
echo ""
echo "1. Look at the LEFT SIDEBAR (not main area)"
echo "2. Scroll down to '🔧 Parser Settings'"
echo "3. Click the 'Choose Parser:' dropdown"
echo "4. You will see:"
echo "   - Docling"
echo "   - PyMuPDF"
echo "   - OCRmyPDF     ← SELECT THIS!"
echo "   - Textract"
echo ""
echo "5. After selecting OCRmyPDF:"
echo "   - OCR Settings panel appears"
echo "   - Language input field"
echo "   - DPI slider"
echo ""
echo "═══════════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start Streamlit
cd /home/senarios/Desktop/aris
streamlit run api/app.py
