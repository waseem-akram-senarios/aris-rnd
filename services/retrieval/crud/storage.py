"""
Vectorstore persistence, statistics, image operations, and document deletion.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import logging
from typing import List, Dict, Optional, Any

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class StorageMixin:
    """Mixin providing vectorstore persistence, statistics, image operations, and document deletion capabilities."""
    
    def save_vectorstore(self, path: str = "vectorstore"):
        """Save vector store to disk (FAISS only) or cloud (OpenSearch)"""
        from scripts.setup_logging import get_logger
        from shared.config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vectorstore:
            if self.vector_store_type == "faiss":
                # Use model-specific path to support multiple embedding models
                base_path = path
                model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
                if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                    # If get_vectorstore_path returns relative path, join with base_path
                    model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
                else:
                    # Use the model-specific path directly
                    model_specific_path = model_specific_path
                
                logger.info(f"[STEP 1] RAGSystem: Saving FAISS vectorstore to: {model_specific_path}")
                # Create directory if it doesn't exist
                os.makedirs(model_specific_path, exist_ok=True)
                
                try:
                    self.vectorstore.save_local(model_specific_path)
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore saved to {model_specific_path}")
                    
                    # Also save document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 2] RAGSystem: Saving document index to: {index_path}")
                    with open(index_path, 'wb') as f:
                        pickle.dump({
                            'document_index': self.document_index,
                            'total_tokens': self.total_tokens,
                            'embedding_model': self.embedding_model
                        }, f)
                    logger.info(f"✅ [STEP 2] RAGSystem: Document index saved to {index_path}")
                except Exception as e:
                    logger.error(f"❌ [STEP 1] RAGSystem: Failed to save vectorstore: {e}", exc_info=True)
            else:
                # OpenSearch stores data in cloud, no local save needed
                logger.info("ℹ️ [STEP 1] RAGSystem: OpenSearch stores data in the cloud. No local save needed.")
    
    def load_vectorstore(self, path: str = "vectorstore"):
        """Load vector store from disk (FAISS) or cloud (OpenSearch) with model-specific path"""
        from scripts.setup_logging import get_logger
        from shared.config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vector_store_type == "faiss":
            # Use model-specific path
            base_path = path
            model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
            if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                # If get_vectorstore_path returns relative path, join with base_path
                model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
            else:
                # Use the model-specific path directly
                model_specific_path = model_specific_path
            
            logger.info(f"[STEP 1] RAGSystem: Loading FAISS vectorstore from: {model_specific_path}")
            if os.path.exists(model_specific_path):
                logger.info(f"[STEP 1.1] RAGSystem: Vectorstore path exists, loading...")
                try:
                    self.vectorstore = VectorStoreFactory.load_vector_store(
                        store_type="faiss",
                        embeddings=self.embeddings,
                        path=model_specific_path
                    )
                    # Also load document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 1.2] RAGSystem: Loading document index from: {index_path}")
                    if os.path.exists(index_path):
                        with open(index_path, 'rb') as f:
                            data = pickle.load(f)
                            self.document_index = data.get('document_index', {})
                            self.total_tokens = data.get('total_tokens', 0)
                            saved_model = data.get('embedding_model', 'unknown')
                            if saved_model != self.embedding_model:
                                logger.warning(
                                    f"⚠️ [STEP 1.2] RAGSystem: Vectorstore was created with '{saved_model}' "
                                    f"but current model is '{self.embedding_model}'. "
                                    f"Dimension mismatch may occur."
                                )
                            logger.info(f"✅ [STEP 1.2] RAGSystem: Document index loaded - {len(self.document_index)} documents, {self.total_tokens:,} tokens")
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore loaded successfully")
                    return True
                except Exception as e:
                    error_msg = str(e)
                    if "dimension" in error_msg.lower():
                        logger.warning(
                            f"⚠️ [STEP 1] RAGSystem: Dimension mismatch when loading vectorstore.\n"
                            f"   This vectorstore was created with a different embedding model.\n"
                            f"   It will be recreated automatically when you add new documents."
                        )
                        return False
                    else:
                        raise
            else:
                # Check if old path exists (backward compatibility)
                if os.path.exists(path) and os.path.isdir(path) and not os.path.basename(path).startswith("text-embedding"):
                    logger.info(f"[STEP 1.1] RAGSystem: Found old vectorstore at {path}, migrating to model-specific path...")
                    try:
                        # Try to load from old path
                        self.vectorstore = VectorStoreFactory.load_vector_store(
                            store_type="faiss",
                            embeddings=self.embeddings,
                            path=path
                        )
                        # If successful, save to new model-specific path
                        self.save_vectorstore(path)
                        logger.info(f"✅ [STEP 1.1] RAGSystem: Migrated to model-specific path: {model_specific_path}")
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 1.1] RAGSystem: Could not migrate old vectorstore: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ [STEP 1] RAGSystem: Vectorstore path does not exist: {model_specific_path}")
            return False
        else:
            # OpenSearch loads from cloud index automatically
            logger.info("[STEP 1] RAGSystem: OpenSearch loads data from the cloud index automatically.")
            try:
                # Load document index map
                self._load_document_index_map()
                
                if self.document_index_map:
                    # Initialize multi-index manager
                    from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                    self.multi_index_manager = OpenSearchMultiIndexManager(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain,
                        region=getattr(self, 'region', None)
                    )
                    
                    # Pre-load all indexes
                    for index_name in self.document_index_map.values():
                        self.multi_index_manager.get_or_create_index_store(index_name)
                    
                    logger.info(f"✅ [STEP 1.1] RAGSystem: Loaded {len(self.document_index_map)} document indexes")
                    return True
                else:
                    # Fallback to single index (backward compatibility)
                    logger.info(f"[STEP 1.1] RAGSystem: No document index mappings found, using default index: {self.opensearch_index or 'aris-rag-index'}")
                self.vectorstore = VectorStoreFactory.load_vector_store(
                    store_type="opensearch",
                    embeddings=self.embeddings,
                    path=self.opensearch_index or "aris-rag-index",
                    opensearch_domain=self.opensearch_domain,
                    opensearch_index=self.opensearch_index
                )
                logger.info(f"✅ [STEP 1.1] RAGSystem: OpenSearch vectorstore connected successfully")
                return True
            except Exception as e:
                logger.error(f"❌ [STEP 1.1] RAGSystem: Failed to load OpenSearch vectorstore: {str(e)}")
                return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG system."""
        total_documents = len(self.document_index)
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        
        # Estimate embedding cost (text-embedding-3-small: $0.02 per 1M tokens)
        estimated_cost = (self.total_tokens / 1_000_000) * 0.02
        
        return {
            'total_documents': total_documents,
            'total_chunks': total_chunks,
            'total_tokens': self.total_tokens,
            'estimated_embedding_cost_usd': estimated_cost
        }
    
    def get_chunk_token_stats(self) -> Dict:
        """
        Get token statistics for all chunks in the vectorstore.
        Uses metrics collector data if available, otherwise estimates from vectorstore.
        
        Returns:
            Dict with token distribution statistics
        """
        if self.vectorstore is None:
            return {
                'chunk_token_counts': [],
                'avg_tokens_per_chunk': 0,
                'min_tokens_per_chunk': 0,
                'max_tokens_per_chunk': 0,
                'total_chunks': 0,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Try to get actual chunk token counts from vectorstore first (most accurate)
        chunk_token_counts = []
        try:
            # Access the underlying documents from vectorstore
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'page_content'):
                        # Always recalculate from actual content for accuracy
                        # This ensures we get the real token count, not potentially stale metadata
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                    elif hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        # Fallback to metadata if page_content not available
                        chunk_token_counts.append(doc.metadata['token_count'])
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass
        
        # Fallback: Try to get from metrics collector
        if not chunk_token_counts and self.metrics_collector and hasattr(self.metrics_collector, 'processing_metrics'):
            for metric in self.metrics_collector.processing_metrics:
                if metric.success and metric.chunks_created > 0:
                    # Estimate tokens per chunk (total tokens / chunks)
                    tokens_per_chunk = metric.tokens_extracted / metric.chunks_created if metric.chunks_created > 0 else 0
                    # Add tokens for each chunk (approximate)
                    for _ in range(metric.chunks_created):
                        chunk_token_counts.append(int(tokens_per_chunk))
        
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # If we got actual counts from vectorstore, return them
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Fallback: try to get from vectorstore directly (if not already done)
        try:
            # Access the underlying documents
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                chunk_token_counts = []
                
                # Extract token counts from document metadata or count from content
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        chunk_token_counts.append(doc.metadata['token_count'])
                    elif hasattr(doc, 'page_content'):
                        # Count tokens from actual content
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                
                if chunk_token_counts:
                    return {
                        'chunk_token_counts': chunk_token_counts,
                        'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                        'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                        'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                        'total_chunks': len(chunk_token_counts),
                        'configured_chunk_size': self.chunk_size,
                        'configured_chunk_overlap': self.chunk_overlap
                    }
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass
        
        # Final fallback: estimate from total tokens and chunks
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        if total_chunks > 0 and self.total_tokens > 0:
            avg_tokens = self.total_tokens / total_chunks
            # Create a distribution estimate
            estimated_counts = [int(avg_tokens)] * total_chunks
            return {
                'chunk_token_counts': estimated_counts,
                'avg_tokens_per_chunk': avg_tokens,
                'min_tokens_per_chunk': int(avg_tokens * 0.8),  # Estimate
                'max_tokens_per_chunk': int(avg_tokens * 1.2),  # Estimate
                'total_chunks': total_chunks,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Return empty stats if nothing works
        return {
            'chunk_token_counts': [],
            'avg_tokens_per_chunk': 0,
            'min_tokens_per_chunk': 0,
            'max_tokens_per_chunk': 0,
            'total_chunks': 0,
            'configured_chunk_size': self.chunk_size,
            'configured_chunk_overlap': self.chunk_overlap
        }


    def _store_extracted_images(
        self,
        image_content_map: Dict,
        contributing_docs: set
    ):
        """
        Store extracted images in OpenSearch at query time.
        
        Args:
            image_content_map: Dictionary mapping (source, image_index) to content list
            contributing_docs: Set of document sources that contributed images
        """
        if not image_content_map:
            return
        
        # Only store if OpenSearch is configured
        if (not hasattr(self, 'vector_store_type') or 
            self.vector_store_type.lower() != 'opensearch'):
            return
        
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            # Import image logger
            try:
                from shared.utils.image_extraction_logger import image_logger
            except ImportError:
                image_logger = None
            
            # Log storage start
            if image_logger:
                total_images = sum(len(contents) for contents in image_content_map.values())
                image_logger.log_storage_start(
                    source="query_time",
                    image_count=total_images,
                    storage_method="opensearch"
                )
            
            # Initialize images store
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            # Convert image_content_map to list of image dictionaries
            images_to_store = []
            for (source, img_idx), contents in image_content_map.items():
                for content_info in contents:
                    image_data = {
                        'source': source,
                        'image_number': img_idx,
                        'page': content_info.get('page', 0),
                        'ocr_text': content_info.get('ocr_text', ''),
                        'marker_detected': True,
                        'extraction_method': 'query_time',
                        'full_chunk': content_info.get('full_chunk', ''),
                        'context_before': content_info.get('context_before', '')
                    }
                    images_to_store.append(image_data)
                    
                    # Log query extraction
                    if image_logger:
                        image_logger.log_query_extraction(
                            source=source,
                            image_number=img_idx,
                            ocr_text_length=len(content_info.get('ocr_text', '')),
                            extraction_method='query_time',
                            page=content_info.get('page')
                        )
            
            # Store images in batch
            if images_to_store:
                image_ids = images_store.store_images_batch(images_to_store)
                
                # Log storage success
                if image_logger:
                    image_logger.log_storage_success(
                        source="query_time",
                        images_stored=len(image_ids),
                        image_ids=image_ids
                    )
                
                logger.info(f"✅ Stored {len(image_ids)} images in OpenSearch at query time")
        except ImportError as e:
            logger.debug(f"OpenSearch images store not available: {str(e)}")
        except Exception as e:
            # Log storage failure
            if image_logger:
                total_images = sum(len(contents) for contents in image_content_map.values())
                image_logger.log_storage_failure(
                    source="query_time",
                    error=str(e),
                    images_attempted=total_images
                )
            logger.warning(f"⚠️  Failed to store images in OpenSearch: {str(e)}")
    
    def query_images(
        self,
        question: str,
        source: Optional[str] = None,
        active_sources: Optional[List[str]] = None,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search images directly in OpenSearch images index.
        
        Args:
            question: Search query
            source: Optional single document source to filter by (deprecated)
            active_sources: Optional list of document names to filter by (preferred)
            k: Number of results to return
            
        Returns:
            List of image dictionaries with OCR text
        """
        # Only search if OpenSearch is configured
        if (not hasattr(self, 'vector_store_type') or 
            self.vector_store_type.lower() != 'opensearch'):
            logger.warning("OpenSearch not configured - cannot search images")
            return []
        
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            # Initialize images store
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            # Determine effective sources: active_sources takes priority over source
            effective_sources = active_sources if active_sources else ([source] if source else None)
            
            # Log the filter being applied
            if effective_sources:
                logger.info(f"Image query filtered to documents: {effective_sources}")
            else:
                logger.info(f"Image query across ALL documents")
            
            # Search images
            results = images_store.search_images(
                query=question,
                sources=effective_sources,
                k=k
            )
            
            logger.info(f"Found {len(results)} images matching query: {question[:50]}")
            if len(results) == 0:
                logger.debug(f"No images found for query: '{question}'. Source filter: {effective_sources}")
            return results
        except ImportError as e:
            logger.warning(f"OpenSearch images store not available: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Failed to search images: {str(e)}")
            return []
    def get_document_images(self, source: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve all images for a specific document source.
        """
        if (not hasattr(self, 'vector_store_type') or 
            self.vector_store_type.lower() != 'opensearch'):
            return []
            
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            return images_store.get_images_by_source(source, limit)
        except Exception as e:
            logger.error(f"Error getting images for source {source}: {e}")
            return []

    def delete_document(self, source: str) -> bool:
        """
        Delete a document and its images from vector stores.
        """
        success = True
        
        # 1. Delete from main vector store
        try:
            if self.vectorstore:
                # We need a way to delete by source
                # In OpenSearch this usually involves a delete_by_query
                client = self.vectorstore.client if hasattr(self.vectorstore, 'client') else None
                if client:
                    index_name = self.opensearch_index
                    query = {"query": {"term": {"metadata.source.keyword": source}}}
                    client.delete_by_query(index=index_name, body=query)
                    logger.info(f"Deleted document {source} from {index_name}")
                else:
                    logger.warning(f"Could not delete {source}: No client available")
        except Exception as e:
            logger.error(f"Error deleting document {source} from main store: {e}")
            success = False

        # 2. Delete from images store
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            # Need to implement delete_by_source in images_store or use client directly
            client = images_store.vectorstore.vectorstore.client
            image_index = images_store.index_name
            query = {"query": {"term": {"metadata.source.keyword": source}}}
            client.delete_by_query(index=image_index, body=query)
            logger.info(f"Deleted images for {source} from {image_index}")
        except Exception as e:
            logger.error(f"Error deleting images for {source}: {e}")
            # Don't strictly fail if images deletion fails
            
        return success
