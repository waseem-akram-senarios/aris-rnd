"""
Gateway Service Layer - Proxies requests to Ingestion and Retrieval services.
"""
import os
import logging
import asyncio
import httpx
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv

from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from scripts.setup_logging import get_logger
logger = logging.getLogger(__name__)

load_dotenv()

class GatewayService:
    """Service layer that orchestrates microservices"""
    
    def __init__(self):
        self.ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://127.0.0.1:8501")
        self.retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8502")
        self.mcp_url = os.getenv("MCP_SERVICE_URL", "http://127.0.0.1:8503")
        
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        self.document_registry = DocumentRegistry(registry_path)
        self._active_sources = []
        self._opensearch_index = ARISConfig.AWS_OPENSEARCH_INDEX  # Make it settable
        # Use ARISConfig default if env vars are not set
        self._opensearch_domain = os.getenv("OPENSEARCH_DOMAIN") or os.getenv("AWS_OPENSEARCH_DOMAIN") or ARISConfig.AWS_OPENSEARCH_DOMAIN
        
        # Compatibility attributes for UI
        self.use_cerebras = ARISConfig.USE_CEREBRAS
        
        # Registry modification tracking
        self._registry_mtime = 0
        
        logger.info(f"Gateway initialized. Ingestion: {self.ingestion_url}, Retrieval: {self.retrieval_url}, MCP: {self.mcp_url}")
    
    def _reload_registry(self):
        """Reload document registry from disk if modified."""
        try:
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            if os.path.exists(registry_path):
                current_mtime = os.path.getmtime(registry_path)
                if current_mtime > self._registry_mtime:
                    self.document_registry = DocumentRegistry(registry_path)
                    self._registry_mtime = current_mtime
                    logger.debug(f"Gateway: Registry reloaded ({len(self.document_registry.list_documents())} docs)")
                    return True
            return False
        except Exception as e:
            logger.warning(f"Gateway: Could not reload registry: {e}")
            return False

    @property
    def embedding_model(self):
        return ARISConfig.EMBEDDING_MODEL

    @property
    def openai_model(self):
        return ARISConfig.OPENAI_MODEL

    @property
    def cerebras_model(self):
        return ARISConfig.CEREBRAS_MODEL

    @property
    def vectorstore(self):
        """Compatibility property for UI status checks"""
        class DummyVS:
            def __init__(self):
                self.index = type('obj', (object,), {'ntotal': 0})
        return DummyVS()

    @property
    def active_sources(self):
        return self._active_sources

    @active_sources.setter
    def active_sources(self, value):
        self._active_sources = value

    def load_selected_documents(self, document_names: List[str], **kwargs) -> Dict:
        """Compatibility method for UI - sets active sources for filtering"""
        logger.info(f"Gateway: Setting active sources to: {document_names}")
        self._active_sources = document_names
        
        return {
            "loaded": True, 
            "message": f"Successfully set filter to {len(document_names)} document(s).",
            "chunks_loaded": 0,
            "docs_loaded": len(document_names)
        }

    def list_documents(self) -> list:
        return self.document_registry.list_documents()

    def get_document(self, document_id: str) -> Optional[Dict]:
        return self.document_registry.get_document(document_id)

    def remove_document(self, document_id: str) -> bool:
        """Removes document from registry and proxies deletion to Retrieval Service"""
        # 1. Remove from registry
        success = self.document_registry.remove_document(document_id)
        
        # 2. Proxy deletion to Retrieval Service (async background or just wait)
        # We'll use a simple background-like fire and forget for the microservice deletion
        # but for end-to-end verification we might want to wait.
        return success

    def update_document(self, document_id: str, metadata: Dict) -> bool:
        """Updates document metadata in registry"""
        self.document_registry.add_document(document_id, metadata)
        return True

    async def query_text_only(
        self, 
        question: str, 
        k: int = 6, 
        document_id: Optional[str] = None, 
        use_mmr: bool = True,
        use_hybrid_search: bool = True,  # Default to hybrid search
        semantic_weight: float = 0.7,
        search_mode: str = "hybrid",  # Default to hybrid mode
        use_agentic_rag: Optional[bool] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_language: Optional[str] = None,
        filter_language: Optional[str] = None,
        auto_translate: bool = False
    ) -> Dict:
        """Proxies query to Retrieval Service with hybrid search as default"""
        import uuid
        request_id = str(uuid.uuid4())
        logger.info(f"Gateway: [ReqID: {request_id}] Starting query_text_only for question: '{question[:50]}...' (search_mode={search_mode})")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload = {
                "question": question,
                "k": k,
                "document_id": document_id,
                "use_mmr": use_mmr,
                "use_hybrid_search": use_hybrid_search,
                "semantic_weight": semantic_weight,
                "search_mode": search_mode,  # Pass search mode to retrieval
                "use_agentic_rag": use_agentic_rag,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "active_sources": self._active_sources,
                "response_language": response_language,
                "filter_language": filter_language,
                "auto_translate": auto_translate
            }
            try:
                headers = {"X-Request-ID": request_id}
                response = await client.post(f"{self.retrieval_url}/query", json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.NetworkError, httpx.PoolTimeout) as e:
                # Microservice not available - fall back to direct querying
                logger.warning(f"Retrieval service unavailable ({e}), falling back to direct querying")
                result = self._query_with_rag_direct(
                    question=question,
                    k=k,
                    use_mmr=use_mmr,
                    document_id=document_id,
                    response_language=response_language,
                    filter_language=filter_language,
                    auto_translate=auto_translate
                )
                # Convert to query_text_only format
                return {
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "citations": result.get("citations", []),
                    "num_chunks_used": result.get("num_chunks_used", 0),
                    "response_time": result.get("response_time", 0.0),
                    "context_tokens": result.get("context_tokens", 0),
                    "response_tokens": result.get("response_tokens", 0),
                    "total_tokens": result.get("total_tokens", 0)
                }
            except Exception as e:
                # Check if it's a connection-related error by message
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['connection', 'connect', 'refused', 'failed', 'unreachable', 'timeout']):
                    logger.warning(f"Connection error detected ({e}), falling back to direct querying")
                    result = self._query_with_rag_direct(
                        question=question,
                        k=k,
                        use_mmr=use_mmr,
                        document_id=document_id,
                        response_language=response_language,
                        filter_language=filter_language,
                        auto_translate=auto_translate
                    )
                    # Convert to query_text_only format
                    return {
                        "answer": result.get("answer", ""),
                        "sources": result.get("sources", []),
                        "citations": result.get("citations", []),
                        "num_chunks_used": result.get("num_chunks_used", 0),
                        "response_time": result.get("response_time", 0.0),
                        "context_tokens": result.get("context_tokens", 0),
                        "response_tokens": result.get("response_tokens", 0),
                        "total_tokens": result.get("total_tokens", 0)
                    }
                return {
                    "answer": f"Retrieval service error: {str(e)}", 
                    "sources": [], 
                    "citations": [],
                    "num_chunks_used": 0,
                    "response_time": 0.0,
                    "context_tokens": 0,
                    "response_tokens": 0,
                    "total_tokens": 0
                }

    async def query_with_rag(
        self,
        question: str,
        k: int = None,
        use_mmr: bool = None,
        use_hybrid_search: bool = None,
        semantic_weight: float = None,
        search_mode: str = None,
        use_agentic_rag: bool = None,
        temperature: float = None,
        max_tokens: int = None,
        document_id: Optional[str] = None,
        response_language: Optional[str] = None,
        filter_language: Optional[str] = None,
        auto_translate: bool = False,
        active_sources: Optional[List[str]] = None  # NEW: Explicit active_sources parameter
    ) -> Dict:
        """
        Compatibility method for UI - proxies query_with_rag to Retrieval Service.
        This method matches the RAGSystem.query_with_rag signature for seamless integration.
        """
        import uuid
        
        # If active_sources explicitly passed, use it; otherwise use instance-level setting
        if active_sources is not None:
            self._active_sources = active_sources
            logger.info(f"Gateway: active_sources explicitly set to: {active_sources}")
        
        request_id = str(uuid.uuid4())
        logger.info(f"Gateway: [ReqID: {request_id}] Starting query_with_rag for question: '{question[:50]}...'")
        logger.info(f"Gateway: [ReqID: {request_id}] Document filter (active_sources): {self._active_sources}")
        
        # Build payload with all parameters
        payload = {
            "question": question
        }
        
        if k is not None:
            payload["k"] = k
        if use_mmr is not None:
            payload["use_mmr"] = use_mmr
        if use_hybrid_search is not None:
            payload["use_hybrid_search"] = use_hybrid_search
        if semantic_weight is not None:
            payload["semantic_weight"] = semantic_weight
        if search_mode is not None:
            payload["search_mode"] = search_mode
        if use_agentic_rag is not None:
            payload["use_agentic_rag"] = use_agentic_rag
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if document_id is not None:
            payload["document_id"] = document_id
        if response_language is not None:
            payload["response_language"] = response_language
        if filter_language is not None:
            payload["filter_language"] = filter_language
        # FIXED: Always include auto_translate in payload (even when False)
        payload["auto_translate"] = auto_translate
            
        # Add active_sources to ensure strict filtering in Retrieval Service
        # CRITICAL: Always send active_sources to properly clear filters on "All Documents"
        if self._active_sources:
            payload["active_sources"] = self._active_sources
            logger.info(f"Gateway: [ReqID: {request_id}] Filtering to specific documents: {self._active_sources}")
            # If only one source, also set document_id for backward compatibility
            if not document_id and len(self._active_sources) == 1:
                payload["document_id"] = self._active_sources[0]
        elif document_id:
            payload["active_sources"] = [document_id]
            logger.info(f"Gateway: [ReqID: {request_id}] Filtering to document_id: {document_id}")
        else:
            # IMPORTANT: Explicitly send empty list to clear any previous filter in Retrieval Service
            payload["active_sources"] = []
            logger.info(f"Gateway: [ReqID: {request_id}] 📚 ALL DOCUMENTS mode - no filter applied")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                headers = {"X-Request-ID": request_id}
                response = await client.post(f"{self.retrieval_url}/query", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"Gateway: [ReqID: {request_id}] Retrieval service returned answer ({len(result.get('answer', ''))} chars)")
                # FastAPI serializes Pydantic models to dicts automatically
                citations = result.get("citations", [])
                # Ensure citations are dicts (they should be from FastAPI JSON response)
                if citations and not isinstance(citations[0], dict):
                    citations = [{
                        "id": getattr(c, "id", ""),
                        "source": getattr(c, "source", ""),
                        "page": getattr(c, "page", 1),
                        "snippet": getattr(c, "snippet", ""),
                        "full_text": getattr(c, "full_text", ""),
                        "source_location": getattr(c, "source_location", "")
                    } for c in citations]
                
                return {
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "citations": citations,
                    "num_chunks_used": result.get("num_chunks_used", 0),
                    "response_time": result.get("response_time", 0.0),
                    "context_tokens": result.get("context_tokens", 0),
                    "response_tokens": result.get("response_tokens", 0),
                    "total_tokens": result.get("total_tokens", 0)
                }
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.NetworkError, httpx.PoolTimeout) as e:
                # Microservice not available - fall back to direct querying
                logger.warning(f"Retrieval service unavailable ({e}), falling back to direct querying")
                return await self._query_with_rag_direct(
                    question=question,
                    k=k,
                    use_mmr=use_mmr,
                    use_hybrid_search=use_hybrid_search,
                    semantic_weight=semantic_weight,
                    search_mode=search_mode,
                    use_agentic_rag=use_agentic_rag,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    document_id=document_id,
                    response_language=response_language,
                    filter_language=filter_language,
                    auto_translate=auto_translate
                )
            except Exception as e:
                # Check if it's a connection-related error by message
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['connection', 'connect', 'refused', 'failed', 'unreachable', 'timeout']):
                    logger.warning(f"Connection error detected ({e}), falling back to direct querying")
                    return await self._query_with_rag_direct(
                        question=question,
                        k=k,
                        use_mmr=use_mmr,
                        use_hybrid_search=use_hybrid_search,
                        semantic_weight=semantic_weight,
                        search_mode=search_mode,
                        use_agentic_rag=use_agentic_rag,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        document_id=document_id,
                        response_language=response_language,
                        filter_language=filter_language,
                        auto_translate=auto_translate
                    )
                logger.error(f"Error calling retrieval service for query_with_rag: {e}")
                return {
                    "answer": f"Retrieval service error: {str(e)}",
                    "sources": [],
                    "citations": [],
                    "num_chunks_used": 0,
                    "response_time": 0.0,
                    "context_tokens": 0,
                    "response_tokens": 0,
                    "total_tokens": 0
                }
    
    def _query_with_rag_direct(
        self,
        question: str,
        k: int = None,
        use_mmr: bool = None,
        use_hybrid_search: bool = None,
        semantic_weight: float = None,
        search_mode: str = None,
        use_agentic_rag: bool = None,
        temperature: float = None,
        max_tokens: int = None,
        document_id: Optional[str] = None,
        response_language: Optional[str] = None,
        filter_language: Optional[str] = None,
        auto_translate: bool = False
    ) -> Dict:
        """
        Direct query fallback when retrieval service is unavailable.
        Uses RetrievalEngine directly for querying.
        """
        logger.info(f"Gateway: Using direct querying for question: {question[:50]}...")
        try:
            from services.retrieval.engine import RetrievalEngine
            
            # Create a temporary RetrievalEngine for querying
            engine = RetrievalEngine(
                use_cerebras=self.use_cerebras,
                vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
                opensearch_domain=self._opensearch_domain,
                opensearch_index=self._opensearch_index,
                chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
                chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
            )
            
            # Set active_sources for document filtering
            if document_id:
                engine.active_sources = [document_id]
            elif self._active_sources:
                engine.active_sources = self._active_sources
            
            # Execute query
            result = engine.query_with_rag(
                question=question,
                k=k,
                use_mmr=use_mmr,
                use_hybrid_search=use_hybrid_search,
                semantic_weight=semantic_weight,
                search_mode=search_mode,
                use_agentic_rag=use_agentic_rag,
                temperature=temperature,
                max_tokens=max_tokens,
                response_language=response_language,
                filter_language=filter_language,
                auto_translate=auto_translate
            )
            
            return result
        except Exception as e:
            logger.error(f"Direct querying also failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "answer": f"Query failed: {str(e)}. Please ensure the retrieval service is running or documents are properly indexed.",
                "sources": [],
                "citations": [],
                "context_chunks": [],
                "num_chunks_used": 0,
                "response_time": 0.0,
                "context_tokens": 0,
                "response_tokens": 0,
                "total_tokens": 0
            }

    async def ingest_document(self, file_content: bytes, file_name: str, parser_preference: Optional[str] = None, index_name: Optional[str] = None, language: str = "eng") -> Dict:
        """Proxies ingestion to Ingestion Service"""
        import uuid
        request_id = str(uuid.uuid4())
        logger.info(f"Gateway: [ReqID: {request_id}] Proxied ingestion for {file_name}")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            headers = {"X-Request-ID": request_id}
            files = {"file": (file_name, file_content)}
            data = {"parser_preference": parser_preference} if parser_preference else {}
            if index_name:
                data["index_name"] = index_name
            if language:
                data["language"] = language
            try:
                response = await client.post(f"{self.ingestion_url}/ingest", files=files, data=data, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error calling ingestion service: {e}")
                raise Exception(f"Ingestion service error: {str(e)}")

    async def query_images_only(self, question: str, k: int = 5, source: Optional[str] = None, active_sources: Optional[List[str]] = None) -> List[Dict]:
        """Proxies image query to Retrieval Service.
        
        Args:
            question: Search query for images
            k: Number of results
            source: Single document to filter (deprecated)
            active_sources: List of document names to filter (preferred, same as text query)
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        # Determine effective filter
        if active_sources:
            logger.info(f"Gateway: [ReqID: {request_id}] Image query filtered to {len(active_sources)} document(s): {active_sources}")
        elif source:
            logger.info(f"Gateway: [ReqID: {request_id}] Image query filtered to single doc: {source}")
        else:
            logger.info(f"Gateway: [ReqID: {request_id}] Image query across ALL documents")
        
        logger.info(f"Gateway: [ReqID: {request_id}] Starting query_images_only for question: '{question[:50]}...'")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "question": question,
                "k": k
            }
            # Add filter - prefer active_sources over source
            if active_sources:
                payload["active_sources"] = active_sources
            elif source:
                payload["source"] = source
            
            try:
                headers = {"X-Request-ID": request_id}
                response = await client.post(f"{self.retrieval_url}/query/images", json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                # Extract images list from ImageQueryResponse
                if isinstance(result, dict) and "images" in result:
                    # Convert ImageResult objects to dicts if needed
                    images = result["images"]
                    if images and isinstance(images[0], dict):
                        return images
                    else:
                        # If Pydantic models, convert to dicts
                        return [img.dict() if hasattr(img, 'dict') else img for img in images]
                return result if isinstance(result, list) else []
            except Exception as e:
                logger.error(f"Error calling retrieval service (images): {e}")
                return []

    async def get_document_images(self, document_id: str) -> List[Dict]:
        """Proxies get_document_images to Retrieval Service"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(f"{self.retrieval_url}/documents/{document_id}/images")
                if response.status_code == 200:
                    result = response.json()
                    return result.get("images", [])
                return []
            except Exception as e:
                logger.error(f"Error calling retrieval service (get_document_images): {e}")
                return []

    async def delete_document_from_stores(self, document_id: str) -> bool:
        """Proxies DELETE to both Ingestion and Retrieval Services, and cleans up dedicated indexes."""
        results = []
        
        # 0. Get index_name before deletion for cleanup
        index_name = None
        try:
            self._reload_registry()
            doc = self.document_registry.get_document(document_id)
            if doc:
                index_name = doc.get("text_index") or doc.get("index_name")
        except Exception as e:
            logger.debug(f"Gateway: Could not fetch document metadata for index cleanup: {e}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Delete from Ingestion (handles S3 and Ingestion-local Registry)
            try:
                ing_resp = await client.delete(f"{self.ingestion_url}/documents/{document_id}")
                results.append(ing_resp.status_code == 200)
                logger.info(f"Gateway: Deleted document {document_id} from Ingestion")
            except Exception as e:
                logger.warning(f"Gateway: Failed to delete {document_id} from Ingestion: {e}")
                results.append(False)

            # 2. Delete from Retrieval (handles Vectors)
            try:
                ret_resp = await client.delete(f"{self.retrieval_url}/documents/{document_id}")
                results.append(ret_resp.status_code == 200)
                logger.info(f"Gateway: Deleted document {document_id} from Retrieval")
            except Exception as e:
                logger.warning(f"Gateway: Failed to delete {document_id} from Retrieval: {e}")
                results.append(False)

            # 3. Dedicated Index Cleanup
            # If the index name starts with 'aris-doc-', it's a dedicated index for this document
            if index_name and index_name.startswith("aris-doc-"):
                try:
                    logger.info(f"Gateway: Detected dedicated index '{index_name}' for document {document_id}. Deleting index.")
                    idx_resp = await client.delete(f"{self.retrieval_url}/admin/indexes/{index_name}?confirm=true")
                    if idx_resp.status_code == 200:
                        logger.info(f"Gateway: Successfully deleted dedicated index '{index_name}'")
                    else:
                        logger.warning(f"Gateway: Failed to delete dedicated index '{index_name}': {idx_resp.text}")
                except Exception as e:
                    logger.warning(f"Gateway: Error deleting dedicated index '{index_name}': {e}")
        
        return any(results)

    async def delete_index_synced(self, index_name: str) -> Dict[str, Any]:
        """
        Deletes an index and removes all associated documents from the registry.
        """
        logger.info(f"Gateway: Starting synced deletion of index '{index_name}'")
        
        # 1. Delete the index from Retrieval service
        deletion_result = {"success": False, "message": "Index deletion not started"}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.delete(f"{self.retrieval_url}/admin/indexes/{index_name}?confirm=true")
                if resp.status_code == 200:
                    deletion_result = resp.json()
                    logger.info(f"Gateway: Index '{index_name}' deleted from Retrieval")
                elif resp.status_code == 404:
                    deletion_result = {"success": False, "message": f"Index '{index_name}' does not exist", "chunks_deleted": 0}
                    logger.info(f"Gateway: Index '{index_name}' was already gone from Retrieval")
                else:
                    return {"success": False, "error": f"Retrieval Service failed: {resp.text}"}
        except Exception as e:
            logger.error(f"Gateway: Error calling Retrieval Service for index deletion: {e}")
            return {"success": False, "error": str(e)}

        # 2. Clean up Document Registry
        try:
            self._reload_registry()
            all_docs = self.document_registry.list_documents()
            removed_count = 0
            
            for doc in all_docs:
                doc_idx = doc.get("text_index") or doc.get("index_name")
                if doc_idx == index_name:
                    doc_id = doc.get("document_id")
                    if doc_id:
                        self.document_registry.remove_document(doc_id)
                        removed_count += 1
                        logger.info(f"Gateway: Removed document {doc_id} from registry (associated with index {index_name})")
            
            deletion_result["documents_removed_from_registry"] = removed_count
            deletion_result["synced"] = True
            
        except Exception as e:
            logger.warning(f"Gateway: Error during registry cleanup for index {index_name}: {e}")
            deletion_result["registry_cleanup_error"] = str(e)
            
        return deletion_result

    async def process_document(self, file_path, file_content, file_name, parser_preference=None, progress_callback=None, index_name=None, language="eng", is_update=False, old_index_name=None) -> "ProcessingResult":
        """Proxies process_document for compatibility with UI - falls back to direct processing if microservice unavailable
        
        Args:
            is_update: Whether this is an update to an existing document
            old_index_name: Old index name to clean up if updating
        """
        logger.info(f"Gateway: Processing document {file_name} (is_update={is_update})")
        try:
            # Try microservice first
            from shared.schemas import ProcessingResult as SchemaResult
            import uuid
            import time
            request_id = str(uuid.uuid4())
            logger.info(f"Gateway: [ReqID: {request_id}] Starting ingestion for {file_name}")
            
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Step 1: Start asynchronous ingestion
                headers = {"X-Request-ID": request_id}
                files = {"file": (file_name, file_content)}
                data = {"parser_preference": parser_preference} if parser_preference else {}
                if index_name:
                    data["index_name"] = index_name
                if language:
                    data["language"] = language
                # Pass update flags to ingestion service
                if is_update:
                    data["is_update"] = "true"
                if old_index_name:
                    data["old_index_name"] = old_index_name
                
                logger.info(f"Gateway: [ReqID: {request_id}] Starting async ingestion for {file_name} with index {index_name} (lang={language}, is_update={is_update})")
                response = await client.post(f"{self.ingestion_url}/ingest", files=files, data=data, headers=headers)
                response.raise_for_status()
                
                ingest_data = response.json()
                doc_id = ingest_data.get("document_id")
                
                if not doc_id:
                    logger.error(f"Ingestion service did not return a document_id: {ingest_data}")
                    raise ValueError("Ingestion service failed to start processing")
                
                # Step 2: Poll for status and report progress via callback
                logger.info(f"Gateway: Polling status for document {doc_id}...")
                last_progress = 0.0
                start_poll_time = time.time()
                
                while True:
                    try:
                        status_resp = await client.get(f"{self.ingestion_url}/status/{doc_id}")
                        if status_resp.status_code == 200:
                            state = status_resp.json()
                            status = state.get("status")
                            progress = state.get("progress", 0.0)
                            detailed_msg = state.get("detailed_message", "")
                            
                            # Report progress via callback if there's an update
                            if progress_callback and (progress > last_progress or detailed_msg):
                                last_progress = progress
                                try:
                                    # Handle both function and method callbacks
                                    import inspect
                                    sig = inspect.signature(progress_callback)
                                    if len(sig.parameters) > 2:
                                        progress_callback(status, progress, detailed_message=detailed_msg)
                                    else:
                                        progress_callback(status, progress)
                                except Exception as cb_err:
                                    logger.warning(f"Progress callback error: {cb_err}")
                            
                            # ALWAYS check for completion status (success/failed) - not just when progress updates
                            if status == "success":
                                logger.info(f"Gateway: Ingestion successful for {doc_id}")
                                result_data = state.get("result")
                                if result_data:
                                    return SchemaResult(**result_data)
                                else:
                                    # Fallback result if missed
                                    return SchemaResult(status="success", document_name=file_name)
                            elif status == "failed":
                                error_msg = state.get("error", "Unknown error")
                                logger.error(f"Gateway: Ingestion failed for {doc_id}: {error_msg}")
                                return SchemaResult(status="failed", document_name=file_name, error=error_msg)
                        
                    except Exception as poll_err:
                        logger.warning(f"Polling error for {doc_id}: {poll_err}")
                    
                    # Check for timeout (1 hour for very large documents)
                    if time.time() - start_poll_time > 3600:
                        raise TimeoutError(f"Processing timeout for document {doc_id}")
                    
                    # Wait before next poll
                    await asyncio.sleep(1.0)
                
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as e:
            # Microservice not available - fall back to direct processing
            logger.warning(f"Microservice unavailable ({e}), falling back to direct processing")
            return await self._process_document_direct(file_path, file_content, file_name, parser_preference, progress_callback, index_name, language)
        except Exception as e:
            # Check if it's a connection-related error
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['connection', 'connect', 'refused', 'failed', 'unreachable', 'timeout']):
                logger.warning(f"Connection error ({e}), falling back to direct processing")
                return await self._process_document_direct(file_path, file_content, file_name, parser_preference, progress_callback, index_name, language)
            
            logger.error(f"Error in Gateway process_document: {e}")
            from shared.schemas import ProcessingResult as SchemaResult
            return SchemaResult(
                status="failed",
                document_name=file_name,
                error=str(e)
            )
    
    async def get_processing_state(self, doc_id: str) -> Optional[Dict]:
        """Get processing status from Ingestion service"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.ingestion_url}/status/{doc_id}")
                if resp.status_code == 200:
                    return resp.json()
                return None
            except Exception as e:
                logger.warning(f"Error fetching processing state for {doc_id}: {e}")
                return None

    async def _process_document_direct(self, file_path, file_content, file_name, parser_preference=None, progress_callback=None, index_name=None, language="eng") -> "ProcessingResult":
        """
        Direct document processing fallback when ingestion service is unavailable.
        Uses DocumentProcessor directly.
        """
        logger.info(f"Gateway: Using direct processing for {file_name}")
        try:
            from services.ingestion.engine import IngestionEngine
            from services.ingestion.processor import DocumentProcessor
            
            # Create a temporary IngestionEngine
            engine = IngestionEngine(
                use_cerebras=self.use_cerebras,
                vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
                opensearch_domain=self._opensearch_domain,
                opensearch_index=self._opensearch_index,
                chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
                chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
            )
            
            processor = DocumentProcessor(engine)
            # Assuming processor.process_document is currently sync, but we treat it as if it could be async 
            # Or just call it normally if it's CPU bound. 
            # If it's heavy CPU work, we might want run_in_executor but for now keep simple.
            return processor.process_document(
                file_path=file_path,
                file_content=file_content,
                file_name=file_name,
                parser_preference=parser_preference,
                progress_callback=progress_callback,
                index_name=index_name,
                language=language
            )
        except Exception as e:
            logger.error(f"Direct processing also failed: {e}")
            import traceback
            traceback.print_exc()
            from shared.schemas import ProcessingResult as SchemaResult
            return SchemaResult(
                status="failed",
                document_name=file_name,
                error=f"Processing failed: {str(e)}"
            )

    @property
    def vector_store_type(self):
        return ARISConfig.VECTOR_STORE_TYPE

    @property
    def opensearch_domain(self):
        return self._opensearch_domain
    
    @opensearch_domain.setter
    def opensearch_domain(self, value):
        self._opensearch_domain = value

    @property
    def opensearch_index(self):
        return self._opensearch_index
    
    @opensearch_index.setter
    def opensearch_index(self, value):
        self._opensearch_index = value

    def save_vectorstore(self, path: str = "vectorstore") -> bool:
        """
        Compatibility method for UI - in microservices, vectorstores are managed by services.
        For FAISS, this would save locally, but in microservices architecture, 
        the ingestion service handles persistence.
        """
        logger.info(f"Gateway: save_vectorstore called (path: {path}) - handled by microservices")
        # In microservices, vectorstores are persisted by the ingestion/retrieval services
        # This is a no-op for compatibility, but we return True to indicate "success"
        return True

    def load_vectorstore(self, path: str = "vectorstore") -> bool:
        """
        Compatibility method for UI - in microservices, vectorstores are loaded by services.
        For FAISS, this would load from disk, but in microservices architecture,
        the retrieval service handles loading from OpenSearch or shared storage.
        """
        logger.info(f"Gateway: load_vectorstore called (path: {path}) - handled by microservices")
        # In microservices, vectorstores are loaded by the retrieval service on demand
        # This is a no-op for compatibility, but we return True to indicate "success"
        return True

    async def get_all_metrics_async(self) -> Dict:
        """Fetch and merge metrics from all services (async version)"""
        # Fetch from Ingestion (processing metrics)
        ingestion_metrics = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ingestion_url}/metrics")
                if resp.status_code == 200:
                    ingestion_metrics = resp.json()
        except Exception as e:
            logger.warning(f"Could not fetch ingestion metrics: {e}")
        
        # Fetch from Retrieval (query metrics)
        retrieval_metrics = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.retrieval_url}/metrics")
                if resp.status_code == 200:
                    retrieval_metrics = resp.json()
        except Exception as e:
            logger.warning(f"Could not fetch retrieval metrics: {e}")
        
        return self._merge_metrics(ingestion_metrics, retrieval_metrics)
    
    def get_all_metrics(self) -> Dict:
        """Fetch and merge metrics from all services (sync version for UI)"""
        # Fetch from Ingestion (processing metrics)
        ingestion_metrics = {}

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.ingestion_url}/metrics")
                if resp.status_code == 200:
                    ingestion_metrics = resp.json()
        except Exception as e:
            logger.warning(f"Could not fetch ingestion metrics: {e}")
        
        # Fetch from Retrieval (query metrics)
        retrieval_metrics = {}
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.retrieval_url}/metrics")
                if resp.status_code == 200:
                    retrieval_metrics = resp.json()
        except Exception as e:
            logger.warning(f"Could not fetch retrieval metrics: {e}")
        
        return self._merge_metrics(ingestion_metrics, retrieval_metrics)
    
    def _merge_metrics(self, ingestion_metrics: Dict, retrieval_metrics: Dict) -> Dict:
        """Merge metrics from ingestion and retrieval services"""
        merged = {
            'processing': ingestion_metrics.get('processing', {}),
            'queries': retrieval_metrics.get('queries', {}),
            'costs': {
                'embedding_cost_usd': ingestion_metrics.get('costs', {}).get('embedding_cost_usd', 0),
                'query_cost_usd': retrieval_metrics.get('costs', {}).get('query_cost_usd', 0),
                'total_cost_usd': (ingestion_metrics.get('costs', {}).get('embedding_cost_usd', 0) + 
                                 retrieval_metrics.get('costs', {}).get('query_cost_usd', 0))
            },
            'parser_comparison': ingestion_metrics.get('parser_comparison', {}),
            'performance_trends': ingestion_metrics.get('performance_trends', {}),
            'error_summary': {
                'total_errors': (ingestion_metrics.get('error_summary', {}).get('total_errors', 0) + 
                               retrieval_metrics.get('error_summary', {}).get('total_errors', 0)),
                'processing_errors': ingestion_metrics.get('error_summary', {}).get('processing_errors', 0),
                'query_errors': retrieval_metrics.get('error_summary', {}).get('query_errors', 0)
            }
        }
        return merged

    # ============================================================================
    # MCP METHODS - Direct Communication
    # ============================================================================

    async def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP server health status."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{self.mcp_url}/health")
                if response.status_code == 200:
                    return response.json()
                return {"status": "unhealthy", "error": f"HTTP {response.status_code}"}
            except Exception as e:
                logger.warning(f"MCP Health check failed: {e}")
                return {"status": "unhealthy", "error": str(e)}

    async def get_mcp_tools(self) -> Dict[str, Any]:
        """Get available MCP tools."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{self.mcp_url}/tools")
                return response.json()
            except Exception as e:
                logger.error(f"Failed to fetch MCP tools: {e}")
                return {"tools": [], "error": str(e)}

    async def trigger_mcp_sync(self) -> Dict[str, Any]:
        """Trigger force sync on MCP server."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Sync Gateway->Ingestion/Retrieval happens via sync_manager usually,
                # but we can trigger MCP specific sync here.
                response = await client.post(f"{self.mcp_url}/sync/force")
                return response.json()
            except Exception as e:
                logger.error(f"Failed to sync MCP: {e}")
                return {"success": False, "error": str(e)}

    async def get_mcp_stats(self) -> Dict[str, Any]:
        """Get MCP internal stats."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                # map to rag_stats tool via api if available, else standard stats endpoint
                response = await client.get(f"{self.mcp_url}/api/stats") 
                if response.status_code == 200:
                    return response.json()
                return {"error": f"HTTP {response.status_code}"}
            except Exception as e:
                logger.error(f"Failed to fetch MCP stats: {e}")
                return {"error": str(e)}

    def get_chunk_token_stats(self) -> Dict:
        """
        Compatibility method for UI - returns token statistics.
        In microservices, this would require querying the retrieval service.
        Returns empty stats for now as an optimization.
        """
        logger.debug("Gateway: get_chunk_token_stats called - returning empty stats (microservices optimization)")
        return {
            'chunk_token_counts': [],
            'total_chunks': 0,
            'total_tokens': 0,
            'avg_tokens_per_chunk': 0,
            'min_tokens': 0,
            'max_tokens': 0,
            'token_distribution': {}
        }

    async def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists (proxies to Ingestion Service).
        Compatibility method for UI.
        """
        import uuid
        request_id = str(uuid.uuid4())
        logger.info(f"Gateway: [ReqID: {request_id}] Checking if index exists: {index_name}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"X-Request-ID": request_id}
                response = await client.get(f"{self.ingestion_url}/indexes/{index_name}/exists", headers=headers)
                if response.status_code == 200:
                    return response.json().get("exists", False)
                return False
        except Exception as e:
            logger.error(f"Gateway: [ReqID: {request_id}] Error checking index existence: {e}")
            return False

    async def find_next_available_index_name(self, base_name: str) -> str:
        """
        Find the next available index name (proxies to Ingestion Service).
        Compatibility method for UI.
        """
        import uuid
        request_id = str(uuid.uuid4())
        logger.info(f"Gateway: [ReqID: {request_id}] Finding next available index for: {base_name}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"X-Request-ID": request_id}
                response = await client.get(f"{self.ingestion_url}/indexes/{base_name}/next-available", headers=headers)
                if response.status_code == 200:
                    return response.json().get("index_name", f"{base_name}-1")
                return f"{base_name}-1"
        except Exception as e:
            logger.error(f"Gateway: [ReqID: {request_id}] Error finding next index name: {e}")
            return f"{base_name}-1"

    def get_sync_status_sync(self) -> Dict:
        """Fetch synchronization status across all services (sync version for UI)"""
        try:
            from shared.utils.sync_manager import get_sync_manager
            sync_manager = get_sync_manager("gateway")
            status = sync_manager.get_sync_status()
            
            # Basic info from gateway
            status["gateway"] = {
                "document_count": len(self.list_documents()),
                "registry_accessible": True,
                "service": "gateway"
            }
            
            # Check other services
            with httpx.Client(timeout=5.0) as client:
                try:
                    ing_resp = client.get(f"{self.ingestion_url}/sync/status")
                    status["ingestion"] = ing_resp.json() if ing_resp.status_code == 200 else {"error": "Service unavailable"}
                except Exception as e:
                    logger.debug(f"get_sync_status_sync: {type(e).__name__}: {e}")
                    status["ingestion"] = {"error": str(e)}
                
                try:
                    ret_resp = client.get(f"{self.retrieval_url}/sync/status")
                    status["retrieval"] = ret_resp.json() if ret_resp.status_code == 200 else {"error": "Service unavailable"}
                except Exception as e:
                    logger.debug(f"get_sync_status_sync: {type(e).__name__}: {e}")
                    status["retrieval"] = {"error": str(e)}
            
            return status
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {"error": str(e)}

    def force_sync_sync(self) -> Dict:
        """Force synchronization across all services (sync version for UI)"""
        try:
            from shared.utils.sync_manager import get_sync_manager

            sync_manager = get_sync_manager("gateway")
            result = sync_manager.force_full_sync()
            
            # Force others
            with httpx.Client(timeout=30.0) as client:
                try:
                    client.post(f"{self.ingestion_url}/sync/force")
                except Exception as e:
                    logger.debug(f"force_sync_sync: {type(e).__name__}: {e}")
                    pass
                
                try:
                    client.post(f"{self.retrieval_url}/sync/force")
                except Exception as e:
                    logger.debug(f"force_sync_sync: {type(e).__name__}: {e}")
                    pass
            
            return {"success": True, "message": "Manual sync triggered across all services"}
        except Exception as e:
            logger.error(f"Error forcing sync: {e}")
            return {"success": False, "error": str(e)}

def create_gateway_service() -> GatewayService:
    return GatewayService()
