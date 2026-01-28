# QA Performance Investigation

## Critical Finding

**QA Reports:**
- English queries: **1.71/10** (17% quality) ❌
- Spanish queries: **4.50/10** (45% quality) ⚠️

**My Testing:**
- English queries: Finding correct answers ✅
- Email query: Working correctly ✅

## Gap Analysis

### Why the Difference?

1. **Different Queries**
   - My test: "Where is the email and contact of Vuormar?"
   - QA might be: More complex or different queries
   
2. **Different Documents**
   - My test: VUORMAR.pdf (Docling parser, 100 chunks)
   - QA might be: Different document versions or parsers

3. **Different Evaluation Criteria**
   - My test: Binary (has email = success)
   - QA: Human evaluation 1-10 scale (more nuanced)

4. **UI vs API Testing**
   - My test: Direct API calls with explicit parameters
   - QA: Might be using UI (parameters may not pass correctly)

5. **Document Selection**
   - My test: Explicit document_id passed
   - QA: Might not be selecting specific documents

## Immediate Actions Needed

### 1. Get QA Test Details ✅ URGENT

**Need from QA Team:**
```
- Exact queries being tested
- Which documents being used
- Testing method (UI or API)
- Evaluation criteria for 1-10 scoring
- Screenshots of failing queries
- Examples of 1.71/10 vs 4.50/10 answers
```

### 2. Test QA's Actual Queries

Once we have their queries, run:
```bash
python3 tests/test_qa_queries.py --queries qa_test_queries.json
```

### 3. Check UI Parameter Passing

Verify UI is actually passing optimized parameters:
- Auto-translate: Should be enabled
- K: Should be 20
- Semantic weight: Should be 0.4
- Document selection: Should be active

### 4. Possible Root Causes

#### Cause A: UI Not Passing Parameters
**Symptom:** API works, UI doesn't
**Solution:** Check frontend parameter passing

#### Cause B: No Document Selection
**Symptom:** Searching all docs instead of specific one
**Solution:** Ensure QA selects specific document

#### Cause C: Complex Queries
**Symptom:** Simple queries work, complex don't
**Solution:** Enable Agentic RAG, increase k further

#### Cause D: Different Document State
**Symptom:** Inconsistent results
**Solution:** Verify document processing status

### 5. Urgent Configuration Adjustments

Based on QA data showing **17% quality for English**, we need more aggressive optimization:

```python
# EMERGENCY CROSS-LANGUAGE FIXES
# shared/config/settings.py

# Current (not working well enough)
DEFAULT_RETRIEVAL_K: int = 20
DEFAULT_SEMANTIC_WEIGHT: float = 0.4

# Proposed URGENT changes
DEFAULT_RETRIEVAL_K: int = 30  # Increase from 20
DEFAULT_SEMANTIC_WEIGHT: float = 0.3  # Reduce from 0.4 (more keyword-focused)
DEFAULT_KEYWORD_WEIGHT: float = 0.7  # Increase from 0.6

# For contact queries, use almost pure keyword search
# In engine.py, adjust contact query detection:
if is_contact_query:
    semantic_weight = 0.2  # Very keyword-focused
    k = 40  # Much higher k for contact info
```

### 6. Parser-Specific Findings

QA Data shows:
- **Docling: 3.25/10** (best)
- **PyMuPDF: 3.13/10**
- **OCRmyPDF: 2.89/10** (worst)

**But:** Difference is only 0.36 points (12%)
**Conclusion:** Parser choice is NOT the main issue

The **2.79 point gap** between English (1.71) and Spanish (4.50) is **162% larger** than parser differences!

### 7. Language-Specific Issues

**Spanish queries (4.50/10)** are also below expectations. This suggests:

1. **Overall document quality issue**
   - Documents may be scanned/low quality
   - Chunking breaking important info
   - OCR errors

2. **Retrieval still not optimal**
   - Even Spanish needs improvement
   - May need k > 20 for all queries

3. **Answer generation issue**
   - LLM not synthesizing well from retrieved chunks
   - Temperature too low (0.0)?
   - Need better prompting?

## Recommended Immediate Changes

### Priority 1: URGENT (Deploy Today)

```python
# shared/config/settings.py

# Increase k significantly
DEFAULT_RETRIEVAL_K: int = 30  # From 20

# More keyword-focused for cross-language
DEFAULT_SEMANTIC_WEIGHT: float = 0.3  # From 0.4
DEFAULT_KEYWORD_WEIGHT: float = 0.7  # From 0.6

# Adjust temperature for better answers
DEFAULT_TEMPERATURE: float = 0.1  # From 0.0 (slightly more creative)
```

### Priority 2: Engine Adjustments

```python
# services/retrieval/engine.py

# For cross-language, be even more aggressive
if detected_language != "en":
    semantic_weight = 0.2  # From 0.4 (much more keyword)
    k = max(30, k * 2)  # From 20 (higher coverage)
    
# For contact queries, use pure keyword
if is_contact_query:
    semantic_weight = 0.1  # Almost pure keyword
    k = 40  # Very high k
```

### Priority 3: UI Verification

Check that UI is passing parameters:
```javascript
// Verify in browser console when querying
console.log("Query params:", {
    auto_translate: true,
    k: 20,
    semantic_weight: 0.4,
    search_mode: "hybrid"
});
```

## Questions for QA Team

1. **What are the exact queries you're testing?**
   - Need full list of English and Spanish queries
   
2. **How are you scoring 1-10?**
   - What's a 1? What's a 10?
   - Example answers for each score?

3. **Are you selecting specific documents?**
   - Or searching all documents?

4. **Are you using the UI or API?**
   - If UI, which settings?

5. **What does a "1.71" answer look like?**
   - Need examples of failing answers

6. **What does a "4.50" answer look like?**
   - Need examples of better Spanish answers

## Action Plan

### Step 1: Information Gathering ⏳
- [  ] Get exact QA test queries
- [  ] Get QA scoring rubric
- [  ] Get example failing answers
- [  ] Get QA testing methodology

### Step 2: Reproduce Issues ⏳
- [  ] Run QA's exact queries
- [  ] Compare my results to QA results
- [  ] Identify specific failure points

### Step 3: Urgent Fixes ⏳
- [  ] Increase k to 30
- [  ] Reduce semantic weight to 0.3
- [  ] Adjust contact query handling
- [  ] Deploy and test

### Step 4: Verification ⏳
- [  ] QA re-tests with new configuration
- [  ] Compare scores before/after
- [  ] Iterate if needed

## Expected Improvements

With more aggressive optimization:
- **Current:** English 1.71/10, Spanish 4.50/10
- **Target:** English 4.0+/10, Spanish 6.0+/10
- **Ideal:** English 6.0+/10, Spanish 8.0+/10

## Next Steps

1. **URGENT:** Get QA team's actual test queries and methodology
2. **URGENT:** Deploy k=30, sw=0.3 configuration
3. **TEST:** Verify improvements with QA
4. **ITERATE:** Adjust based on results

---

**Status:** Investigation in progress  
**Priority:** CRITICAL  
**Next:** Awaiting QA test details

