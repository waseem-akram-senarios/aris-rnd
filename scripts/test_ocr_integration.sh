#!/bin/bash
# Test script for OCRmyPDF integration
# Tests both API and parser availability

set -e

echo "=========================================="
echo "Testing OCRmyPDF Integration"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check Tesseract installation
echo "Test 1: Checking Tesseract OCR..."
if command -v tesseract &> /dev/null; then
    echo -e "${GREEN}✅ Tesseract installed:${NC} $(tesseract --version | head -n 1)"
    echo "   Installed languages:"
    tesseract --list-langs 2>/dev/null | tail -n +2 | sed 's/^/      - /'
else
    echo -e "${RED}❌ Tesseract not found${NC}"
    echo "   Install with: sudo apt-get install tesseract-ocr tesseract-ocr-eng"
    exit 1
fi

# Test 2: Check OCRmyPDF Python package
echo ""
echo "Test 2: Checking OCRmyPDF Python package..."
if python3 -c "import ocrmypdf" 2>/dev/null; then
    version=$(python3 -c "import ocrmypdf; print(ocrmypdf.__version__)")
    echo -e "${GREEN}✅ OCRmyPDF installed:${NC} v$version"
else
    echo -e "${RED}❌ OCRmyPDF not found${NC}"
    echo "   Install with: pip install ocrmypdf>=16.0.0"
    exit 1
fi

# Test 3: Check parser availability
echo ""
echo "Test 3: Checking OCRmyPDF parser..."
if python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; parser = OCRmyPDFParser(); assert parser.is_available()" 2>/dev/null; then
    echo -e "${GREEN}✅ OCRmyPDF parser available${NC}"
else
    echo -e "${RED}❌ OCRmyPDF parser not available${NC}"
    exit 1
fi

# Test 4: Check parser registration
echo ""
echo "Test 4: Checking parser registration..."
if python3 -c "from parsers.parser_factory import ParserFactory; parser = ParserFactory.get_parser('test.pdf', 'ocrmypdf'); assert parser is not None" 2>/dev/null; then
    echo -e "${GREEN}✅ OCRmyPDF registered in ParserFactory${NC}"
else
    echo -e "${RED}❌ OCRmyPDF not registered${NC}"
    exit 1
fi

# Test 5: Check API endpoint (if server is running)
echo ""
echo "Test 5: Checking API endpoint..."
API_URL="http://localhost:8500"

if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API server is running${NC}"
    
    # Check if OCR preprocessing endpoint exists
    if curl -s "$API_URL/docs" | grep -q "ocr-preprocess" 2>/dev/null; then
        echo -e "${GREEN}✅ OCR preprocessing endpoint available${NC}"
    else
        echo -e "${YELLOW}⚠️  OCR preprocessing endpoint not found in API docs${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  API server not running (skipping API tests)${NC}"
    echo "   Start with: uvicorn api.main:app --host 0.0.0.0 --port 8500"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}✅ All core tests passed!${NC}"
echo ""
echo "OCRmyPDF is ready to use:"
echo "  - API: Set parser_preference='ocrmypdf'"
echo "  - UI: Select 'OCRmyPDF' from parser dropdown"
echo ""
echo "Documentation:"
echo "  - OCR_INTEGRATION_GUIDE.md"
echo "  - OCR_QUICK_START.md"
echo ""
