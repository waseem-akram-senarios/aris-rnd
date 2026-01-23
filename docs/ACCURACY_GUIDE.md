# 🎯 ARIS RAG System - Accuracy Optimization Guide

This guide provides **actionable steps** to maximize the accuracy of your RAG system for both the MCP server and overall system.

---

## 📊 Current Accuracy Configuration

Your system is configured with these accuracy-optimized settings:

| Setting | Current Value | Purpose |
|---------|---------------|---------|
| `EMBEDDING_MODEL` | text-embedding-3-large | 3072D embeddings for semantic precision |
| `DEFAULT_CHUNK_SIZE` | 512 tokens | Granular retrieval |
| `DEFAULT_CHUNK_OVERLAP` | 128 tokens | Context continuity |
| `DEFAULT_RETRIEVAL_K` | 30 | Retrieve more, rerank to top |
| `ENABLE_RERANKING` | true | FlashRank cross-encoder reranking |
| `DEFAULT_USE_HYBRID_SEARCH` | true | Combines semantic + BM25 |
| `DEFAULT_SEMANTIC_WEIGHT` | 0.3 | 30% semantic, 70% keyword |
| `DEFAULT_USE_AGENTIC_RAG` | true | Query decomposition |
| `DEFAULT_PARSER` | docling | High accuracy text extraction |

---

## 🚀 Accuracy Improvements to Implement

### 1. **Optimize Hybrid Search Weights** (High Impact)

Your current 30/70 semantic/keyword split is aggressive on keyword matching. For most RAG use cases:

```bash
# Recommended for technical documents
DEFAULT_SEMANTIC_WEIGHT=0.5
DEFAULT_KEYWORD_WEIGHT=0.5

# For code/error message queries
DEFAULT_SEMANTIC_WEIGHT=0.3
DEFAULT_KEYWORD_WEIGHT=0.7

# For conceptual questions
DEFAULT_SEMANTIC_WEIGHT=0.7
DEFAULT_KEYWORD_WEIGHT=0.3
```

**Action**: Test with different weights using your actual queries.

---

### 2. **Enable Better Chunking** (Medium Impact)

Current chunking is good (512/128), but consider:

```python
# Add to settings.py for larger documents
ENABLE_SEMANTIC_CHUNKING = True  # Chunk at sentence boundaries
RESPECT_PAGE_BOUNDARIES = True   # Don't split across pages
```

**Action**: For very large documents (100+ pages), increase:
```bash
DEFAULT_CHUNK_SIZE=768
DEFAULT_CHUNK_OVERLAP=192
```

---

### 3. **Tune Reranking** (High Impact)

FlashRank is enabled, but you can optimize:

```python
# In retrieval/engine.py, adjust reranking parameters:

# Retrieve 3x more than needed, let reranker pick best
retrieval_k = k * 3

# Use a minimum reranking threshold
RERANK_SCORE_THRESHOLD = 0.3  # Filter low-confidence results
```

**Action**: Add score filtering after reranking:

```python
# Filter results below threshold
reranked_docs = [doc for doc in reranked_docs if doc.metadata.get('rerank_score', 0) > 0.3]
```

---

### 4. **Improve Query Understanding** (High Impact)

Your Agentic RAG decomposes queries well. Enhance it:

```python
# Add query type classification
QUERY_TYPES = {
    "factual": {"k": 5, "semantic_weight": 0.5},    # "What is X?"
    "comparison": {"k": 10, "semantic_weight": 0.6}, # "Compare X and Y"
    "procedural": {"k": 8, "semantic_weight": 0.4},  # "How to do X?"
    "summary": {"k": 20, "semantic_weight": 0.5},    # "Summarize X"
    "specific": {"k": 3, "semantic_weight": 0.3}     # "Error code ERR-123"
}
```

**Action**: Implement query type detection and dynamic parameter selection.

---

### 5. **Document Quality Scoring** (Medium Impact)

Add quality metadata during ingestion:

```python
# Track parsing quality
doc_quality = {
    "extraction_confidence": parsed.confidence,  # 0-1
    "image_to_text_ratio": parsed.image_count / len(parsed.text.split()),
    "ocr_used": parsed.parser_used in ["ocrmypdf", "llamascan"],
    "page_extraction_completeness": parsed.pages_detected / parsed.pages_total
}

# Use quality scores to boost/demote in retrieval
metadata["quality_score"] = calculate_quality_score(doc_quality)
```

---

### 6. **MCP Server Accuracy Settings**

The updated MCP server now includes:

```python
# rag_search tool with all accuracy features
@mcp.tool()
def rag_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 10,
    search_mode: str = "hybrid",
    use_agentic_rag: bool = True,      # ✅ Query decomposition
    include_answer: bool = True         # ✅ Full RAG answer
):
```

