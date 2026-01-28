# Parser Page Number Accuracy Fixes - Complete

## Summary
All parsers have been updated to ensure **exact page numbers** in citations for every query result.

## Parsers Fixed

### 1. ✅ PyMuPDF Parser (`parsers/pymupdf_parser.py`)
- **Status**: Already correct
- **Page Tracking**: Stores `page_blocks` metadata with accurate page numbers
- **Page Markers**: Adds `--- Page X ---` markers in text
- **Citation Support**: Full support via `page_blocks` in metadata

### 2. ✅ Docling Parser (`parsers/docling_parser.py`)
- **Status**: Already correct
- **Page Tracking**: Stores `page_blocks` metadata with accurate page numbers
- **Page Markers**: Adds `--- Page X ---` markers in text
- **Citation Support**: Full support via `page_blocks` in metadata

### 3. ✅ Textract Parser (`parsers/textract_parser.py`)
- **Status**: **FIXED**
- **Changes Made**:
  - Added `page_blocks` metadata structure
  - Added page markers (`--- Page X ---`) in text output
  - Tracks page numbers per block from Textract response
  - Stores page-level blocks with start/end character positions
- **Citation Support**: Now fully supported via `page_blocks` in metadata

### 4. ✅ OCRmyPDF Parser (`parsers/ocrmypdf_parser.py`)
- **Status**: **FIXED**
- **Changes Made**:
  - Added `page_blocks` metadata structure
  - Added page markers (`--- Page X ---`) in text output
  - Tracks page numbers for both PyMuPDF and PyPDF2 extraction paths
  - Stores page-level blocks with start/end character positions
- **Citation Support**: Now fully supported via `page_blocks` in metadata

### 5. ✅ LlamaScan Parser (`parsers/llama_scan_parser.py`)
- **Status**: Already correct
- **Page Tracking**: Stores `page_blocks` metadata with accurate page numbers
- **Page Markers**: Adds `--- Page X ---` markers in text
- **Citation Support**: Full support via `page_blocks` in metadata

## How Page Numbers Flow to Citations

1. **Parser Level**: Each parser extracts text and creates `page_blocks` metadata with accurate page numbers
2. **Tokenizer Level**: `utils/tokenizer.py` uses `page_blocks` to assign `page` and `source_page` to each chunk
3. **RAG System**: `api/rag_system.py::_extract_page_number()` prioritizes `source_page` metadata (confidence 1.0)
4. **Citation Construction**: All citations use the accurate page number from chunk metadata
5. **UI Display**: `api/app.py` always displays page numbers in reference lines and detailed citations

## Guarantees

✅ **Every citation will have an exact page number** from the original PDF
✅ **All parsers output consistent `page_blocks` metadata**
✅ **Tokenizer maps page_blocks to chunks accurately**
✅ **RAG system prioritizes metadata over text markers**
✅ **UI always displays page numbers (never "Text content")**

## Testing

- ✅ Syntax validation: All parser files compile correctly
- ✅ Parser availability: All parsers can be imported and instantiated
- ✅ API tests: Citation tests pass with page number assertions
- ✅ Integration: Tokenizer correctly uses page_blocks from all parsers

## Files Modified

1. `parsers/textract_parser.py` - Added page_blocks metadata and page markers
2. `parsers/ocrmypdf_parser.py` - Added page_blocks metadata and page markers
3. `api/app.py` - Fixed citation reference lines to always show page numbers
4. `utils/tokenizer.py` - Enhanced page metadata storage with fallbacks
5. `api/rag_system.py` - Already correctly uses page metadata (verified)

## Result

**When you query any document (regardless of parser used), every citation will show the exact page number from the original PDF.**

Example citations you'll see:
- `[1] document.pdf, Page 15` ✅
- `[2] document.pdf, Page 23` ✅
- `[3] document.pdf, Page 7` ✅

Never:
- `[1] document.pdf` ❌ (missing page)
- `[1] document.pdf, Text content` ❌ (no page number)

