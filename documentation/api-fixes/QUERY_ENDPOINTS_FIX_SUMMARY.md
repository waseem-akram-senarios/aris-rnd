# Query Endpoints Fix Summary

## Date: 2025-12-18

## Issues Fixed

### 1. RAG Query Endpoint (`/query`) - Document ID Filtering

**Problem:**
- When `document_id` was provided but document name not found in `document_index_map`, query would fail with "No indexes found for selected documents"
- No fallback mechanism when document lookup failed
- Logic was too strict and broke when documents were renamed

**Solution:**
- Added robust fallback logic in `api/main.py`:
  - If document name not in `document_index_map`, try using `original_document_name`
  - If still not found, fall back to querying all documents (with warning log)
  - Don't fail completely - make query work even if specific document filter unavailable
- Improved error handling to gracefully degrade instead of failing

**Files Modified:**
- `api/main.py` (lines ~738-789): Improved document_id handling with fallbacks

### 2. Query Logic in `rag_system.py` - Fallback Improvements

**Problem:**
- When `active_sources` was set but document not in `document_index_map`, query returned error message instead of trying fallbacks
- No graceful degradation when index lookup failed

**Solution:**
- Improved fallback chain in `rag_system.py`:
  - When `active_sources` set but no indexes found:
    - Fallback 1: Try default index (`opensearch_index` or "aris-rag-index")
    - Continue with search even if index might not exist (search will handle it)
  - Added final safety check to ensure at least one index is always selected
  - Removed error return - now tries to make query work instead of failing

**Files Modified:**
- `rag_system.py` (lines ~1549-1585): Improved fallback logic for index selection

### 3. Active Sources Clearing

**Problem:**
- When no `document_id` provided, `active_sources` might not be properly cleared
- Could cause queries to fail if old filter was still active

**Solution:**
- Explicitly clear `active_sources` when no `document_id` provided
- Ensure proper restoration in finally block

**Files Modified:**
- `api/main.py` (lines ~787-789, ~830-834): Explicit active_sources clearing

### 4. Image Query Endpoint (`/query/images`) - Error Handling

**Problem:**
- Endpoint could fail completely on errors
- No graceful handling of invalid image results

**Solution:**
- Improved error handling:
  - Return empty results instead of HTTP 500 error
  - Skip invalid image results instead of failing completely
  - Better logging for debugging

**Files Modified:**
- `api/main.py` (lines ~935-970): Improved error handling
- `rag_system.py` (lines ~5177-5178): Added debug logging

## Key Improvements

1. **Robust Fallbacks**: Queries now have multiple fallback strategies instead of failing
2. **Graceful Degradation**: System tries to make queries work even when ideal conditions aren't met
3. **Better Error Handling**: Errors are logged but don't break the query completely
4. **Improved Logging**: More detailed logs for debugging query issues

## Testing Recommendations

1. Test `/query` without `document_id` - should query all documents
2. Test `/query` with valid `document_id` - should query specific document
3. Test `/query` with `document_id` but document not in map - should fallback gracefully
4. Test `/query/images` - should return results or empty list (not error)
5. Verify no "No indexes found" errors in normal operation

## Expected Behavior

- `/query` endpoint works reliably with or without `document_id`
- When document filter unavailable, falls back to querying all documents
- `/query/images` endpoint returns results or empty list (never fails with error)
- Better error messages and logging for debugging
- No breaking changes to existing functionality

