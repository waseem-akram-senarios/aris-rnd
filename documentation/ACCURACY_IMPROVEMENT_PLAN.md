# Accuracy Improvement Plan
**Goal**: Maximize Retrieval and Generation Accuracy for ARIS RAG System.

## 1. The "Silver Bullet": Cross-Encoder Reranking 🎯
**Impact**: High (typically +10-20% retrieval accuracy)
**Effort**: Medium

Current RAG retrieves chunks based on Vector Similarity (Cosine). This is fast but "fuzzy". It misses subtle nuances.
**Solution**: Implement a **Result Reranking** step.
1.  Retrieve significantly more chunks than needed (e.g., `k=50`).
2.  Pass these 50 chunks + Query to a **Cross-Encoder Model** (e.g., `ms-marco-MiniLM-L-6-v2` or `FlashRank`).
3.  The Cross-Encoder scores specifically "How relevant is THIS chunk to THIS query?".
4.  Return the top `k=10` highest correlations.

**Why FlashRank?**
- It runs on CPU (no heavy GPU needed).
- It is extremely small and fast (< 50ms).
- It is state-of-the-art for lightweight RAG.

## 2. Advanced Chunking: Context-Aware Splitting 📄
**Impact**: Medium
**Effort**: Low

Current: `TokenTextSplitter` (Hard limits, e.g., 500 tokens). This cuts sentences in half.
**Solution**: Switch to **RecursiveCharacterTextSplitter**.
- Splits by Headers (`#`), then Paragraphs (`\n\n`), then Sentences (`.`), then Words.
- Keeps related text together semantically.
- **Combined with your Page-Aware Chunking**, this ensures chunks are both page-accurate and semantically coherent.

## 3. Query Expansion: HyDE (Hypothetical Document Embeddings) 🔮
**Impact**: Medium-High (for complex questions)
**Effort**: Medium

Sometimes the user's query doesn't match the document's vocabulary.
**Solution**: Use the LLM to hallucinate a "Perfect Answer" (Hypothetical Document).
- Embed the *Hypothetical Answer* instead of the Question.
- Search for documents matching the Answer.

## 4. Metadata Enrichment 🏷️
**Impact**: Low-Medium
**Effort**: High

- Extract **Dates**, **Authors**, **Key Entities** during parsing.
- Filter retrieval by these entities. (Requires heavily modifying Parsers).

---

## 🏆 Recommendation: The "Accuracy First" Roadmap

1.  **Immediate Win**: Implement **FlashRank Reranking**. This is the single most effective change for accuracy.
2.  **Easy Win**: Switch to `RecursiveCharacterTextSplitter`.
3.  **Advanced**: Add Query Expansion if users ask vague questions.

### Implementation Draft for Reranking
```python
# In rag_system.py
from flashrank import Ranker, RerankRequest

class RAGSystem:
    def __init__(self):
        self.ranker = Ranker() # Loads efficient model
        
    def query(self, question, k=10):
        # 1. Retrieve Candidate Pool (Large k)
        candidates = self.vectorstore.similarity_search(question, k=50)
        
        # 2. Rerank
        rerank_request = RerankRequest(query=question, passages=[
            {"id": c.metadata['id'], "text": c.page_content} for c in candidates
        ])
        results = self.ranker.rerank(rerank_request)
        
        # 3. Take Top k
        return [get_doc(r['id']) for r in results[:k]]
```
