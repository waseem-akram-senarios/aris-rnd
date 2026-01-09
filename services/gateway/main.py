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
import httpx

from scripts.setup_logging import setup_logging
from shared.schemas import (
    QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse,
    DocumentCreateRequest, DocumentUpdateRequest, DocumentDeleteResponse,
    BulkDocumentDeleteRequest, BulkDocumentDeleteResponse,
    VectorIndexListResponse, VectorChunkListResponse, VectorIndexDeleteResponse,
    BulkVectorIndexDeleteRequest, BulkVectorIndexDeleteResponse,
    VectorChunkCreateRequest, VectorChunkUpdateRequest,
    VectorSearchRequest, VectorSearchResponse, IndexMapResponse, IndexMapUpdateRequest
)
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

@app.get("/")
async def root():
    """Root endpoint for basic connectivity check (matches test script expectation)"""
    return {"message": "ARIS RAG System API Gateway", "status": "online"}

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
            "message": "ARIS RAG System API Gateway is operational",
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
async def delete_document(
    document_id: str,
    service: GatewayService = Depends(get_service)
):
    """Delete document from registry and vector stores"""
    # 1. Delete from vector stores (via retrieval service)
    await service.delete_document_from_stores(document_id)
    
    # 2. Remove from registry
    success = service.remove_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    return {"status": "success", "message": f"Document {document_id} deleted"}

@app.get("/documents/{document_id}/images")
async def get_document_images(
    document_id: str,
    service: GatewayService = Depends(get_service)
):
    """Get all images for a document"""
    images = await service.get_document_images(document_id)
    return {"images": images, "total": len(images)}

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
        use_mmr=request.use_mmr,
        response_language=request.response_language,
        filter_language=request.filter_language,
        auto_translate=request.auto_translate
    )
    return QueryResponse(**result)

@app.post("/query/images")
async def query_images(
    request: Dict[str, Any],
    service: GatewayService = Depends(get_service)
):
    """Query images specifically"""
    question = request.get("question", "")
    k = request.get("k", 5)
    source = request.get("source")
    
    images = await service.query_images_only(question, k, source)
    return {"images": images, "total": len(images)}

@app.get("/stats")
async def get_system_stats(service: GatewayService = Depends(get_service)):
    """Get overall system statistics"""
    return await service.get_all_metrics()

@app.get("/stats/chunks")
async def get_chunk_stats(service: GatewayService = Depends(get_service)):
    """Get chunk-level statistics"""
    metrics = await service.get_all_metrics()
    return metrics.get("processing", {})

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


# ============================================================================
# ADMIN CRUD ENDPOINTS - Document Registry Management
# ============================================================================

