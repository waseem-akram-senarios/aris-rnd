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
    
    def query_text_only(self, question: str, k: int = 6, document_id: Optional[str] = None, use_mmr: bool = True) -> Dict:
        """Query Gateway for text results"""
        logger.info(f"[UI] ServiceContainer: Proxying text query to Gateway: {question[:50]}...")
        try:
            import concurrent.futures
            
            async def _query():
                return await self.gateway_service.query_text_only(question, k, document_id, use_mmr)
            
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

    @property
    def rag_system(self):
        """Compatibility property for RAG logic"""
        return self.gateway_service

    @property
    def document_processor(self):
        """Compatibility property for processor logic"""
        return self.gateway_service

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
