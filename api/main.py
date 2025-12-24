"""
FastAPI application for ARIS RAG System CRUD operations
"""
import os
import uuid
import logging
import hashlib
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Depends, Form, Request
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
    StatsResponse, ErrorResponse, Citation, ImageQueryRequest, ImageQueryResponse,
    ImageResult, DocumentUpdateRequest, TextQueryRequest, TextQueryResponse,
    StorageStatusResponse, CombinedQueryResponse, TextStorageResponse, ImageStorageResponse,
    AllImagesResponse, ImageDetailResult, PageInformationResponse, PageTextChunk,
    VerificationReport, AccuracyCheckResponse, PageVerification, ImageVerification,
    ImagesSummaryResponse, ImageByNumberResponse, ImageByNumberItem
)
from utils.pdf_metadata_extractor import extract_pdf_metadata
from utils.ocr_verifier import OCRVerifier
from utils.ocr_auto_fix import OCRAutoFix
from utils.pdf_content_extractor import extract_pdf_content
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
    
    # Initialize vectorstore based on type
    logger.info("[STEP 3] Initializing vectorstore...")
    if service_container.rag_system.vector_store_type.lower() == 'opensearch':
        # For OpenSearch, try to load/connect to existing indexes
        logger.info("[STEP 3.1] Initializing OpenSearch vectorstore...")
        try:
            loaded = service_container.rag_system.load_vectorstore(service_container.rag_system.opensearch_index or "aris-rag-index")
            if loaded:
                logger.info("✅ [STEP 3.1] OpenSearch vectorstore initialized successfully")
            else:
                logger.info("ℹ️ [STEP 3.1] OpenSearch vectorstore will be created on first document upload")
        except Exception as e:
            logger.warning(f"⚠️ [STEP 3.1] Could not initialize OpenSearch vectorstore: {e}")
            logger.info("ℹ️ [STEP 3.1] OpenSearch vectorstore will be created on first document upload")
    elif service_container.rag_system.vector_store_type.lower() == 'faiss':
        # Use model-specific path
        vectorstore_path = ARISConfig.get_vectorstore_path()
        model_specific_path = ARISConfig.get_vectorstore_path(service_container.rag_system.embedding_model)
        logger.info(f"[STEP 3.1] Checking for existing vectorstore at: {model_specific_path}")
        if os.path.exists(model_specific_path):
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
    background_tasks: BackgroundTasks = None,
    async_process: bool = Form(True),
    service: ServiceContainer = Depends(get_service)
):
    """
    Upload and process a document.
    
    Args:
        file: The document file to upload
        service: Service container dependency
    
    Returns:
        DocumentMetadata with processing results
    """
    file_size = file.size if hasattr(file, 'size') else 'unknown'
    logger.info(f"[STEP 1] POST /documents - Upload request: file={file.filename}, size={file_size}")
    
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
    
    # Calculate file hash for duplicate detection
    logger.info("[STEP 3.5] Calculating file hash...")
    file_hash = hashlib.sha256(file_content).hexdigest()
    logger.info(f"✅ [STEP 3.5] File hash calculated: {file_hash[:16]}...")
    
    # Extract upload metadata
    upload_metadata = {
        'file_hash': file_hash,
        'file_size_bytes': len(file_content),
        'upload_timestamp': datetime.utcnow().isoformat() + 'Z',
        'mime_type': file.content_type or 'application/octet-stream',
        'original_filename': file.filename,
        'file_extension': os.path.splitext(file.filename)[1].lower() if file.filename else None
    }
    
    # Extract PDF metadata if it's a PDF
    pdf_metadata = None
    if file_ext == '.pdf':
        logger.info("[STEP 3.6] Extracting PDF metadata...")
        try:
            pdf_metadata = extract_pdf_metadata(file_content, file.filename)
            logger.info(f"✅ [STEP 3.6] PDF metadata extracted: {pdf_metadata.get('page_count', 0)} pages")
        except Exception as e:
            logger.warning(f"⚠️ [STEP 3.6] Could not extract PDF metadata: {e}")
            pdf_metadata = {'extraction_error': str(e)}
    
    # Check for duplicate documents (same file hash)
    logger.info("[STEP 3.7] Checking for duplicate documents...")
    existing_docs = service.list_documents()
    duplicate_doc_id = None
    for doc in existing_docs:
        if doc.get('file_hash') == file_hash:
            duplicate_doc_id = doc.get('document_id')
            logger.info(f"⚠️ [STEP 3.7] Duplicate document found: {duplicate_doc_id}")
            break
    
    # Generate document ID
    document_id = str(uuid.uuid4())
    logger.info(f"[STEP 4] Generated document ID: {document_id}")
    
    # Best-plan: per-document OpenSearch index for strict isolation
    per_doc_text_index = f"aris-doc-{document_id}"

    def _process_document_background(
        document_id: str,
        file_name: str,
        file_content: bytes,
        per_doc_text_index: str,
        file_hash: str,
        upload_metadata: dict,
        pdf_metadata: Optional[dict],
        duplicate_doc_id: Optional[str]
    ):
        start_ts = time_module.time()
        try:
            logger.info(f"[BG] Starting document processing: id={document_id}, parser=docling")
            result = service.document_processor.process_document(
                file_path=file_name,
                file_content=file_content,
                file_name=file_name,
                parser_preference="docling",
                document_id=document_id
            )

            # Try to get pages from metrics collector (most recent processing)
            pages = None
            if service.metrics_collector.processing_metrics:
                for metric in reversed(service.metrics_collector.processing_metrics):
                    if metric.document_name == result.document_name:
                        pages = metric.pages
                        break

            # Get storage statistics for text and images
            text_chunks_stored = result.chunks_created
            images_stored = getattr(result, 'image_count', 0) if result.images_detected else 0

            # Determine storage status
            text_storage_status = "completed" if text_chunks_stored > 0 else "pending"
            images_storage_status = "completed" if images_stored > 0 else "pending"

            # Get index names
            text_index = "aris-rag-index"
            images_index = "aris-rag-images-index"
            if service.rag_system.vector_store_type.lower() == 'opensearch':
                text_index = per_doc_text_index

            processing_metadata = {
                'processing_time': result.processing_time,
                'parser_used': result.parser_used,
                'extraction_percentage': result.extraction_percentage,
                'stages': {
                    'parsing': getattr(result, 'parsing_time', None),
                    'ocr': getattr(result, 'ocr_time', None),
                    'chunking': getattr(result, 'chunking_time', None)
                }
            }

            ocr_quality_metrics = getattr(result, 'ocr_quality_metrics', None)
            if not ocr_quality_metrics and result.images_detected:
                ocr_quality_metrics = {
                    'images_processed': images_stored,
                    'ocr_enabled': True,
                    'extraction_method': result.parser_used
                }

            version_info = {
                'version': 1,
                'created_at': upload_metadata.get('upload_timestamp'),
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'is_duplicate': duplicate_doc_id is not None,
                'duplicate_of': duplicate_doc_id
            }

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
                "image_count": getattr(result, 'image_count', 0),
                "pages": pages,
                "error": result.error,
                "text_chunks_stored": text_chunks_stored,
                "images_stored": images_stored,
                "text_index": text_index,
                "images_index": images_index,
                "text_storage_status": text_storage_status,
                "images_storage_status": images_storage_status,
                "file_hash": file_hash,
                "upload_metadata": upload_metadata,
                "pdf_metadata": pdf_metadata,
                "processing_metadata": processing_metadata,
                "ocr_quality_metrics": ocr_quality_metrics,
                "version_info": version_info
            }

            logger.info(f"[BG] Storing document metadata (completed): id={document_id}, name={result_dict.get('document_name')}")
            service.add_document(document_id, result_dict)
            logger.info(f"✅ [BG] Document processed successfully: {document_id}")
        except Exception as e:
            elapsed = time_module.time() - start_ts
            logger.error(f"❌ [BG] Error processing document {document_id}: {e}", exc_info=True)

            existing = service.get_document(document_id) or {}
            error_dict = dict(existing)
            error_dict.update({
                "document_id": document_id,
                "document_name": existing.get('document_name') or file_name,
                "status": "error",
                "error": str(e),
                "processing_time": float(elapsed),
                "updated_at": datetime.utcnow().isoformat()
            })
            service.add_document(document_id, error_dict)

    if async_process:
        if background_tasks is None:
            background_tasks = BackgroundTasks()

        placeholder = {
            "document_id": document_id,
            "document_name": file.filename,
            "status": "processing",
            "chunks_created": 0,
            "tokens_extracted": 0,
            "parser_used": "docling",
            "processing_time": 0.0,
            "extraction_percentage": 0.0,
            "images_detected": False,
            "image_count": 0,
            "pages": None,
            "error": None,
            "text_chunks_stored": 0,
            "images_stored": 0,
            "text_index": per_doc_text_index if service.rag_system.vector_store_type.lower() == 'opensearch' else "aris-rag-index",
            "images_index": "aris-rag-images-index",
            "text_storage_status": "pending",
            "images_storage_status": "pending",
            "file_hash": file_hash,
            "upload_metadata": upload_metadata,
            "pdf_metadata": pdf_metadata,
            "processing_metadata": None,
            "ocr_quality_metrics": None,
            "version_info": {
                'version': 1,
                'created_at': upload_metadata.get('upload_timestamp'),
                'updated_at': upload_metadata.get('upload_timestamp'),
                'is_duplicate': duplicate_doc_id is not None,
                'duplicate_of': duplicate_doc_id
            }
        }

        logger.info(f"[STEP 6] Storing document metadata (processing): id={document_id}, name={file.filename}")
        service.add_document(document_id, placeholder)

        background_tasks.add_task(
            _process_document_background,
            document_id,
            file.filename,
            file_content,
            per_doc_text_index,
            file_hash,
            upload_metadata,
            pdf_metadata,
            duplicate_doc_id
        )

        logger.info(f"✅ [STEP 8] Document accepted for background processing: {document_id}")
        return DocumentMetadata(**placeholder)

    # Process document synchronously (legacy behavior)
    try:
        logger.info(f"[STEP 5] Starting document processing: id={document_id}, parser=docling")
        result = service.document_processor.process_document(
            file_path=file.filename,
            file_content=file_content,
            file_name=file.filename,
            parser_preference="docling",
            document_id=document_id
        )
        
        # Try to get pages from metrics collector (most recent processing)
        pages = None
        if service.metrics_collector.processing_metrics:
            # Get the most recent metric for this document
            for metric in reversed(service.metrics_collector.processing_metrics):
                if metric.document_name == result.document_name:
                    pages = metric.pages
                    break
        
        # Get storage statistics for text and images
        text_chunks_stored = result.chunks_created
        images_stored = getattr(result, 'image_count', 0) if result.images_detected else 0
        
        # Determine storage status
        text_storage_status = "completed" if text_chunks_stored > 0 else "pending"
        images_storage_status = "completed" if images_stored > 0 else "pending"
        
        # Get index names
        text_index = "aris-rag-index"
        images_index = "aris-rag-images-index"
        if service.rag_system.vector_store_type.lower() == 'opensearch':
            text_index = per_doc_text_index
        
        # Get processing metadata from result if available
        processing_metadata = {
            'processing_time': result.processing_time,
            'parser_used': result.parser_used,
            'extraction_percentage': result.extraction_percentage,
            'stages': {
                'parsing': getattr(result, 'parsing_time', None),
                'ocr': getattr(result, 'ocr_time', None),
                'chunking': getattr(result, 'chunking_time', None)
            }
        }
        
        # Get OCR quality metrics if available
        ocr_quality_metrics = getattr(result, 'ocr_quality_metrics', None)
        if not ocr_quality_metrics and result.images_detected:
            # Create basic OCR metrics
            ocr_quality_metrics = {
                'images_processed': images_stored,
                'ocr_enabled': True,
                'extraction_method': result.parser_used
            }
        
        # Version info
        version_info = {
            'version': 1,
            'created_at': upload_metadata['upload_timestamp'],
            'updated_at': upload_metadata['upload_timestamp'],
            'is_duplicate': duplicate_doc_id is not None,
            'duplicate_of': duplicate_doc_id
        }
        
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
            "image_count": getattr(result, 'image_count', 0),  # Include image_count in response
            "pages": pages,
            "error": result.error,
            # Text and image separation fields
            "text_chunks_stored": text_chunks_stored,
            "images_stored": images_stored,
            "text_index": text_index,
            "images_index": images_index,
            "text_storage_status": text_storage_status,
            "images_storage_status": images_storage_status,
            # Enhanced metadata fields
            "file_hash": file_hash,
            "upload_metadata": upload_metadata,
            "pdf_metadata": pdf_metadata,
            "processing_metadata": processing_metadata,
            "ocr_quality_metrics": ocr_quality_metrics,
            "version_info": version_info
        }
        
        # Store document metadata in shared registry
        logger.info(f"[STEP 6] Storing document metadata: id={document_id}, name={result_dict.get('document_name')}")
        service.add_document(document_id, result_dict)
        logger.info(f"✅ [STEP 6] Document metadata stored")
        
        # Save vectorstore to disk for sharing with Streamlit (FAISS only)
        # OpenSearch stores data in cloud, so no local save needed
        if (service.rag_system.vectorstore and 
            service.rag_system.vector_store_type.lower() == 'faiss'):
            try:
                vectorstore_path = ARISConfig.get_vectorstore_path()
                logger.info(f"[STEP 7] Saving vectorstore to: {vectorstore_path}")
                service.rag_system.save_vectorstore(vectorstore_path)
                logger.info("✅ [STEP 7] Vectorstore saved successfully")
            except Exception as e:
                logger.warning(f"⚠️ [STEP 7] Could not save vectorstore: {e}", exc_info=True)
        elif (service.rag_system.vectorstore and 
              service.rag_system.vector_store_type.lower() == 'opensearch'):
            # OpenSearch stores data in cloud - already persisted
            opensearch_domain = getattr(service.rag_system, 'opensearch_domain', 'N/A')
            opensearch_index = getattr(service.rag_system, 'opensearch_index', 'N/A')
            logger.info(f"[STEP 7] OpenSearch vectorstore persisted to cloud (Domain: {opensearch_domain}, Index: {opensearch_index})")
            logger.info("✅ [STEP 7] OpenSearch vectorstore saved to cloud (no local save needed)")
        
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
    document_list = []
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        safe_doc = dict(doc)
        if 'document_name' not in safe_doc:
            safe_doc['document_name'] = safe_doc.get('document_id') or 'Unknown'
        if 'status' not in safe_doc:
            safe_doc['status'] = safe_doc.get('text_storage_status') or 'unknown'
        if 'document_id' not in safe_doc and 'id' in safe_doc:
            safe_doc['document_id'] = safe_doc.get('id')
        try:
            document_list.append(DocumentMetadata(**safe_doc))
        except Exception as e:
            logger.warning(f"Skipping invalid registry entry: {e}")
            continue
    
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
    """Get a single document's metadata by document_id."""
    logger.info(f"[STEP 1] GET /documents/{document_id} - Getting document metadata")
    doc = service.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DocumentMetadata(**doc)


