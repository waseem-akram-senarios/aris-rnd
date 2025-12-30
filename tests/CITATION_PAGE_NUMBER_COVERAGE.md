# Citation Page Number Coverage Documentation

## Overview
This document describes the page number coverage for citations in the ARIS RAG system. All citations (text and image) are guaranteed to have a valid page number (integer >= 1).

## Implementation Details

### Page Number Extraction Strategy
The system uses a multi-tiered approach to extract page numbers:

1. **Highest Confidence (1.0)**: `source_page` metadata field
2. **High Confidence (0.8)**: `page` metadata field  
3. **Medium Confidence (0.6)**: Text marker `--- Page X ---`
4. **Low Confidence (0.4)**: Text marker `Page X` or page ranges
5. **Fallback (0.1)**: Default to page 1 if no page can be determined

### Guaranteed Page Numbers
- **All text citations**: Always have `page >= 1` (defaults to 1 if not found)
- **All image citations**: Always have `page >= 1` (defaults to 1 if not found)
- **All ImageResult objects**: Always have `page >= 1` (defaults to 1 if not found)

### Code Locations

#### Citation Construction
- **Standard RAG**: `api/rag_system.py` line ~2355-2495
- **Agentic RAG**: `api/rag_system.py` line ~4804-4910
- **Find All Occurrences**: `api/rag_system.py` line ~1614-1635
- **API Response Building**: `api/main.py` line ~473-484

#### Page Extraction
- **Primary Method**: `api/rag_system.py::_extract_page_number()` (line ~4157)
  - Returns `(page_number, confidence)` tuple
  - Always returns `(1, 0.1)` as fallback if no page found

#### Schema Enforcement
- **Citation Model**: `api/schemas.py` line ~23-42
  - `page: int = Field(default=1, ge=1)` - Required, defaults to 1, minimum 1
- **ImageResult Model**: `api/schemas.py` line ~193-201
  - `page: int = Field(default=1, ge=1)` - Required, defaults to 1, minimum 1

## Edge Cases Handled

### 1. Missing Metadata
- **Scenario**: Document chunk has no page metadata
- **Solution**: Falls back to page 1 with confidence 0.1
- **Location**: `_extract_page_number()` method

### 2. Invalid Page Numbers
- **Scenario**: Page number exceeds document page count or is out of range
- **Solution**: Validation rejects invalid pages, falls back to page 1
- **Location**: `_extract_page_number()` validation logic

### 3. Text-Only Documents
- **Scenario**: Document has no page markers or metadata
- **Solution**: Defaults to page 1
- **Impact**: All citations will show "Page 1" even if actual page is unknown

### 4. Image Queries
- **Scenario**: Image results from OpenSearch may not have page numbers
- **Solution**: API layer ensures page=1 if missing
- **Location**: `api/main.py` line ~412-423

## Test Coverage

All test assertions verify:
- `citation["page"]` exists
- `citation["page"]` is an integer
- `citation["page"] >= 1`

Test files updated:
- `tests/utils/assertions.py::assert_query_result()` - Enhanced to check all citations
- `tests/api_tests/test_api_query_endpoints.py` - All query tests verify page numbers
- `tests/functional/test_query_features.py` - All query feature tests verify page numbers
- `tests/functional/test_agentic_rag.py` - Agentic RAG tests verify page numbers
- `tests/regression/test_backward_compatibility.py` - Backward compatibility tests verify page numbers
- `tests/e2e/test_query_workflow.py` - E2E tests verify page numbers

## Future Improvements

### Areas for Enhancement
1. **Better Page Detection**: Improve text marker extraction for more accurate page numbers
2. **Document Registry Lookup**: Use document registry to cross-reference page numbers when available
3. **OCR-Based Page Detection**: For scanned documents, use OCR position to infer page numbers
4. **Confidence Reporting**: Expose `page_confidence` in API responses to indicate page number reliability

### Known Limitations
- **Fallback to Page 1**: When page cannot be determined, system defaults to page 1. This may not reflect the actual page.
- **Multi-Page Chunks**: Chunks spanning multiple pages currently use the starting page number.
- **Image-Only Documents**: Images without text markers may default to page 1.

## Summary

✅ **All citations guaranteed to have page numbers**
✅ **Page numbers are always integers >= 1**
✅ **Fallback mechanism ensures no None values**
✅ **Tests enforce page number presence and validity**
✅ **Schema validation ensures type safety**

The system prioritizes having a valid page number (even if it's a best guess) over having None, ensuring the API always returns complete citation information.


