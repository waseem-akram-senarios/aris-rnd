#!/bin/bash

# Test PyMuPDF Timeout Fix
# Tests if PyMuPDF can process FL10.11 SPECIFIC8 (1).pdf without hanging

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$PROJECT_ROOT/scripts/ec2_wah_pk.pem"
BENCHMARK_FILE="FL10.11 SPECIFIC8 (1).pdf"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  PyMuPDF Timeout Fix Test                               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📄 Testing with: $BENCHMARK_FILE"
echo "🌐 Server: $SERVER_IP"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo "❌ PEM file not found: $PEM_FILE"
    exit 1
fi

# Run test on server
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
cd $SERVER_DIR

echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST: PyMuPDF Parser with Timeout Protection         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if benchmark file exists
BENCHMARK_FILE="samples/$BENCHMARK_FILE"
if [ ! -f "\$BENCHMARK_FILE" ]; then
    echo "❌ Benchmark file not found: \$BENCHMARK_FILE"
    echo "Available files in samples/:"
    ls -lh samples/*.pdf 2>/dev/null | head -5
    exit 1
fi

FILE_SIZE=\$(du -h "\$BENCHMARK_FILE" | cut -f1)
echo "📄 File: \$BENCHMARK_FILE"
echo "📊 Size: \$FILE_SIZE"
echo ""

echo "🧪 Starting PyMuPDF parsing test..."
echo "   (This should complete within 10 minutes or timeout with error)"
echo ""

# Test PyMuPDF parser with timeout
sudo docker exec aris-rag-app python -c "
import sys
import time
sys.path.insert(0, '/app')
from parsers.pymupdf_parser import PyMuPDFParser

try:
    print('   Initializing PyMuPDF parser...')
    parser = PyMuPDFParser()
    print('   ✅ Parser initialized')
    
    test_file = '/app/samples/$BENCHMARK_FILE'
    print(f'   Processing: {test_file}')
    print('   Starting parse (with 10-minute timeout)...')
    print('')
    
    start_time = time.time()
    result = parser.parse(test_file)
    elapsed_time = time.time() - start_time
    
    print('')
    print('   ╔════════════════════════════════════════════════════════╗')
    print('   ║  ✅ PyMuPDF Parsing SUCCESSFUL                         ║')
    print('   ╚════════════════════════════════════════════════════════╝')
    print('')
    print(f'   ⏱️  Processing time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)')
    print(f'   📄 Pages processed: {result.pages}')
    print(f'   📝 Text extracted: {len(result.text):,} characters')
    print(f'   📊 Extraction rate: {result.extraction_percentage*100:.1f}%')
    print(f'   🎯 Confidence: {result.confidence*100:.1f}%')
    print(f'   🖼️  Images detected: {result.images_detected}')
    
    if result.text and len(result.text.strip()) > 0:
        preview = result.text[:200].replace(chr(10), ' ').replace(chr(13), ' ')
        print(f'   📖 Text preview: {preview}...')
    else:
        print('   ⚠️  Warning: No text extracted')
    
    print('')
    print('   ✅ Test PASSED: PyMuPDF processed document successfully')
    print('   ✅ Timeout protection is working (did not hang)')
    
except ValueError as e:
    error_msg = str(e)
    elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
    print('')
    print('   ╔════════════════════════════════════════════════════════╗')
    if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
        print('   ║  ⏱️  PyMuPDF TIMEOUT (Expected for problematic PDFs)  ║')
    else:
        print('   ║  ❌ PyMuPDF PARSING FAILED                          ║')
    print('   ╚════════════════════════════════════════════════════════╝')
    print('')
    print(f'   ⏱️  Time before error: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)')
    print(f'   ❌ Error: {error_msg[:200]}')
    print('')
    if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
        print('   ✅ Test PASSED: Timeout protection worked correctly')
        print('   💡 Recommendation: Use Docling parser for this document')
    else:
        print('   ❌ Test FAILED: Unexpected error occurred')
    sys.exit(1)
    
except Exception as e:
    elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
    print('')
    print('   ╔════════════════════════════════════════════════════════╗')
    print('   ║  ❌ UNEXPECTED ERROR                                   ║')
    print('   ╚════════════════════════════════════════════════════════╝')
    print('')
    print(f'   ⏱️  Time before error: {elapsed_time:.2f} seconds')
    print(f'   ❌ Error: {str(e)[:200]}')
    print('')
    print('   ❌ Test FAILED: Unexpected error')
    sys.exit(1)
" 2>&1

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST COMPLETE                                         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

EOF

echo ""
echo "📊 Test Summary:"
echo "   ✅ PyMuPDF timeout fix test completed"
echo ""
echo "🌐 Application: http://$SERVER_IP/"
echo ""



