# Fixes Applied During In-Depth Testing

## Date: 2025-12-18

### Fix 1: Document Name Update Breaking Queries

**Problem:**
When a document name was updated via `PUT /documents/{document_id}`, queries using `document_id` would fail with "No indexes found for selected documents" because:
1. The `document_index_map` wasn't updated with the new name
2. Chunks in the vectorstore still have the old document name in `metadata.source`
3. Query filtering uses the new name, but chunks have the old name

**Solution:**
1. **Updated `PUT /documents/{document_id}` endpoint** (`api/main.py`):
   - When document name is updated, also update `document_index_map` to map new name to same index
   - Store `original_document_name` in document metadata for query compatibility
   - This ensures both old and new names can be used for queries

2. **Updated `POST /query` endpoint** (`api/main.py`):
   - Check for `original_document_name` in document metadata
   - If found, use it for query filtering (since chunks have this name in `metadata.source`)
   - This ensures queries work correctly even after document name updates

**Code Changes:**
```python
# In update_document endpoint:
if request.document_name is not None and old_document_name and request.document_name != old_document_name:
    if (hasattr(service.rag_system, 'document_index_map') and 
        service.rag_system.vector_store_type == "opensearch" and
        old_document_name in service.rag_system.document_index_map):
        index_name = service.rag_system.document_index_map[old_document_name]
        service.rag_system.document_index_map[request.document_name] = index_name
        updates['original_document_name'] = old_document_name  # Store for query compatibility
        service.rag_system._save_document_index_map()

# In query_documents endpoint:
original_name = doc.get('original_document_name')
if original_name and original_name in service.rag_system.document_index_map:
    query_document_name = original_name  # Use original name for query
    logger.info(f"Using original_document_name '{original_name}' for query")
```

**Files Modified:**
- `api/main.py` (lines ~332-359, ~748-770)

### Fix 2: Image Query Test Script Bug

**Problem:**
Test script `test_in_depth_verification.py` was using wrong field name (`query` instead of `question`) for image queries, causing 422 validation errors.

**Solution:**
Updated test script to use correct field name `question` as per `ImageQueryRequest` schema.

**Code Changes:**
```python
# Changed from:
json={"query": query, "k": 5}
# To:
json={"question": query, "k": 5}
```

**Files Modified:**
- `test_in_depth_verification.py`

## Testing Performed

1. **Comprehensive Endpoint Testing:**
   - All 14 endpoint tests passed
   - Document upload, CRUD, queries, and image operations all working

2. **Image Endpoint Testing:**
   - All 9 image tests passed
   - 100 images retrieved successfully
   - OCR text extraction working (98% success rate)

3. **Server Logs Analysis:**
   - No errors found in logs
   - All processing successful
   - Images stored correctly

4. **Verification Testing:**
   - Document name update and query test
   - Image semantic search test
   - Health check test

## Status

✅ **All fixes applied and tested**  
✅ **System functioning correctly**  
✅ **No critical errors found**

