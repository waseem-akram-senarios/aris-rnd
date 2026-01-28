# Citation Fix Implementation Summary

## Problem
The RAG system consistently cites **Page 10** instead of **Page 4** for answers located in transcribed images from the 'EM11 MK' document.

## Root Cause
Image-transcribed content was losing page number metadata during chunking and retrieval. The system wasn't properly prioritizing image-specific page metadata over generic page extraction methods.

## Fixes Implemented

### 1. Enhanced Page Extraction in Retrieval (`services/retrieval/engine.py`)

**Changes to `_extract_page_number()` method:**

- ✅ **Enhanced image_ref checking**: Now checks multiple fields (`page`, `image_page`, `source_page`) in `image_ref` dictionary
- ✅ **Added HTML marker detection**: Detects `<!-- image page=X -->` patterns in transcribed content
- ✅ **Improved page marker detection**: Checks for `--- Page X ---` markers in image content (first 200 chars instead of 100)
- ✅ **Better pattern matching**: Enhanced regex patterns to catch more image page reference formats

**Key improvements:**
```python
# Now checks multiple fields in image_ref
img_page = image_ref.get('page') or image_ref.get('image_page') or image_ref.get('source_page')

# Detects HTML-style markers
html_marker_match = re.search(r'<!--\s*image\s+page\s*=\s*(\d+)\s*-->', chunk_text, re.IGNORECASE)

# Checks page markers in first 200 chars (was 100)
page_marker_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text[:200])
```

### 2. Enhanced Metadata Assignment During Chunking (`services/ingestion/engine.py`)

**Changes to `_assign_metadata_to_chunks()` method:**

- ✅ **Image page mapping**: Builds a map of `image_index -> page` from image references
- ✅ **Priority-based assignment**: 
  1. First checks if chunk has `image_index` and looks it up in image page map
  2. Then checks for `image_ref` in chunk metadata
  3. Falls back to existing page_blocks logic
- ✅ **Multi-field page storage**: Sets `page`, `source_page`, and `image_page` for redundancy
- ✅ **Extraction method tracking**: Records how page was determined (`image_metadata`, `image_ref`, etc.)

**Key improvements:**
```python
# Build image page mapping
image_page_map = {}  # Map image_index -> page
for block in page_blocks:
    if block.get('type') == 'image':
        img_idx = block.get('image_index')
        img_page = block.get('page') or block.get('image_page')
        if img_idx is not None and img_page is not None:
            image_page_map[img_idx] = img_page

# Priority 1: Check image_index in map
if chunk_image_idx in image_page_map:
    img_page = image_page_map[chunk_image_idx]
    chunk.metadata['page'] = img_page
    chunk.metadata['source_page'] = img_page
    chunk.metadata['image_page'] = img_page
    chunk.metadata['page_extraction_method'] = 'image_metadata'
```

### 3. Enhanced Tokenizer Image Metadata Preservation (`shared/utils/tokenizer.py`)

**Changes to `split_documents()` method:**

- ✅ **Image page override**: When `chunk_image_ref` is found, extracts page from it and overrides chunk page metadata
- ✅ **Redundant storage**: Sets `page`, `source_page`, and `image_page` from image reference
- ✅ **Method tracking**: Records `page_extraction_method` as `'image_ref_tokenizer'`
- ✅ **Debug logging**: Logs when image page is set from image_ref

**Key improvements:**
```python
if chunk_image_ref:
    # Extract page from image_ref
    img_page = chunk_image_ref.get('page') or chunk_image_ref.get('image_page')
    if img_page:
        # Override page metadata with image's page number
        chunk_metadata_copy['page'] = img_page
        chunk_metadata_copy['source_page'] = img_page
        chunk_metadata_copy['image_page'] = img_page
        chunk_metadata_copy['page_extraction_method'] = 'image_ref_tokenizer'
```

## Testing Requirements

### Test Case 1: EM11 MK Document
- **Document**: EM11 MK
- **Query**: "how can the heating layer surface be cleaned?" / "Cómo se puede limpiar la superficie de la capa de calentamiento?"
- **Expected Result**: Citation should show **Page 4** (not Page 10)
- **Validation**: 
  - Check that `image_page` metadata is present in retrieved chunks
  - Verify `page_extraction_method` is `'image_metadata'` or `'image_ref'`
  - Confirm citation shows Page 4

### Test Case 2: Verify Metadata Flow
1. **Ingestion**: Check that image metadata is properly stored during document processing
2. **Chunking**: Verify that chunks from images have correct `image_page` metadata
3. **Retrieval**: Confirm that `_extract_page_number()` correctly extracts page from image metadata
4. **Citation**: Validate that final citation shows correct page number

### Test Case 3: Multi-Page Image Content
- Test with documents containing images on multiple pages
- Verify each image-transcribed chunk cites the correct source page

## Monitoring

### Log Messages to Watch For

**During Ingestion:**
```
Tokenizer: Set page X from image_ref for chunk Y
```

**During Retrieval:**
```
📸 [IMAGE PAGE] Page X from image_ref metadata (image Y)
📸 [IMAGE PAGE] Page X from image_page metadata
📸 [IMAGE PAGE] Page X from HTML marker (<!-- image page=X -->)
📸 [IMAGE PAGE] Page X from page marker (--- Page X ---) in image content
```

### Metrics to Track
- `page_extraction_method` distribution (should see `'image_metadata'` and `'image_ref'` for image content)
- Page confidence scores (should be 0.9-1.0 for image metadata)
- Citation accuracy (correct page / total citations)

## Next Steps

### Immediate Actions
1. ✅ Code changes implemented
2. ⏳ **Re-index EM11 MK document** to ensure new metadata is stored
3. ⏳ **Run QA test suite** with the specific test case
4. ⏳ **Verify citations** show Page 4 instead of Page 10

### Optional Enhancements (Future)
- Add page marker injection during parser processing (inject `<!-- image page=X -->` into OCR text)
- Implement page-aware reranking that boosts high-confidence image citations
- Add validation to prevent invalid page numbers from being indexed

## Files Modified

1. `services/retrieval/engine.py` - Enhanced `_extract_page_number()` method
2. `services/ingestion/engine.py` - Enhanced `_assign_metadata_to_chunks()` method  
3. `shared/utils/tokenizer.py` - Enhanced image metadata preservation in `split_documents()`

## Expected Outcome

After re-indexing the EM11 MK document and running queries:
- ✅ Image-transcribed content will correctly cite **Page 4** instead of Page 10
- ✅ Page metadata will be preserved through the entire pipeline (ingestion → chunking → retrieval → citation)
- ✅ Multiple redundant page fields ensure page number is never lost
- ✅ Enhanced logging will help diagnose any remaining issues

## Notes

- The "Page 10" issue may have been caused by a default value or a chunk with incorrect metadata being prioritized. The enhanced logging will help identify the source if the issue persists.
- **Important**: Documents must be re-indexed after these changes for the fixes to take effect, as existing chunks may have incorrect metadata.
- The fixes are backward-compatible - existing documents will continue to work, but may need re-indexing for optimal accuracy.

