# RAG Citation Error Fix Strategy: Page Number Accuracy for Image-Transcribed Content

## Problem Summary

**Issue**: The RAG system consistently cites **Page 10** instead of **Page 4** for answers located in transcribed images from the 'EM11 MK' document.

**Root Cause Analysis**:
1. **Metadata Loss During Chunking**: When image OCR text is chunked, the original page number metadata may not be properly preserved or associated with the chunk.
2. **Page Blocks Misalignment**: The `page_blocks` metadata structure may not correctly map transcribed image content to its source page.
3. **Retrieval Priority**: The retriever may be selecting chunks with incorrect page metadata when multiple similar chunks exist.

---

## Comprehensive Solution Framework

### 1. Pre-processing/Chunking Strategy

#### 1.1 Enhanced Image Metadata Preservation

**Problem**: Image-transcribed content loses page association during chunking.

**Solution**: Implement a robust metadata preservation pipeline that explicitly tracks image-to-page relationships.

**Implementation Steps**:

1. **Parser-Level Enhancement** (in `services/ingestion/parsers/`):
   - When extracting images, store explicit page metadata:
     ```python
     image_metadata = {
         'image_index': img_idx,
         'page': page_num + 1,  # Explicit page number
         'image_page': page_num + 1,  # Duplicate for redundancy
         'source_page': page_num + 1,  # Triple redundancy
         'is_ocr_content': True,
         'ocr_text': ocr_text,
         'bbox': image_bbox
     }
     ```

2. **Chunking-Level Enhancement** (in `services/ingestion/engine.py`):
   - Modify `_assign_metadata_to_chunks()` to prioritize image metadata:
     ```python
     def _assign_metadata_to_chunks(self, chunks: List[Document], original_metadata: Dict) -> List[Document]:
         # ... existing code ...
         
         # NEW: Check for image-related metadata in original_metadata
         image_refs = original_metadata.get('image_refs', [])
         image_page_map = {}  # Map image_index -> page
         
         for img_ref in image_refs:
             if isinstance(img_ref, dict):
                 img_idx = img_ref.get('image_index')
                 img_page = img_ref.get('page')
                 if img_idx is not None and img_page is not None:
                     image_page_map[img_idx] = img_page
         
         for chunk in chunks:
             # PRIORITY 1: Check if chunk contains image markers
             chunk_text = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
             
             # Check for image index in chunk metadata
             chunk_image_idx = chunk.metadata.get('image_index')
             if chunk_image_idx is not None and chunk_image_idx in image_page_map:
                 # This chunk is from an image - use image's page number
                 chunk.metadata['page'] = image_page_map[chunk_image_idx]
                 chunk.metadata['source_page'] = image_page_map[chunk_image_idx]
                 chunk.metadata['image_page'] = image_page_map[chunk_image_idx]
                 chunk.metadata['has_image'] = True
                 chunk.metadata['page_extraction_method'] = 'image_metadata'
                 continue
             
             # PRIORITY 2: Check for image markers in text
             if '<!-- image -->' in chunk_text or chunk.metadata.get('has_image', False):
                 # Try to extract page from image reference
                 image_ref = chunk.metadata.get('image_ref')
                 if image_ref and isinstance(image_ref, dict):
                     img_page = image_ref.get('page')
                     if img_page:
                         chunk.metadata['page'] = img_page
                         chunk.metadata['source_page'] = img_page
                         chunk.metadata['image_page'] = img_page
                         chunk.metadata['page_extraction_method'] = 'image_ref'
                         continue
             
             # ... rest of existing logic ...
     ```

3. **Page Blocks Enhancement** (in `services/ingestion/processor.py`):
   - Ensure page_blocks correctly associate image OCR text with source pages:
     ```python
     # When creating page_blocks for image content:
     if page_has_images:
         for img_idx, img_info in enumerate(image_list):
             # Create a dedicated page_block for image OCR content
             page_blocks.append({
                 'type': 'image',
                 'page': page_num + 1,  # Explicit page number
                 'image_index': img_idx,
                 'text': ocr_text,  # Transcribed image text
                 'start_char': image_start_char,
                 'end_char': image_end_char,
                 'is_ocr': True,
                 'image_page': page_num + 1  # Redundant page reference
             })
     ```

#### 1.2 Chunk-Level Page Marker Injection

**Problem**: Text markers like "--- Page X ---" may not be present in transcribed image content.

