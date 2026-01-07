"""
Gateway Entrypoint - Orchestrates Ingestion and Retrieval services.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from scripts.setup_logging import setup_logging
from shared.schemas import QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse
from .service import GatewayService, create_gateway_service

logger = setup_logging(
    name="aris_rag.gateway",
    level=logging.INFO,
    log_file="logs/gateway_service.log"
)

load_dotenv()

gateway_service: Optional[GatewayService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global gateway_service
    
    logger.info("=" * 60)
    logger.info("[STARTUP] Initializing ARIS Gateway Service")
    logger.info("=" * 60)
    
    gateway_service = create_gateway_service()
    
    logger.info("✅ [STARTUP] Gateway Service Ready")
    yield
    
    logger.info("[SHUTDOWN] Gateway Service Shutting Down")

app = FastAPI(
    title="ARIS RAG API - Gateway",
    description="Orchestrator microservice for ARIS RAG",
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

def get_service() -> GatewayService:
    if gateway_service is None:
        raise HTTPException(status_code=500, detail="Gateway service not initialized")
    return gateway_service

@app.get("/health")
async def health_check(service: GatewayService = Depends(get_service)):
    """Health check with registry sync verification"""
    try:
        # Verify document registry is accessible
        from shared.config.settings import ARISConfig
        import os
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        registry_accessible = os.path.exists(registry_path) or os.path.exists(os.path.dirname(registry_path))
        
        # Get document count from registry
        try:
            docs = service.list_documents()
            doc_count = len(docs)
        except Exception as e:
            doc_count = 0
            registry_error = str(e)
        
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        index_map_accessible = os.path.exists(index_map_path) or os.path.exists(ARISConfig.VECTORSTORE_PATH)
        
        return {
            "status": "healthy",
            "service": "gateway",
            "registry_accessible": registry_accessible,
            "registry_document_count": doc_count if 'doc_count' in locals() else 0,
            "index_map_accessible": index_map_accessible
        }
    except Exception as e:
        return {
            "status": "healthy",
            "service": "gateway",
            "registry_accessible": False,
            "index_map_accessible": False,
            "error": str(e)
        }

@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(service: GatewayService = Depends(get_service)):
    """List all processed documents from the registry"""
    docs = service.list_documents()
    
    # Ensure all documents have required fields for DocumentMetadata
    formatted_docs = []
    for doc in docs:
        # Add default status if missing
        if 'status' not in doc:
            doc['status'] = doc.get('chunks_created', 0) > 0 and 'success' or 'processing'
        
        # Ensure all required fields exist
        formatted_doc = {
            'document_id': doc.get('document_id', ''),
            'document_name': doc.get('document_name', ''),
            'status': doc.get('status', 'processing'),
            'chunks_created': doc.get('chunks_created', 0),
            **doc  # Include all other fields
        }
        formatted_docs.append(DocumentMetadata(**formatted_doc))
    
    return DocumentListResponse(
        documents=formatted_docs,
        total=len(formatted_docs)
    )

@app.get("/documents/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    service: GatewayService = Depends(get_service)
):
    """Get a specific document by ID"""
    doc = service.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Ensure all required fields exist
    if 'status' not in doc:
        doc['status'] = doc.get('chunks_created', 0) > 0 and 'success' or 'processing'
    
    formatted_doc = {
        'document_id': doc.get('document_id', document_id),
        'document_name': doc.get('document_name', ''),
        'status': doc.get('status', 'processing'),
        'chunks_created': doc.get('chunks_created', 0),
        **doc  # Include all other fields
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

@app.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    service: GatewayService = Depends(get_service)
):
    """Query the Retrieval service"""
    # Ensure request-scoped document filtering is forwarded to retrieval (critical for citation/page accuracy)
    if request.active_sources is not None:
        service.active_sources = request.active_sources
    elif request.document_id is not None:
        # Backward-compatible: treat document_id as a single active source for strict filtering
        service.active_sources = [request.document_id]

    result = await service.query_text_only(
        question=request.question,
        k=request.k,
        document_id=request.document_id,
        use_mmr=request.use_mmr
    )
    return QueryResponse(**result)

@app.get("/sync/status")
async def sync_status(service: GatewayService = Depends(get_service)):
    """Check synchronization status of shared resources"""
    from shared.config.settings import ARISConfig
    import os
    import json
    
    status = {
        "registry": {
            "path": ARISConfig.DOCUMENT_REGISTRY_PATH,
            "exists": os.path.exists(ARISConfig.DOCUMENT_REGISTRY_PATH),
            "accessible": os.path.exists(ARISConfig.DOCUMENT_REGISTRY_PATH) or os.path.exists(os.path.dirname(ARISConfig.DOCUMENT_REGISTRY_PATH))
        },
        "index_map": {
            "path": os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json"),
            "exists": os.path.exists(os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")),
            "accessible": os.path.exists(ARISConfig.VECTORSTORE_PATH)
        },
        "vectorstore": {
            "path": ARISConfig.VECTORSTORE_PATH,
            "exists": os.path.exists(ARISConfig.VECTORSTORE_PATH),
            "accessible": True
        }
    }
    
    # Get document count from registry
    try:
        docs = service.list_documents()
        status["registry"]["document_count"] = len(docs)
    except Exception as e:
        status["registry"]["error"] = str(e)
    
    # Get index map count
    try:
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        if os.path.exists(index_map_path):
            with open(index_map_path, 'r') as f:
                index_map = json.load(f)
                status["index_map"]["entry_count"] = len(index_map)
    except Exception as e:
        status["index_map"]["error"] = str(e)
    
    return status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
