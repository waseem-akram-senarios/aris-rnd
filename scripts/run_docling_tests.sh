#!/bin/bash
# Quick test runner for Docling integration tests

echo "=========================================="
echo "Docling Integration Test Runner"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please create a virtual environment first:"
    echo "   python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if test file exists
if [ ! -f "test_docling_integration.py" ]; then
    echo "❌ Test file not found: test_docling_integration.py"
    exit 1
fi

# Run tests
echo "🧪 Running Docling integration tests..."
echo ""
python3 test_docling_integration.py

# Capture exit code
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests completed successfully!"
else
    echo "⚠️  Some tests failed. Check the output above."
fi

exit $EXIT_CODE



