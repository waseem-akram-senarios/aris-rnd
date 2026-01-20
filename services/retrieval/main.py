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
    VectorSearchRequest, VectorSearchResponse, IndexMapResponse, IndexMapEntry, IndexMapUpdateRequest
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

@app.post("/query", response_model=QueryResponse)
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
        
        # Build citations for response schema with full metadata including image_number
        citations = []
        for i, src in enumerate(result.get("citations", [])):
            # Extract image_number from source data
            image_number = src.get('image_number')
            if image_number is None and src.get('image_ref'):
                image_ref = src.get('image_ref')
                if isinstance(image_ref, dict):
                    image_number = image_ref.get('image_index')
            
            # Build source_location with page and image info
            page = src.get("page", 1)
            if image_number is not None:
                source_location = f"Page {page}, Image {image_number}"
            else:
                source_location = src.get("source_location", f"Page {page}")
            
            citations.append(
                Citation(
                    id=src.get('id', i) if isinstance(src.get('id'), int) else i,
                    source=src.get("source", ""),
                    page=page,
                    image_number=image_number,
                    snippet=src.get("snippet", ""),
                    full_text=src.get("full_text", ""),
                    source_location=source_location,
                    content_type=src.get("content_type", "image" if image_number else "text"),
                    image_ref=src.get("image_ref"),
                    image_info=src.get("image_info"),
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


@app.post("/query/images", response_model=ImageQueryResponse)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
