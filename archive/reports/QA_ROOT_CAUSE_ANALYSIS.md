# QA Root Cause Analysis - Document Identification Failure

## Critical Issues Identified

### Issue #1: "RAG is not identifying the document, no information fetched"

**Reported By:** QA Team  
**Affected Parsers:** Docling (and potentially all parsers)  
**Severity:** CRITICAL

#### Root Cause

**51 out of 95 documents (54%) have incomplete metadata:**

1. **Missing `vector_store_type` field:** 50 documents have `vector_store_type: "unknown"`
2. **Missing `text_index` field:** 51 documents don't have this field
3. **Consequence:** Retrieval system cannot locate these documents

#### Investigation Details

```bash
# Documents in registry
Total documents: 95
Documents WITH text_index: 44
Documents WITHOUT text_index: 51

# Vector store type distribution
Unknown vector_store_type: 50
FAISS: 1
OpenSearch: 44
```

#### Why This Happens

**Historical Context:**
- Older documents were processed before `vector_store_type` field was added to metadata
- The `text_index` field is only populated for OpenSearch, not FAISS
- System is currently using **FAISS** (not OpenSearch)
- Document registry has mixed metadata schemas from different versions

**Code Location:**
```python
# services/ingestion/processor.py:735-745
doc_metadata['vector_store_type'] = self.rag_system.vector_store_type
if self.rag_system.vector_store_type.lower() == 'opensearch':
    # Only sets text_index for OpenSearch!
    doc_metadata['text_index'] = self.rag_system.opensearch_index
    doc_metadata['storage_location'] = 'opensearch_cloud'
else:
    doc_metadata['storage_location'] = 'local_faiss'
    # No text_index set for FAISS!
```

---

### Issue #2: 0% Similarity on Correct Citations

**Reported By:** QA Team  
**Example:** PyMuPDF fetched correct answer but showed "0% similarity index for first citation"

#### Root Cause

The similarity percentage calculation in `_rank_citations_by_relevance` handles equal scores, but there may be edge cases:

1. **Mixed scoring systems:** Some chunks use distance (lower = better), others use similarity (higher = better)
2. **Score normalization issues:** When all scores are very close, the calculation can produce 0%
3. **Reranking interference:** FlashRank reranking may reset scores

#### Code Location

```python
# services/retrieval/engine.py:1100-1150
def _rank_citations_by_relevance(self, citations: List[Dict]) -> List[Dict]:
    # Handles equal scores, but edge cases exist
    if score_range < 0.0001:
        if idx == 0:
            citation['similarity_percentage'] = 100.0
        else:
            citation['similarity_percentage'] = 95.0
```

---

### Issue #3: Incorrect Metadata (Wrong Image/Page Numbers)

**Reported By:** QA Team  
**Example:** "100% similarity but mentioned image 4 which is not the case"

#### Root Cause

**Metadata Propagation Issues:**

1. **Page blocks vs chunks:** System uses page_blocks for accurate citations, but metadata may not align
2. **Image numbering:** Image references in text don't match actual image positions
3. **Parser differences:** Different parsers extract different metadata structures

#### Investigation Needed

- Check how page/image metadata flows from parser → chunks → citations
- Verify Docling's image extraction and numbering
- Test with documents that have known image positions

---

### Issue #4: Incomplete Answers (70-90% Information)

**Reported By:** QA Team  
**Example:** PyMuPDF fetched "around 70% information" for contact queries

#### Root Causes

**Multiple Contributing Factors:**

1. **Insufficient k value:** Even with k=30, contact info may be scattered across more chunks
2. **Chunking breaks context:** Email on one page, phone on another → different chunks
3. **Reranking drops relevant chunks:** FlashRank may demote chunks with partial info
4. **LLM synthesis issues:** Temperature=0.1 may be too deterministic to combine scattered info

#### Current Mitigations

```python
# Already implemented:
- k=40 for contact queries (100% increase)
- semantic_weight=0.1 for contact queries (90% keyword)
- Cross-language k=30 minimum

# May need:
- k=50+ for contact queries
- Disable reranking for contact queries
- Higher temperature (0.2-0.3) for better synthesis
```

---

### Issue #5: Query Variation Instability

