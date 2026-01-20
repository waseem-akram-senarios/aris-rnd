"""
Gateway Entrypoint - Orchestrates Ingestion and Retrieval services.
Minimal API surface - admin operations go directly to respective services.
"""
import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx

from scripts.setup_logging import setup_logging
from shared.schemas import QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse
from .service import GatewayService, create_gateway_service
from shared.utils.sync_manager import SyncManager, get_sync_manager

logger = setup_logging(
    name="aris_rag.gateway",
    level=logging.INFO,
    log_file="logs/gateway_service.log"
)

load_dotenv()

gateway_service: Optional[GatewayService] = None
sync_manager: Optional[SyncManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global gateway_service, sync_manager
    
    logger.info("=" * 60)
    logger.info("[STARTUP] Initializing ARIS Gateway Service")
    logger.info("=" * 60)
    
    # Initialize sync manager with service name for tracking
    sync_manager = get_sync_manager("gateway")
    logger.info("✅ [STARTUP] Sync Manager initialized")
    
    gateway_service = create_gateway_service()
    
    # Force initial sync on startup
    sync_manager.force_full_sync()
    
    # Register callback to reload gateway's registry on sync
    def on_sync(result):
        if gateway_service and (result.get("registry") or result.get("index_map")):
            try:
                gateway_service._reload_registry()
                logger.debug("[gateway] Registry reloaded via sync callback")
            except Exception as e:
                logger.warning(f"[gateway] Failed to reload registry in callback: {e}")
    
    sync_manager.register_sync_callback(on_sync)
    
    # Start background sync task for automatic synchronization
    try:
        loop = asyncio.get_event_loop()
        sync_manager.start_background_sync(loop)
        logger.info("✅ [STARTUP] Background sync task started")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not start async background sync: {e}")
        sync_manager._start_threaded_sync()
    
    logger.info("✅ [STARTUP] Gateway Service Ready")
    yield
    
    # Cleanup
    sync_manager.stop_background_sync()
    logger.info("[SHUTDOWN] Gateway Service Shutting Down")

app = FastAPI(
    title="ARIS RAG API - Gateway",
    description="Orchestrator microservice for ARIS RAG. Admin operations available at Ingestion (:8501) and Retrieval (:8502) services.",
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
    
    # Auto-sync before critical operations (queries, document listing)
    if sync_manager and request.url.path in ["/query", "/documents", "/health"]:
        try:
            sync_manager.check_and_sync()
        except Exception as e:
            logger.debug(f"Auto-sync check failed in middleware: {e}")
    
    logger.info(f"Gateway: [ReqID: {request_id}] {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def get_service() -> GatewayService:
    if gateway_service is None:
        raise HTTPException(status_code=500, detail="Gateway service not initialized")
    return gateway_service


# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint for basic connectivity check"""
    return {"message": "ARIS RAG System API Gateway", "status": "online"}


@app.get("/health")
async def health_check(service: GatewayService = Depends(get_service)):
    """Health check with registry sync verification"""
    try:
        from shared.config.settings import ARISConfig
        import os
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        registry_accessible = os.path.exists(registry_path) or os.path.exists(os.path.dirname(registry_path))
        
        try:
            docs = service.list_documents()
            doc_count = len(docs)
        except Exception:
            doc_count = 0
        
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        index_map_accessible = os.path.exists(index_map_path) or os.path.exists(ARISConfig.VECTORSTORE_PATH)
        
        return {
            "status": "healthy",
            "message": "ARIS RAG System API Gateway is operational",
            "service": "gateway",
            "registry_accessible": registry_accessible,
            "registry_document_count": doc_count,
            "index_map_accessible": index_map_accessible
        }
    except Exception as e:
        return {
            "status": "healthy",
            "service": "gateway",
            "error": str(e)
        }


# ============================================================================
# DOCUMENT ENDPOINTS
# ============================================================================

@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(service: GatewayService = Depends(get_service)):
    """List all processed documents from the registry"""
    docs = service.list_documents()
    
    formatted_docs = []
    for doc in docs:
        if 'status' not in doc:
            doc['status'] = 'success' if doc.get('chunks_created', 0) > 0 else 'processing'
        
        formatted_doc = {
            'document_id': doc.get('document_id', ''),
            'document_name': doc.get('document_name', ''),
            'status': doc.get('status', 'processing'),
            'chunks_created': doc.get('chunks_created', 0),
            **doc
        }
        formatted_docs.append(DocumentMetadata(**formatted_doc))
    
    return DocumentListResponse(documents=formatted_docs, total=len(formatted_docs))


@app.get("/documents/{document_id}", response_model=DocumentMetadata)
async def get_document(document_id: str, service: GatewayService = Depends(get_service)):
    """Get a specific document by ID"""
    doc = service.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    if 'status' not in doc:
        doc['status'] = 'success' if doc.get('chunks_created', 0) > 0 else 'processing'
    
    formatted_doc = {
        'document_id': doc.get('document_id', document_id),
        'document_name': doc.get('document_name', ''),
        'status': doc.get('status', 'processing'),
        'chunks_created': doc.get('chunks_created', 0),
        **doc
    }
    
    return DocumentMetadata(**formatted_doc)


@app.post("/documents", response_model=DocumentMetadata, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    parser_preference: Optional[str] = Form(default=None),
    index_name: Optional[str] = Form(default=None),
    service: GatewayService = Depends(get_service)
):
    """Upload document to Ingestion service"""
    content = await file.read()
    try:
        result = await service.ingest_document(content, file.filename, parser_preference, index_name)
        return DocumentMetadata(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/documents/{document_id}", response_model=DocumentMetadata)
async def update_document(
    document_id: str,
    metadata_update: Dict[str, Any],
    service: GatewayService = Depends(get_service)
):
    """Update document metadata"""
    existing = service.get_document(document_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    updated_meta = {**existing, **metadata_update}
    service.update_document(document_id, updated_meta)
    return DocumentMetadata(**updated_meta)


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str, service: GatewayService = Depends(get_service)):
    """Delete document from registry and vector stores"""
    await service.delete_document_from_stores(document_id)
    success = service.remove_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    return {"status": "success", "message": f"Document {document_id} deleted"}


@app.get("/documents/{document_id}/images")
async def get_document_images(document_id: str, service: GatewayService = Depends(get_service)):
    """Get all images for a document"""
    images = await service.get_document_images(document_id)
    return {"images": images, "total": len(images)}


# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest, service: GatewayService = Depends(get_service)):
    """Query the Retrieval service with hybrid search as default"""
    # Handle document filtering
    if request.active_sources is not None:
        service.active_sources = request.active_sources
    elif request.document_id is not None:
        service.active_sources = [request.document_id]

    search_mode = request.search_mode if request.search_mode else "hybrid"
    use_hybrid_search = request.use_hybrid_search if request.use_hybrid_search is not None else True
    semantic_weight = request.semantic_weight if request.semantic_weight is not None else 0.7

    result = await service.query_text_only(
        question=request.question,
        k=request.k,
        document_id=request.document_id,
        use_mmr=request.use_mmr,
        use_hybrid_search=use_hybrid_search,
        semantic_weight=semantic_weight,
        search_mode=search_mode,
        response_language=request.response_language,
        filter_language=request.filter_language,
        auto_translate=request.auto_translate
    )
    return QueryResponse(**result)


@app.post("/query/images")
async def query_images(request: Dict[str, Any], service: GatewayService = Depends(get_service)):
    """Query images specifically.
    
    Supports filtering by:
    - active_sources: List of document names (same as text query)
    - source: Single document name (deprecated)
    - Empty = search ALL documents
    """
    question = request.get("question", "")
    k = request.get("k", 5)
    source = request.get("source")
    active_sources = request.get("active_sources")
    
    # Use active_sources from request, or from gateway service state
    if active_sources is None and hasattr(service, 'active_sources') and service.active_sources:
        active_sources = service.active_sources
    
    images = await service.query_images_only(question, k, source, active_sources)
    
    filter_msg = f" from {len(active_sources)} document(s)" if active_sources else " from all documents"
    return {"images": images, "total": len(images), "message": f"Found {len(images)} images{filter_msg}"}


# ============================================================================
# STATS ENDPOINTS
# ============================================================================

@app.get("/stats")
async def get_system_stats(service: GatewayService = Depends(get_service)):
    """Get overall system statistics"""
    try:
        return await service.get_all_metrics_async()
    except Exception as e:
        logger.error(f"Error getting system stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")


@app.get("/stats/chunks")
async def get_chunk_stats(service: GatewayService = Depends(get_service)):
    """Get chunk-level statistics"""
    try:
        metrics = await service.get_all_metrics_async()
        return metrics.get("processing", {})
    except Exception as e:
        logger.error(f"Error getting chunk stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching chunk stats: {str(e)}")


# ============================================================================
# SYNC ENDPOINTS
# ============================================================================

@app.get("/sync/status")
async def get_sync_status(service: GatewayService = Depends(get_service)):
    """Get current synchronization status across all services"""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        status = sync_manager.get_sync_status()
        status["gateway"] = {
            "document_count": len(service.list_documents()),
            "registry_accessible": True
        }
        
        ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://127.0.0.1:8501")
        retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8502")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                ingestion_status = await client.get(f"{ingestion_url}/sync/status")
                status["ingestion"] = ingestion_status.json() if ingestion_status.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                status["ingestion"] = {"error": str(e)}
            
            try:
                retrieval_status = await client.get(f"{retrieval_url}/sync/status")
                status["retrieval"] = retrieval_status.json() if retrieval_status.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                status["retrieval"] = {"error": str(e)}
        
        return {"success": True, "status": status}
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/force")
async def force_sync(service: GatewayService = Depends(get_service)):
    """Force full synchronization of all shared state across all services"""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        result = sync_manager.force_full_sync()
        
        ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://127.0.0.1:8501")
        retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8502")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                ingestion_result = await client.post(f"{ingestion_url}/sync/force")
                result["ingestion"] = ingestion_result.json() if ingestion_result.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                result["ingestion"] = {"error": str(e)}
            
            try:
                retrieval_result = await client.post(f"{retrieval_url}/sync/force")
                result["retrieval"] = retrieval_result.json() if retrieval_result.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                result["retrieval"] = {"error": str(e)}
        
        return {
            "success": True,
            "message": "Full synchronization completed across all services",
            "sync_result": result
        }
    except Exception as e:
        logger.error(f"Error forcing sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sync/check")
async def check_and_sync(service: GatewayService = Depends(get_service)):
    """Check for changes and sync if needed across all services"""
    global sync_manager
    if sync_manager is None:
        raise HTTPException(status_code=500, detail="Sync manager not initialized")
    
    try:
        result = sync_manager.check_and_sync()
        
        ingestion_url = os.getenv("INGESTION_SERVICE_URL", "http://127.0.0.1:8501")
        retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8502")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                ingestion_result = await client.post(f"{ingestion_url}/sync/check")
                result["ingestion"] = ingestion_result.json() if ingestion_result.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                result["ingestion"] = {"error": str(e)}
            
            try:
                retrieval_result = await client.post(f"{retrieval_url}/sync/check")
                result["retrieval"] = retrieval_result.json() if retrieval_result.status_code == 200 else {"error": "Failed"}
            except Exception as e:
                result["retrieval"] = {"error": str(e)}
        
        return {
            "success": True,
            "synced": result,
            "message": "Sync check completed across all services"
        }
    except Exception as e:
        logger.error(f"Error checking sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
