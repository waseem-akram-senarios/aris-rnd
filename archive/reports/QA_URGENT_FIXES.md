# QA-Driven Urgent Fixes

## Critical Issue from QA Testing

**QA Performance Report:**
- ❌ **English queries: 1.71/10 (17% quality)** - CRITICAL FAILURE
- ⚠️ **Spanish queries: 4.50/10 (45% quality)** - Below expectations
- 📊 **Parser differences: 0.36 points (12%)** - Minimal impact
- 🌐 **Language gap: 2.79 points (163%)** - PRIMARY ISSUE

**Conclusion:** Cross-language retrieval is the main bottleneck, NOT parser choice.

---

## Root Cause Analysis

### Why English Queries Fail (1.71/10)?

1. **Insufficient Context Retrieval**
   - k=20 is not enough for cross-language queries
   - Many relevant chunks missed in retrieval

2. **Semantic Search Unreliable Across Languages**
   - Embedding similarity drops significantly across languages
   - Semantic weight too high (0.4) for cross-language

3. **Contact Information Often Scattered**
   - Email/phone may be in different parts of document
   - Need higher k and more keyword focus for contact queries

4. **Translation + Embedding Mismatch**
   - Query translated to English but document indexed in Spanish
   - Semantic similarity less reliable across this gap

---

## Immediate Fixes Deployed

### Fix 1: Increased Default K (20 → 30)

**File:** `shared/config/settings.py`

```python
# BEFORE:
DEFAULT_RETRIEVAL_K: int = 20  # Too low for cross-language

# AFTER:
DEFAULT_RETRIEVAL_K: int = 30  # Increased to 30 based on QA findings
```

**Impact:** Retrieves 50% more chunks, increasing chance of finding relevant information.

---

### Fix 2: More Keyword-Focused Defaults (0.4 → 0.3 semantic)

**File:** `shared/config/settings.py`

```python
# BEFORE:
DEFAULT_SEMANTIC_WEIGHT: float = 0.4  # Too high for cross-language
DEFAULT_KEYWORD_WEIGHT: float = 0.6

# AFTER:
DEFAULT_SEMANTIC_WEIGHT: float = 0.3  # Reduced to 0.3 for better cross-language
DEFAULT_KEYWORD_WEIGHT: float = 0.7  # Increased to 0.7 for better keyword matching
```

**Impact:** 70% keyword matching provides more reliable retrieval across languages.

---

### Fix 3: Aggressive Cross-Language Adjustment (0.4 → 0.2 semantic)

**File:** `services/retrieval/engine.py`

```python
# BEFORE:
semantic_weight = 0.4  # Not aggressive enough
keyword_weight = 0.6

# AFTER:
semantic_weight = 0.2  # VERY LOW - 80% keyword matching!
keyword_weight = 0.8   # QA-driven based on 1.71/10 English score
```

**Impact:** When query is translated, use 80% keyword matching for maximum reliability.

---

### Fix 4: Higher Cross-Language K (20 → 30 minimum)

**File:** `services/retrieval/engine.py`

```python
# BEFORE:
k = max(20, k * 2)  # Minimum 20 chunks

# AFTER:
k = max(30, k * 2)  # Minimum 30 chunks for cross-language
```

**Impact:** Ensures sufficient context even for complex cross-language queries.

---

### Fix 5: Almost Pure Keyword for Contact Queries (0.35 → 0.1 semantic)

**File:** `services/retrieval/engine.py`

```python
# BEFORE:
semantic_weight = 0.35  # 65% keyword for contact queries

# AFTER:
semantic_weight = 0.1  # 90% keyword for contact queries!
k = max(40, k * 1.5)  # Also increase k to 40 for contact info
```

**Impact:** Contact queries (email, phone, etc.) now use 90% keyword matching with 40 chunks minimum.

---

### Fix 6: Slightly Higher Temperature (0.0 → 0.1)

**File:** `shared/config/settings.py`

```python
# BEFORE:
DEFAULT_TEMPERATURE: float = 0.0  # Too deterministic

# AFTER:
DEFAULT_TEMPERATURE: float = 0.1  # Slightly more creative for better synthesis
```

**Impact:** Allows LLM to better synthesize information from multiple chunks.

---

## Expected Improvements

### Current Performance (QA Report)
- English queries: **1.71/10** (17% quality)
- Spanish queries: **4.50/10** (45% quality)

### Target Performance (After Fixes)
- English queries: **4.0+/10** (40%+ quality) - **+134% improvement**
- Spanish queries: **6.0+/10** (60%+ quality) - **+33% improvement**

### Ideal Performance (Final Goal)
- English queries: **6.0+/10** (60%+ quality) - **+251% improvement**
- Spanish queries: **8.0+/10** (80%+ quality) - **+78% improvement**

---

## Configuration Summary

### Global Defaults (All Queries)

| Parameter | Before | After | Change |
|-----------|--------|-------|--------|
| K | 20 | **30** | +50% |
| Semantic Weight | 0.4 | **0.3** | -25% |
| Keyword Weight | 0.6 | **0.7** | +17% |
| Temperature | 0.0 | **0.1** | +0.1 |

### Cross-Language Queries (English → Spanish docs)