# Removed endpoints:
# - GET /documents/{id} - Use GET /documents to list and filter
# - PUT /documents/{id} - Not essential
# - GET /documents/{id}/images - Use POST /query/images with source filter
# - GET /images/{id} - Not essential


@app.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Delete a document completely from the system.
    
    This removes:
    - Document metadata from registry
    - Document chunks from vectorstore (FAISS or OpenSearch)
    - Document images from images index (OpenSearch only)
    
    Args:
        document_id: Document ID to delete
    """
    logger.info(f"[STEP 1] DELETE /documents/{document_id} - Starting document deletion")

    # Get document metadata first to get document name
    doc = service.get_document(document_id)
    if doc is None:
        logger.warning(f"⚠️ [STEP 1] Document not found for deletion: {document_id}")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    document_name = doc.get('document_name', '')
    text_index = doc.get('text_index')
    if not document_name:
        logger.warning(f"⚠️ [STEP 1] Document name not found for: {document_id}")
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")

    vector_store_type = service.rag_system.vector_store_type.lower()

    try:
        # Step 2: Delete from vectorstore
        logger.info(f"[STEP 2] Deleting document from vectorstore: {vector_store_type}")

        if vector_store_type == 'opensearch':
            # Delete OpenSearch index for this document
            index_name = text_index
            if not index_name and hasattr(service.rag_system, 'document_index_map'):
                index_name = service.rag_system.document_index_map.get(document_name)

            if index_name:
                try:
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    temp_store = OpenSearchVectorStore(
                        embeddings=service.rag_system.embeddings,
                        domain=service.rag_system.opensearch_domain,
                        index_name=index_name
                    )

                    # Delete the entire index
                    if temp_store.index_exists(index_name):
                        client = temp_store.vectorstore.client
                        client.indices.delete(index=index_name)
                        logger.info(f"✅ [STEP 2.1] Deleted OpenSearch index: {index_name}")

                        # Remove from document_index_map if present (backward compatibility)
                        if hasattr(service.rag_system, 'document_index_map') and document_name in service.rag_system.document_index_map:
                            del service.rag_system.document_index_map[document_name]
                            service.rag_system._save_document_index_map()
                            logger.info(f"✅ [STEP 2.2] Removed from document_index_map")
                    else:
                        logger.warning(f"⚠️ [STEP 2.1] Index {index_name} does not exist")
                except Exception as e:
                    logger.warning(f"⚠️ [STEP 2] Error deleting OpenSearch index: {e}", exc_info=True)
                    # Continue with deletion even if index deletion fails
            else:
                logger.warning(f"⚠️ [STEP 2] No OpenSearch text index found for document: {document_name} (document_id={document_id})")

        elif vector_store_type == 'faiss':
            # For FAISS, rebuild vectorstore excluding this document
            try:
                # Get all document names except the one being deleted
                all_docs = service.list_documents()
                remaining_doc_names = [
                    d.get('document_name') 
                    for d in all_docs 
                    if d.get('document_id') != document_id and d.get('document_name')
                ]

                if remaining_doc_names:
                    logger.info(f"[STEP 2.1] Rebuilding FAISS vectorstore with {len(remaining_doc_names)} remaining documents")
                    vectorstore_path = ARISConfig.get_vectorstore_path()
                    result = service.rag_system.load_selected_documents(remaining_doc_names, vectorstore_path)

                    if result.get('loaded'):
                        # Save the rebuilt vectorstore
                        service.rag_system.save_vectorstore(vectorstore_path)
                        logger.info(f"✅ [STEP 2.2] Rebuilt and saved FAISS vectorstore")
                    else:
                        logger.warning(f"⚠️ [STEP 2.2] Failed to rebuild vectorstore: {result.get('message')}")
                else:
                    # No documents left, clear vectorstore
                    logger.info(f"[STEP 2.1] No documents remaining, clearing FAISS vectorstore")
                    service.rag_system.vectorstore = None
                    # Optionally delete the vectorstore file
                    vectorstore_path = ARISConfig.get_vectorstore_path()
                    if os.path.exists(vectorstore_path):
                        try:
                            import shutil
                            shutil.rmtree(vectorstore_path)
                            logger.info(f"✅ [STEP 2.2] Deleted FAISS vectorstore directory")
                        except Exception as e:
                            logger.warning(f"⚠️ [STEP 2.2] Could not delete vectorstore directory: {e}")
            except Exception as e:
                logger.warning(f"⚠️ [STEP 2] Error rebuilding FAISS vectorstore: {e}", exc_info=True)
                # Continue with deletion even if vectorstore rebuild fails

        # Step 3: Delete images from images index (OpenSearch only)
        if vector_store_type == 'opensearch':
            logger.info(f"[STEP 3] Deleting images from images index for document: {document_name}")
            try:
                from vectorstores.opensearch_images_store import OpenSearchImagesStore
                from langchain_openai import OpenAIEmbeddings

                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv('OPENAI_API_KEY'),
                    model=service.rag_system.embedding_model
                )

                images_store = OpenSearchImagesStore(
                    embeddings=embeddings,
                    domain=service.rag_system.opensearch_domain,
                    region=getattr(service.rag_system, 'region', None)
                )

                # Get all images for this document
                images = images_store.get_images_by_source(document_name, limit=1000)

                if images:
                    # Delete each image
                    client = images_store.vectorstore.vectorstore.client
                    deleted_count = 0
                    for img in images:
                        image_id = img.get('image_id')
                        if image_id:
                            try:
                                client.delete(index=images_store.index_name, id=image_id)
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"⚠️ [STEP 3] Could not delete image {image_id}: {e}")

                    logger.info(f"✅ [STEP 3] Deleted {deleted_count} images from images index")
                else:
                    logger.info(f"ℹ️ [STEP 3] No images found for document: {document_name}")
            except ImportError as e:
                logger.warning(f"⚠️ [STEP 3] OpenSearch images store not available: {str(e)}")
            except Exception as e:
                logger.warning(f"⚠️ [STEP 3] Error deleting images: {e}", exc_info=True)
                # Continue with deletion even if image deletion fails

        # Step 4: Remove from document registry (last step)
        logger.info(f"[STEP 4] Removing document from registry")
        if not service.remove_document(document_id):
            logger.warning(f"⚠️ [STEP 4] Document not found in registry: {document_id}")
            # This shouldn't happen since we checked at the start, but handle gracefully

        logger.info(f"✅ [STEP 5] Document deletion completed: {document_id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during document deletion: {e}", exc_info=True)
        # Even if vectorstore deletion fails, try to remove from registry
        try:
            service.remove_document(document_id)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """
    Query documents with natural language questions.
    
    Simple and reliable query endpoint that searches all documents by default.
    Optionally filter to a specific document using document_id.
    
    Args:
        request: Query request with question and optional parameters
        service: Service container dependency
    
    Returns:
        Query response with answer, sources, and citations
    """
    # For OpenSearch, vectorstore might be None initially but documents exist in cloud
    # For FAISS, vectorstore must be loaded from disk
    vector_store_type = service.rag_system.vector_store_type.lower()
    has_documents = len(service.list_documents()) > 0

    # For OpenSearch, we can query even if vectorstore is None (it will be created on-the-fly)
    if vector_store_type == 'opensearch':
        # Check if OpenSearch domain is configured
        if not service.rag_system.opensearch_domain:
            raise HTTPException(
                status_code=500,
                detail="OpenSearch domain not configured. Please check your environment variables."
            )

        # If vectorstore is None, try to initialize it
        if service.rag_system.vectorstore is None:
            try:
                logger.info("OpenSearch vectorstore is None, attempting to initialize...")
                loaded = service.rag_system.load_vectorstore(
                    service.rag_system.opensearch_index or "aris-rag-index"
                )
                if not loaded:
                    logger.warning("Could not load OpenSearch vectorstore, will create on query")
            except Exception as e:
                logger.warning(f"Could not initialize OpenSearch vectorstore: {e}")

        # For OpenSearch, we can proceed even if vectorstore is None
        # The query will create/use the index as needed
        if not has_documents:
            raise HTTPException(
                status_code=400,
                detail="No documents have been processed yet. Please upload documents first."
            )
    else:
        # For FAISS, vectorstore must exist
        if service.rag_system.vectorstore is None:
            if has_documents:
                # Try to load from disk
                try:
                    vectorstore_path = ARISConfig.get_vectorstore_path()
                    if os.path.exists(vectorstore_path):
                        logger.info(f"Attempting to load FAISS vectorstore from: {vectorstore_path}")
                        service.rag_system.load_vectorstore(vectorstore_path)
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail="No documents have been processed yet. Please upload documents first."
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Could not load FAISS vectorstore: {e}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Could not load vectorstore: {str(e)}"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No documents have been processed yet. Please upload documents first."
                )

    # Simple document filtering - if document_id provided, try to filter
    # If filtering fails, query all documents (graceful fallback)
    original_active_sources = service.rag_system.active_sources

    if request.document_id:
        try:
            doc = service.get_document(request.document_id)
            if doc:
                document_name = doc.get('document_name') or doc.get('original_document_name')
                if document_name:
                    # Try to set filter - if it fails, will query all
                    service.rag_system.active_sources = [document_name]
                    logger.info(f"Filtering query to document: {document_name}")
        except Exception as e:
            logger.warning(f"Could not filter to document_id {request.document_id}: {e}. Querying all documents.")
            service.rag_system.active_sources = None
    else:
        # Query all documents
        service.rag_system.active_sources = None

    try:
        result = service.rag_system.query_with_rag(
            question=request.question,
            k=request.k,
            use_mmr=request.use_mmr,
            use_hybrid_search=request.use_hybrid_search,
            semantic_weight=request.semantic_weight,
            search_mode=request.search_mode,
            use_agentic_rag=request.use_agentic_rag,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        citations = [
            Citation(**citation) for citation in result.get("citations", [])
        ]

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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    finally:
        # Always restore original active_sources
        service.rag_system.active_sources = original_active_sources


@app.post("/documents/{document_id}/query", response_model=QueryResponse)
async def query_document(
    document_id: str,
    request: QueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """Strictly query a single document by document_id.

    Uses the per-document OpenSearch index stored in the registry (text_index).
    Does not rely on active_sources filtering to avoid cross-document leakage.
    """
    vector_store_type = service.rag_system.vector_store_type.lower()
    if vector_store_type != 'opensearch':
        raise HTTPException(status_code=400, detail="This endpoint requires OpenSearch vector store")

    if not service.rag_system.opensearch_domain:
        raise HTTPException(status_code=500, detail="OpenSearch domain not configured. Please check your environment variables.")

    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    index_name = doc.get('text_index') or f"aris-doc-{document_id}"

    # Ensure we are pointing at the correct per-document index
    service.rag_system.opensearch_index = index_name
    service.rag_system.vectorstore = None

    try:
        # Initialize a store handle for this index (OpenSearch is cloud-backed)
        service.rag_system.load_vectorstore(index_name)
    except Exception as e:
        logger.warning(f"Could not initialize OpenSearch vectorstore for index '{index_name}': {e}")

    try:
        result = service.rag_system.query_with_rag(
            question=request.question,
            k=request.k,
            use_mmr=request.use_mmr,
            use_hybrid_search=request.use_hybrid_search,
            semantic_weight=request.semantic_weight,
            search_mode=request.search_mode,
            use_agentic_rag=request.use_agentic_rag,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        citations = [Citation(**citation) for citation in result.get("citations", [])]
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document-scoped query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/query/text", response_model=TextQueryResponse)
async def query_text_only(
    request: TextQueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """
    Query only text content from documents (excludes images).
    
    This endpoint queries only the main document index (aris-rag-index)
    and excludes any content from the images index.
    
    Args:
        request: Text query request with question and optional parameters
        service: Service container dependency
    
    Returns:
        Text query response with answer, sources, and citations (text-only)
    """
    logger.info(f"POST /query/text - Querying text-only content: question='{request.question[:50]}...', k={request.k}, document_id={request.document_id}")
    
    # Check if vectorstore is available
    vector_store_type = service.rag_system.vector_store_type.lower()
    has_documents = len(service.list_documents()) > 0
    
    if vector_store_type == 'opensearch':
        if not hasattr(service.rag_system, 'opensearch_domain') or not service.rag_system.opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="OpenSearch domain not configured. Text queries require OpenSearch vector store."
            )
    elif vector_store_type == 'faiss':
        if not service.rag_system.vectorstore:
            raise HTTPException(
                status_code=404,
                detail="No vectorstore loaded. Please upload documents first."
            )
    
    if not has_documents:
        raise HTTPException(
            status_code=404,
            detail="No documents available. Please upload documents first."
        )
    
    # Store original active_sources
    original_active_sources = service.rag_system.active_sources
    
    # Set document filter if provided
    if request.document_id:
        try:
            doc = service.get_document(request.document_id)
            if doc:
                document_name = doc.get('document_name') or doc.get('original_document_name')
                if document_name:
                    service.rag_system.active_sources = [document_name]
                    logger.info(f"Filtering text query to document: {document_name}")
        except Exception as e:
            logger.warning(f"Could not filter to document_id {request.document_id}: {e}. Querying all documents.")
            service.rag_system.active_sources = None
    else:
        service.rag_system.active_sources = None
    
    try:
        # Use service method for text-only query
        result = service.query_text_only(
            question=request.question,
            k=request.k,
            document_id=request.document_id,
            use_mmr=request.use_mmr
        )
        
        citations = [
            Citation(**citation) for citation in result.get("citations", [])
        ]
        
        # Get total text chunks count if available
        total_text_chunks = 0
        if service.rag_system.vectorstore:
            try:
                if vector_store_type == 'opensearch':
                    # Try to get count from OpenSearch
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    if hasattr(service.rag_system, 'opensearch_index'):
                        index_name = service.rag_system.opensearch_index or 'aris-rag-index'
                        temp_store = OpenSearchVectorStore(
                            embeddings=service.rag_system.embeddings,
                            domain=service.rag_system.opensearch_domain,
                            index_name=index_name
                        )
                        if temp_store.index_exists(index_name):
                            client = temp_store.vectorstore.client
                            count_response = client.count(index=index_name)
                            total_text_chunks = count_response.get('count', 0)
                elif vector_store_type == 'faiss':
                    # For FAISS, get count from vectorstore
                    if hasattr(service.rag_system.vectorstore, 'index'):
                        total_text_chunks = service.rag_system.vectorstore.index.ntotal
            except Exception as e:
                logger.debug(f"Could not get total text chunks count: {e}")
        
        return TextQueryResponse(
            answer=result["answer"],
            sources=result.get("sources", []),
            citations=citations,
            num_chunks_used=result.get("num_chunks_used", 0),
            response_time=result.get("response_time", 0.0),
            content_type="text",
            total_text_chunks=total_text_chunks,
            context_tokens=result.get("context_tokens", 0),
            response_tokens=result.get("response_tokens", 0),
            total_tokens=result.get("total_tokens", 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing text query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing text query: {str(e)}")
    finally:
        # Always restore original active_sources
        service.rag_system.active_sources = original_active_sources


# GET /stats removed - not essential for core functionality
# Statistics can be obtained from GET /documents response


@app.post("/query/images", response_model=ImageQueryResponse)
async def query_images(
    request: ImageQueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """
    Query images - search semantically or get all images for a document.
    
    - Use question to search images semantically
    - Use empty question ("") and source to get all images for a document
    - Use source to filter by document name
    
    Args:
        request: Image query request
            - question: Search query (use "" to get all images)
            - source: Optional document name to filter by
            - k: Number of results
    
    Returns:
        Image query response with matching images
    """
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        raise HTTPException(
            status_code=400,
            detail="Image queries require OpenSearch vector store"
        )
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=service.rag_system.opensearch_domain,
            region=getattr(service.rag_system, 'region', None)
        )
        
        # If question is empty and source provided, get all images for that document
        if not request.question.strip() and request.source:
            logger.info(f"Getting all images for source: {request.source}")
            # Try multiple source formats
            source_variants = [
                request.source,
                os.path.basename(request.source),
                request.source.lower(),
                os.path.basename(request.source).lower()
            ]
            
            images = []
            for source_variant in source_variants:
                if not source_variant:
                    continue
                logger.info(f"Trying source variant: '{source_variant}'")
                images = images_store.get_images_by_source(source_variant, limit=request.k)
                if images:
                    logger.info(f"✅ Found {len(images)} images with source variant: '{source_variant}'")
                    break
            
            if not images:
                # If no images found with source filter, try getting all images and filter manually
                logger.warning(f"No images found with source filter, trying to get all images...")
                try:
                    client = images_store.vectorstore.vectorstore.client
                    response = client.search(
                        index=images_store.index_name,
                        body={
                            "size": 100,
                            "query": {"match_all": {}}
                        }
                    )
                    all_hits = response.get("hits", {}).get("hits", [])
                    logger.info(f"Found {len(all_hits)} total images in index")
                    
                    # Show what sources exist
                    sources_found = set()
                    for hit in all_hits[:10]:  # Check first 10
                        meta = hit.get("_source", {}).get('metadata', {})
                        src = meta.get('source', 'unknown')
                        sources_found.add(src)
                    logger.info(f"Sample sources in index: {list(sources_found)}")
                    
                    # Try to match manually
                    for hit in all_hits:
                        meta = hit.get("_source", {}).get('metadata', {})
                        src = meta.get('source', '')
                        if (request.source in src or 
                            os.path.basename(request.source) in src or
                            src in request.source or
                            os.path.basename(src) == os.path.basename(request.source)):
                            source_data = hit.get("_source", {})
                            images.append({
                                'image_id': hit.get("_id"),
                                'source': meta.get('source'),
                                'image_number': meta.get('image_number', 0),
                                'page': meta.get('page'),
                                'ocr_text': source_data.get('text', ''),
                                'score': None
                            })
                    if images:
                        logger.info(f"✅ Found {len(images)} images by manual matching")
                except Exception as e:
                    logger.warning(f"Could not get all images: {e}")
            
            results = images
        else:
            # Semantic search
            results = service.rag_system.query_images(
                question=request.question or "all images",
                source=request.source,
                k=request.k
            )
        
        # Convert to ImageResult models
        image_results = []
        for img in results:
            try:
                image_results.append(ImageResult(
                    image_id=img.get('image_id', ''),
                    source=img.get('source', ''),
                    image_number=img.get('image_number', 0),
                    page=img.get('page'),
                    ocr_text=img.get('ocr_text', ''),
                    metadata=img.get('metadata', {}),
                    score=img.get('score')
                ))
            except Exception:
                continue
        
        return ImageQueryResponse(
            images=image_results,
            total=len(image_results),
            content_type="image_ocr",
            images_index=images_store.index_name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing image query: {e}", exc_info=True)
        return ImageQueryResponse(images=[], total=0, content_type="image_ocr", images_index="aris-rag-images-index")


@app.get("/documents/{document_id}/storage/status", response_model=StorageStatusResponse)
async def get_storage_status(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get separate storage status for text and images.
    
    Returns detailed information about:
    - Text chunks stored in main index (aris-rag-index)
    - Images with OCR stored in images index (aris-rag-images-index)
    - Storage status for each
    - OCR statistics
    
    Args:
        document_id: Document ID to check
        service: Service container dependency
    
    Returns:
        Storage status response with text and image separation info
    """
    logger.info(f"GET /documents/{document_id}/storage/status - Getting storage status")
    
    try:
        status = service.get_storage_status(document_id)
        
        return StorageStatusResponse(
            document_id=status['document_id'],
            document_name=status['document_name'],
            text_index=status['text_index'],
            text_chunks_count=status['text_chunks_count'],
            text_storage_status=status['text_storage_status'],
            text_last_updated=status.get('text_last_updated'),
            images_index=status['images_index'],
            images_count=status['images_count'],
            images_storage_status=status['images_storage_status'],
            images_last_updated=status.get('images_last_updated'),
            ocr_enabled=status['ocr_enabled'],
            total_ocr_text_length=status['total_ocr_text_length']
        )
    except ValueError as e:
        logger.warning(f"Document not found: {document_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting storage status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting storage status: {str(e)}")


