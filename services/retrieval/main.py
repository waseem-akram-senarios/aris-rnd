"""
FastAPI Entrypoint for ARIS Retrieval Service
Handles querying, reranking, and answer synthesis.
"""
import os
import logging
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from scripts.setup_logging import setup_logging
from shared.config.settings import ARISConfig
from shared.schemas import QueryRequest, QueryResponse, Citation, ImageQueryRequest, ImageQueryResponse, ImageResult
from storage.document_registry import DocumentRegistry
from .engine import RetrievalEngine

logger = setup_logging(
    name="aris_rag.retrieval",
    level=logging.INFO,
    log_file="logs/retrieval_service.log"
)

load_dotenv()

# Global engine instance
engine: Optional[RetrievalEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global engine
    
    logger.info("=" * 60)
    logger.info("[STARTUP] Initializing ARIS Retrieval Service")
    logger.info("=" * 60)
    
    # Initialize engine with retrieval-relevant settings
    engine = RetrievalEngine(
        use_cerebras=ARISConfig.USE_CEREBRAS,
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
        chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
    )
    
    logger.info("✅ [STARTUP] Retrieval Service Ready")
    yield
    
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
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "internal")
    # For future log formatting, we can use contextvars or simply log it here
    logger.info(f"Retrieval: [ReqID: {request_id}] Incoming {request.method} {request.url.path}")
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
        citations = []
        for i, src in enumerate(result.get("citations", [])):
            citations.append(
                Citation(
                    id=src.get('id', i) if isinstance(src.get('id'), int) else i,
                    source=src.get("source", ""),
                    page=src.get("page", 1),
                    snippet=src.get("snippet", ""),
                    full_text=src.get("full_text", ""),
                    source_location=src.get("source_location", f"Page {src.get('page', 1)}"),
                    similarity_score=src.get("similarity_score"),
                    similarity_percentage=src.get("similarity_percentage")
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
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.info(f"POST /query/images - [ReqID: {request_id}] Query: {image_request.question[:50]}...")
    
    try:
        # Use the engine's query_images method
        results = engine.query_images(
            question=image_request.question,
            source=image_request.source,
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
        
        return ImageQueryResponse(
            images=image_results,
            total=len(image_results),
            message=f"Found {len(image_results)} images matching query"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
