# OCR Extraction Test - Server Instructions

## Quick Start

### On Your Server:

1. **Transfer files to server:**
   ```bash
   # Copy the test script and document
   scp test_ocr_extraction.py user@server:/path/to/aris/
   scp run_ocr_test_server.sh user@server:/path/to/aris/
   scp samples/FL10.11\ SPECIFIC8\ \(1\).pdf user@server:/path/to/aris/samples/
   ```

2. **SSH to server:**
   ```bash
   ssh user@server
   cd /path/to/aris
   ```

3. **Run the test:**
   ```bash
   ./run_ocr_test_server.sh
   ```

   Or with a custom PDF:
   ```bash
   ./run_ocr_test_server.sh path/to/your/document.pdf
   ```

## What the Test Does

1. **Baseline Extraction** - Extracts text using PyMuPDF (no OCR)
2. **OCR Configuration Check** - Verifies OCR is properly configured
3. **OCR Extraction** - Extracts text using Docling with OCR enabled
4. **Comparison** - Compares OCR vs non-OCR results
5. **Analysis** - Shows what unique text OCR found

## Output Files

All results are saved in `ocr_test_results/`:

- `baseline_pymupdf_*.txt` - Text extracted without OCR
- `ocr_docling_*.txt` - Text extracted with OCR
- `comparison_*.txt` - Detailed comparison report
- `ocr_test_report_*.txt` - Full test report

## Requirements

- Python 3.8+
- docling: `pip install docling`
- pymupdf: `pip install pymupdf`

The script will check and install dependencies automatically.

## Expected Runtime

- **Small document (1-10 pages)**: 2-5 minutes
- **Medium document (10-50 pages)**: 5-15 minutes
- **Large document (50+ pages)**: 15-30 minutes

Processing time depends on:
- Document size and page count
- Number of images
- Server CPU/RAM
- Whether GPU is available

## Troubleshooting

### OCR models not found
```bash
# Docling should auto-download models, but if needed:
python3 -c "from docling.document_converter import DocumentConverter; DocumentConverter()"
```

### Out of memory
- Close other applications
- Process document in smaller chunks
- Use a server with more RAM

### Slow processing
- Normal for large documents
- Consider using GPU if available
- Check server CPU usage

## Manual Run

If you prefer to run manually:

```bash
python3 test_ocr_extraction.py samples/FL10.11\ SPECIFIC8\ \(1\).pdf
```

## What OCR Extracts

OCR will extract text from:
- ✅ Scanned image pages
- ✅ Text embedded in images/diagrams
- ✅ Handwritten text (if legible)
- ✅ Text in tables/charts
- ✅ Text that regular parsers miss

## Understanding Results

- **OCR extracted MORE text**: OCR successfully found text in images
- **OCR extracted SAME text**: Document is text-based, OCR not needed
- **OCR extracted LESS text**: Possible OCR processing error

