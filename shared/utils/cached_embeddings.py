import hashlib
from typing import List
from langchain_core.embeddings import Embeddings

class CachedEmbeddings(Embeddings):
    """
    Wrapper for embeddings that caches results in memory to avoid redundant API calls.
    Particularly useful for Agentic RAG where sub-queries might overlap.
    """
    def __init__(self, underlying_embeddings: Embeddings, max_cache_size: int = 1000):
        self.underlying = underlying_embeddings
        self.cache = {}
        self.max_cache_size = max_cache_size

    def _get_cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        results = []
        texts_to_embed = []
        text_indices = []
        
        for i, text in enumerate(texts):
            key = self._get_cache_key(text)
            if key in self.cache:
                results.append(self.cache[key])
            else:
                results.append(None) # Placeholder
                texts_to_embed.append(text)
                text_indices.append(i)
        
        if texts_to_embed:
            new_embeddings = self.underlying.embed_documents(texts_to_embed)
            for i, emb in enumerate(new_embeddings):
                key = self._get_cache_key(texts_to_embed[i])
                # Manage cache size
                if len(self.cache) >= self.max_cache_size:
                    # Simple FIFO-ish: clear cache if too big
                    self.cache.clear()
                self.cache[key] = emb
                results[text_indices[i]] = emb
                
        return results

    def embed_query(self, text: str) -> List[float]:
        key = self._get_cache_key(text)
        if key in self.cache:
            return self.cache[key]
        
        embedding = self.underlying.embed_query(text)
        if len(self.cache) >= self.max_cache_size:
            self.cache.clear()
        self.cache[key] = embedding
        return embedding
