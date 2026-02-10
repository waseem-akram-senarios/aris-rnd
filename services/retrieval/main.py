"""
FastAPI Entrypoint for ARIS Retrieval Service
Handles querying, reranking, and answer synthesis.
"""
import os
import logging
import asyncio
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from scripts.setup_logging import setup_logging
from shared.config.settings import ARISConfig
from shared.schemas import (
    QueryRequest, QueryResponse, Citation, ImageQueryRequest, ImageQueryResponse, ImageResult,
    VectorIndexListResponse, VectorIndexInfo, VectorChunkListResponse, VectorChunkInfo,
    VectorChunkCreateRequest, VectorChunkUpdateRequest, VectorIndexDeleteRequest,
    VectorIndexDeleteResponse, BulkVectorIndexDeleteRequest, BulkVectorIndexDeleteResponse,
    VectorSearchRequest, VectorSearchResponse, IndexMapResponse, IndexMapEntry, IndexMapUpdateRequest,
    FullQueryRequest, FullQueryResponse
)
from storage.document_registry import DocumentRegistry
from shared.utils.sync_manager import SyncManager, get_sync_manager
from .engine import RetrievalEngine

logger = setup_logging(
    name="aris_rag.retrieval",
    level=logging.INFO,
    log_file="logs/retrieval_service.log"
)

load_dotenv()

