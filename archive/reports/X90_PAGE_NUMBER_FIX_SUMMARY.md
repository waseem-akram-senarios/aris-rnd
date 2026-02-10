# X90 Page Number Accuracy Fix - Summary

## Issues Fixed

### 1. ✅ Filename Resolution to Latest Document ID
**Problem**: When selecting documents by filename, the system might query an older document_id/index instead of the latest version.

**Fix**: 
- Added `get_latest_document_id_by_name()` and `resolve_filenames_to_document_ids()` methods to `DocumentRegistry`
- Updated `GatewayService` to resolve filenames to latest document_ids before querying Retrieval service
- Ensures the most recent version of a document is always queried when selecting by filename

**Files Changed**:
- `storage/document_registry.py`
- `services/gateway/service.py`

### 2. ✅ OpenSearch Metadata Extraction
**Problem**: OpenSearch hybrid search results were not correctly extracting page metadata (`page`, `source_page`, `start_char`, `end_char`) from search hits because LangChain stores metadata at the top level of `_source`, not nested under `metadata`.

**Fix**:
- Updated `hybrid_search()` in `opensearch_store.py` to check both `_source.metadata` and top-level `_source` fields
- Merges essential metadata fields (page, source_page, start_char, end_char, etc.) from both locations
- Ensures page metadata is available for citation extraction

**Files Changed**:
- `vectorstores/opensearch_store.py`

### 3. ✅ Similarity Percentage Calculation
**Problem**: When all similarity scores were equal (or very close), the system was showing misleading 100% similarity for all citations.

**Fix**:
- Updated `_rank_citations_by_relevance()` in `services/retrieval/engine.py` to set `similarity_percentage = None` when all scores are equal (instead of 100%)
- UI updated to display "N/A" when similarity_percentage is None
- Provides more accurate similarity information

**Files Changed**:
- `services/retrieval/engine.py`
- `api/app.py`

### 4. ✅ Regression Tests Added
**Files Added**:
- `tests/test_similarity_percentage_accuracy.py` - Tests for similarity percentage behavior

## Current Status

**Deployed**: All fixes have been deployed to the server and services restarted.

**Remaining Issue**: The X90 document (`1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf`) was ingested **before** these fixes were implemented. The document registry shows:
- `"pages": null` for both existing document_ids
- Page metadata was not stored in OpenSearch during original ingestion

## Next Steps Required

### Re-ingest X90 Document
To get correct page numbers, the X90 document needs to be **re-ingested** with the latest code:

1. **Re-upload the document** via Gateway API or UI:
   ```bash
   curl -X POST http://44.221.84.58:8500/documents \
     -F "file=@1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf" \
     -F "parser_preference=ocrmypdf"
   ```

2. **Wait for processing to complete** (check status endpoint)

3. **Query again** - The new document_id will have:
   - Proper `pages` metadata in registry
   - Page metadata (`page`, `source_page`, `start_char`, `end_char`) stored in OpenSearch
   - Correct page numbers in citations (not always Page 1)

### Verification
After re-ingestion, query the document and verify:
- ✅ Citations show correct page numbers (not always Page 1)
- ✅ Similarity percentage is meaningful (not misleading 100% or None when scores differ)
- ✅ Filename resolution picks the latest document_id automatically

## Technical Details

### How Page Numbers Are Extracted (Priority Order)
1. **Character position matching** (highest confidence: 1.0) - Uses `start_char`/`end_char` with `page_blocks`
2. **source_page metadata** (with cross-validation)
3. **page_blocks matching** (with cross-validation)
4. **page metadata** (with cross-validation)
5. **Text markers** (e.g., "--- Page X ---")
6. **Fallback to page 1** (only if all above fail)

### Why Re-ingestion Is Needed
The original ingestion happened before:
- The OpenSearch metadata extraction fix
- The enhanced page metadata storage in tokenizer
- The proper page_blocks generation in ocrmypdf parser

Re-ingestion will ensure all page metadata is properly stored and can be retrieved correctly.