**Solution**: Inject explicit page markers into image-transcribed chunks during pre-processing.

**Implementation**:
```python
# In DocumentProcessor.process_document(), before chunking:
if page_has_images and ocr_text:
    # Inject explicit page marker at the start of OCR text
    page_marker = f"--- Page {page_num + 1} ---\n"
    ocr_text_with_marker = page_marker + ocr_text
    
    # Also add metadata marker
    ocr_text_with_marker = f"<!-- image page={page_num + 1} -->\n" + ocr_text_with_marker
```

---

### 2. Metadata/Indexing Strategy

#### 2.1 Multi-Layer Page Metadata

**Problem**: Single metadata field may be lost or overwritten.

**Solution**: Store page number in multiple redundant metadata fields with different priorities.

**Implementation**:

1. **Primary Fields** (highest priority):
   - `source_page`: The original page number from the document
   - `page`: Standard page number
   - `image_page`: Page number specifically for image content

2. **Secondary Fields** (fallback):
   - `page_from_blocks`: Page extracted from page_blocks
   - `page_from_marker`: Page extracted from text markers

3. **Validation Fields**:
   - `page_confidence`: Confidence score (0.0-1.0)
   - `page_extraction_method`: How the page was determined

**Code Example**:
```python
# In _assign_metadata_to_chunks():
chunk.metadata.update({
    'source_page': page_num,  # Primary
    'page': page_num,  # Primary
    'image_page': page_num if has_image else None,  # Image-specific
    'page_from_blocks': page_from_blocks,  # Secondary
    'page_confidence': 1.0 if has_image else 0.9,  # Validation
    'page_extraction_method': 'image_metadata' if has_image else 'page_blocks'
})
```

#### 2.2 Indexing-Time Validation

**Problem**: Invalid page numbers may be indexed.

**Solution**: Validate and correct page numbers before indexing.

**Implementation** (in `services/ingestion/engine.py`):
```python
def _validate_and_correct_page_metadata(self, chunk: Document, doc_pages: int) -> Document:
    """Validate and correct page metadata before indexing."""
    page = chunk.metadata.get('page') or chunk.metadata.get('source_page')
    
    # Validation checks
    if page is None:
        logger.warning(f"Chunk has no page metadata, cannot validate")
        return chunk
    
    if page < 1:
        logger.warning(f"Invalid page {page} (< 1), correcting to 1")
        chunk.metadata['page'] = 1
        chunk.metadata['source_page'] = 1
    
    if doc_pages and page > doc_pages:
        logger.warning(f"Page {page} exceeds document pages {doc_pages}, correcting to {doc_pages}")
        chunk.metadata['page'] = doc_pages
        chunk.metadata['source_page'] = doc_pages
    
    # Ensure all page fields are consistent
    if 'source_page' not in chunk.metadata:
        chunk.metadata['source_page'] = chunk.metadata['page']
    if 'image_page' in chunk.metadata and chunk.metadata['image_page'] != chunk.metadata['page']:
        # Image page should match main page
        chunk.metadata['image_page'] = chunk.metadata['page']
    
    return chunk
```

#### 2.3 OpenSearch Index Schema Enhancement

**Problem**: OpenSearch may not properly store or retrieve page metadata.

**Solution**: Ensure OpenSearch mapping includes all page-related fields with proper types.

**Implementation**:
```python
# In vectorstores/opensearch_store.py or similar:
page_metadata_mapping = {
    "properties": {
        "page": {"type": "integer"},
        "source_page": {"type": "integer"},
        "image_page": {"type": "integer"},
        "page_confidence": {"type": "float"},
        "page_extraction_method": {"type": "keyword"},
        "has_image": {"type": "boolean"},
        "image_index": {"type": "integer"}
    }
}
```

---

### 3. Retriever/Reranker Logic

#### 3.1 Enhanced Page Extraction Priority

**Problem**: Current `_extract_page_number()` may not prioritize image metadata correctly.

**Solution**: Strengthen the priority hierarchy to always prefer image metadata.

**Implementation** (in `services/retrieval/engine.py`):