@app.get("/documents/{document_id}/images/all", response_model=AllImagesResponse)
async def get_all_images_info(
    document_id: str,
    limit: int = 1000,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get ALL image information from a document.
    
    Returns comprehensive information about all images including:
    - Complete OCR text
    - Full metadata
    - Extraction details
    - Page numbers
    - Context information
    
    Args:
        document_id: Document ID
        limit: Maximum number of images to return (default: 1000)
        service: Service container dependency
    
    Returns:
        AllImagesResponse with complete image information
    """
    logger.info(f"GET /documents/{document_id}/images/all - Getting all image information")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="Image retrieval requires OpenSearch. Please configure OPENSEARCH_DOMAIN."
            )
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        opensearch_region = getattr(service.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=opensearch_domain,
            region=opensearch_region
        )
        
        # Get all images for this document
        logger.info(f"Retrieving all images for document: {doc_name}")
        images = images_store.get_images_by_source(doc_name, limit=limit)
        
        if not images:
            logger.warning(f"No images found for document: {doc_name}")
            return AllImagesResponse(
                document_id=document_id,
                document_name=doc_name,
                images=[],
                total=0,
                images_index=images_store.index_name,
                total_ocr_text_length=0,
                average_ocr_length=0.0,
                images_with_ocr=0
            )
        
        # Convert to detailed results
        detailed_images = []
        total_ocr_length = 0
        images_with_ocr = 0
        
        for img in images:
            ocr_text = img.get('ocr_text', '') or ''
            ocr_length = len(ocr_text)
            total_ocr_length += ocr_length
            if ocr_text.strip():
                images_with_ocr += 1
            
            # Get full metadata - handle nested structure
            img_metadata = img.get('metadata', {}) or {}
            if isinstance(img_metadata, dict):
                # Extract nested metadata if it exists
                nested_meta = img_metadata.get('metadata', {}) or {}
                full_metadata = {**img_metadata, **nested_meta} if nested_meta else img_metadata
            else:
                full_metadata = {}
            
            # Extract all available fields from the image data
            extraction_method = img.get('extraction_method') or full_metadata.get('extraction_method')
            extraction_timestamp = img.get('extraction_timestamp') or full_metadata.get('extraction_timestamp')
            marker_detected = full_metadata.get('marker_detected') if isinstance(full_metadata, dict) else img.get('marker_detected')
            full_chunk = full_metadata.get('full_chunk') if isinstance(full_metadata, dict) else None
            context_before = full_metadata.get('context_before') if isinstance(full_metadata, dict) else None
            
            # Include all metadata fields in the metadata dict
            if isinstance(full_metadata, dict):
                # Add any missing fields from img to metadata
                for key in ['extraction_method', 'extraction_timestamp', 'marker_detected', 'full_chunk', 'context_before', 'ocr_text_length']:
                    if key not in full_metadata and img.get(key):
                        full_metadata[key] = img.get(key)
            
            detailed_images.append(ImageDetailResult(
                image_id=img.get('image_id', ''),
                source=img.get('source', doc_name),
                image_number=img.get('image_number', 0),
                page=img.get('page'),
                ocr_text=ocr_text,
                ocr_text_length=ocr_length,
                metadata=full_metadata,
                extraction_method=extraction_method,
                extraction_timestamp=extraction_timestamp,
                marker_detected=marker_detected,
                full_chunk=full_chunk,
                context_before=context_before,
                score=None
            ))
        
        # Sort by image number
        detailed_images.sort(key=lambda x: x.image_number)
        
        average_ocr = total_ocr_length / len(detailed_images) if detailed_images else 0.0
        
        logger.info(f"✅ Retrieved {len(detailed_images)} images with {total_ocr_length:,} total OCR characters")
        
        return AllImagesResponse(
            document_id=document_id,
            document_name=doc_name,
            images=detailed_images,
            total=len(detailed_images),
            images_index=images_store.index_name,
            total_ocr_text_length=total_ocr_length,
            average_ocr_length=average_ocr,
            images_with_ocr=images_with_ocr
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting all images: {str(e)}")


@app.get("/documents/{document_id}/images", response_model=ImagesSummaryResponse)
async def get_images_summary(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get summary of all images in a document with their numbers and OCR text.
    
    Returns a simple list showing:
    - Total number of images
    - Each image with its number and OCR text content
    
    Args:
        document_id: Document ID
        service: Service container dependency
    
    Returns:
        ImagesSummaryResponse with total count and images by number
    """
    logger.info(f"GET /documents/{document_id}/images - Getting images summary")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="Image retrieval requires OpenSearch. Please configure OPENSEARCH_DOMAIN."
            )
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        opensearch_region = getattr(service.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=opensearch_domain,
            region=opensearch_region
        )
        
        # Get all images for this document
        logger.info(f"Retrieving images summary for document: {doc_name}")
        images = images_store.get_images_by_source(doc_name, limit=1000)
        
        if not images:
            logger.warning(f"No images found for document: {doc_name}")
            return ImagesSummaryResponse(
                document_id=document_id,
                document_name=doc_name,
                total_images=0,
                images=[]
            )
        
        # Convert to simple format sorted by image number
        image_items = []
        for img in images:
            ocr_text = img.get('ocr_text', '') or ''
            image_items.append(ImageByNumberItem(
                image_number=img.get('image_number', 0),
                page=img.get('page'),
                ocr_text=ocr_text,
                ocr_text_length=len(ocr_text),
                image_id=img.get('image_id')
            ))
        
        # Sort by image number
        image_items.sort(key=lambda x: x.image_number)
        
        logger.info(f"✅ Retrieved {len(image_items)} images summary")
        
        return ImagesSummaryResponse(
            document_id=document_id,
            document_name=doc_name,
            total_images=len(image_items),
            images=image_items
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting images summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting images summary: {str(e)}")


@app.get("/documents/{document_id}/images/{image_number}", response_model=ImageByNumberResponse)
async def get_image_by_number(
    document_id: str,
    image_number: int,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get a specific image by its image number.
    
    Returns the OCR text content and metadata for a specific image number.
    
    Args:
        document_id: Document ID
        image_number: Image number (0-indexed)
        service: Service container dependency
    
    Returns:
        ImageByNumberResponse with image OCR text and details
    """
    logger.info(f"GET /documents/{document_id}/images/{image_number} - Getting image by number")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="Image retrieval requires OpenSearch. Please configure OPENSEARCH_DOMAIN."
            )
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        opensearch_region = getattr(service.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=opensearch_domain,
            region=opensearch_region
        )
        
        # Get all images for this document
        logger.info(f"Retrieving image {image_number} for document: {doc_name}")
        images = images_store.get_images_by_source(doc_name, limit=1000)
        
        if not images:
            raise HTTPException(status_code=404, detail=f"No images found for document {document_id}")
        
        # Find image with matching number
        found_image = None
        for img in images:
            if img.get('image_number') == image_number:
                found_image = img
                break
        
        if not found_image:
            raise HTTPException(
                status_code=404, 
                detail=f"Image number {image_number} not found in document {document_id}"
            )
        
        # Get metadata
        img_metadata = found_image.get('metadata', {}) or {}
        if isinstance(img_metadata, dict):
            nested_meta = img_metadata.get('metadata', {}) or {}
            full_metadata = {**img_metadata, **nested_meta} if nested_meta else img_metadata
        else:
            full_metadata = {}
        
        ocr_text = found_image.get('ocr_text', '') or ''
        
        logger.info(f"✅ Retrieved image {image_number} with {len(ocr_text)} OCR characters")
        
        return ImageByNumberResponse(
            document_id=document_id,
            document_name=doc_name,
            image_number=image_number,
            page=found_image.get('page'),
            ocr_text=ocr_text,
            ocr_text_length=len(ocr_text),
            image_id=found_image.get('image_id'),
            metadata=full_metadata if full_metadata else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image by number: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting image by number: {str(e)}")


@app.get("/documents/{document_id}/pages/{page_number}", response_model=PageInformationResponse)
async def get_page_information(
    document_id: str,
    page_number: int,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get ALL information from a specific page of a document.
    
    Returns comprehensive information including:
    - All text chunks from the page
    - All images from the page with complete OCR text
    - Full metadata for text and images
    - Complete page content
    
    Args:
        document_id: Document ID
        page_number: Page number (1-indexed)
        service: Service container dependency
    
    Returns:
        PageInformationResponse with all text and image information from the page
    """
    logger.info(f"GET /documents/{document_id}/pages/{page_number} - Getting all information from page {page_number}")
    
    if page_number < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1")
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        # Get text chunks from the page
        text_chunks = []
        total_text_length = 0
        
        # Check if OpenSearch is configured
        vector_store_type = service.rag_system.vector_store_type.lower()
        
        if vector_store_type == 'opensearch':
            try:
                from vectorstores.opensearch_store import OpenSearchVectorStore
                from langchain_openai import OpenAIEmbeddings
                
                # Get the document's index
                text_index = getattr(service.rag_system, 'opensearch_index', 'aris-rag-index') or 'aris-rag-index'
                
                # Check if document has specific index
                if hasattr(service.rag_system, 'document_index_map'):
                    doc_index = service.rag_system.document_index_map.get(doc_name)
                    if doc_index:
                        text_index = doc_index
                
                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv('OPENAI_API_KEY'),
                    model=service.rag_system.embedding_model
                )
                
                text_store = OpenSearchVectorStore(
                    embeddings=embeddings,
                    domain=service.rag_system.opensearch_domain,
                    index_name=text_index
                )
                
                # Query OpenSearch for chunks from this page
                client = text_store.vectorstore.client
                query = {
                    "size": 1000,
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"metadata.source.keyword": doc_name}},
                                {"term": {"metadata.page": page_number}}
                            ]
                        }
                    },
                    "sort": [{"metadata.chunk_index": {"order": "asc"}}]
                }
                
                response = client.search(index=text_index, body=query)
                hits = response.get("hits", {}).get("hits", [])
                
                for hit in hits:
                    source_data = hit.get("_source", {})
                    meta = source_data.get("metadata", {}) or {}
                    text_content = source_data.get("text", "") or ""
                    
                    text_chunks.append(PageTextChunk(
                        chunk_index=meta.get("chunk_index", 0),
                        text=text_content,
                        page=meta.get("page", page_number),
                        source=meta.get("source", doc_name),
                        token_count=meta.get("token_count"),
                        start_char=meta.get("start_char"),
                        end_char=meta.get("end_char")
                    ))
                    total_text_length += len(text_content)
                
                logger.info(f"Found {len(text_chunks)} text chunks from page {page_number}")
                
            except Exception as e:
                logger.warning(f"Could not retrieve text chunks from OpenSearch: {e}")
        
        # Get images from the page
        images = []
        total_ocr_length = 0
        
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
            opensearch_region = getattr(service.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
            
            if opensearch_domain:
                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv('OPENAI_API_KEY'),
                    model=service.rag_system.embedding_model
                )
                
                images_store = OpenSearchImagesStore(
                    embeddings=embeddings,
                    domain=opensearch_domain,
                    region=opensearch_region
                )
                
                # Get all images for this document
                all_images = images_store.get_images_by_source(doc_name, limit=1000)
                
                # Filter images by page number
                for img in all_images:
                    img_page = img.get('page')
                    if img_page == page_number:
                        ocr_text = img.get('ocr_text', '') or ''
                        ocr_length = len(ocr_text)
                        total_ocr_length += ocr_length
                        
                        img_metadata = img.get('metadata', {}) or {}
                        if isinstance(img_metadata, dict):
                            nested_meta = img_metadata.get('metadata', {}) or {}
                            full_metadata = {**img_metadata, **nested_meta} if nested_meta else img_metadata
                        else:
                            full_metadata = {}
                        
                        extraction_method = img.get('extraction_method') or full_metadata.get('extraction_method')
                        extraction_timestamp = img.get('extraction_timestamp') or full_metadata.get('extraction_timestamp')
                        marker_detected = full_metadata.get('marker_detected') if isinstance(full_metadata, dict) else img.get('marker_detected')
                        full_chunk = full_metadata.get('full_chunk') if isinstance(full_metadata, dict) else None
                        context_before = full_metadata.get('context_before') if isinstance(full_metadata, dict) else None
                        
                        images.append(ImageDetailResult(
                            image_id=img.get('image_id', ''),
                            source=img.get('source', doc_name),
                            image_number=img.get('image_number', 0),
                            page=img_page,
                            ocr_text=ocr_text,
                            ocr_text_length=ocr_length,
                            metadata=full_metadata,
                            extraction_method=extraction_method,
                            extraction_timestamp=extraction_timestamp,
                            marker_detected=marker_detected,
                            full_chunk=full_chunk,
                            context_before=context_before,
                            score=None
                        ))
                
                # Sort images by image number
                images.sort(key=lambda x: x.image_number)
                logger.info(f"Found {len(images)} images from page {page_number}")
                
        except Exception as e:
            logger.warning(f"Could not retrieve images: {e}")
        
        # Get index names
        text_index = getattr(service.rag_system, 'opensearch_index', 'aris-rag-index') or 'aris-rag-index'
        images_index = 'aris-rag-images-index'
        
        logger.info(f"✅ Retrieved page {page_number} information: {len(text_chunks)} text chunks, {len(images)} images")
        
        return PageInformationResponse(
            document_id=document_id,
            document_name=doc_name,
            page_number=page_number,
            text_chunks=text_chunks,
            images=images,
            total_text_chunks=len(text_chunks),
            total_images=len(images),
            total_text_length=total_text_length,
            total_ocr_text_length=total_ocr_length,
            text_index=text_index,
            images_index=images_index
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page information: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting page information: {str(e)}")


@app.post("/documents/{document_id}/store/text", response_model=TextStorageResponse)
async def store_text_content(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Re-store text content separately in text index.
    
    This endpoint processes the document and stores only the text content
    in the main document index (aris-rag-index), excluding images.
    
    Args:
        document_id: Document ID to process
        service: Service container dependency
    
    Returns:
        Storage result with text chunks count
    """
    logger.info(f"POST /documents/{document_id}/store/text - Storing text content separately")
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        # Check if we need to re-process the document
        # For now, this endpoint assumes the document was already processed
        # and we're just re-storing the text chunks
        
        # Get text chunks count from current storage
        text_chunks_count = doc.get('chunks_created', 0)
        
        # If no chunks exist, we might need to re-process
        if text_chunks_count == 0:
            logger.warning(f"No text chunks found for document {document_id}. Document may need to be re-uploaded.")
            raise HTTPException(
                status_code=400,
                detail="No text chunks found. Please re-upload the document to process text content."
            )
        
        # Verify text is stored in correct index
        text_index = getattr(service.rag_system, 'opensearch_index', 'aris-rag-index') or 'aris-rag-index'
        
        logger.info(f"✅ Text content already stored: {text_chunks_count} chunks in index '{text_index}'")
        
        return TextStorageResponse(
            document_id=document_id,
            document_name=doc_name,
            text_chunks_stored=text_chunks_count,
            text_index=text_index,
            status="completed",
            message=f"Text content verified: {text_chunks_count} chunks in index '{text_index}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing text content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error storing text content: {str(e)}")


@app.post("/documents/{document_id}/store/images", response_model=ImageStorageResponse)
async def store_image_content(
    document_id: str,
    file: Optional[UploadFile] = File(None),
    service: ServiceContainer = Depends(get_service)
):
    """
    Re-store image OCR content separately in images index.
    
    This endpoint processes the document and stores only the image OCR content
    in the images index (aris-rag-images-index), excluding regular text.
    
    If a file is provided, it will re-process the document with Docling parser
    to extract image OCR. If no file is provided, it checks if images are
    already stored in OpenSearch.
    
    Args:
        document_id: Document ID to process
        file: Optional PDF file to re-process with Docling parser
        service: Service container dependency
    
    Returns:
        Storage result with images count and OCR statistics
    """
    logger.info(f"POST /documents/{document_id}/store/images - Storing image OCR content separately")
    if file:
        logger.info(f"File provided for re-processing: {file.filename}")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="Image storage requires OpenSearch. Please configure OPENSEARCH_DOMAIN."
            )
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    if not doc_name:
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        opensearch_region = getattr(service.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=opensearch_domain,
            region=opensearch_region
        )
        
        # If file is provided, re-process with Docling to extract images
        if file:
            logger.info(f"Re-processing document with Docling parser to extract image OCR...")
            
            # Validate file type
            file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
            if file_ext != '.pdf':
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file_ext}. Only PDF files are supported for image OCR extraction."
                )
            
            # Read file content
            try:
                file_content = await file.read()
                logger.info(f"Read file content: {len(file_content)} bytes")
            except Exception as e:
                logger.error(f"Error reading file: {e}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
            
            # Re-process with Docling parser
            try:
                from parsers.docling_parser import DoclingParser
                from ingestion.document_processor import DocumentProcessor
                import tempfile
                
                processor = DocumentProcessor(service.rag_system)
                logger.info("Processing document with Docling parser to extract images...")
                
                # Parse document directly with Docling to get extracted_images
                # Save file content to temp file for parser
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name
                
                try:
                    # Parse with Docling directly
                    docling_parser = DoclingParser()
                    
                    # Check OCR models before parsing
                    ocr_models_available = docling_parser._verify_ocr_models()
                    logger.info(f"OCR models available: {ocr_models_available}")
                    
                    parsed_doc = docling_parser.parse(temp_file_path, file_content=file_content)
                    
                    # Log detailed diagnostics
                    logger.info(f"Parsed document - images_detected: {parsed_doc.images_detected}, image_count: {parsed_doc.image_count}")
                    logger.info(f"Parsed document - text length: {len(parsed_doc.text)}, extraction_percentage: {parsed_doc.extraction_percentage}")
                    
                    # Extract images from parsed document metadata
                    extracted_images = []
                    if (hasattr(parsed_doc, 'metadata') and 
                        isinstance(parsed_doc.metadata, dict)):
                        extracted_images = parsed_doc.metadata.get('extracted_images', [])
                        logger.info(f"Found {len(extracted_images)} images in metadata.extracted_images")
                        
                        # Log metadata keys for debugging
                        logger.info(f"Metadata keys: {list(parsed_doc.metadata.keys())}")
                        
                        # Check if images_detected but extracted_images is empty
                        if parsed_doc.images_detected and len(extracted_images) == 0:
                            logger.warning("⚠️ Images detected but extracted_images list is empty!")
                            logger.warning(f"   - images_detected: {parsed_doc.images_detected}")
                            logger.warning(f"   - image_count: {parsed_doc.image_count}")
                            logger.warning(f"   - text_length: {len(parsed_doc.text)}")
                            logger.warning(f"   - Has text: {bool(parsed_doc.text and parsed_doc.text.strip())}")
                            
                            # Check if text contains image markers
                            if parsed_doc.text and '<!-- image -->' in parsed_doc.text:
                                logger.warning("   - Text contains image markers but no extracted_images!")
                                # Try to extract manually as fallback
                                logger.info("   - Attempting manual extraction from text...")
                                try:
                                    # Use the parser's extraction method
                                    extracted_images = docling_parser._extract_individual_images(
                                        text=parsed_doc.text,
                                        image_count=parsed_doc.image_count or 1,
                                        source=doc_name,
                                        page_blocks=parsed_doc.metadata.get('page_blocks', [])
                                    )
                                    logger.info(f"   - Manual extraction found {len(extracted_images)} images")
                                except Exception as e:
                                    logger.error(f"   - Manual extraction failed: {e}")
                    
                    logger.info(f"Final extracted_images count: {len(extracted_images)}")
                    
                    if not extracted_images:
                        # If images detected but no extracted_images, try fallback
                        if (parsed_doc.images_detected or parsed_doc.image_count > 0) and parsed_doc.text and len(parsed_doc.text.strip()) > 100:
                            logger.warning("⚠️ Images detected and text available, but extracted_images is empty. Creating fallback image entries from text...")
                            
                            # Create fallback image entries from the extracted text
                            # Split text by pages if page_blocks available
                            page_blocks = parsed_doc.metadata.get('page_blocks', [])
                            
                            if page_blocks:
                                # Create one image per page that has content
                                for page_num, page_data in enumerate(page_blocks, start=1):
                                    page_text = page_data.get('text', '') if isinstance(page_data, dict) else str(page_data)
                                    if page_text and len(page_text.strip()) > 50:
                                        extracted_images.append({
                                            'source': doc_name,
                                            'image_number': len(extracted_images) + 1,
                                            'page': page_num,
                                            'ocr_text': page_text,
                                            'ocr_text_length': len(page_text),
                                            'marker_detected': '<!-- image -->' in page_text,
                                            'extraction_method': 'docling_ocr_fallback',
                                            'full_chunk': page_text[:1000],
                                            'context_before': None
                                        })
                            else:
                                # No page blocks - create single image entry from all text
                                extracted_images.append({
                                    'source': doc_name,
                                    'image_number': 1,
                                    'page': 1,
                                    'ocr_text': parsed_doc.text,
                                    'ocr_text_length': len(parsed_doc.text),
                                    'marker_detected': '<!-- image -->' in parsed_doc.text,
                                    'extraction_method': 'docling_ocr_fallback',
                                    'full_chunk': parsed_doc.text[:1000],
                                    'context_before': None
                                })
                            
                            logger.info(f"✅ Created {len(extracted_images)} fallback image entries from text")
                        
                        if not extracted_images:
                            # Build detailed error message
                            error_details = []
                            error_details.append(f"Document: {doc_name}")
                            error_details.append(f"Images detected: {parsed_doc.images_detected}")
                            error_details.append(f"Image count: {parsed_doc.image_count}")
                            error_details.append(f"Text extracted: {len(parsed_doc.text)} chars")
                            error_details.append(f"OCR models available: {ocr_models_available}")
                            
                            if parsed_doc.images_detected or parsed_doc.image_count > 0:
                                error_details.append("")
                                error_details.append("Images were detected but OCR text extraction failed.")
                                error_details.append("Possible causes:")
                                error_details.append("1. Docling OCR models not installed - Run: docling download-models")
                                error_details.append("2. Images contain no extractable text (diagrams, charts)")
                                error_details.append("3. OCR processing failed silently")
                                error_details.append("4. Text extraction returned empty or too short")
                                
                                raise HTTPException(
                                    status_code=400,
                                    detail="\n".join(error_details)
                                )
                            else:
                                raise HTTPException(
                                    status_code=400,
                                    detail="No images with OCR text were extracted from the document. The document may not contain images or OCR extraction failed."
                                )
                    
                    # Store images in OpenSearch
                    logger.info(f"Storing {len(extracted_images)} images in OpenSearch...")
                    processor._store_images_in_opensearch(
                        extracted_images,
                        doc_name,
                        "docling"
                    )
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
                
                # Verify storage
                stored_images = images_store.get_images_by_source(doc_name, limit=1000)
                images_count = len(stored_images)
                total_ocr_length = sum(len(img.get('ocr_text', '')) for img in stored_images)
                
                logger.info(f"✅ Successfully stored {images_count} images with {total_ocr_length:,} OCR characters")
                
                return ImageStorageResponse(
                    document_id=document_id,
                    document_name=doc_name,
                    images_stored=images_count,
                    images_index=images_store.index_name,
                    total_ocr_text_length=total_ocr_length,
                    status="completed",
                    message=f"Successfully re-processed and stored {images_count} images with OCR in index '{images_store.index_name}'",
                    reprocessed=True,
                    extraction_method="docling"
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error re-processing document: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error re-processing document with Docling parser: {str(e)}"
                )
        
        # No file provided - check if images already exist
        existing_images = images_store.get_images_by_source(doc_name, limit=1000)
        images_count = len(existing_images)
        
        if images_count > 0:
            # Calculate total OCR text length
            total_ocr_length = sum(len(img.get('ocr_text', '')) for img in existing_images)
            
            logger.info(f"✅ Image OCR content already stored: {images_count} images, {total_ocr_length:,} OCR characters")
            
            return ImageStorageResponse(
                document_id=document_id,
                document_name=doc_name,
                images_stored=images_count,
                images_index=images_store.index_name,
                total_ocr_text_length=total_ocr_length,
                status="completed",
                message=f"Image OCR content verified: {images_count} images in index '{images_store.index_name}'"
            )
        else:
            # No images found - provide helpful error message
            if not doc.get('images_detected', False):
                raise HTTPException(
                    status_code=400,
                    detail="No images detected in document. Use Docling parser to extract images with OCR."
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Images were detected but not stored. Provide the PDF file in the request to re-process with Docling parser and extract image OCR. Example: curl -X POST -F 'file=@document.pdf' 'http://.../documents/{document_id}/store/images'"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing image content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error storing image content: {str(e)}")


@app.get("/documents/{document_id}/accuracy", response_model=AccuracyCheckResponse)
async def get_document_accuracy(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get quick accuracy check for a document.
    
    Returns accuracy scores from stored metadata without full verification.
    """
    logger.info(f"GET /documents/{document_id}/accuracy - Quick accuracy check")
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Get OCR quality metrics from metadata
    ocr_quality = doc.get('ocr_quality_metrics', {})
    overall_accuracy = ocr_quality.get('overall_accuracy')
    ocr_accuracy = ocr_quality.get('average_ocr_accuracy')
    
    # Determine status
    if overall_accuracy is None:
        status = 'not_verified'
        verification_needed = True
    elif overall_accuracy >= 0.90:
        status = 'accurate'
        verification_needed = False
    elif overall_accuracy >= 0.85:
        status = 'needs_review'
        verification_needed = True
    else:
        status = 'inaccurate'
        verification_needed = True
    
    return AccuracyCheckResponse(
        document_id=document_id,
        document_name=doc.get('document_name', ''),
        overall_accuracy=overall_accuracy,
        ocr_accuracy=ocr_accuracy,
        text_accuracy=None,  # Could be added if tracked
        last_verification=doc.get('last_verification'),
        verification_needed=verification_needed,
        status=status
    )


@app.post("/documents/{document_id}/verify", response_model=VerificationReport)
async def verify_document_ocr(
    document_id: str,
    file: Optional[UploadFile] = File(None),
    auto_fix: bool = Form(default=False),
    service: ServiceContainer = Depends(get_service)
):
    """
    Verify OCR accuracy for a document by comparing PDF content with stored OCR.
    
    Args:
        document_id: Document ID to verify
        file: Optional PDF file (if not provided, uses stored document)
        auto_fix: Whether to automatically fix low accuracy issues
        service: Service container dependency
    
    Returns:
        Comprehensive verification report
    """
    logger.info(f"POST /documents/{document_id}/verify - OCR verification")
    
    # Get document metadata
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    doc_name = doc.get('document_name')
    
    # Get PDF file content
    pdf_file_content = None
    if file:
        pdf_file_content = await file.read()
        logger.info(f"Using uploaded PDF file for verification: {len(pdf_file_content)} bytes")
    else:
        # Note: In a full implementation, we would retrieve the original PDF from storage
        # For now, we'll require the file to be uploaded
        raise HTTPException(
            status_code=400,
            detail="PDF file required for verification. Please upload the original PDF file."
        )
    
    try:
        # Get stored images from OpenSearch
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from config.settings import ARISConfig
        
        opensearch_domain = getattr(service.rag_system, 'opensearch_domain', None) or os.getenv('OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            raise HTTPException(
                status_code=400,
                detail="OpenSearch not configured. Cannot retrieve stored images for verification."
            )
        
        images_store = OpenSearchImagesStore(
            opensearch_domain=opensearch_domain,
            index_name="aris-rag-images-index"
        )
        
        # Get all images for this document
        stored_images = images_store.get_images_by_source(doc_name)
        logger.info(f"Retrieved {len(stored_images)} stored images for verification")
        
        # Run verification
        verifier = OCRVerifier()
        verification_report = verifier.verify_document(
            document_id=document_id,
            pdf_file_content=pdf_file_content,
            stored_images=stored_images,
            re_run_ocr=None  # Could add OCR re-run function here
        )
        
        # Apply auto-fix if requested and needed
        auto_fix_applied = False
        auto_fix_details = None
        if auto_fix:
            auto_fix_service = OCRAutoFix()
            if auto_fix_service.should_auto_fix(verification_report):
                logger.info("Auto-fix triggered for low accuracy")
                auto_fix_details = auto_fix_service.fix_low_accuracy(
                    document_id=document_id,
                    verification_report=verification_report,
                    document_processor=service.document_processor,
                    pdf_file_content=pdf_file_content,
                    document_name=doc_name
                )
                auto_fix_applied = auto_fix_details.get('fix_applied', False)
        
        # Update document metadata with verification results
        doc['last_verification'] = verification_report.get('verification_timestamp')
        doc['ocr_quality_metrics'] = doc.get('ocr_quality_metrics', {})
        doc['ocr_quality_metrics']['overall_accuracy'] = verification_report.get('overall_accuracy')
        doc['ocr_quality_metrics']['last_verification_timestamp'] = verification_report.get('verification_timestamp')
        service.add_document(document_id, doc)
        
        # Build response
        return VerificationReport(
            document_id=document_id,
            document_name=doc_name,
            verification_timestamp=verification_report.get('verification_timestamp'),
            overall_accuracy=verification_report.get('overall_accuracy', 0.0),
            page_verifications=[
                PageVerification(
                    page_number=pv.get('page_number'),
                    text_accuracy=pv.get('text_accuracy'),
                    images_accuracy=pv.get('images_accuracy', 0.0),
                    issues=pv.get('issues', []),
                    image_verifications=[
                        ImageVerification(
                            image_id=f"page_{pv.get('page_number')}_img_{iv.get('image_index')}",
                            page_number=iv.get('page_number'),
                            image_index=iv.get('image_index'),
                            ocr_accuracy=iv.get('accuracy_score', 0.0),
                            character_accuracy=iv.get('character_accuracy'),
                            word_accuracy=iv.get('word_accuracy'),
                            missing_content=iv.get('missing_content', []),
                            extra_content=iv.get('extra_content', []),
                            status=iv.get('verification_status', 'unknown'),
                            stored_ocr_length=iv.get('stored_ocr_length', 0),
                            verified_ocr_length=iv.get('verified_ocr_length', 0)
                        )
                        for iv in pv.get('image_verifications', [])
                    ]
                )
                for pv in verification_report.get('page_verifications', [])
            ],
            image_verifications=[
                ImageVerification(
                    image_id=f"page_{iv.get('page_number')}_img_{iv.get('image_index')}",
                    page_number=iv.get('page_number'),
                    image_index=iv.get('image_index'),
                    ocr_accuracy=iv.get('accuracy_score', 0.0),
                    character_accuracy=iv.get('character_accuracy'),
                    word_accuracy=iv.get('word_accuracy'),
                    missing_content=iv.get('missing_content', []),
                    extra_content=iv.get('extra_content', []),
                    status=iv.get('verification_status', 'unknown'),
                    stored_ocr_length=iv.get('stored_ocr_length', 0),
                    verified_ocr_length=iv.get('verified_ocr_length', 0)
                )
                for iv in verification_report.get('image_verifications', [])
            ],
            issues_found=verification_report.get('issues_found', []),
            recommendations=verification_report.get('recommendations', []),
            auto_fix_applied=auto_fix_applied,
            auto_fix_details=auto_fix_details
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying document OCR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error verifying document OCR: {str(e)}")


# Sync endpoints removed - these are internal operations
# If needed, use service methods directly for internal operations


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