@app.post("/admin/documents", response_model=DocumentMetadata, status_code=201)
async def create_document_entry(
    request: DocumentCreateRequest,
    service: GatewayService = Depends(get_service)
):
    """
    Create a document entry in the registry manually (without file upload).
    Useful for creating placeholder entries or manual management.
    """
    import uuid
    from datetime import datetime
    
    doc_id = request.document_id or str(uuid.uuid4())
    
    metadata = {
        'document_id': doc_id,
        'document_name': request.document_name,
        'status': request.status,
        'language': request.language,
        'chunks_created': 0,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    if request.metadata:
        metadata.update(request.metadata)
    
    service.document_registry.add_document(doc_id, metadata)
    
    return DocumentMetadata(**metadata)


@app.put("/admin/documents/{document_id}", response_model=DocumentMetadata)
async def update_document_metadata(
    document_id: str,
    request: DocumentUpdateRequest,
    service: GatewayService = Depends(get_service)
):
    """Update document metadata in the registry."""
    existing = service.get_document(document_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Merge updates
    if request.document_name is not None:
        existing['document_name'] = request.document_name
    if request.status is not None:
        existing['status'] = request.status
    if request.language is not None:
        existing['language'] = request.language
    if request.error is not None:
        existing['error'] = request.error
    if request.metadata:
        existing.update(request.metadata)
    
    service.update_document(document_id, existing)
    
    return DocumentMetadata(**existing)


@app.delete("/admin/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document_full(
    document_id: str,
    delete_vectors: bool = True,
    delete_s3: bool = True,
    service: GatewayService = Depends(get_service)
):
    """
    Delete a document completely from the system.
    
    Args:
        document_id: Document ID to delete
        delete_vectors: Also delete vector data from OpenSearch
        delete_s3: Also delete files from S3
    """
    doc = service.get_document(document_id)
    doc_name = doc.get('document_name', '') if doc else None
    
    result = {
        'success': True,
        'document_id': document_id,
        'document_name': doc_name,
        'message': '',
        'vector_deleted': False,
        's3_deleted': False,
        'registry_deleted': False
    }
    
    errors = []
    
    # 1. Delete from vector stores
    if delete_vectors:
        try:
            await service.delete_document_from_stores(document_id)
            result['vector_deleted'] = True
        except Exception as e:
            errors.append(f"Vector deletion failed: {str(e)}")
    
    # 2. Delete from S3
    if delete_s3:
        try:
            from shared.utils.s3_service import S3Service
            s3 = S3Service()
            if s3.enabled and doc_name:
                s3.delete_file(f"documents/{document_id}/{doc_name}")
                result['s3_deleted'] = True
        except Exception as e:
            errors.append(f"S3 deletion failed: {str(e)}")
    
    # 3. Delete from registry
    try:
        removed = service.remove_document(document_id)
        result['registry_deleted'] = removed
    except Exception as e:
        errors.append(f"Registry deletion failed: {str(e)}")
    
    if errors:
        result['success'] = result['registry_deleted']  # Success if at least registry deleted
        result['message'] = f"Partial deletion. Errors: {'; '.join(errors)}"
    else:
        result['message'] = f"Successfully deleted document {document_id}"
    
    return DocumentDeleteResponse(**result)


@app.post("/admin/documents/bulk-delete", response_model=BulkDocumentDeleteResponse)
async def bulk_delete_documents(
    request: BulkDocumentDeleteRequest,
    service: GatewayService = Depends(get_service)
):
    """Delete multiple documents at once."""
    results = {
        'success': True,
        'total_requested': len(request.document_ids),
        'total_deleted': 0,
        'failed': [],
        'message': ''
    }
    
    for doc_id in request.document_ids:
        try:
            doc = service.get_document(doc_id)
            
            # Delete vectors if requested
            if request.delete_vectors:
                try:
                    await service.delete_document_from_stores(doc_id)
                except:
                    pass
            
            # Delete S3 if requested
            if request.delete_s3 and doc:
                try:
                    from shared.utils.s3_service import S3Service
                    s3 = S3Service()
                    if s3.enabled:
                        doc_name = doc.get('document_name', '')
                        s3.delete_file(f"documents/{doc_id}/{doc_name}")
                except:
                    pass
            
            # Delete from registry
            removed = service.remove_document(doc_id)
            if removed:
                results['total_deleted'] += 1
            else:
                results['failed'].append({'document_id': doc_id, 'error': 'Not found in registry'})
                
        except Exception as e:
            results['failed'].append({'document_id': doc_id, 'error': str(e)})
    
    results['success'] = results['total_deleted'] > 0
    results['message'] = f"Deleted {results['total_deleted']}/{results['total_requested']} documents"
    
    return BulkDocumentDeleteResponse(**results)


@app.get("/admin/documents/registry-stats")
async def get_registry_stats(service: GatewayService = Depends(get_service)):
    """Get document registry statistics."""
    docs = service.list_documents()
    
    stats = {
        'total_documents': len(docs),
        'by_status': {},
        'by_language': {},
        'by_parser': {},
        'total_chunks': 0,
        'total_images': 0
    }
    
    for doc in docs:
        status = doc.get('status', 'unknown')
        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        lang = doc.get('language', 'unknown')
        stats['by_language'][lang] = stats['by_language'].get(lang, 0) + 1
        
        parser = doc.get('parser_used', 'unknown')
        stats['by_parser'][parser] = stats['by_parser'].get(parser, 0) + 1
        
        stats['total_chunks'] += doc.get('chunks_created', 0)
        stats['total_images'] += doc.get('images_stored', 0) or doc.get('image_count', 0)
    
    return stats


# ============================================================================
# ADMIN CRUD ENDPOINTS - Vector Database Proxy (to Retrieval Service)
# ============================================================================

@app.get("/admin/vectors/indexes", response_model=VectorIndexListResponse)
async def list_vector_indexes_proxy(
    prefix: str = "aris-",
    service: GatewayService = Depends(get_service)
):
    """List all vector indexes (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{service.retrieval_url}/admin/indexes",
                params={"prefix": prefix}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.get("/admin/vectors/indexes/{index_name}")
async def get_index_info_proxy(
    index_name: str,
    service: GatewayService = Depends(get_service)
):
    """Get detailed index info (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{service.retrieval_url}/admin/indexes/{index_name}")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.delete("/admin/vectors/indexes/{index_name}", response_model=VectorIndexDeleteResponse)
async def delete_vector_index_proxy(
    index_name: str,
    confirm: bool = False,
    service: GatewayService = Depends(get_service)
):
    """Delete a vector index (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.delete(
                f"{service.retrieval_url}/admin/indexes/{index_name}",
                params={"confirm": confirm}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.post("/admin/vectors/indexes/bulk-delete", response_model=BulkVectorIndexDeleteResponse)
async def bulk_delete_indexes_proxy(
    request: BulkVectorIndexDeleteRequest,
    service: GatewayService = Depends(get_service)
):
    """Bulk delete vector indexes (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{service.retrieval_url}/admin/indexes/bulk-delete",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.get("/admin/vectors/indexes/{index_name}/chunks", response_model=VectorChunkListResponse)
async def list_chunks_proxy(
    index_name: str,
    offset: int = 0,
    limit: int = 100,
    source: Optional[str] = None,
    service: GatewayService = Depends(get_service)
):
    """List chunks in an index (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {"offset": offset, "limit": limit}
            if source:
                params["source"] = source
            response = await client.get(
                f"{service.retrieval_url}/admin/indexes/{index_name}/chunks",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.get("/admin/vectors/indexes/{index_name}/chunks/{chunk_id}")
async def get_chunk_proxy(
    index_name: str,
    chunk_id: str,
    service: GatewayService = Depends(get_service)
):
    """Get a specific chunk (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{service.retrieval_url}/admin/indexes/{index_name}/chunks/{chunk_id}"
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.post("/admin/vectors/indexes/{index_name}/chunks")
async def create_chunk_proxy(
    index_name: str,
    request: VectorChunkCreateRequest,
    service: GatewayService = Depends(get_service)
):
    """Create a new chunk (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{service.retrieval_url}/admin/indexes/{index_name}/chunks",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.put("/admin/vectors/indexes/{index_name}/chunks/{chunk_id}")
async def update_chunk_proxy(
    index_name: str,
    chunk_id: str,
    request: VectorChunkUpdateRequest,
    service: GatewayService = Depends(get_service)
):
    """Update a chunk (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.put(
                f"{service.retrieval_url}/admin/indexes/{index_name}/chunks/{chunk_id}",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.delete("/admin/vectors/indexes/{index_name}/chunks/{chunk_id}")
async def delete_chunk_proxy(
    index_name: str,
    chunk_id: str,
    service: GatewayService = Depends(get_service)
):
    """Delete a chunk (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(
                f"{service.retrieval_url}/admin/indexes/{index_name}/chunks/{chunk_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.post("/admin/vectors/search", response_model=VectorSearchResponse)
async def vector_search_proxy(
    request: VectorSearchRequest,
    service: GatewayService = Depends(get_service)
):
    """Direct vector search (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{service.retrieval_url}/admin/search",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.get("/admin/vectors/index-map", response_model=IndexMapResponse)
async def get_index_map_proxy(service: GatewayService = Depends(get_service)):
    """Get the document-to-index mapping (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{service.retrieval_url}/admin/index-map")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.post("/admin/vectors/index-map")
async def update_index_map_proxy(
    request: IndexMapUpdateRequest,
    service: GatewayService = Depends(get_service)
):
    """Update the document-to-index mapping (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{service.retrieval_url}/admin/index-map",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


@app.delete("/admin/vectors/index-map/{document_name}")
async def delete_index_map_entry_proxy(
    document_name: str,
    service: GatewayService = Depends(get_service)
):
    """Remove a document from the index map (proxy to retrieval service)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.delete(
                f"{service.retrieval_url}/admin/index-map/{document_name}"
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Document '{document_name}' not in index map")
            response.raise_for_status()
            return response.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval service error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