```python
def _extract_page_number(self, doc, chunk_text: str) -> tuple:
    """
    Enhanced page extraction with STRICT image metadata priority.
    
    PRIORITY ORDER (updated):
    0. Image metadata (image_ref.page, image_page) - HIGHEST
    1. Character position matching with page_blocks
    2. source_page metadata
    3. page_blocks cross-validation
    4. page metadata
    5. Text markers ("--- Page X ---")
    6. Fallback to page 1
    """
    
    # PRIORITY 0: Image metadata (STRICT - must check first)
    image_ref = doc.metadata.get('image_ref', None)
    image_page = doc.metadata.get('image_page', None)
    has_image = doc.metadata.get('has_image', False)
    image_index = doc.metadata.get('image_index', None)
    
    # Check image_ref first (most reliable)
    if image_ref and isinstance(image_ref, dict):
        img_page = image_ref.get('page') or image_ref.get('image_page')
        if img_page and validate_against_doc(img_page):
            logger.info(f"📸 [IMAGE PAGE] Page {img_page} from image_ref (image {image_ref.get('image_index', '?')})")
            return int(img_page), 1.0  # Highest confidence
    
    # Check image_page metadata
    if image_page and validate_against_doc(image_page):
        logger.info(f"📸 [IMAGE PAGE] Page {image_page} from image_page metadata")
        return int(image_page), 1.0
    
    # Check for image markers in text (for transcribed content)
    if has_image or image_index is not None:
        # Pattern 1: "Image X on Page Y"
        image_page_match = re.search(r'Image\s+\d+\s+on\s+[Pp]age\s+(\d+)', chunk_text)
        if image_page_match:
            img_page_num = int(image_page_match.group(1))
            if validate_against_doc(img_page_num):
                logger.info(f"📸 [IMAGE PAGE] Page {img_page_num} from image marker text")
                return img_page_num, 0.95
        
        # Pattern 2: "<!-- image page=X -->"
        html_marker_match = re.search(r'<!--\s*image\s+page\s*=\s*(\d+)\s*-->', chunk_text)
        if html_marker_match:
            img_page_num = int(html_marker_match.group(1))
            if validate_against_doc(img_page_num):
                logger.info(f"📸 [IMAGE PAGE] Page {img_page_num} from HTML marker")
                return img_page_num, 0.95
        
        # Pattern 3: Early page reference in image content (first 200 chars)
        page_ref_match = re.search(r'[Pp]age\s+(\d+)', chunk_text[:200])
        if page_ref_match:
            img_page_num = int(page_ref_match.group(1))
            if validate_against_doc(img_page_num):
                logger.info(f"📸 [IMAGE PAGE] Page {img_page_num} from early page reference")
                return img_page_num, 0.9
    
    # ... rest of existing priority logic (character position, source_page, etc.) ...
```

#### 3.2 Page-Aware Reranking

**Problem**: When multiple chunks have similar content, the wrong page may be selected.

**Solution**: Implement page-aware reranking that penalizes chunks with lower confidence page numbers.

**Implementation** (in `services/retrieval/engine.py`):

```python
def _rank_citations_by_relevance(self, citations: List[Dict], query: str) -> List[Dict]:
    """
    Enhanced ranking that considers page confidence and image metadata.
    """
    # ... existing similarity-based ranking ...
    
    # ENHANCEMENT: Boost citations with high page confidence and image metadata
    for citation in citations:
        page_confidence = citation.get('page_confidence', 0.5)
        has_image = citation.get('has_image', False)
        extraction_method = citation.get('page_extraction_method', 'unknown')
        
        # Boost image-transcribed content with correct page metadata
        if has_image and extraction_method in ('image_metadata', 'image_ref'):
            # Add confidence boost to similarity score
            similarity_score = citation.get('similarity_score', 0.0)
            if similarity_score > 0:
                # Boost by up to 10% for high-confidence image citations
                confidence_boost = page_confidence * 0.1
                citation['similarity_score'] = min(1.0, similarity_score + confidence_boost)
                citation['page_boost_applied'] = True
    
    # Sort with page confidence as secondary sort key
    citations.sort(key=lambda c: (
        -c.get('similarity_score', -999),  # Primary: similarity (descending)
        -c.get('page_confidence', 0.0),  # Secondary: page confidence (descending)
        c.get('page', 999),  # Tertiary: lower page numbers first (for tie-breaking)
        -c.get('source_confidence', 0.0)  # Quaternary: source confidence
    ))
    
    return citations
```

#### 3.3 Page Number Validation in Retrieval

**Problem**: Retrieved chunks may have inconsistent or invalid page numbers.

