# API Issues - Priority Fix Plan

## Executive Summary
Multiple API endpoints are failing due to interconnected issues. This document provides a prioritized fix plan with root cause analysis and specific solutions.

---

## 🔴 CRITICAL FIXES (Do These First)

### **FIX #1: search_mode Validation Error** ✅ **FIXED**
**Status:** COMPLETED
**Issue:** Query endpoints failing with validation error - `search_mode` has no valid options
**Affected Endpoints:**
- POST /query
- POST /documents/{id}/query  
- POST /query/text

**Root Cause:** `search_mode` defined as `Optional[str]` with no enum validation

**Solution Applied:**
- Changed `search_mode` type to `Optional[Literal['semantic', 'keyword', 'hybrid']]`
- Set default value to `'hybrid'`
- Added proper type hints with `Literal` import

**File Modified:** `api/schemas.py` line 16

---

### **FIX #2: Zero Chunks Created (ROOT CAUSE OF 90% OF ISSUES)**
**Status:** NEEDS INVESTIGATION
**Priority:** CRITICAL - This is blocking most other endpoints

**Issue:** Documents processed but `chunks_created = 0` in metadata
**Affected Endpoints:** ALL query endpoints (no chunks = no results)

**Symptoms:**
- Document status: "failed"
- Chunking error in response body
- Zero chunks in document metadata
- All query endpoints return no results

**Root Cause Analysis:**
1. **Possible Cause A:** Chunking process failing silently
   - Check: `utils/tokenizer.py` TokenTextSplitter
   - Verify: `split_text()` returning empty list
   - Log location: `logs/document_processor.log`

2. **Possible Cause B:** Chunks created but not saved
   - Check: `rag_system.py` line 489 - validation failing
   - Check: `ingestion/document_processor.py` line 410 - stats collection
   - Verify: `add_documents_incremental()` return value

3. **Possible Cause C:** Parser extracting no text
   - Check: Docling parser output
   - Check: PDF compatibility issues
   - Try: PyMuPDF parser as fallback

**Investigation Steps:**
```bash
# 1. Check recent processing logs
tail -n 500 logs/document_processor.log | grep -i "chunks"

# 2. Check if documents have text content
grep -r "extracted.*0.*tokens" logs/

# 3. Test with simple PDF
# Upload a small text-based PDF and check logs
```

**Immediate Fix to Test:**
```python
# In document_processor.py, add defensive check after parsing:
if not parsed_doc.text or len(parsed_doc.text.strip()) == 0:
    logger.error(f"Parser extracted NO TEXT from {file_path}")
    raise ValueError(f"Parser {parser_used} extracted no text. Try different parser.")
```

---

### **FIX #3: Storage Status Endpoint (422/500 Errors)**
**Status:** NEEDS FIX
**Endpoint:** GET /documents/{id}/storage

**Issue:** Validation error 422 and internal server error 500

**Root Cause:** Missing or incorrect schema validation

**Investigation Needed:**
1. Check if endpoint exists in `api/main.py`
2. Verify `StorageStatusResponse` schema matches actual data
3. Check if document_id validation is working

**Quick Fix:**
```python
# Add better error handling in storage status endpoint
try:
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(404, f"Document {document_id} not found")
    
    # Ensure all required fields have defaults
    return StorageStatusResponse(
        document_id=document_id,
        text_chunks_stored=doc.get('chunks_created', 0),
        images_stored=doc.get('images_stored', 0),
        text_index=doc.get('text_index', 'aris-rag-index'),
        images_index=doc.get('images_index', 'aris-rag-images-index'),
        text_storage_status=doc.get('text_storage_status', 'unknown'),
        images_storage_status=doc.get('images_storage_status', 'unknown')
    )
except KeyError as e:
    raise HTTPException(500, f"Missing field in document metadata: {e}")
```

---

## 🟡 HIGH PRIORITY FIXES

### **FIX #4: Image Query Endpoints (No Results)**
**Status:** NEEDS FIX
**Affected Endpoints:**
- POST /query/images
- GET /documents/{id}/images
- GET /documents/{id}/images/summary
- GET /documents/{id}/images/{number}

**Issue:** APIs working but returning no results

**Root Cause:** Images not being stored in OpenSearch images index

**Verification Steps:**
```python
# Check if images were extracted during processing
doc = service.get_document(document_id)
print(f"Images detected: {doc.get('images_detected')}")
print(f"Image count: {doc.get('image_count')}")
print(f"Images stored: {doc.get('images_stored')}")

# Check OpenSearch images index
from vectorstores.opensearch_images_store import OpenSearchImagesStore
images_store = OpenSearchImagesStore(...)
images = images_store.get_images_by_source(document_name)
print(f"Images in index: {len(images)}")
```

**Fix Required:**
1. Verify `_store_images_in_opensearch()` is being called in `document_processor.py`
2. Check if Docling parser is extracting images properly
3. Ensure images are being saved with correct metadata

