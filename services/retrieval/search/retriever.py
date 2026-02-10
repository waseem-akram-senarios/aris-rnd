"""
Hybrid search, chunk retrieval, occurrence search, and deduplication.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import re
import logging
import time as time_module
from typing import List, Dict, Optional, Any

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class SearchMixin:
    """Mixin providing hybrid search, chunk retrieval, occurrence search, and deduplication capabilities."""
    
    def _find_occurrences_opensearch(self, term: str, max_hits: int = 5000) -> List:
        """Fetch chunks containing term from OpenSearch for the active document."""
        if not hasattr(self, 'multi_index_manager'):
            from vectorstores.opensearch_store import OpenSearchMultiIndexManager
            self.multi_index_manager = OpenSearchMultiIndexManager(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )

        indexes_to_search = []
        if self.active_sources:
            for doc_name in self.active_sources:
                if doc_name in self.document_index_map:
                    indexes_to_search.append(self.document_index_map[doc_name])
        if not indexes_to_search:
            return []

        # Lucene query_string escaping (minimal)
        q = term.replace('\\', '\\\\').replace('"', '\\"')
        query = f'"{q}"'

        results = []
        page_size = 500
        for index_name in indexes_to_search:
            try:
                store = self.multi_index_manager.get_or_create_index_store(index_name)
                client = store.vectorstore.client
                offset = 0
                while offset < max_hits:
                    body = {
                        "from": offset,
                        "size": min(page_size, max_hits - offset),
                        "query": {
                            "query_string": {
                                "query": query,
                                "fields": ["text"],
                                "default_operator": "AND"
                            }
                        }
                    }
                    resp = client.search(index=index_name, body=body)
                    hits = resp.get("hits", {}).get("hits", [])
                    if not hits:
                        break
                    results.extend(hits)
                    if len(hits) < page_size:
                        break
                    offset += page_size
            except Exception as e:
                logger.warning(f"Occurrence search failed for index '{index_name}': {e}")
                continue

        # Convert to LangChain documents (best-effort)
        from langchain_core.documents import Document
        docs = []
        for h in results:
            src = h.get('_source', {}) or {}
            text = src.get('text', '')
            meta = src.get('metadata', {}) or {}
            try:
                docs.append(Document(page_content=text, metadata=meta))
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                continue
        return docs

    def find_all_occurrences(self, term: str, max_results: int = 200) -> Dict:
        """Find all occurrences of a term in the active document and return an answer + citations."""
        import re

        if not term or not term.strip():
            return {
                "answer": "Please provide a word or phrase to find.",
                "sources": [],
                "citations": [],
                "context_chunks": [],
                "num_chunks_used": 0
            }

        if not self.active_sources:
            return {
                "answer": "Select one document (Active Document) first, then ask again.",
                "sources": [],
                "citations": [],
                "context_chunks": [],
                "num_chunks_used": 0
            }

        term_clean = term.strip()
        # Pull candidate chunks
        if self.vector_store_type == 'opensearch':
            candidate_docs = self._find_occurrences_opensearch(term_clean)
        else:
            # FAISS fallback: retrieve a large set of chunks then scan
            try:
                candidate_docs = self.vectorstore.similarity_search(term_clean, k=1000)
            except Exception as e:
                logger.warning(f"operation: {type(e).__name__}: {e}")
                candidate_docs = []

        occurrences = []
        for doc in candidate_docs:
            text = getattr(doc, 'page_content', '') or ''
            if not text:
                continue

            # Strict-ish matching: match whole word when term is a single token; else substring
            if ' ' in term_clean:
                pattern = re.compile(re.escape(term_clean), re.IGNORECASE)
            else:
                pattern = re.compile(rf"\b{re.escape(term_clean)}\b", re.IGNORECASE)

            for m in pattern.finditer(text):
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 80)
                snippet = text[start:end].replace('\n', ' ').strip()
                page = None
                if hasattr(doc, 'metadata') and doc.metadata:
                    page = doc.metadata.get('source_page') or doc.metadata.get('page')
                image_ref = doc.metadata.get('image_ref') if hasattr(doc, 'metadata') and doc.metadata else None
                image_index = None
                if isinstance(image_ref, dict):
                    image_index = image_ref.get('image_index')
                elif hasattr(doc, 'metadata') and doc.metadata:
                    image_index = doc.metadata.get('image_index')

                # Ensure page is always set (fallback to 1 if None)
                if page is None:
                    page = 1
                
                occurrences.append({
                    "source": doc.metadata.get('source') if hasattr(doc, 'metadata') and doc.metadata else None,
                    "page": int(page),  # Always guaranteed to be an integer >= 1
                    "snippet": snippet,
                    "image_index": image_index,
                    "start_char": doc.metadata.get('start_char') if hasattr(doc, 'metadata') and doc.metadata else None,
                    "end_char": doc.metadata.get('end_char') if hasattr(doc, 'metadata') and doc.metadata else None,
                })

        # Sort by page then snippet
        occurrences.sort(key=lambda x: (x.get('page') or 10**9, x.get('image_index') or 10**9, x.get('start_char') or 10**9))

        truncated = False
        if len(occurrences) > max_results:
            occurrences = occurrences[:max_results]
            truncated = True

        source_name = self.active_sources[0] if self.active_sources else 'selected document'
        answer = self._build_occurrence_answer(term_clean, source_name, occurrences, truncated)

        # Create citations-like objects so UI can render references
        citations = []
        for idx, occ in enumerate(occurrences, 1):
            # Ensure page is always set (fallback to 1 if None)
            page = occ.get('page')
            if page is None:
                page = 1
                logger.debug(f"find_all_occurrences citation {idx}: page was None, using fallback page 1")
            
            # Extract image metadata (for internal tracking only)
            # NOTE: image_number from ingestion is a document-wide sequential counter, not per-page position
            # So we DON'T show it in citations as it's misleading (e.g., "Image 2" doesn't mean 2nd image on page)
            raw_image_number = occ.get('image_index') or occ.get('image_number')
            is_image_content = raw_image_number is not None or '<!-- image -->' in (occ.get('snippet') or '')
            
            # Build source_location - just show Page number, indicate image content via content_type
            source_location = f"Page {page}"
            
            citations.append({
                'id': idx,
                'source': occ.get('source') or source_name,
                'page': page,  # Always guaranteed to be an integer >= 1
                'image_number': None,  # Don't show misleading sequential image numbers
                'snippet': occ.get('snippet'),
                'full_text': occ.get('snippet') or '',
                'source_location': source_location,
                'content_type': 'image' if is_image_content else 'text',
                'image_ref': {'page': page, 'has_image': True} if is_image_content else None,
            })

        sources = [source_name]
        return {
            "answer": answer,
            "sources": sources,
            "citations": citations,
            "context_chunks": [],
            "num_chunks_used": len(citations),
            "occurrences": occurrences
        }
    
    def _retrieve_chunks_for_query(
        self,
        query: str,
        k: int,
        use_mmr: bool,
        use_hybrid_search: bool,
        semantic_weight: float,
        keyword_weight: float,
        search_mode: str,
        active_sources: List[str] = None,
        alternate_query: Optional[str] = None,  # For dual-language search (original language query)
        filter_language: Optional[str] = None,   # Filter results by language
        disable_reranking: bool = False  # Disable reranking (e.g., for contact queries)
    ) -> List:
        """
        Retrieves chunks with optional Reranking (FlashRank) for higher accuracy.
        Supports dual-language search for cross-lingual retrieval.
        
        Args:
            query: Primary query (typically English for semantic search)
            k: Number of chunks to retrieve
            use_mmr: Use Maximum Marginal Relevance
            use_hybrid_search: Enable hybrid search
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
            search_mode: 'semantic', 'keyword', or 'hybrid'
            active_sources: Filter by document sources
            alternate_query: Original language query for dual-search (boosts keyword matches)
            filter_language: Filter results by language code (e.g., 'spa')
        
        Returns:
            List of relevant Document chunks
        """
        # 1. Expand retrieval window for Reranking
        # Retrieve 4x chunks to give Reranker candidates to choose from
        # QA FIX: Disable reranking for contact queries (may drop relevant chunks)
        initial_k = k
        if self.ranker and not disable_reranking:
            initial_k = k * 4
            logger.debug(f"Reranking enabled: expanding k from {k} to {initial_k}")
        elif disable_reranking:
            logger.info(f"🚫 Reranking DISABLED for this query (e.g., contact query to preserve all relevant chunks)")
        
        # 2. Get Raw Candidates (with dual-language support)
        relevant_docs = self._retrieve_chunks_raw(
            query, 
            initial_k, 
            use_mmr, 
            use_hybrid_search, 
            semantic_weight, 
            keyword_weight, 
            search_mode,
            active_sources,  # Pass active_sources to raw retrieval
            alternate_query=alternate_query,  # Pass alternate query for dual-search
            filter_language=filter_language    # Pass language filter
        )
        
        # 3. Rerank Results (only if not disabled)
        if self.ranker and relevant_docs and not disable_reranking:
            try:
                # Prepare Rerank Request
                passages = [
                    {"id": str(i), "text": doc.page_content, "meta": doc.metadata} 
                    for i, doc in enumerate(relevant_docs)
                ]
                
                # For cross-lingual reranking, use the original query if available
                # This helps preserve relevance to the user's original intent
                rerank_query = alternate_query if alternate_query else query
                
                logger.info(f"⚡ Reranking {len(passages)} chunks with FlashRank...")
                rerank_request = RerankRequest(query=rerank_query, passages=passages)
                results = self.ranker.rerank(rerank_request)
                
                # Reconstruct sorted document list
                # Map back to original documents using index/id
                reranked_docs = []
                for res in results:
                    original_idx = int(res['id'])
                    # Update metadata with rerank score
                    doc = relevant_docs[original_idx]
                    doc.metadata['rerank_score'] = res['score']
                    reranked_docs.append(doc)
                
                # Slice to requested k
                return reranked_docs[:k]
                
            except Exception as e:
                logger.warning(f"Reranking failed: {e}. Returning raw results.")
                return relevant_docs[:k]
        
        return relevant_docs[:k]

    def _retrieve_chunks_raw(
        self,
        query: str,
        k: int,
        use_mmr: bool,
        use_hybrid_search: bool,
        semantic_weight: float,
        keyword_weight: float,
        search_mode: str,
        active_sources: List[str] = None,
        alternate_query: Optional[str] = None,  # For dual-language search
        filter_language: Optional[str] = None   # Filter by document language
    ) -> List:
        """
        Retrieve chunks for a single query with dual-language search support.
        
        Args:
            query: Primary query (typically English for semantic search)
            k: Number of chunks to retrieve
            use_mmr: Use Maximum Marginal Relevance
            use_hybrid_search: Use hybrid search
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
            search_mode: Search mode
            active_sources: List of document sources to filter by (optional)
            alternate_query: Original language query for dual-search keyword matching
            filter_language: Filter results by language code (e.g., 'spa')
        
        Returns:
            List of Document objects
        """
        # For OpenSearch: Use per-document indexes instead of metadata filtering
        if self.vector_store_type == "opensearch":
            # Determine which index(es) to search
            indexes_to_search = []
            
            if active_sources:
                # Map active sources to their respective OpenSearch indexes
                found_indexes = set()
                for doc_name in active_sources:
                    if doc_name in self.document_index_map:
                        indexes_to_search.append(self.document_index_map[doc_name])
                    else:
                        logger.warning(f"Agentic RAG - Document '{doc_name}' not found in index map. Available: {list(self.document_index_map.keys())}")
                
                if not indexes_to_search:
                    logger.warning(f"Agentic RAG - No indexes found for selected documents")
                    return []
            else:
                # No filter - search all document indexes
                indexes_to_search = list(self.document_index_map.values())
                if not indexes_to_search:
                    # Fallback to default index if no mappings exist (backward compatibility)
                    indexes_to_search = [self.opensearch_index or "aris-rag-index"]
            
            # Initialize multi-index manager if needed
            if not hasattr(self, 'multi_index_manager'):
                from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                self.multi_index_manager = OpenSearchMultiIndexManager(
                    embeddings=self.embeddings,
                    domain=self.opensearch_domain,
                    region=getattr(self, 'region', None)
                )
            
            # Search across selected indexes
            if len(indexes_to_search) == 1:
                # Single index - use it directly
                index_name = indexes_to_search[0]
                store = self.multi_index_manager.get_or_create_index_store(index_name)
                
                # Use hybrid search if enabled (with dual-language support)
                if use_hybrid_search:
                    try:
                        query_vector = self.embeddings.embed_query(query)
                        
                        # Build language filter if specified
                        lang_filter = None
                        if filter_language:
                            lang_filter = {"bool": {"must": [{"term": {"metadata.language": filter_language}}]}}
                        
                        relevant_docs = store.hybrid_search(
                            query=query,
                            query_vector=query_vector,
                            k=k,
                            semantic_weight=semantic_weight,
                            keyword_weight=keyword_weight,
                            filter=lang_filter,
                            alternate_query=alternate_query  # Pass original language query for dual-search
                        )
                        return relevant_docs
                    except Exception as e:
                        logger.warning(f"Agentic RAG - Hybrid search failed for sub-query, falling back: {e}")
                
                # Standard search
                if use_mmr:
                    fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                    lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                    retriever = store.vectorstore.as_retriever(
                        search_type="mmr",
                        search_kwargs={
                            "k": k,
                            "fetch_k": fetch_k,
                            "lambda_mult": lambda_mult
                        }
                    )
                else:
                    retriever = store.vectorstore.as_retriever(
                        search_kwargs={"k": k}
                    )
                relevant_docs = retriever.invoke(query)
                return relevant_docs
            else:
                # Multiple indexes - search across all with dual-language support
                from shared.config.settings import ARISConfig
                
                # Build language filter if specified
                lang_filter = None
                if filter_language:
                    lang_filter = {"bool": {"must": [{"term": {"metadata.language": filter_language}}]}}
                
                relevant_docs = self.multi_index_manager.search_across_indexes(
                    query=query,
                    index_names=indexes_to_search,
                    k=k,
                    use_mmr=use_mmr,
                    fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K if use_mmr else 50,
                    lambda_mult=ARISConfig.DEFAULT_MMR_LAMBDA if use_mmr else 0.3,
                    use_hybrid_search=use_hybrid_search,
                    semantic_weight=semantic_weight,
                    keyword_weight=keyword_weight,
                    filter=lang_filter,
                    alternate_query=alternate_query  # Pass for dual-language search
                )
                return relevant_docs
        
        # FAISS: Use existing filter logic
        # Prepare filter for OpenSearch (different syntax than FAISS) - not needed for FAISS
        opensearch_filter = None
        
        # Use hybrid search if enabled and OpenSearch is available (for non-per-doc path)
        if use_hybrid_search and self.vector_store_type.lower() == "opensearch":
            try:
                from vectorstores.opensearch_store import OpenSearchVectorStore
                
                is_opensearch = False
                if self.vectorstore is not None:
                    if isinstance(self.vectorstore, OpenSearchVectorStore):
                        is_opensearch = True
                    elif hasattr(self.vectorstore, '__class__') and 'OpenSearch' in self.vectorstore.__class__.__name__:
                        is_opensearch = True
                
                if is_opensearch:
                    query_vector = self.embeddings.embed_query(query)
                    
                    # Add language filter if specified
                    combined_filter = opensearch_filter
                    if filter_language:
                        lang_clause = {"bool": {"must": [{"term": {"metadata.language": filter_language}}]}}
                        if combined_filter:
                            combined_filter = {"bool": {"must": [combined_filter, lang_clause]}}
                        else:
                            combined_filter = lang_clause
                    
                    relevant_docs = self.vectorstore.hybrid_search(
                        query=query,
                        query_vector=query_vector,
                        k=k,
                        semantic_weight=semantic_weight,
                        keyword_weight=keyword_weight,
                        filter=combined_filter,
                        alternate_query=alternate_query  # Pass for dual-language search
                    )
                    return relevant_docs
            except Exception as e:
                logger.warning(f"Hybrid search failed for sub-query, falling back: {e}")
        
        # Standard retrieval
        # For FAISS: Increase k when filtering is needed (FAISS doesn't support native filtering)
        effective_k = k
        if self.active_sources and self.vector_store_type.lower() != "opensearch":
            # Increase k to account for post-filtering (retrieve 3-5x more to ensure we get enough after filtering)
            effective_k = k * 4
            logger.info(f"Agentic RAG - FAISS filtering active: Increasing k from {k} to {effective_k} to account for post-filtering")
        
        if use_mmr:
            from shared.config.settings import ARISConfig
            fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
            lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
            
            # Adjust fetch_k for FAISS filtering
            if self.active_sources and self.vector_store_type.lower() != "opensearch":
                fetch_k = max(fetch_k, effective_k * 2)
            
            search_kwargs = {
                "k": effective_k,
                "fetch_k": fetch_k,
                "lambda_mult": lambda_mult,
            }
            
            # Add filter only for OpenSearch (FAISS doesn't support native filtering)
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            # Note: FAISS filtering is done post-retrieval, not via search_kwargs
            
            retriever = self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs
            )
        else:
            search_kwargs = {"k": effective_k}
            
            # Add filter only for OpenSearch (FAISS doesn't support native filtering)
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            # Note: FAISS filtering is done post-retrieval, not via search_kwargs
            
            retriever = self.vectorstore.as_retriever(
                search_kwargs=search_kwargs
            )
        
        try:
            relevant_docs = retriever.invoke(query)
        except AttributeError as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            relevant_docs = retriever.get_relevant_documents(query)
        
        # Filter by active sources if set (strict filtering with robust matching)
        # CRITICAL: Always apply post-retrieval filter even for OpenSearch to prevent document mixing
        # The per-document index approach is a performance optimization but NOT a guarantee
        if self.active_sources:
            allowed_sources = set(self.active_sources)
            # Also create normalized versions for case-insensitive matching
            allowed_sources_normalized = {s.lower().strip() if s else "" for s in allowed_sources if s}
            allowed_filenames = {os.path.basename(s).lower().strip() if s else "" for s in allowed_sources if s}
            
            def matches_source(doc_source, doc_text=""):
                """Check if document source matches any allowed source using multiple strategies"""
                if not doc_source:
                    # If no metadata source, try extracting from text markers
                    if doc_text:
                        # Look for source markers in text (e.g., "Source: filename.pdf")
                        import re
                        source_patterns = [
                            r"Source:\s*([^\n]+)",
                            r"Document:\s*([^\n]+)",
                            r"File:\s*([^\n]+)",
                        ]
                        for pattern in source_patterns:
                            match = re.search(pattern, doc_text, re.IGNORECASE)
                            if match:
                                extracted_source = match.group(1).strip()
                                # Check if extracted source matches
                                if extracted_source in allowed_sources or \
                                   extracted_source.lower().strip() in allowed_sources_normalized or \
                                   os.path.basename(extracted_source).lower().strip() in allowed_filenames:
                                    return True
                    return False
                # Strategy 1: Exact match
                if doc_source in allowed_sources:
                    return True
                # Strategy 2: Case-insensitive match
                if doc_source.lower().strip() in allowed_sources_normalized:
                    return True
                # Strategy 3: Filename match
                doc_filename = os.path.basename(doc_source).lower().strip()
                if doc_filename in allowed_filenames:
                    return True
                # Strategy 4: Check if any allowed source is contained in doc_source (for path variations)
                for allowed in allowed_sources:
                    if allowed and allowed.lower() in doc_source.lower():
                        return True
                return False
            
            # Filter with strict matching
            filtered_docs = [
                doc for doc in relevant_docs 
                if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
            ]
            
            # Validate: Ensure NO documents from other sources slipped through
            invalid_sources = set()
            for doc in filtered_docs:
                doc_source = doc.metadata.get('source', '')
                if doc_source and not matches_source(doc_source):
                    invalid_sources.add(doc_source)
            
            if invalid_sources:
                logger.warning(f"Agentic RAG - Document mixing detected! Found invalid sources in filtered results: {invalid_sources}")
                # Remove invalid sources
                filtered_docs = [
                    doc for doc in filtered_docs 
                    if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
                ]
            
            if filtered_docs:
                # Final validation: Log document isolation status
                final_sources = set(doc.metadata.get('source', 'Unknown') for doc in filtered_docs)
                logger.info(f"Agentic RAG - Filtered to {len(filtered_docs)} chunks from selected documents: {self.active_sources}. Final sources: {final_sources}")
                if final_sources - allowed_sources:
                    logger.error(f"Agentic RAG - CRITICAL: Document mixing detected! Allowed: {allowed_sources}, Found: {final_sources}")
                return filtered_docs
            else:
                logger.warning(f"No chunks matched selected documents: {self.active_sources}. Available sources in results: {set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])}")
                return []  # Return empty if no matches
        
        return relevant_docs
    
    def _deduplicate_chunks(self, chunks: List, threshold: float = 0.95) -> List:
        """
        Deduplicate chunks using content hash and similarity.
        
        Args:
            chunks: List of Document objects
            threshold: Similarity threshold for near-duplicates (0.0-1.0)
        
        Returns:
            List of unique Document objects
        """
        import hashlib
        
        if not chunks:
            return []
        
        # Use content hash for exact duplicates
        seen_hashes = set()
        unique_chunks = []
        chunk_scores = {}  # Track how many times each chunk appears (priority)
        
        for chunk in chunks:
            # Ensure source metadata is preserved
            if hasattr(chunk, 'metadata') and chunk.metadata:
                # Validate source exists in metadata
                if 'source' not in chunk.metadata or not chunk.metadata.get('source'):
                    from scripts.setup_logging import get_logger
                    logger = get_logger("aris_rag.rag_system")
                    logger.warning(f"Chunk missing source metadata during deduplication. Available keys: {list(chunk.metadata.keys())}")
            
            # Create hash of content
            content_hash = hashlib.md5(chunk.page_content.encode('utf-8')).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(chunk)
                chunk_scores[content_hash] = 1
            else:
                # Increment score for chunks that appear multiple times (they're more relevant)
                chunk_scores[content_hash] = chunk_scores.get(content_hash, 1) + 1
        
        # Sort by score (chunks appearing in multiple sub-queries are more relevant)
        # Then by position (keep first occurrence)
        unique_chunks_with_scores = []
        for chunk in unique_chunks:
            content_hash = hashlib.md5(chunk.page_content.encode('utf-8')).hexdigest()
            score = chunk_scores.get(content_hash, 1)
            unique_chunks_with_scores.append((score, chunk))
        
        # Sort by score (descending), then maintain order
        unique_chunks_with_scores.sort(key=lambda x: x[0], reverse=True)
        unique_chunks = [chunk for _, chunk in unique_chunks_with_scores]
        
        # TODO: Add similarity-based deduplication for near-duplicates if needed
        # This would require embedding comparison which is expensive
        
        return unique_chunks