**Solution**: Validate and correct page numbers during retrieval, before citation generation.

**Implementation**:

```python
def _validate_retrieved_chunk_page(self, doc, chunk_text: str, doc_pages: int) -> int:
    """
    Validate and correct page number for retrieved chunk.
    Returns validated page number.
    """
    # Extract page using enhanced method
    page, confidence = self._extract_page_number(doc, chunk_text)
    
    # Validate against document
    if page < 1:
        logger.warning(f"Invalid page {page} (< 1), correcting to 1")
        return 1, 0.1
    
    if doc_pages and page > doc_pages:
        logger.warning(f"Page {page} exceeds document pages {doc_pages}, correcting to {doc_pages}")
        return doc_pages, 0.1
    
    # If confidence is low and we have image metadata, try to re-extract
    if confidence < 0.5 and doc.metadata.get('has_image', False):
        # Re-check image metadata
        image_page = doc.metadata.get('image_page') or doc.metadata.get('image_ref', {}).get('page')
        if image_page and 1 <= image_page <= (doc_pages or 10000):
            logger.info(f"Re-extracted page {image_page} from image metadata (was {page})")
            return image_page, 0.9
    
    return page, confidence
```

---

## Implementation Priority

### Phase 1: Critical Fixes (Immediate)
1. ✅ Enhance `_extract_page_number()` to strictly prioritize image metadata
2. ✅ Add page marker injection for image-transcribed content
3. ✅ Implement multi-layer page metadata storage

### Phase 2: Robustness (Short-term)
4. ✅ Add page validation before indexing
5. ✅ Implement page-aware reranking
6. ✅ Enhance page_blocks creation for image content

### Phase 3: Optimization (Medium-term)
7. ✅ OpenSearch schema enhancement
8. ✅ Add page confidence scoring
9. ✅ Implement page number validation in retrieval

---

## Testing Strategy

### Test Case 1: Image-Transcribed Content Citation
- **Document**: EM11 MK
- **Query**: "how can the heating layer surface be cleaned?"
- **Expected**: Page 4 citation
- **Current**: Page 10 citation
- **Validation**: Check that `image_page` metadata is correctly extracted and used

### Test Case 2: Multi-Page Image Content
- **Document**: Document with images on multiple pages
- **Query**: Questions targeting specific pages
- **Expected**: Correct page citations for each image
- **Validation**: Verify page numbers match image source pages

### Test Case 3: Mixed Content (Text + Images)
- **Document**: Document with both text and image content
- **Query**: Questions targeting both types
- **Expected**: Correct citations for both text and image content
- **Validation**: Verify page numbers are accurate for both content types

---

## Monitoring and Validation

### Logging Enhancements
Add detailed logging for page extraction:
```python
logger.info(f"[PAGE EXTRACTION] Chunk from {source}: "
           f"page={page}, confidence={confidence}, "
           f"method={extraction_method}, has_image={has_image}")
```

### Metrics Collection
- Track page extraction method distribution
- Monitor page confidence scores
- Alert on low-confidence page extractions

---

## Deployment Checklist

- [ ] Update parser implementations to store image page metadata
- [ ] Enhance `_assign_metadata_to_chunks()` with image metadata priority
- [ ] Update `_extract_page_number()` with strict image metadata priority
- [ ] Implement page marker injection for OCR content
- [ ] Add page validation before indexing
- [ ] Update reranking logic to consider page confidence
- [ ] Test with EM11 MK document and QA questions
- [ ] Validate page citations match expected pages
- [ ] Deploy to staging environment
- [ ] Run full QA test suite
- [ ] Deploy to production

---

## Expected Outcomes

1. **Citation Accuracy**: Image-transcribed content will cite the correct source page (Page 4 instead of Page 10)
2. **Metadata Reliability**: Page numbers will be stored in multiple redundant fields
3. **Retrieval Precision**: Page-aware reranking will prioritize chunks with correct page metadata
4. **System Robustness**: Validation at multiple stages will prevent invalid page numbers from propagating

---

## Notes

- The "Page 10" issue may be related to a default value or a specific chunk that's being incorrectly prioritized. The enhanced logging will help identify the source.
- Consider re-indexing the EM11 MK document after implementing these fixes to ensure correct metadata is stored.
- Monitor the `page_extraction_method` field to understand which extraction method is being used for each citation.