**Usage for maximum accuracy:**

```python
# Complex question - enable all features
result = rag_search(
    query="Compare the maintenance procedures for Model X and Y, including safety requirements",
    k=15,  # More results for comprehensive answer
    use_agentic_rag=True,  # Decompose into sub-queries
    include_answer=True
)

# Precise lookup - minimal features for speed
result = rag_search(
    query="ERR-5042",
    k=5,
    search_mode="keyword",  # Exact match
    use_agentic_rag=False,  # Simple query
    include_answer=False    # Just return chunks
)
```

---

## 📈 Accuracy Metrics to Track

Add these metrics to your monitoring:

### 1. **Retrieval Accuracy**
```python
# In retrieval logs
metrics = {
    "query": query,
    "rerank_score_avg": avg([doc.metadata['rerank_score'] for doc in docs]),
    "rerank_score_top1": docs[0].metadata.get('rerank_score'),
    "chunks_retrieved": len(docs),
    "unique_sources": len(set([d.metadata['source'] for d in docs]))
}
```

### 2. **Answer Quality Indicators**
- **Source diversity**: Number of unique documents cited
- **Citation coverage**: % of answer sentences with citations
- **Confidence score**: Average rerank score of used chunks

### 3. **User Feedback Loop** (Recommended)
```python
# Add feedback endpoint
@mcp.tool()
def rag_feedback(
    query_id: str,
    helpful: bool,
    correct_answer: Optional[str] = None
):
    """Track which answers were helpful for continuous improvement."""
```

---

## 🔧 Environment Variables for Accuracy

Add these to your `.env` or `docker-compose.yml`:

```bash
# High Accuracy Configuration
EMBEDDING_MODEL=text-embedding-3-large
ENABLE_RERANKING=true
DEFAULT_USE_HYBRID_SEARCH=true
DEFAULT_USE_AGENTIC_RAG=true
ENABLE_AUTO_TRANSLATE=true

# Retrieval Tuning
DEFAULT_RETRIEVAL_K=30
DEFAULT_SEMANTIC_WEIGHT=0.5
DEFAULT_KEYWORD_WEIGHT=0.5

# Generation Quality
DEFAULT_TEMPERATURE=0.1
DEFAULT_MAX_TOKENS=2000

# Parser Selection
DEFAULT_PARSER=docling  # Best accuracy
DOCLING_MAX_TIMEOUT=1800

# OCR Quality
OCR_DEFAULT_DPI=300
OCR_CJK_DPI=400
```

---

## ✅ Accuracy Checklist

Use this checklist when deploying or troubleshooting:

- [ ] **Embedding model**: Using text-embedding-3-large
- [ ] **Reranking**: FlashRank enabled (`ENABLE_RERANKING=true`)
- [ ] **Hybrid search**: Enabled with balanced weights
- [ ] **Agentic RAG**: Enabled for complex queries
- [ ] **Parser**: Docling as default
- [ ] **Chunk size**: 512-768 tokens with 25% overlap
- [ ] **Retrieval K**: At least 20-30 before reranking
- [ ] **Temperature**: Low (0.1) for factual answers
- [ ] **Auto-translate**: Enabled for multilingual content

---

## 🎯 Common Accuracy Issues & Fixes

### Issue: "Irrelevant results returned"
**Fix**: Increase retrieval K, enable reranking, lower semantic weight

### Issue: "Missing obvious matches"
**Fix**: Increase keyword weight, check if document was fully parsed

### Issue: "Answer doesn't cite sources"
**Fix**: Lower temperature, check citation rules in prompts

### Issue: "Cross-language queries fail"
**Fix**: Enable auto_translate, check language detection

### Issue: "Complex questions get partial answers"
**Fix**: Enable Agentic RAG, increase max_sub_queries

---

## 📊 Benchmark Your Accuracy

Create a test set to measure improvements:

```python
test_queries = [
    {
        "query": "What is the warranty period?",
        "expected_source": "policy.pdf",
        "expected_answer_contains": ["warranty", "months", "years"]
    },
    {
        "query": "Error code ERR-5042",
        "expected_source": "troubleshooting.pdf",
        "expected_answer_contains": ["ERR-5042", "solution"]
    }
]

# Run tests and track:
# - Top-1 accuracy: Correct document in first result
# - Top-3 accuracy: Correct document in top 3
# - Answer accuracy: Expected terms present in answer
```

---

## 🚀 Next Steps

1. **Deploy updated MCP server** with accuracy features
2. **Create test dataset** with known correct answers
3. **Run A/B tests** with different settings
4. **Monitor rerank scores** in production
5. **Collect user feedback** on answer quality

