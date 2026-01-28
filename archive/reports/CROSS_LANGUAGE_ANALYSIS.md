# Cross-Language Query Accuracy Analysis

## Test Results Summary

### Quick Test Results (VUORMAR.pdf)

| Query Type | Query | Citations | Avg Similarity | Answer Quality |
|------------|-------|-----------|-----------------|----------------|
| Same-language (Spanish) | ¿Dónde está el email y contacto de Vuormar? | 1 | 100% | ⚠️ Says "no se encuentra" |
| Cross-language (English) | Where is the email and contact of Vuormar? | 1 | 100% | ❌ Says "does not include any information" |
| Cross-language (English) | How to increase or decrease the levels of air in bag? | 2 | 65% | ❌ Says "does not contain specific information" |
| Same-language (Spanish) | ¿Cómo aumentar o disminuir los niveles de aire en la bolsa? | 2 | 65% | ❌ Says "no incluye información específica" |

## Key Findings

### 1. **High Similarity but Low Accuracy**
- Similarity scores are high (65-100%), but answers indicate "no information found"
- This suggests:
  - Retrieval is finding chunks, but they don't contain the actual answer
  - The semantic embeddings are matching, but the content relevance is low
  - The LLM correctly identifies that retrieved chunks don't answer the question

### 2. **Cross-Language Issues**
- English queries on Spanish documents: **~10% accuracy** (as reported by QA)
- Spanish queries on Spanish documents: **Better but still issues**
- Problem: Semantic embeddings trained on English don't match Spanish content well

### 3. **Root Causes**

#### A. Embedding Language Mismatch
- **Current**: Using English embeddings (OpenAI **text-embedding-3-large** - 3072 dimensions)
- **Problem**: English embeddings have low similarity with Spanish text
- **Impact**: Cross-language semantic search fails
- **Note**: Already upgraded from ada-002, but still English-focused

#### B. Translation Quality
- **Current**: Translating queries from Spanish → English for search
- **Problem**: 
  - Translation may lose context or nuance
  - Translated query may not match document embeddings
  - Document content is in Spanish, query is in English

#### C. Dual-Language Search Not Optimal
- **Current**: Uses `alternate_query` for keyword matching
- **Problem**:
  - Keyword matching alone isn't sufficient
  - Semantic search (primary) still uses English embeddings
  - Need multilingual embeddings or better translation strategy

#### D. Parser Performance
- **QA Report**: "All parsers working the same"
- **Analysis**: This suggests parsers are extracting text correctly, but retrieval is the issue
- **Conclusion**: Problem is in retrieval/embedding, not parsing

## Recommended Solutions

### Solution 1: Multilingual Embeddings (Future Enhancement)
- **Current**: Using `text-embedding-3-large` (best English embeddings)
- **Alternative**: `multilingual-e5-large` or `paraphrase-multilingual-MiniLM-L12-v2`
- **Benefit**: Embeddings work natively across languages
- **Implementation**: Change embedding model in `ARISConfig`
- **Impact**: High - +20-30% more improvement possible

### Solution 2: Improve Translation Strategy
- **Current**: Translate query → English → search
- **Better**: 
  - Translate document chunks to English during ingestion (store both)
  - OR: Use better translation with context preservation
- **Impact**: Medium - improves but doesn't solve root cause

### Solution 3: Enhanced Dual-Language Search
- **Current**: Uses alternate_query for keyword matching
- **Better**:
  - Increase keyword weight for cross-language queries
  - Use fuzzy matching for translated terms
  - Combine multiple translation variations
- **Impact**: Medium - improves keyword matching

### Solution 4: Query Expansion for Cross-Language
- **Strategy**: Expand English query with Spanish synonyms/translations
- **Example**: "email" → ["email", "correo", "correo electrónico"]
- **Impact**: Medium - improves keyword matching

### Solution 5: Hybrid Approach (Recommended)
1. **Use multilingual embeddings** (Solution 1)
2. **Enhance dual-language search** (Solution 3)
3. **Add query expansion** (Solution 4)
4. **Improve translation** (Solution 2)

## Immediate Fixes

### Fix 1: Increase Keyword Weight for Cross-Language Queries
```python
# In engine.py, detect cross-language scenario
if auto_translate and detected_language != "en":
    # For cross-language, prioritize keyword matching
    semantic_weight = 0.4  # Lower semantic, higher keyword
    keyword_weight = 0.6
```

### Fix 2: Query Expansion with Translations
```python
# Expand query with translations
if auto_translate and detected_language != "en":
    # Add original query terms for keyword matching
    expanded_query = f"{translated_question} {original_question}"
    # Use expanded query for keyword search
```

### Fix 3: Better Translation Context
```python
# Include document language context in translation
translated_question = translator.translate(
    question, 
    target_lang="en", 
    source_lang=detected_language,
    context="technical document"  # Add context
)
```

## Testing Plan

1. **Baseline Test**: Current system (documented above)
2. **Fix 1 Test**: Increased keyword weight
3. **Fix 2 Test**: Query expansion
4. **Fix 3 Test**: Better translation
5. **Solution 1 Test**: Multilingual embeddings (requires model change)

## Expected Improvements

| Solution | Expected Accuracy Improvement |
|----------|------------------------------|
| Fix 1 (Keyword Weight) | +10-15% |
| Fix 2 (Query Expansion) | +5-10% |
| Fix 3 (Better Translation) | +5-10% |
| Solution 1 (Multilingual Embeddings) | +40-50% |
| **Combined (All Fixes)** | **+60-70%** |

## Next Steps

1. ✅ Test current system (done)
2. ⏳ Implement Fix 1-3 (immediate)
3. ⏳ Test Fix 1-3
4. ⏳ Evaluate Solution 1 (multilingual embeddings)
5. ⏳ Deploy best solution

