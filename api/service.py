"""
Service container for RAG system components
"""
import os
import logging
from typing import Dict, Optional, List
from dotenv import load_dotenv
from services.gateway.service import GatewayService
from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from scripts.setup_logging import get_logger
import asyncio

load_dotenv()

logger = get_logger("aris_rag.service")


class ServiceContainer:
    """Container for RAG system services proxying to Gateway"""
    
    def __init__(self, **kwargs):
        """Initialize service container with Gateway service."""
        logger.info("=" * 60)
        logger.info("[UI] ServiceContainer: Initializing Gateway Service Connection...")
        self.gateway_service = GatewayService()
        self.document_registry = self.gateway_service.document_registry
        logger.info("✅ ServiceContainer initialized with Gateway")
        logger.info("=" * 60)
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata by ID"""
        return self.document_registry.get_document(document_id)
    
    def list_documents(self) -> list:
        """List all documents"""
        return self.document_registry.list_documents()
    
    def add_document(self, document_id: str, result: Dict):
        """Add document metadata"""
        self.document_registry.add_document(document_id, result)
    
    def remove_document(self, document_id: str) -> bool:
        """Remove document metadata"""
        return self.document_registry.remove_document(document_id)
    
    def clear_documents(self):
        """Clear all documents"""
        self.document_registry.clear_all()
    
    def query_text_only(
        self, 
        question: str, 
        k: int = 6, 
        document_id: Optional[str] = None, 
        use_mmr: bool = True,
        response_language: Optional[str] = None,
        filter_language: Optional[str] = None,
        auto_translate: bool = False
    ) -> Dict:
        """Query Gateway for text results"""
        logger.info(f"[UI] ServiceContainer: Proxying text query to Gateway: {question[:50]}...")
        try:
            import concurrent.futures
            
            async def _query():
                return await self.gateway_service.query_text_only(
                    question, k, document_id, use_mmr,
                    response_language=response_language,
                    filter_language=filter_language,
                    auto_translate=auto_translate
                )
            
            # Handle nested event loop case
            try:
                loop = asyncio.get_running_loop()
                # Already in an event loop, use thread pool
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _query())
                    return future.result(timeout=120)
            except RuntimeError:
                # No running event loop, safe to use asyncio.run
                return asyncio.run(_query())
        except Exception as e:
            logger.error(f"Gateway query failed: {e}")
            return {"answer": f"Error: {e}", "citations": [], "num_chunks_used": 0}
    
    def query_images_only(self, question: str, k: int = 5, source: Optional[str] = None) -> List[Dict]:
        """Query Gateway for image results"""
        logger.info(f"[UI] ServiceContainer: Proxying image query to Gateway: {question[:50]}...")
        try:
            import concurrent.futures
            
            async def _query():
                return await self.gateway_service.query_images_only(question, k, source)
            
            # Handle nested event loop case
            try:
                loop = asyncio.get_running_loop()
                # Already in an event loop, use thread pool
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _query())
                    return future.result(timeout=120)
            except RuntimeError:
                # No running event loop, safe to use asyncio.run
                return asyncio.run(_query())
        except Exception as e:
            logger.error(f"Gateway image query failed: {e}")
            return []

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
        document_id: Optional[str] = None,
        response_language: Optional[str] = None,
        filter_language: Optional[str] = None,
        auto_translate: bool = False
    ) -> Dict:
        """Query Gateway with full RAG parameters"""
        logger.info(f"[UI] ServiceContainer: Proxying full RAG query to Gateway: {question[:50]}...")
        try:
            async def _query():
                return await self.gateway_service.query_with_rag(
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
            
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _query())
                    return future.result(timeout=120)
            except RuntimeError:
                return asyncio.run(_query())
        except Exception as e:
            logger.error(f"Gateway query_with_rag failed: {e}")
            return {"answer": f"Error: {e}", "citations": [], "num_chunks_used": 0}

    @property
    def opensearch_index(self) -> str:
        """Get current OpenSearch index"""
        return self.gateway_service.opensearch_index

    @opensearch_index.setter
    def opensearch_index(self, value: str):
        """Set current OpenSearch index"""
        self.gateway_service.opensearch_index = value

    @property
    def rag_system(self):
        """Compatibility property for RAG logic"""
        return self.gateway_service

    @property
    def document_processor(self):
        """Compatibility property for processor logic"""
        return self

    def index_exists(self, index_name: str) -> bool:
        """Check if index exists (proxies to Gateway)"""
        try:
            async def _check():
                return await self.gateway_service.index_exists(index_name)
            
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _check())
                    return future.result(timeout=10)
            except RuntimeError:
                return asyncio.run(_check())
        except Exception:
            return False

    def find_next_available_index_name(self, base_name: str) -> str:
        """Find next available index name (proxies to Gateway)"""
        try:
            async def _find():
                return await self.gateway_service.find_next_available_index_name(base_name)
            
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _find())
                    return future.result(timeout=10)
            except RuntimeError:
                return asyncio.run(_find())
        except Exception:
            return f"{base_name}-1"

    def process_document(self, file_path, file_content, file_name, parser_preference=None, progress_callback=None, index_name=None, language="eng"):
        """Process document (proxies to Gateway)"""
        try:
            async def _process():
                return await self.gateway_service.process_document(
                    file_path, file_content, file_name, parser_preference, progress_callback, index_name, language
                )
            
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _process())
                    return future.result(timeout=600)
            except RuntimeError:
                return asyncio.run(_process())
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            from shared.schemas import ProcessingResult
            return ProcessingResult(status="failed", document_name=file_name, error=str(e))

    def get_all_metrics(self) -> Dict:
        """Fetch all metrics (proxies to Gateway)"""
        try:
            async def _metrics():
                return await self.gateway_service.get_all_metrics()
            
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _metrics())
                    return future.result(timeout=15)
            except RuntimeError:
                return asyncio.run(_metrics())
        except Exception:
            return {}

    def get_storage_status(self, document_id: str) -> Dict:
        """Get storage status from registry (simplified)"""
        logger.info(f"[UI] ServiceContainer: Getting storage status for document: {document_id}")
        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        return {
            'document_id': document_id,
            'document_name': doc.get('document_name', 'unknown'),
            'text_index': doc.get('text_index') or 'aris-rag-index',
            'text_chunks_count': doc.get('chunks_created', 0),
            'text_storage_status': 'completed' if doc.get('chunks_created', 0) > 0 else 'pending',
            'images_index': 'aris-rag-images-index',
            'images_count': doc.get('image_count', 0),
            'images_storage_status': 'completed' if doc.get('images_detected', False) and doc.get('image_count', 0) > 0 else 'pending',
            'ocr_enabled': str(doc.get('parser_used', '')).lower() == 'docling'
        }


def create_service_container(**kwargs) -> ServiceContainer:
    """Create a service container (compatibility wrapper)"""
    return ServiceContainer(**kwargs)
