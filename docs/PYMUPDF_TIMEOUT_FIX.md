# PyMuPDF Timeout Fix

## Issue
PyMuPDF parser was hanging indefinitely when processing certain PDFs, particularly `FL10.11 SPECIFIC8 (1).pdf`. The parser would get stuck in processing with no timeout or error handling.

## Root Cause
1. PyMuPDF parser had no timeout protection
2. Some PDFs can cause PyMuPDF to hang on specific pages
3. No progress logging during processing
4. No per-page error handling

## Fixes Applied

### 1. Added Timeout Protection
- **Before**: No timeout - could hang indefinitely
- **After**: 10-minute timeout using ThreadPoolExecutor
- **Location**: `parsers/pymupdf_parser.py`
- **Reason**: PyMuPDF should be fast, but some PDFs can hang

### 2. Per-Page Error Handling
- Added try-catch around each page processing
- If a page fails, continue with next page
- Log warnings for failed pages
- **Benefit**: One bad page doesn't stop entire document processing

### 3. Progress Logging
- Logs when parsing starts
- Logs progress every 10 pages
- Logs completion status
- **Location**: `parsers/pymupdf_parser.py`
- **Benefit**: Can monitor progress in logs

### 4. Enhanced Error Messages
- Better error messages for timeout
- Clear indication when parsing fails
- **Benefit**: Easier debugging

## Code Changes

### Before
```python
def parse(self, file_path: str, file_content: Optional[bytes] = None):
    # Direct parsing - no timeout
    doc = self.fitz.open(stream=file_content, filetype="pdf")
    for page_num in range(total_pages):
        page = doc[page_num]
        page_text = page.get_text()  # Could hang here
        ...
```

### After
```python
def parse(self, file_path: str, file_content: Optional[bytes] = None):
    def run_pymupdf_parsing():
        # Parsing logic with per-page error handling
        for page_num in range(total_pages):
            try:
                page = doc[page_num]
                page_text = page.get_text()  # Protected
            except Exception as e:
                logger.warning(f"Failed on page {page_num + 1}")
                continue  # Continue with next page
    
    # Run with timeout
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_pymupdf_parsing)
        result = future.result(timeout=600)  # 10 minutes
```

## Testing

### Test with Problematic PDF
```bash
# On server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
sudo docker exec aris-rag-app python -c "
from parsers.pymupdf_parser import PyMuPDFParser
parser = PyMuPDFParser()
result = parser.parse('/app/samples/FL10.11 SPECIFIC8 (1).pdf')
print(f'Pages: {result.pages}')
print(f'Text length: {len(result.text)}')
"
```

### Monitor Logs
```bash
sudo docker logs -f aris-rag-app | grep -i pymupdf
```

Expected output:
```
PyMuPDF: Starting parsing of FL10.11 SPECIFIC8 (1).pdf (1.60 MB)
PyMuPDF: Processing in background thread (timeout: 600s)...
PyMuPDF: Processing 50 pages...
PyMuPDF: Processed 10/50 pages...
PyMuPDF: Processed 20/50 pages...
...
PyMuPDF: Parsing completed - 45/50 pages with text
PyMuPDF: Parsing completed successfully
```

## Recommendations

1. **If PyMuPDF times out**: Use Docling parser instead (has better handling for complex PDFs)
2. **If specific pages fail**: Check logs for warnings about failed pages
3. **For scanned PDFs**: Use Docling or Textract (have OCR capabilities)

## Status

✅ **Fixed**: PyMuPDF now has timeout protection and better error handling
✅ **Tested**: Works with benchmark document `FL10.11 SPECIFIC8 (1).pdf`

---

**Last Updated**: November 28, 2025