---

### **FIX #5: Text Query Citations (Wrong/Missing)**
**Status:** NEEDS FIX
**Endpoint:** POST /query/text

**Issue:** 
- Wrong citations provided
- Large PDFs not returning human-readable content
- Citations pointing to wrong pages/sections

**Root Cause:** Citation extraction logic issues

**Investigation:**
```python
# Check citation generation in rag_system.py
# Look for query_with_rag() method
# Verify metadata is being preserved during chunking
```

**Fix Areas:**
1. **Page Number Tracking:** Ensure page numbers are preserved in chunk metadata
2. **Source Attribution:** Verify document name is correctly attached to chunks
3. **Snippet Extraction:** Check if snippet length is appropriate
4. **Large PDF Handling:** May need to adjust chunk size for large documents

---

### **FIX #6: Page Content Endpoint**
**Status:** NEEDS FIX
**Endpoint:** GET /documents/{id}/page/{page}

**Issue:** Not bringing requested content

**Root Cause:** Page number not being used to filter chunks correctly

**Fix:**
```python
# In main.py, improve page filtering logic
# Ensure chunks have 'page' metadata
# Filter chunks where metadata['page'] == page_number
text_chunks = [
    chunk for chunk in all_chunks 
    if chunk.metadata.get('page') == page_number
]
```

---

## 🟢 MEDIUM PRIORITY FIXES

### **FIX #7: Re-store Endpoints (400/500 Errors)**
**Endpoints:**
- POST /documents/{id}/store/text (Error 400)
- POST /documents/{id}/store/images (Docling error)

**Issue:** Cannot re-process documents

**Root Cause:** 
- Text endpoint: Bad request - likely missing file path
- Images endpoint: Docling compatibility issues

**Fix:**
1. Store original file path in document metadata
2. Add file existence check before re-processing
3. Provide better error messages for unsupported PDFs

---

### **FIX #8: Accuracy Check Endpoints (500 Errors)**
**Endpoints:**
- GET /documents/{id}/accuracy
- POST /documents/{id}/verify

**Issue:** Internal server error 500

**Root Cause:** OCR verifier likely failing

**Fix:**
```python
# Add try-catch around OCR verification
try:
    verifier = OCRVerifier()
    result = verifier.verify(document_id)
    return result
except FileNotFoundError:
    raise HTTPException(404, "Original PDF not found")
except Exception as e:
    logger.error(f"OCR verification failed: {e}")
    raise HTTPException(500, f"Verification failed: {str(e)}")
```

---

## 📋 TESTING CHECKLIST

After applying fixes, test in this order:

### Phase 1: Core Functionality
- [ ] Upload simple text-based PDF
- [ ] Verify chunks_created > 0
- [ ] Check document metadata endpoint
- [ ] Test basic query with search_mode='hybrid'

### Phase 2: Query Endpoints
- [ ] POST /query (all documents)
- [ ] POST /documents/{id}/query (single document)
- [ ] POST /query/text (text only)
- [ ] Verify citations are correct

### Phase 3: Image Functionality
- [ ] Upload PDF with images
- [ ] Verify images_stored > 0
- [ ] POST /query/images
- [ ] GET /documents/{id}/images

### Phase 4: Advanced Features
- [ ] GET /documents/{id}/page/{page}
- [ ] GET /documents/{id}/storage
- [ ] POST /documents/{id}/store/text
- [ ] GET /documents/{id}/accuracy

---

## 🔧 DEBUGGING COMMANDS

```bash
# Check API logs
tail -f logs/fastapi.log

# Check document processing logs
tail -f logs/document_processor.log

# Test specific endpoint
curl -X POST http://localhost:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "search_mode": "hybrid"}'

# Check OpenSearch indices
curl -X GET "http://localhost:9200/_cat/indices?v"

# Check document registry
cat storage/document_registry.json | jq '.[] | {id, chunks_created, images_stored}'
```

---

## 🎯 NEXT STEPS

1. **Immediate Action:** Investigate zero chunks issue
   - Check logs for chunking errors
   - Test with simple PDF
   - Verify parser is extracting text

2. **Quick Wins:** Fix remaining validation errors
   - Storage status endpoint
   - Accuracy check endpoints

3. **Comprehensive Testing:** Once chunks are being created
   - Test all query endpoints
   - Verify image extraction
   - Check citation accuracy

---

## 📞 SUPPORT INFORMATION

If issues persist after fixes:
1. Check `logs/fastapi.log` for detailed error traces
2. Verify OpenSearch connection: `AWS_OPENSEARCH_DOMAIN` in .env
3. Test with PyMuPDF parser instead of Docling
4. Ensure embedding model is accessible (OpenAI API key valid)

---

**Last Updated:** December 26, 2025
**Status:** Fix #1 Complete, Investigating Fix #2
