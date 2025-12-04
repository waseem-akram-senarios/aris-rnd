"""
FastAPI application for ARIS RAG System CRUD operations
"""
import os
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from scripts.setup_logging import setup_logging

# Set up enhanced logging with file persistence
logger = setup_logging(
    name="aris_rag.fastapi",
    level=logging.INFO,
    log_file="logs/fastapi.log"
)

from api.schemas import (
    QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse,
    StatsResponse, ErrorResponse, Citation
)
from api.service import ServiceContainer, create_service_container
from config.settings import ARISConfig

load_dotenv()

# Global service container
service_container: Optional[ServiceContainer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global service_container
    
    logger.info("=" * 60)
    logger.info("[STEP 1] FastAPI Application Starting Up")
    logger.info("=" * 60)
    
    # Startup: Initialize service container using shared config
    logger.info("[STEP 2] Initializing service container...")
    service_container = create_service_container()
    logger.info(f"✅ [STEP 2] Service container initialized: vector_store={service_container.rag_system.vector_store_type}")
    
    # Try to load existing vectorstore if FAISS
    logger.info("[STEP 3] Checking for existing vectorstore...")
    if service_container.rag_system.vector_store_type.lower() == 'faiss':
        vectorstore_path = ARISConfig.get_vectorstore_path()
        logger.info(f"[STEP 3.1] Checking for existing vectorstore at: {vectorstore_path}")
        if os.path.exists(vectorstore_path):
            try:
                logger.info("[STEP 3.2] Loading vectorstore from disk...")
                loaded = service_container.rag_system.load_vectorstore(vectorstore_path)
                if loaded:
                    # Load existing documents from shared registry
                    existing_docs = service_container.document_registry.list_documents()
                    if existing_docs:
                        logger.info(f"✅ [STEP 3.2] Loaded {len(existing_docs)} existing document(s) from shared storage")
                    else:
                        logger.info("✅ [STEP 3.2] Vectorstore loaded (no existing documents)")
                else:
                    logger.warning("⚠️ [STEP 3.2] Vectorstore path exists but failed to load")
            except Exception as e:
                logger.error(f"❌ [STEP 3.2] Could not load existing vectorstore: {e}", exc_info=True)
        else:
            logger.info("ℹ️ [STEP 3] No existing vectorstore found (will create on first document upload)")
    else:
        logger.info("ℹ️ [STEP 3] Using OpenSearch (cloud-based, no local vectorstore)")
    
    logger.info("=" * 60)
    logger.info("✅ [STEP 4] FastAPI Application Ready")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown: Save vectorstore if FAISS
    logger.info("=" * 60)
    logger.info("[SHUTDOWN STEP 1] FastAPI Application Shutting Down")
    logger.info("=" * 60)
    
    if service_container and service_container.rag_system.vector_store_type.lower() == 'faiss':
        vectorstore_path = ARISConfig.get_vectorstore_path()
        try:
            logger.info(f"[SHUTDOWN STEP 2] Saving vectorstore to: {vectorstore_path}")
            service_container.rag_system.save_vectorstore(vectorstore_path)
            logger.info("✅ [SHUTDOWN STEP 2] Vectorstore saved successfully")
        except Exception as e:
            logger.error(f"❌ [SHUTDOWN STEP 2] Could not save vectorstore: {e}", exc_info=True)
    
    logger.info("✅ [SHUTDOWN STEP 3] FastAPI Application Shutdown Complete")


app = FastAPI(
    title="ARIS RAG API",
    description="CRUD API for ARIS RAG Document Q&A System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service() -> ServiceContainer:
    """Dependency to get service container"""
    if service_container is None:
        raise HTTPException(status_code=500, detail="Service container not initialized")
    return service_container


@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("GET / - Root endpoint accessed")
    return {
        "message": "ARIS RAG API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("GET /health - Health check")
    return {"status": "healthy"}


@app.post("/documents", response_model=DocumentMetadata, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    parser: str = Form(default="docling"),
    service: ServiceContainer = Depends(get_service)
):
    """
    Upload and process a document.
    
    Args:
        file: The document file to upload
        parser: Parser to use ('docling', 'pymupdf', 'textract', 'auto')
        service: Service container dependency
    
    Returns:
        DocumentMetadata with processing results
    """
    file_size = file.size if hasattr(file, 'size') else 'unknown'
    logger.info(f"[STEP 1] POST /documents - Upload request: file={file.filename}, parser={parser}, size={file_size}")
    
    # Validate file type
    logger.info("[STEP 2] Validating file type...")
    allowed_extensions = {'.pdf', '.txt', '.docx', '.doc'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        logger.warning(f"⚠️ [STEP 2] Unsupported file type: {file_ext} for file: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    logger.info(f"✅ [STEP 2] File type validated: {file_ext}")
    
    # Read file content
    try:
        logger.info(f"[STEP 3] Reading file content: {file.filename}")
        file_content = await file.read()
        logger.info(f"✅ [STEP 3] File read successfully: {len(file_content)} bytes")
    except Exception as e:
        logger.error(f"❌ [STEP 3] Error reading file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Generate document ID
    document_id = str(uuid.uuid4())
    logger.info(f"[STEP 4] Generated document ID: {document_id}")
    
    # Process document
    try:
        logger.info(f"[STEP 5] Starting document processing: id={document_id}, parser={parser}")
        result = service.document_processor.process_document(
            file_path=file.filename,
            file_content=file_content,
            file_name=file.filename,
            parser_preference=parser.lower() if parser else None
        )
        
        # Try to get pages from metrics collector (most recent processing)
        pages = None
        if service.metrics_collector.processing_metrics:
            # Get the most recent metric for this document
            for metric in reversed(service.metrics_collector.processing_metrics):
                if metric.document_name == result.document_name:
                    pages = metric.pages
                    break
        
        # Convert ProcessingResult to dict
        result_dict = {
            "document_id": document_id,
            "document_name": result.document_name,
            "status": result.status,
            "chunks_created": result.chunks_created,
            "tokens_extracted": result.tokens_extracted,
            "parser_used": result.parser_used,
            "processing_time": result.processing_time,
            "extraction_percentage": result.extraction_percentage,
            "images_detected": result.images_detected,
            "pages": pages,
            "error": result.error
        }
        
        # Store document metadata in shared registry
        logger.info(f"[STEP 6] Storing document metadata: id={document_id}, name={result_dict.get('document_name')}")
        service.add_document(document_id, result_dict)
        logger.info(f"✅ [STEP 6] Document metadata stored")
        
        # Save vectorstore to disk for sharing with Streamlit (FAISS only)
        if (service.rag_system.vectorstore and 
            service.rag_system.vector_store_type.lower() == 'faiss'):
            try:
                vectorstore_path = ARISConfig.get_vectorstore_path()
                logger.info(f"[STEP 7] Saving vectorstore to: {vectorstore_path}")
                service.rag_system.save_vectorstore(vectorstore_path)
                logger.info("✅ [STEP 7] Vectorstore saved successfully")
            except Exception as e:
                logger.warning(f"⚠️ [STEP 7] Could not save vectorstore: {e}", exc_info=True)
        
        logger.info(f"✅ [STEP 8] Document processed successfully: {document_id} - Total time: {result.processing_time:.2f}s")
        # Return metadata with document_id
        return DocumentMetadata(**result_dict)
        
    except Exception as e:
        logger.error(f"❌ [STEP 5] Error processing document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(service: ServiceContainer = Depends(get_service)):
    """List all processed documents"""
    logger.info("[STEP 1] GET /documents - Listing documents")
    """
    List all processed documents.
    
    Returns:
        List of document metadata
    """
    documents = service.list_documents()
    logger.info(f"[STEP 2] Retrieved {len(documents)} document(s) from registry")
    
    # Convert to DocumentMetadata models
    document_list = [
        DocumentMetadata(**doc)
        for doc in documents
    ]
    
    logger.info(f"✅ [STEP 3] Returning {len(document_list)} document(s)")
    return DocumentListResponse(
        documents=document_list,
        total=len(document_list)
    )


@app.get("/documents/{document_id}", response_model=DocumentMetadata)
async def get_document(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get document metadata by ID.
    
    Args:
        document_id: Document ID
    
    Returns:
        Document metadata
    """
    logger.info(f"[STEP 1] GET /documents/{document_id} - Retrieving document")
    doc = service.get_document(document_id)
    if doc is None:
        logger.warning(f"⚠️ [STEP 1] Document not found: {document_id}")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    logger.info(f"✅ [STEP 2] Document retrieved: {document_id}")
    return DocumentMetadata(**doc)


@app.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Delete a document.
    
    Note: This removes metadata only. Vector store cleanup would require
    rebuilding the entire vectorstore, which is expensive. For production,
    consider implementing a more sophisticated deletion strategy.
    
    Args:
        document_id: Document ID to delete
    """
    logger.info(f"[STEP 1] DELETE /documents/{document_id} - Deleting document")
    if not service.remove_document(document_id):
        logger.warning(f"⚠️ [STEP 1] Document not found for deletion: {document_id}")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    logger.info(f"✅ [STEP 2] Document deleted: {document_id}")
    # Note: Vector store cleanup is not implemented here as it requires
    # rebuilding the entire vectorstore. This is a limitation of the current
    # FAISS/OpenSearch implementation that stores all documents together.
    return None


@app.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """Query the RAG system"""
    query_preview = request.question[:50] + "..." if len(request.question) > 50 else request.question
    logger.info(f"[STEP 1] POST /query - Query validation: '{query_preview}' (k={request.k}, mmr={request.use_mmr})")
    """
    Query the RAG system with a question.
    
    Args:
        request: Query request with question and parameters
        service: Service container dependency
    
    Returns:
        Query response with answer, sources, and citations
    """
    if service.rag_system.vectorstore is None:
        logger.warning("⚠️ [STEP 1] Query attempted but no vectorstore available")
        raise HTTPException(
            status_code=400,
            detail="No documents have been processed yet. Please upload documents first."
        )
    logger.info(f"✅ [STEP 1] Query validated - vectorstore available")
    
    try:
        logger.info(f"[STEP 2] Executing vector store retrieval: k={request.k}, mmr={request.use_mmr}")
        result = service.rag_system.query_with_rag(
            question=request.question,
            k=request.k,
            use_mmr=request.use_mmr
        )
        logger.info(f"✅ [STEP 2] Vector store retrieval completed")
        
        # Convert citations to Citation models
        logger.info(f"[STEP 3] Formatting response and extracting citations...")
        citations = [
            Citation(**citation) for citation in result.get("citations", [])
        ]
        logger.info(f"✅ [STEP 3] Response formatted: {len(citations)} citations extracted")
        
        response_time = result.get('response_time', 0)
        logger.info(f"✅ [STEP 4] Query completed successfully: {len(citations)} citations, {response_time:.2f}s")
        
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
        logger.error(f"❌ [STEP 2] Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(service: ServiceContainer = Depends(get_service)):
    """
    Get system statistics and metrics.
    
    Returns:
        Statistics from RAG system and metrics collector
    """
    logger.info("[STEP 1] GET /stats - Retrieving system statistics")
    try:
        logger.info("[STEP 2] Collecting RAG system stats...")
        rag_stats = service.rag_system.get_stats()
        logger.info("[STEP 3] Collecting metrics...")
        metrics = service.metrics_collector.get_all_metrics()
        
        processing_count = len(metrics.get('processing_metrics', []))
        logger.info(f"✅ [STEP 4] Stats retrieved: {processing_count} processing metrics")
        return StatsResponse(
            rag_stats=rag_stats,
            metrics=metrics
        )
    except Exception as e:
        logger.error(f"❌ Error retrieving stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")


@app.get("/sync/status")
async def get_sync_status(service: ServiceContainer = Depends(get_service)):
    """
    Get synchronization status between FastAPI and Streamlit.
    
    Returns:
        Sync status including document count, last update, vectorstore status, conflicts
    """
    logger.info("[STEP 1] GET /sync/status - Checking synchronization status")
    try:
        registry_status = service.document_registry.get_sync_status()
        
        # Check for conflicts
        conflict = service.document_registry.check_for_conflicts()
        
        # Check vectorstore status
        vectorstore_status = {
            'type': service.rag_system.vector_store_type,
            'exists': service.rag_system.vectorstore is not None,
            'path': ARISConfig.get_vectorstore_path() if service.rag_system.vector_store_type.lower() == 'faiss' else None
        }
        
        if service.rag_system.vector_store_type.lower() == 'faiss':
            vectorstore_path = ARISConfig.get_vectorstore_path()
            vectorstore_status['path_exists'] = os.path.exists(vectorstore_path)
            if os.path.exists(vectorstore_path):
                vectorstore_status['last_modified'] = datetime.fromtimestamp(
                    os.path.getmtime(vectorstore_path)
                ).isoformat()
        
        return {
            'document_registry': registry_status,
            'vectorstore': vectorstore_status,
            'rag_stats': service.rag_system.get_stats(),
            'conflicts': conflict
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sync status: {str(e)}")


@app.post("/sync/reload-vectorstore")
async def reload_vectorstore(service: ServiceContainer = Depends(get_service)):
    """
    Manually reload vectorstore from disk.
    Useful when vectorstore was updated by Streamlit.
    Also reloads document registry to sync metadata.
    
    Returns:
        Success message
    """
    logger.info("[STEP 1] POST /sync/reload-vectorstore - Reloading vectorstore and registry")
    try:
        # Check for conflicts and reload registry if needed
        conflict = service.document_registry.check_for_conflicts()
        if conflict:
            service.document_registry.reload_from_disk()
        
        if service.rag_system.vector_store_type.lower() == 'faiss':
            vectorstore_path = ARISConfig.get_vectorstore_path()
            if os.path.exists(vectorstore_path):
                loaded = service.rag_system.load_vectorstore(vectorstore_path)
                if loaded:
                    logger.info(f"✅ [STEP 2] Vectorstore reloaded successfully from: {vectorstore_path}")
                    return {
                        "message": "Vectorstore and registry reloaded successfully",
                        "path": vectorstore_path,
                        "conflict_resolved": conflict is not None
                    }
                else:
                    logger.error(f"❌ Failed to load vectorstore from: {vectorstore_path}")
                    raise HTTPException(status_code=400, detail="Failed to load vectorstore")
            else:
                raise HTTPException(status_code=404, detail=f"Vectorstore path not found: {vectorstore_path}")
        else:
            # OpenSearch loads automatically
            return {"message": "OpenSearch vectorstore is cloud-based and always in sync"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reloading vectorstore: {str(e)}")


@app.post("/sync/save-vectorstore")
async def save_vectorstore(service: ServiceContainer = Depends(get_service)):
    """
    Manually save vectorstore to disk.
    Useful for forcing a save before shutdown or for sharing with Streamlit.
    
    Returns:
        Success message
    """
    logger.info("[STEP 1] POST /sync/save-vectorstore - Manually saving vectorstore")
    try:
        if service.rag_system.vectorstore and service.rag_system.vector_store_type.lower() == 'faiss':
            vectorstore_path = ARISConfig.get_vectorstore_path()
            logger.info(f"[STEP 2] Saving vectorstore to: {vectorstore_path}")
            service.rag_system.save_vectorstore(vectorstore_path)
            logger.info("✅ [STEP 2] Vectorstore saved successfully")
            return {"message": "Vectorstore saved successfully", "path": vectorstore_path}
        else:
            logger.warning("⚠️ No vectorstore to save or using OpenSearch")
            raise HTTPException(
                status_code=400, 
                detail="No vectorstore to save or using OpenSearch (cloud-based)"
            )
    except Exception as e:
        logger.error(f"❌ Error saving vectorstore: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving vectorstore: {str(e)}")


@app.post("/sync/reload-registry")
async def reload_registry(service: ServiceContainer = Depends(get_service)):
    """
    Manually reload document registry from disk.
    Useful when registry was updated by Streamlit.
    
    Returns:
        Success message
    """
    logger.info("[STEP 1] POST /sync/reload-registry - Reloading document registry")
    try:
        conflict = service.document_registry.check_for_conflicts()
        if conflict:
            logger.info(f"⚠️ [STEP 1] Conflict detected: {conflict}")
        logger.info("[STEP 2] Reloading registry from disk...")
        if service.document_registry.reload_from_disk():
            logger.info("✅ [STEP 2] Document registry reloaded successfully")
            return {
                "message": "Document registry reloaded successfully",
                "conflict_resolved": conflict is not None
            }
        else:
            logger.error("❌ Failed to reload registry")
            raise HTTPException(status_code=400, detail="Failed to reload registry")
    except Exception as e:
        logger.error(f"❌ Error reloading registry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error reloading registry: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