**Reported By:** QA Team  
**Example:** Same question in different phrasings gives different results (70% vs 90%)

#### Root Cause

**Query Processing Variability:**

1. **Translation differences:** "What is" vs "Where is" may translate differently
2. **Keyword matching:** Different phrasings trigger different keywords
3. **Semantic embedding:** Slight phrasing changes affect vector similarity
4. **Auto-adjustments:** System auto-adjusts parameters based on query detection

#### Example

```
Query 1: "what is the email and contact of vuormar?"
- Detected as: contact query
- Result: 70% information

Query 2: "Where is the email and contact of vuormar?"
- Detected as: location + contact query
- Auto-translate enabled
- Result: 90% information
```

---

## Immediate Fixes Required

### Priority 1: Document Identification (CRITICAL)

**Problem:** 51 documents cannot be found due to missing metadata

**Solution:**

1. **Backfill `vector_store_type`:**
   - Check current system configuration (FAISS or OpenSearch)
   - Update all documents with `vector_store_type: "faiss"` or `"opensearch"`

2. **Backfill `text_index`:**
   - For OpenSearch: `text_index = f"aris-doc-{document_id}"`
   - For FAISS: `text_index = "faiss-shared"` (placeholder)

3. **Update `document_index_map.json`:**
   - Add all documents to the mapping
   - Ensure retrieval can find them

**Implementation:**
```bash
# Run migration script (after fixing vector_store_type detection)
python3 scripts/migrate_add_text_index.py
```

---

### Priority 2: Fix 0% Similarity

**Problem:** Correct citations showing 0% similarity

**Solution:**

1. **Enhanced logging:** Add debug logs to track score transformation
2. **Score validation:** Ensure scores are in expected range before normalization
3. **Reranking audit:** Check if FlashRank is resetting scores incorrectly

**Implementation:**
```python
# Add to _rank_citations_by_relevance
logger.debug(f"Citation {i}: raw_score={raw_score}, normalized={similarity_percentage}%")

# Validate score range
if similarity_percentage < 0 or similarity_percentage > 100:
    logger.warning(f"Invalid similarity percentage: {similarity_percentage}% for citation {i}")
    similarity_percentage = max(0, min(100, similarity_percentage))
```

---

### Priority 3: Fix Metadata Accuracy

**Problem:** Wrong page/image numbers in citations

**Solution:**

1. **Metadata validation:** Verify page_blocks metadata during ingestion
2. **Parser audit:** Check Docling's image extraction logic
3. **Citation mapping:** Ensure chunk metadata correctly maps to source

**Implementation:**
- Add validation in `processor.py` after parsing
- Log metadata structure for debugging
- Test with known documents

---

### Priority 4: Improve Answer Completeness

**Problem:** Only 70-90% of information retrieved

**Solution:**

1. **Increase k for contact queries:** 40 → 50
2. **Disable reranking for contact queries:** Reranking may drop relevant chunks
3. **Higher temperature:** 0.1 → 0.3 for better synthesis
4. **Multi-pass retrieval:** First pass for email, second pass for phone

**Implementation:**
```python
# In engine.py, contact query handling
if is_contact_query:
    k = max(50, k * 2)  # Increase from 40
    semantic_weight = 0.1
    # Disable reranking for contact queries
    use_reranking = False
    # Higher temperature for synthesis
    temperature = 0.3
```

---

### Priority 5: Stabilize Query Variations

**Problem:** Different phrasings give inconsistent results

**Solution:**

1. **Query normalization:** Standardize queries before processing
2. **Consistent auto-adjustments:** Log all parameter changes
3. **Query expansion:** Always include synonyms and variations
4. **Ensemble retrieval:** Retrieve with multiple query variations and merge results

**Implementation:**
```python
# Query normalization
def normalize_query(question: str) -> str:
    # Convert "Where is X?" to "What is X?"
    # Standardize contact-related phrasings
    # Remove filler words
    return normalized_question

# Ensemble retrieval
def retrieve_with_variations(question: str, k: int) -> List[Document]:
    variations = generate_query_variations(question)
    all_docs = []
    for variation in variations:
        docs = retrieve(variation, k=k//len(variations))
        all_docs.extend(docs)
    return deduplicate_and_rerank(all_docs, k=k)
```