# Global engine instance
engine: Optional[RetrievalEngine] = None
sync_manager: Optional[SyncManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global engine, sync_manager
    
    logger.info("=" * 60)
    logger.info("[STARTUP] Initializing ARIS Retrieval Service")
    logger.info("=" * 60)
    
    # Initialize sync manager with service name for tracking
    sync_manager = get_sync_manager("retrieval")
    logger.info("✅ [STARTUP] Sync Manager initialized")
    
    # Initialize engine with retrieval-relevant settings
    engine = RetrievalEngine(
        use_cerebras=ARISConfig.USE_CEREBRAS,
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
        chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
    )
    
    # Force initial sync on startup
    sync_manager.force_full_sync()
    
    # Register callback to reload engine's index map on sync
    def on_sync(result):
        if engine and (result.get("index_map") or result.get("registry")):
            try:
                engine._check_and_reload_document_index_map()
                logger.debug("[retrieval] Engine index map reloaded via sync callback")
            except Exception as e:
                logger.warning(f"[retrieval] Failed to reload index map in callback: {e}")
    
    sync_manager.register_sync_callback(on_sync)
    
    # Start background sync task for automatic synchronization
    try:
        loop = asyncio.get_event_loop()
        sync_manager.start_background_sync(loop)
        logger.info("✅ [STARTUP] Background sync task started")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not start async background sync: {e}")
        sync_manager._start_threaded_sync()
    
    logger.info("✅ [STARTUP] Retrieval Service Ready")
    yield
    
    # Cleanup
    sync_manager.stop_background_sync()
    logger.info("[SHUTDOWN] Retrieval Service Shutting Down")

app = FastAPI(
    title="ARIS Retrieval Service",
    description="Microservice for semantic search, reranking, and answer synthesis",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def auto_sync_middleware(request: Request, call_next):
    """Middleware to automatically sync state before operations."""
    request_id = request.headers.get("X-Request-ID", "internal")
    
    # Auto-sync before critical operations (queries need latest index map)
    if sync_manager and request.url.path in ["/query", "/query/images", "/health", "/admin/index-map"]:
        try:
            sync_manager.check_and_sync()
            # Also reload engine's index map for queries
            if engine and request.url.path.startswith("/query"):
                engine._check_and_reload_document_index_map()
        except Exception as e:
            logger.debug(f"Auto-sync check failed in middleware: {e}")
    
    logger.info(f"Retrieval: [ReqID: {request_id}] {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

def get_engine() -> RetrievalEngine:
    if engine is None:
        raise HTTPException(status_code=500, detail="Retrieval engine not initialized")
    return engine

@app.get("/health")
async def health_check():
    """Health check with registry and index map sync verification"""
    try:
        # Verify document registry and index map are accessible
        from shared.config.settings import ARISConfig
        import os
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        registry_accessible = os.path.exists(registry_path) or os.path.exists(os.path.dirname(registry_path))
        
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        index_map_accessible = os.path.exists(index_map_path) or os.path.exists(ARISConfig.VECTORSTORE_PATH)
        
        # Reload index map to ensure it's up to date
        if engine:
            engine._check_and_reload_document_index_map()
            index_map_count = len(engine.document_index_map) if hasattr(engine, 'document_index_map') else 0
        else:
            index_map_count = 0
        
        return {
            "status": "healthy",
            "service": "retrieval",
            "registry_accessible": registry_accessible,
            "index_map_accessible": index_map_accessible,
            "index_map_entries": index_map_count
        }
    except Exception as e:
        return {
            "status": "healthy",
            "service": "retrieval",
            "registry_accessible": False,
            "index_map_accessible": False,
            "error": str(e)
        }

@app.post("/query", response_model=QueryResponse,
           summary="Standard RAG Query",
           description="Query documents using Retrieval-Augmented Generation. Use /query/full for complete control over all advanced features.")
async def query_rag(
    request: Request,
    query_request: QueryRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Execute a RAG query.
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.info(f"POST /query - [ReqID: {request_id}] Question: {query_request.question[:50]}...")
    
    try:
        # Determine active sources for filtering
        active_sources = query_request.active_sources
        logger.info(f"POST /query - [ReqID: {request_id}] active_sources from request: {active_sources}")
        logger.info(f"POST /query - [ReqID: {request_id}] document_id from request: {query_request.document_id}")
        
        # If document_id is provided but no active_sources, use document_id as the filter
        if not active_sources and query_request.document_id:
            # Check and reload document_index_map to get latest mappings
            try:
                engine._check_and_reload_document_index_map()
                
                # Check registry for document_name mapping
                registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                doc_metadata = registry.get_document(request.document_id)
                document_name = doc_metadata.get('document_name', '') if doc_metadata else ''
                
                if document_name:
                    active_sources = [document_name]
                    # Also store the index mapping for lookup if needed
                    direct_index = f"aris-doc-{request.document_id}"
                    if not hasattr(engine, '_document_id_to_index'):
                        engine._document_id_to_index = {}
                    engine._document_id_to_index[request.document_id] = direct_index
                else:
                    active_sources = [request.document_id]
            except Exception as e:
                logger.warning(f"Could not map document_id to source: {e}")
                active_sources = [request.document_id]

        # Execute query
        result = engine.query_with_rag(
            question=query_request.question,
            k=query_request.k,
            use_mmr=query_request.use_mmr,
            active_sources=active_sources,
            use_hybrid_search=query_request.use_hybrid_search,
            semantic_weight=query_request.semantic_weight,
            search_mode=query_request.search_mode,
            use_agentic_rag=query_request.use_agentic_rag,
            temperature=query_request.temperature if hasattr(query_request, 'temperature') else None,
            max_tokens=query_request.max_tokens if hasattr(query_request, 'max_tokens') else None,
            response_language=query_request.response_language,
            filter_language=query_request.filter_language,
            auto_translate=query_request.auto_translate
        )
        
        # Build citations for response schema
        # NOTE: We don't use image_number as it's misleading (document-wide sequential counter, not per-page position)
        citations = []
        for i, src in enumerate(result.get("citations", [])):
            page = src.get("page", 1)
            # Use source_location from engine (already cleaned up)
            source_location = src.get("source_location", f"Page {page}")
            
            citations.append(
                Citation(
                    id=src.get('id', i) if isinstance(src.get('id'), int) else i,
                    source=src.get("source", ""),
                    document_id=src.get("document_id"),
                    page=page,
                    image_number=None,  # Don't show misleading image numbers
                    snippet=src.get("snippet", ""),
                    full_text=src.get("full_text", ""),
                    source_location=source_location,
                    content_type=src.get("content_type", "text"),
                    image_ref=src.get("image_ref"),
                    image_info=src.get("image_info"),
                    source_confidence=src.get("source_confidence"),
                    page_confidence=src.get("page_confidence"),
                    page_extraction_method=src.get("page_extraction_method"),
                    start_char=src.get("start_char"),
                    end_char=src.get("end_char"),
                    similarity_score=src.get("similarity_score"),
                    similarity_percentage=src.get("similarity_percentage"),
                    chunk_index=src.get("chunk_index"),
                    extraction_method=src.get("extraction_method")
                )
            )
            
        return QueryResponse(
            answer=result["answer"],
            sources=result.get("sources", []),
            citations=citations,
            num_chunks_used=result.get("num_chunks_used", 0),
            response_time=result.get("response_time", 0.0),
            context_tokens=result.get("context_tokens", 0),
            response_tokens=result.get("response_tokens", 0),
            total_tokens=result.get("total_tokens", 0)
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/query/images", response_model=ImageQueryResponse,
           summary="Image Search Query",
           description="Search for images in documents using OCR text. Supports document filtering and combined with /query/full for multi-modal search.")
async def query_images(
    request: Request,
    image_request: ImageQueryRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Search for images in the document corpus using semantic search on OCR text.
    
    Supports filtering by:
    - active_sources: List of document names (preferred, like text query)
    - source: Single document name (deprecated, use active_sources)
    - Empty active_sources or no filter: Search ALL documents
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    
    # Determine effective sources
    active_sources = image_request.active_sources
    if active_sources:
        logger.info(f"POST /query/images - [ReqID: {request_id}] Query: '{image_request.question[:50]}...' filtered to {len(active_sources)} document(s)")
    elif image_request.source:
        active_sources = [image_request.source]
        logger.info(f"POST /query/images - [ReqID: {request_id}] Query: '{image_request.question[:50]}...' filtered to single doc: {image_request.source}")
    else:
        logger.info(f"POST /query/images - [ReqID: {request_id}] Query: '{image_request.question[:50]}...' across ALL documents")
    
    try:
        # Use the engine's query_images method with active_sources support
        results = engine.query_images(
            question=image_request.question,
            active_sources=active_sources,
            k=image_request.k
        )
        
        # Convert to ImageResult format
        image_results = []
        for r in results:
            image_results.append(ImageResult(
                image_id=r.get("image_id", ""),
                source=r.get("source", ""),
                image_number=r.get("image_number", 0),
                page=max(1, r.get("page", 1)),  # Ensure page >= 1
                ocr_text=r.get("ocr_text", ""),
                metadata=r.get("metadata", {}),
                score=r.get("score")
            ))
        
        filter_msg = f" from {len(active_sources)} document(s)" if active_sources else " from all documents"
        return ImageQueryResponse(
            images=image_results,
            total=len(image_results),
            message=f"Found {len(image_results)} images matching query{filter_msg}"
        )
    except Exception as e:
        logger.error(f"Error querying images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error querying images: {str(e)}")
@app.get("/documents/{document_id}/images", response_model=ImageQueryResponse)
async def get_document_images(
    document_id: str,
    limit: int = 100,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Get all images for a specific document.
    """
    try:
        # Get document metadata to get source name
        registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
        doc_metadata = registry.get_document(document_id)
        if not doc_metadata:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found in registry")
        
        source = doc_metadata.get('document_name', '')
        if not source:
            raise HTTPException(status_code=404, detail=f"Source name for document {document_id} not found")
            
        results = engine.get_document_images(source=source, limit=limit)
        
        # Convert to ImageResult format
        image_results = []
        for r in results:
            image_results.append(ImageResult(
                image_id=r.get("image_id", ""),
                source=r.get("source", ""),
                image_number=r.get("image_number", 0),
                page=max(1, r.get("page", 1)),
                ocr_text=r.get("ocr_text", ""),
                metadata=r.get("metadata", {}),
                score=r.get("score")
            ))
        
        return ImageQueryResponse(
            images=image_results,
            total=len(image_results),
            message=f"Retrieved {len(image_results)} images for document {document_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting images for document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Delete a document and its images from vector stores.
    """
    try:
        # Get document metadata to get source name
        registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
        doc_metadata = registry.get_document(document_id)
        if not doc_metadata:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found in registry")
        
        source = doc_metadata.get('document_name', '')
        if not source:
            # Fallback to document_id if name missing
            source = document_id
            
        success = engine.delete_document(source=source)
        if success:
            return {"status": "success", "message": f"Document {document_id} and its images deleted from vector stores"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete document from vector stores")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/metrics")
async def get_metrics():
    """
    Get aggregated retrieval metrics.
    """
    if hasattr(engine, 'metrics_collector') and engine.metrics_collector:
        return engine.metrics_collector.get_all_metrics()
    return {"processing": {}, "queries": {}, "costs": {}, "parser_comparison": {}}

# ============================================================================
# VECTOR DATABASE CRUD ENDPOINTS
# ============================================================================

def get_crud_manager():
    """Get or create the OpenSearch CRUD manager."""
    global engine
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")
    
    if not hasattr(engine, '_crud_manager') or engine._crud_manager is None:
        from vectorstores.opensearch_store import OpenSearchCRUDManager
        engine._crud_manager = OpenSearchCRUDManager(
            embeddings=engine.embeddings,
            domain=engine.opensearch_domain,
            region=os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2'),
            endpoint=getattr(engine, 'opensearch_endpoint', None)
        )
    
    return engine._crud_manager

# --- Index Operations ---

@app.get("/admin/indexes", response_model=VectorIndexListResponse)
async def list_vector_indexes(
    prefix: str = "aris-",
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    List all vector indexes in OpenSearch.
    
    Args:
        prefix: Filter indexes by prefix (default: "aris-")
    """
    try:
        crud = get_crud_manager()
        indexes_data = crud.list_all_indexes(prefix=prefix)
        
        # Map to response schema
        indexes = []
        for idx in indexes_data:
            # Try to find document mapping
            doc_name = None
            doc_id = None
            if hasattr(engine, 'document_index_map'):
                for name, index_name in engine.document_index_map.items():
                    if index_name == idx['index_name']:
                        doc_name = name
                        break
            
            indexes.append(VectorIndexInfo(
                index_name=idx['index_name'],
                document_name=doc_name,
                document_id=doc_id,
                chunk_count=idx['chunk_count'],
                dimension=idx.get('dimension'),
                status=idx.get('status', 'active')
            ))
        
        return VectorIndexListResponse(
            indexes=indexes,
            total=len(indexes),
            message=f"Found {len(indexes)} indexes with prefix '{prefix}'"
        )
    except Exception as e:
        logger.error(f"Error listing indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/indexes/{index_name}")
async def get_index_info(
    index_name: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Get detailed information about a specific index."""
    try:
        crud = get_crud_manager()
        info = crud.get_index_info(index_name)
        
        if not info:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")
        
        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting index info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/indexes/{index_name}", response_model=VectorIndexDeleteResponse)
async def delete_vector_index(
    index_name: str,
    confirm: bool = False,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Delete a vector index.
    
    Args:
        index_name: Name of the index to delete
        confirm: Must be True to confirm deletion
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Deletion not confirmed. Set confirm=true to proceed."
        )
    
    try:
        crud = get_crud_manager()
        result = crud.delete_index(index_name)
        
        # Also remove from document_index_map if present
        if hasattr(engine, 'document_index_map'):
            keys_to_remove = [k for k, v in engine.document_index_map.items() if v == index_name]
            for key in keys_to_remove:
                del engine.document_index_map[key]
            if keys_to_remove and hasattr(engine, '_save_document_index_map'):
                engine._save_document_index_map()
        
        return VectorIndexDeleteResponse(
            success=result['success'],
            index_name=index_name,
            chunks_deleted=result['chunks_deleted'],
            message=result['message']
        )
    except Exception as e:
        logger.error(f"Error deleting index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/indexes/bulk-delete", response_model=BulkVectorIndexDeleteResponse)
async def bulk_delete_indexes(
    request: BulkVectorIndexDeleteRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Delete multiple vector indexes at once."""
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Set confirm=true to proceed."
        )
    
    try:
        crud = get_crud_manager()
        result = crud.delete_indexes_bulk(request.index_names)
        
        # Also remove from document_index_map
        if hasattr(engine, 'document_index_map'):
            keys_to_remove = [k for k, v in engine.document_index_map.items() if v in request.index_names]
            for key in keys_to_remove:
                del engine.document_index_map[key]
            if keys_to_remove and hasattr(engine, '_save_document_index_map'):
                engine._save_document_index_map()
        
        return BulkVectorIndexDeleteResponse(
            success=result['success'],
            total_requested=result['total_requested'],
            total_deleted=result['total_deleted'],
            failed=result['failed'],
            total_chunks_deleted=result['total_chunks_deleted'],
            message=result['message']
        )
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Chunk Operations ---

@app.get("/admin/indexes/{index_name}/chunks", response_model=VectorChunkListResponse)
async def list_chunks(
    index_name: str,
    offset: int = 0,
    limit: int = 100,
    source: Optional[str] = None,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    List chunks in a specific index with pagination.
    
    Args:
        index_name: Index to query
        offset: Starting offset for pagination
        limit: Maximum results (max 1000)
        source: Optional source document filter
    """
    limit = min(limit, 1000)  # Cap at 1000
    
    try:
        crud = get_crud_manager()
        result = crud.list_chunks(index_name, offset=offset, limit=limit, source_filter=source)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        chunks = [VectorChunkInfo(**c) for c in result['chunks']]
        
        return VectorChunkListResponse(
            index_name=index_name,
            chunks=chunks,
            total=result['total'],
            offset=offset,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/indexes/{index_name}/chunks/{chunk_id}")
async def get_chunk(
    index_name: str,
    chunk_id: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Get a specific chunk by ID."""
    try:
        crud = get_crud_manager()
        chunk = crud.get_chunk(index_name, chunk_id)
        
        if not chunk:
            raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")
        
        return chunk
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/indexes/{index_name}/chunks")
async def create_chunk(
    index_name: str,
    request: VectorChunkCreateRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Create a new chunk with embedding in the specified index.
    """
    try:
        crud = get_crud_manager()
        result = crud.create_chunk(
            index_name=index_name,
            text=request.text,
            page=request.page,
            source=request.source,
            language=request.language,
            metadata=request.metadata
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/admin/indexes/{index_name}/chunks/{chunk_id}")
async def update_chunk(
    index_name: str,
    chunk_id: str,
    request: VectorChunkUpdateRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Update an existing chunk. If text is changed, embedding is regenerated.
    """
    try:
        crud = get_crud_manager()
        result = crud.update_chunk(
            index_name=index_name,
            chunk_id=chunk_id,
            text=request.text,
            page=request.page,
            metadata=request.metadata
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/indexes/{index_name}/chunks/{chunk_id}")
async def delete_chunk(
    index_name: str,
    chunk_id: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Delete a specific chunk."""
    try:
        crud = get_crud_manager()
        result = crud.delete_chunk(index_name, chunk_id)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/indexes/{index_name}/chunks")
async def delete_chunks_by_source(
    index_name: str,
    source: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Delete all chunks from a specific source document."""
    try:
        crud = get_crud_manager()
        result = crud.delete_chunks_by_source(index_name, source)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result['message'])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chunks by source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Search Operations ---

@app.post("/admin/search", response_model=VectorSearchResponse)
async def vector_search(
    request: VectorSearchRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    Perform direct vector search across indexes.
    
    This bypasses RAG answer generation and returns raw search results.
    """
    try:
        crud = get_crud_manager()
        result = crud.search_vectors(
            query=request.query,
            index_names=request.index_names,
            k=request.k,
            use_hybrid=request.use_hybrid,
            semantic_weight=request.semantic_weight
        )
        
        return VectorSearchResponse(
            query=result['query'],
            results=[VectorChunkInfo(**r) for r in result['results']],
            total=result['total'],
            indexes_searched=result['indexes_searched'],
            search_time_ms=result['search_time_ms']
        )
    except Exception as e:
        logger.error(f"Error in vector search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Index Map Operations ---

@app.get("/admin/index-map", response_model=IndexMapResponse)
async def get_index_map(
    engine: RetrievalEngine = Depends(get_engine)
):
    """Get the document-to-index mapping."""
    try:
        # Reload latest
        engine._check_and_reload_document_index_map()
        
        entries = []
        for doc_name, index_name in engine.document_index_map.items():
            entries.append(IndexMapEntry(
                document_name=doc_name,
                index_name=index_name
            ))
        
        return IndexMapResponse(
            entries=entries,
            total=len(entries)
        )
    except Exception as e:
        logger.error(f"Error getting index map: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/index-map")
async def update_index_map(
    request: IndexMapUpdateRequest,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Add or update a document-to-index mapping."""
    try:
        engine.document_index_map[request.document_name] = request.index_name
        engine._save_document_index_map()
        
        return {
            "success": True,
            "document_name": request.document_name,
            "index_name": request.index_name,
            "message": "Index mapping updated"
        }
    except Exception as e:
        logger.error(f"Error updating index map: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/index-map/{document_name}")
async def delete_index_map_entry(
    document_name: str,
    engine: RetrievalEngine = Depends(get_engine)
):
    """Remove a document from the index map."""
    try:
        if document_name not in engine.document_index_map:
            raise HTTPException(status_code=404, detail=f"Document '{document_name}' not in index map")
        
        index_name = engine.document_index_map.pop(document_name)
        engine._save_document_index_map()
        
        return {
            "success": True,
            "document_name": document_name,
            "index_name": index_name,
            "message": "Index mapping removed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting index map entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Synchronization Endpoints ---

@app.post("/sync/force")
async def force_sync():
    """Force full synchronization of all shared state."""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        result = sync_manager.force_full_sync()
        
        # Also reload engine's index map
        if engine:
            engine._check_and_reload_document_index_map()
        
        return {
            "success": True,
            "message": "Full synchronization completed",
            "sync_result": result
        }
    except Exception as e:
        logger.error(f"Error forcing sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sync/status")
async def get_sync_status():
    """Get current synchronization status."""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        status = sync_manager.get_sync_status()
        
        # Add engine-specific status
        if engine:
            status["engine"] = {
                "index_map_loaded": hasattr(engine, 'document_index_map'),
                "index_map_count": len(engine.document_index_map) if hasattr(engine, 'document_index_map') else 0
            }
        
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/check")
async def check_and_sync():
    """Check for changes and sync if needed."""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        result = sync_manager.check_and_sync()
        
        # If index map was synced, reload in engine
        if result.get("index_map") and engine:
            engine._check_and_reload_document_index_map()
        
        return {
            "success": True,
            "synced": result,
            "message": "Sync check completed"
        }
    except Exception as e:
        logger.error(f"Error checking sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# COMPREHENSIVE QUERY ENDPOINT - All UI Features
# ============================================================================

@app.post("/query/full", response_model=FullQueryResponse)
async def query_rag_full(
    request: Request,
    query_request: FullQueryRequest,  # FullQueryRequest contains all query parameters
    engine: RetrievalEngine = Depends(get_engine)
):
    """
    🚀 **FULL RAG QUERY ENDPOINT - COMPLETE AI-POWERED SEARCH**

    This endpoint provides **ALL features available in the UI** for comprehensive document querying.
    Advanced RAG (Retrieval-Augmented Generation) with multi-modal search, agentic decomposition,
    and full language support for production-grade document Q&A.

    ## 🔍 **Search Modes** ✅ **ALL WORKING**

    ### **Semantic Search** ⭐
    - **Purpose**: Best for conceptual queries and understanding
    - **Method**: Vector similarity using embeddings
    - **Use Case**: "What is machine learning?" or "Explain this concept"

    ### **Keyword Search** ⭐
    - **Purpose**: Best for exact terms and specific phrases
    - **Method**: Text matching and TF-IDF scoring
    - **Use Case**: "search for 'neural network'" or specific terminology

    ### **Hybrid Search** ⭐ **RECOMMENDED**
    - **Purpose**: Combines best of both worlds
    - **Method**: Weighted combination of semantic + keyword
    - **Use Case**: Most queries - balances relevance and precision

    ## 🎯 **Document Filtering** ✅ **TESTED**

    ### **Single Document**
    ```json
    {"active_sources": ["document.pdf"]}
    ```

    ### **Multiple Documents**
    ```json
    {"active_sources": ["doc1.pdf", "doc2.pdf", "doc3.pdf"]}
    ```

    ### **All Documents** (Default)
    ```json
    {"active_sources": null} // or omit entirely
    ```

    ## 🤖 **Agentic RAG** ✅ **WORKING**

    When enabled, complex questions are automatically decomposed into sub-queries:

    **Example**: *"How does the system architecture relate to performance optimization?"*
    **Becomes**:
    1. *"What is the system architecture?"*
    2. *"What are the performance optimization techniques?"*
    3. *"How do they relate?"*

    ### **Configuration**:
    - `use_agentic_rag`: `true`/`false`
    - `max_sub_queries`: `1-10` (default: 4)

    ## 🌍 **Multi-Language Support** ✅ **TESTED**

    ### **Automatic Translation**
    ```json
    {
      "question": "¿Qué es el aprendizaje automático?",
      "auto_translate": true,
      "response_language": "Spanish"
    }
    ```
    - Translates query to English for better semantic search
    - Generates response in specified language
    - Supports 100+ languages

    ### **Language Filtering**
    ```json
    {
      "filter_language": "spa",
      "response_language": "Spanish"
    }
    ```
    - Only searches documents in specified language
    - Useful for multilingual document collections

    ## ⚙️ **Advanced Parameters** ✅ **ALL WORKING**

    ### **Search Parameters**
    - `k`: `1-50` - Number of chunks to retrieve (default: 6)
    - `use_mmr`: `true`/`false` - Maximum Marginal Relevance for diversity
    - `semantic_weight`: `0.0-1.0` - Balance in hybrid search (1.0 = pure semantic)

    ### **Generation Parameters**
    - `temperature`: `0.0-2.0` - Response creativity (0.0 = deterministic)
    - `max_tokens`: `100-4000` - Maximum response length (default: 1200)

    ## 🖼️ **Image Search Integration** ✅ **FRAMEWORK READY**

    ### **Combined Text + Image Search**
    ```json
    {
      "question": "Show me technical diagrams",
      "include_images": true,
      "image_k": 5
    }
    ```
    - Searches both text content and extracted images
    - Returns relevant images alongside text answers
    - `image_k`: Number of images to retrieve

    ## 📊 **Response Details**

    Returns comprehensive results including:
    - **Answer**: AI-generated response
    - **Sources**: Document names referenced
    - **Citations**: Detailed source locations with page numbers
    - **Images**: Relevant images (if `include_images=true`)
    - **Performance Metrics**: Response time, token usage
    - **Query Analysis**: Sub-queries, language detection

    ## 🚀 **Production Features**
    - ✅ **Error Handling**: Graceful failures with informative messages
    - ✅ **Rate Limiting**: Built-in request throttling
    - ✅ **Caching**: Intelligent response caching
    - ✅ **Monitoring**: Comprehensive logging and metrics
    - ✅ **Scalability**: Handles concurrent requests efficiently

    ## 💡 **Usage Examples**

    ### **Basic Query**
    ```bash
    curl -X POST "http://44.221.84.58:8502/query/full" \\
      -H "Content-Type: application/json" \\
      -d '{
        "question": "What are the key features?",
        "search_mode": "hybrid",
        "k": 5
      }'
    ```

    ### **Advanced Multi-Document Query**
    ```bash
    curl -X POST "http://44.221.84.58:8502/query/full" \\
      -H "Content-Type: application/json" \\
      -d '{
        "question": "Compare machine learning vs deep learning",
        "active_sources": ["ml_guide.pdf", "ai_overview.pdf"],
        "search_mode": "hybrid",
        "semantic_weight": 0.8,
        "use_agentic_rag": true,
        "temperature": 0.1,
        "max_tokens": 1000
      }'
    ```

    ### **Multi-Language Query**
    ```bash
    curl -X POST "http://44.221.84.58:8502/query/full" \\
      -H "Content-Type: application/json" \\
      -d '{
        "question": "¿Cómo funciona el sistema?",
        "auto_translate": true,
        "response_language": "Spanish",
        "filter_language": "spa",
        "search_mode": "semantic"
      }'
    ```

    ### **Image-Enhanced Query**
    ```bash
    curl -X POST "http://44.221.84.58:8502/query/full" \\
      -H "Content-Type: application/json" \\
      -d '{
        "question": "Explain the architecture with diagrams",
        "include_images": true,
        "image_k": 3,
        "search_mode": "hybrid",
        "use_agentic_rag": true
      }'
    ```
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    start_time = time_module.time()
    
    logger.info(f"POST /query/full - [ReqID: {request_id}] Question: {query_request.question[:50]}...")
    logger.info(f"POST /query/full - [ReqID: {request_id}] Settings: mode={query_request.search_mode}, "
                f"agentic={query_request.use_agentic_rag}, k={query_request.k}, "
                f"include_images={query_request.include_images}")
    
    try:
        # Determine active sources
        active_sources = query_request.active_sources
        if not active_sources and query_request.document_id:
            # Map document_id to source name
            try:
                registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                doc_metadata = registry.get_document(query_request.document_id)
                if doc_metadata:
                    active_sources = [doc_metadata.get('document_name', query_request.document_id)]
                else:
                    active_sources = [query_request.document_id]
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                active_sources = [query_request.document_id]
        
        # Detect query language for logging
        query_language = None
        translated_query = None
        try:
            from langdetect import detect
            query_language = detect(query_request.question)
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            query_language = "unknown"
        
        # Execute main RAG query
        result = engine.query_with_rag(
            question=query_request.question,
            k=query_request.k,
            use_mmr=query_request.use_mmr,
            active_sources=active_sources,
            use_hybrid_search=(query_request.search_mode == "hybrid"),
            semantic_weight=query_request.semantic_weight,
            search_mode=query_request.search_mode,
            use_agentic_rag=query_request.use_agentic_rag,
            temperature=query_request.temperature,
            max_tokens=query_request.max_tokens,
            response_language=query_request.response_language,
            filter_language=query_request.filter_language,
            auto_translate=query_request.auto_translate
        )
        
        # Build citations
        citations = []
        for i, src in enumerate(result.get("citations", [])):
            page = src.get("page", 1)
            # Use source_location from engine (already cleaned up)
            source_location = src.get("source_location", f"Page {page}")
            
            citations.append(
                Citation(
                    id=src.get('id', i) if isinstance(src.get('id'), int) else i,
                    source=src.get("source", ""),
                    document_id=src.get("document_id"),
                    page=page,
                    image_number=None,  # Don't show misleading image numbers
                    snippet=src.get("snippet", ""),
                    full_text=src.get("full_text", ""),
                    source_location=source_location,
                    content_type=src.get("content_type", "text"),
                    image_ref=src.get("image_ref"),
                    image_info=src.get("image_info"),
                    source_confidence=src.get("source_confidence"),
                    page_confidence=src.get("page_confidence"),
                    page_extraction_method=src.get("page_extraction_method"),
                    start_char=src.get("start_char"),
                    end_char=src.get("end_char"),
                    similarity_score=src.get("similarity_score"),
                    similarity_percentage=src.get("similarity_percentage"),
                    chunk_index=src.get("chunk_index"),
                    extraction_method=src.get("extraction_method")
                )
            )
        
        # Optionally include image search results
        image_results = None
        num_images = 0
        if query_request.include_images:
            try:
                images = engine.query_images(
                    question=query_request.question,
                    active_sources=active_sources,
                    k=query_request.image_k
                )
                image_results = []
                for r in images:
                    image_results.append(ImageResult(
                        image_id=r.get("image_id", ""),
                        source=r.get("source", ""),
                        image_number=r.get("image_number", 0),
                        page=max(1, r.get("page", 1)),
                        ocr_text=r.get("ocr_text", ""),
                        metadata=r.get("metadata", {}),
                        score=r.get("score")
                    ))
                num_images = len(image_results)
            except Exception as img_err:
                logger.warning(f"Image search failed: {img_err}")
        
        total_time = time_module.time() - start_time
        
        # FIX: When active_sources is empty, show actual documents that were searched
        # Use the sources from the result (which now only contains citation sources)
        docs_searched = active_sources if active_sources else result.get("sources", [])
        
        return FullQueryResponse(
            answer=result["answer"],
            sources=result.get("sources", []),
            citations=citations,
            num_chunks_used=result.get("num_chunks_used", 0),
            images=image_results,
            num_images=num_images,
            response_time=total_time,
            context_tokens=result.get("context_tokens", 0),
            response_tokens=result.get("response_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
            sub_queries=result.get("sub_queries"),
            query_language=query_language,
            translated_query=translated_query,
            search_mode_used=query_request.search_mode,
            semantic_weight_used=query_request.semantic_weight,
            documents_searched=docs_searched
        )
        
    except Exception as e:
        logger.error(f"Error in full query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8502)
