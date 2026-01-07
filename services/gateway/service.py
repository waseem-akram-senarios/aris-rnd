"""
Gateway Service Layer - Proxies requests to Ingestion and Retrieval services.
"""
import os
import logging
import httpx
from typing import Dict, Optional, List
from dotenv import load_dotenv

from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from scripts.setup_logging import get_logger

load_dotenv()

logger = get_logger("aris_rag.gateway_service")

class GatewayService:
    """Service layer that orchestrates microservices"""
    
    def __init__(self):
        self.ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8501")
        self.retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8502")
        
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        self.document_registry = DocumentRegistry(registry_path)
        self._active_sources = []
        self._opensearch_index = ARISConfig.AWS_OPENSEARCH_INDEX  # Make it settable
        # Use ARISConfig default if env vars are not set
        self._opensearch_domain = os.getenv("OPENSEARCH_DOMAIN") or os.getenv("AWS_OPENSEARCH_DOMAIN") or ARISConfig.AWS_OPENSEARCH_DOMAIN
        
        # Compatibility attributes for UI
        self.use_cerebras = ARISConfig.USE_CEREBRAS
        
        logger.info(f"Gateway initialized. Ingestion: {self.ingestion_url}, Retrieval: {self.retrieval_url}")

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

    async def query_text_only(self, question: str, k: int = 6, document_id: Optional[str] = None, use_mmr: bool = True) -> Dict:
        """Proxies query to Retrieval Service"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "question": question,
                "k": k,
                "document_id": document_id,
                "use_mmr": use_mmr,
                "active_sources": self._active_sources
            }
            try:
                response = await client.post(f"{self.retrieval_url}/query", json=payload)
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.NetworkError, httpx.PoolTimeout) as e:
                # Microservice not available - fall back to direct querying
                logger.warning(f"Retrieval service unavailable ({e}), falling back to direct querying")
                result = self._query_with_rag_direct(
                    question=question,
                    k=k,
                    use_mmr=use_mmr,
                    document_id=document_id
                )
                # Convert to query_text_only format
                return {
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                    "citations": result.get("citations", [])
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
                        document_id=document_id
                    )
                    # Convert to query_text_only format
                    return {
                        "answer": result.get("answer", ""),
                        "sources": result.get("sources", []),
                        "citations": result.get("citations", [])
                    }
                logger.error(f"Error calling retrieval service: {e}")
                return {"answer": f"Retrieval service error: {str(e)}", "sources": [], "citations": []}

    def query_with_rag(
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
        document_id: Optional[str] = None
    ) -> Dict:
        """
        Compatibility method for UI - proxies query_with_rag to Retrieval Service.
        This method matches the RAGSystem.query_with_rag signature for seamless integration.
        """
        import asyncio
        
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
            
        # Add active_sources to ensure strict filtering in Retrieval Service
        if self._active_sources:
            payload["active_sources"] = self._active_sources
            # If only one source, also set document_id for backward compatibility
            if not document_id and len(self._active_sources) == 1:
                payload["document_id"] = self._active_sources[0]
        elif document_id:
            payload["active_sources"] = [document_id]
        
        async def _query():
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    response = await client.post(f"{self.retrieval_url}/query", json=payload)
                    response.raise_for_status()
                    result = response.json()
                    
                    # Convert QueryResponse format to RAGSystem format
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
                        "context_chunks": result.get("sources", []),  # Compatibility field
                        "num_chunks_used": result.get("num_chunks_used", 0),
                        "response_time": result.get("response_time", 0.0),
                        "context_tokens": result.get("context_tokens", 0),
                        "response_tokens": result.get("response_tokens", 0),
                        "total_tokens": result.get("total_tokens", 0)
                    }
                except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.NetworkError, httpx.PoolTimeout) as e:
                    # Microservice not available - fall back to direct querying
                    logger.warning(f"Retrieval service unavailable ({e}), falling back to direct querying")
                    return self._query_with_rag_direct(
                        question=question,
                        k=k,
                        use_mmr=use_mmr,
                        use_hybrid_search=use_hybrid_search,
                        semantic_weight=semantic_weight,
                        search_mode=search_mode,
                        use_agentic_rag=use_agentic_rag,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        document_id=document_id
                    )
                except Exception as e:
                    # Check if it's a connection-related error by message
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['connection', 'connect', 'refused', 'failed', 'unreachable', 'timeout']):
                        logger.warning(f"Connection error detected ({e}), falling back to direct querying")
                        return self._query_with_rag_direct(
                            question=question,
                            k=k,
                            use_mmr=use_mmr,
                            use_hybrid_search=use_hybrid_search,
                            semantic_weight=semantic_weight,
                            search_mode=search_mode,
                            use_agentic_rag=use_agentic_rag,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            document_id=document_id
                        )
                    logger.error(f"Error calling retrieval service for query_with_rag: {e}")
                    return {
                        "answer": f"Retrieval service error: {str(e)}",
                        "sources": [],
                        "citations": [],
                        "context_chunks": [],
                        "num_chunks_used": 0,
                        "response_time": 0.0,
                        "context_tokens": 0,
                        "response_tokens": 0,
                        "total_tokens": 0
                    }
        
        return asyncio.run(_query())
    
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
        document_id: Optional[str] = None
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
                max_tokens=max_tokens
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
        async with httpx.AsyncClient(timeout=300.0) as client:
            files = {"file": (file_name, file_content)}
            data = {"parser_preference": parser_preference} if parser_preference else {}
            if index_name:
                data["index_name"] = index_name
            if language:
                data["language"] = language
            try:
                response = await client.post(f"{self.ingestion_url}/ingest", files=files, data=data)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error calling ingestion service: {e}")
                raise Exception(f"Ingestion service error: {str(e)}")

    async def query_images_only(self, question: str, k: int = 5, source: Optional[str] = None) -> List[Dict]:
        """Proxies image query to Retrieval Service"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "question": question,
                "k": k,
                "source": source
            }
            try:
                response = await client.post(f"{self.retrieval_url}/query/images", json=payload)
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

    def process_document(self, file_path, file_content, file_name, parser_preference=None, progress_callback=None, index_name=None, language="eng") -> "ProcessingResult":
        """Proxies process_document for compatibility with UI - falls back to direct processing if microservice unavailable"""
        logger.info(f"Gateway: Processing document {file_name}")
        try:
            # Try microservice first
            from shared.schemas import ProcessingResult as SchemaResult
            import asyncio
            import concurrent.futures
            
            async def _internal():
                import time
                async with httpx.AsyncClient(timeout=600.0) as client:
                    # Step 1: Start asynchronous ingestion
                    files = {"file": (file_name, file_content)}
                    data = {"parser_preference": parser_preference} if parser_preference else {}
                    if index_name:
                        data["index_name"] = index_name
                    if language:
                        data["language"] = language
                    
                    logger.info(f"Gateway: Starting async ingestion for {file_name} with index {index_name} (lang={language})")
                    response = await client.post(f"{self.ingestion_url}/ingest", files=files, data=data)
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
                                
                            # We update if progress increased OR if we have a new detailed message
                            if progress_callback and (progress > last_progress or detailed_msg):
                                last_progress = progress
                                # Ensure we don't block the async loop too much
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
            
            # Handle nested event loop case
            try:
                loop = asyncio.get_running_loop()
                # Already in an event loop, use thread pool
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _internal())
                    return future.result(timeout=620)
            except RuntimeError:
                # No running event loop, safe to use asyncio.run
                return asyncio.run(_internal())
                
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as e:
            # Microservice not available - fall back to direct processing
            logger.warning(f"Microservice unavailable ({e}), falling back to direct processing")
            return self._process_document_direct(file_path, file_content, file_name, parser_preference, progress_callback, index_name, language)
        except Exception as e:
            # Check if it's a connection-related error
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['connection', 'connect', 'refused', 'failed', 'unreachable', 'timeout']):
                logger.warning(f"Connection error ({e}), falling back to direct processing")
                return self._process_document_direct(file_path, file_content, file_name, parser_preference, progress_callback, index_name, language)
            
            logger.error(f"Error in Gateway process_document: {e}")
            from shared.schemas import ProcessingResult as SchemaResult
            return SchemaResult(
                status="failed",
                document_name=file_name,
                error=str(e)
            )
    
    def get_processing_state(self, doc_id: str) -> Optional[Dict]:
        """Get processing status from Ingestion service"""
        import asyncio
        import concurrent.futures
        
        async def _fetch():
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    # In microservices, doc_id might be the filename or a UUID
                    # We try to get from ingestion service
                    response = await client.get(f"{self.ingestion_url}/status/{doc_id}")
                    if response.status_code == 200:
                        return response.json()
                    return None
                except Exception:
                    return None
        
        # Handle async call
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _fetch())
                return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(_fetch())

    def _process_document_direct(self, file_path, file_content, file_name, parser_preference=None, progress_callback=None, index_name=None, language="eng") -> "ProcessingResult":
        """Direct document processing fallback when microservice is unavailable"""
        logger.info(f"Gateway: Using direct processing for {file_name}")
        try:
            from services.ingestion.processor import DocumentProcessor
            from services.ingestion.engine import IngestionEngine
            
            # Validate OpenSearch domain - fall back to FAISS if invalid
            vector_store_type = ARISConfig.VECTOR_STORE_TYPE
            opensearch_domain = self._opensearch_domain
            opensearch_index = index_name or self._opensearch_index
            
            if vector_store_type.lower() == 'opensearch':
                if not opensearch_domain or len(str(opensearch_domain).strip()) < 3:
                    logger.warning(
                        f"Invalid OpenSearch domain '{opensearch_domain}'. "
                        f"Falling back to FAISS for local storage."
                    )
                    vector_store_type = 'faiss'
                    opensearch_domain = None
                    opensearch_index = None
            
            # Create a temporary IngestionEngine for processing
            engine = IngestionEngine(
                vector_store_type=vector_store_type,
                opensearch_domain=opensearch_domain,
                opensearch_index=opensearch_index,
                chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
                chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
            )
            
            processor = DocumentProcessor(engine)
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

    def get_all_metrics(self) -> Dict:
        """Fetch and merge metrics from all services"""
        import asyncio
        import concurrent.futures
        
        async def _fetch():
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Fetch from Ingestion (processing metrics)
                ingestion_metrics = {}
                try:
                    resp = await client.get(f"{self.ingestion_url}/metrics")
                    if resp.status_code == 200:
                        ingestion_metrics = resp.json()
                except Exception as e:
                    logger.warning(f"Could not fetch ingestion metrics: {e}")
                
                # Fetch from Retrieval (query metrics)
                retrieval_metrics = {}
                try:
                    resp = await client.get(f"{self.retrieval_url}/metrics")
                    if resp.status_code == 200:
                        retrieval_metrics = resp.json()
                except Exception as e:
                    logger.warning(f"Could not fetch retrieval metrics: {e}")
                
                # Merge metrics
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

        # Handle nested event loop case
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _fetch())
                return future.result(timeout=15)
        except RuntimeError:
            return asyncio.run(_fetch())

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

    def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists (proxies to Ingestion Service).
        Compatibility method for UI.
        """
        try:
            import httpx
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.ingestion_url}/indexes/{index_name}/exists")
                if response.status_code == 200:
                    return response.json().get("exists", False)
                return False
        except Exception as e:
            logger.error(f"Error checking index exists via Gateway: {e}")
            return False

    def find_next_available_index_name(self, base_name: str) -> str:
        """
        Get next available index name (proxies to Ingestion Service).
        Compatibility method for UI.
        """
        try:
            import httpx
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.ingestion_url}/indexes/{base_name}/next-available")
                if response.status_code == 200:
                    return response.json().get("index_name", f"{base_name}-1")
                return f"{base_name}-1"
        except Exception as e:
            logger.error(f"Error getting next index name via Gateway: {e}")
            return f"{base_name}-1"

def create_gateway_service() -> GatewayService:
    return GatewayService()