---

## Testing Plan

### Test Case 1: Document Identification

```python
# Test that all documents can be found
documents = registry.get_all_documents()
for doc in documents:
    result = query_with_rag(
        question=f"What is in {doc['document_name']}?",
        active_sources=[doc['document_name']]
    )
    assert len(result['citations']) > 0, f"Document not found: {doc['document_name']}"
```

### Test Case 2: Similarity Scores

```python
# Test that similarity scores are never 0% for relevant results
result = query_with_rag(question="test query", k=10)
for citation in result['citations']:
    assert citation['similarity_percentage'] > 0, "0% similarity on citation"
    assert citation['similarity_percentage'] <= 100, "Invalid similarity percentage"
```

### Test Case 3: Metadata Accuracy

```python
# Test that page/image numbers are correct
result = query_with_rag(question="Where is the email?", k=10)
for citation in result['citations']:
    # Verify page number exists in document
    assert citation['page'] <= document.total_pages
    # Verify image number if referenced
    if 'image' in citation:
        assert citation['image'] <= document.total_images
```

### Test Case 4: Answer Completeness

```python
# Test that contact queries retrieve all information
result = query_with_rag(question="What is the email and phone number?", k=50)
answer = result['answer'].lower()
assert 'email' in answer or '@' in answer, "Email not found"
assert 'phone' in answer or any(char.isdigit() for char in answer), "Phone not found"
```

### Test Case 5: Query Variation Consistency

```python
# Test that different phrasings give similar results
variations = [
    "What is the email of vuormar?",
    "Where is the email of vuormar?",
    "vuormar email address",
    "contact email for vuormar"
]

results = [query_with_rag(q, k=30) for q in variations]
# Check that all results contain similar information
for i in range(len(results)-1):
    similarity = compare_answers(results[i]['answer'], results[i+1]['answer'])
    assert similarity > 0.7, f"Inconsistent results: {similarity}"
```

---

## Deployment Plan

### Phase 1: Emergency Fixes (Today)

1. ✅ Deploy cross-language optimizations (k=30, sw=0.3)
2. ⏳ Run migration to backfill missing metadata
3. ⏳ Restart services to load updated mappings
4. ⏳ Test with QA's failing queries

### Phase 2: Metadata Fixes (Tomorrow)

1. ⏳ Fix 0% similarity calculation
2. ⏳ Validate page/image metadata
3. ⏳ Enhanced logging for debugging
4. ⏳ Deploy and test

### Phase 3: Answer Quality (This Week)

1. ⏳ Increase k for contact queries (50+)
2. ⏳ Disable reranking for contact queries
3. ⏳ Higher temperature for synthesis
4. ⏳ Query normalization
5. ⏳ Deploy and test

### Phase 4: Stability (Next Week)

1. ⏳ Ensemble retrieval
2. ⏳ Query variation handling
3. ⏳ Comprehensive testing
4. ⏳ Performance optimization

---

## Status

**Date:** 2026-01-14  
**Priority:** CRITICAL  
**Status:** Investigation Complete, Fixes In Progress  
**Next:** Run migration and test

---

## Questions for QA Team

1. **Which documents are failing?**
   - Specific document names and IDs
   - Which parsers were used?

2. **Exact queries that fail?**
   - Word-for-word questions
   - Expected vs actual answers

3. **Testing environment?**
   - UI or API?
   - Which settings selected?
   - Document selection method?

4. **Scoring methodology?**
   - How is 1-10 scale determined?
   - What's a 5? What's an 8?
   - Examples of each score level?

---

## Conclusion

The QA report revealed **5 critical issues**, with the most severe being **document identification failure** affecting 54% of documents. This is caused by incomplete metadata from older ingestion runs.

**Immediate actions:**
1. Backfill missing metadata (vector_store_type, text_index)
2. Fix similarity calculation edge cases
3. Increase k and adjust parameters for contact queries
4. Stabilize query variation handling

**Expected improvements after fixes:**
- Document identification: 54% failing → 0% failing
- Similarity scores: 0% anomalies → accurate percentages
- Answer completeness: 70% → 95%+
- Query consistency: Variable → Stable