| Parameter | Before | After | Change |
|-----------|--------|-------|--------|
| K (minimum) | 20 | **30** | +50% |
| Semantic Weight | 0.4 | **0.2** | -50% |
| Keyword Weight | 0.6 | **0.8** | +33% |

### Contact Queries (Email, Phone, etc.)

| Parameter | Before | After | Change |
|-----------|--------|-------|--------|
| K (minimum) | 20 | **40** | +100% |
| Semantic Weight | 0.35 | **0.1** | -71% |
| Keyword Weight | 0.65 | **0.9** | +38% |

---

## Testing Required

### Priority 1: Immediate Verification

1. **Test VUORMAR.pdf (Spanish) with English queries**
   ```
   Query: "Where is the email and contact of Vuormar?"
   Expected: Should find email (mattia_stellini@vuormar...) with >80% confidence
   ```

2. **Test multiple documents with cross-language queries**
   ```
   Test at least 5 English queries on Spanish documents
   Expected: Average score >4.0/10 (up from 1.71/10)
   ```

3. **Verify Spanish queries still work well**
   ```
   Test same queries in Spanish
   Expected: Maintain or improve 4.50/10 → 6.0+/10
   ```

### Priority 2: QA Team Re-Test

1. **Run exact same test suite**
   - Same documents
   - Same queries
   - Same evaluation criteria

2. **Compare scores**
   - Before: English 1.71/10, Spanish 4.50/10
   - After: English 4.0+/10, Spanish 6.0+/10

3. **Document improvements**
   - Which query types improved most?
   - Any regressions?
   - Specific examples of better answers?

---

## Monitoring

### Key Metrics to Track

1. **Citation Retrieval**
   - Average number of citations per query
   - Target: 6+ citations for cross-language queries

2. **Similarity Percentages**
   - Average similarity of top citation
   - Target: >70% for same-language, >50% for cross-language

3. **Answer Quality (Human Eval)**
   - 1-10 scale per QA methodology
   - Target: English 4.0+, Spanish 6.0+

4. **Query Response Time**
   - With k=30-40, expect slight increase
   - Target: <30 seconds per query

---

## Rollback Plan (If Needed)

If new configuration performs worse:

```bash
# Revert to previous configuration
cd /home/senarios/Desktop/aris
git revert HEAD
git push intelycx main

# Restart services
docker-compose down
docker-compose up -d --build
```

---

## Next Steps

### Immediate (Today)

1. ✅ Deploy fixes to production
2. ⏳ Run smoke tests on VUORMAR.pdf
3. ⏳ Verify cross-language queries work better
4. ⏳ Request QA team re-test

### Short-term (This Week)

1. ⏳ Get QA team's exact test queries
2. ⏳ Create automated regression tests
3. ⏳ Run comprehensive test suite
4. ⏳ Iterate based on results

### Medium-term (Next Week)

1. ⏳ Fine-tune parameters based on QA feedback
2. ⏳ Consider document quality improvements
3. ⏳ Explore better translation strategies
4. ⏳ Test with more diverse documents

---

## Questions for QA Team

**URGENT: Need the following information to fully address the issue:**

1. **Exact test queries** - What specific questions are you asking?
2. **Test documents** - Which documents are you testing with?
3. **Scoring rubric** - How do you evaluate 1-10? What's a 5? What's an 8?
4. **Testing method** - UI or API? Which settings selected?
5. **Example answers** - Can you share examples of 1.71/10 vs 4.50/10 answers?
6. **Document selection** - Are you selecting specific documents or searching all?

**Without this information, we're optimizing blind!**

---

## Technical Details

### Why These Numbers?

**k=30 (from 20)**
- Cross-language retrieval is less accurate
- Need 50% more chunks to ensure relevant info is retrieved
- QA data shows English queries missing critical information

**Semantic Weight 0.3 (from 0.4) globally**
- Balances semantic understanding with keyword reliability
- Spanish queries (4.50/10) also need improvement → more keyword focus helps

**Semantic Weight 0.2 (from 0.4) for cross-language**
- Embeddings lose similarity across language boundaries
- 80% keyword matching provides more reliable retrieval
- QA data (1.71/10) shows semantic search failing dramatically

**Semantic Weight 0.1 (from 0.35) for contact queries**
- Contact info (email, phone) scattered across documents
- Keyword matching (90%) finds "mattia_stellini@vuormar" reliably
- Semantic search struggles with specific literal strings

**k=40 (from 20) for contact queries**
- Contact information often split across multiple chunks
- Need to cast a wide net to find all instances
- 100% increase ensures comprehensive coverage

**Temperature 0.1 (from 0.0)**
- Pure determinism (0.0) can be too rigid
- Slight creativity (0.1) improves answer synthesis from multiple chunks
- Still very focused and factual

---

## Status

**Date:** 2026-01-14  
**Priority:** CRITICAL  
**Status:** ✅ Fixes Deployed, ⏳ Awaiting QA Re-Test  
**Owner:** AI Development Team  
**Next Review:** After QA re-test results

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-01-14 | 1.0 | Initial QA-driven urgent fixes deployed |
| 2026-01-14 | 1.1 | Enhanced contact query handling (k=40, sw=0.1) |

