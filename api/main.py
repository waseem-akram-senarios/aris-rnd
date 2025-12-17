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
    StatsResponse, ErrorResponse, Citation, ImageQueryRequest, ImageQueryResponse,
    ImageResult, DocumentUpdateRequest
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
            "image_count": getattr(result, 'image_count', 0),  # Include image_count in response
            "pages": pages,
            "error": result.error
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


@app.put("/documents/{document_id}", response_model=DocumentMetadata)
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    service: ServiceContainer = Depends(get_service)
):
    """
    Update document metadata.
    
    Args:
        document_id: Document ID
        request: Update request with optional fields
    
    Returns:
        Updated document metadata
    """
    logger.info(f"[STEP 1] PUT /documents/{document_id} - Updating document")
    
    # Get existing document
    doc = service.get_document(document_id)
    if doc is None:
        logger.warning(f"⚠️ [STEP 1] Document not found: {document_id}")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Update fields if provided
    updates = {}
    if request.document_name is not None:
        updates['document_name'] = request.document_name
        logger.info(f"[STEP 2] Updating document_name: {request.document_name}")
    if request.status is not None:
        updates['status'] = request.status
        logger.info(f"[STEP 2] Updating status: {request.status}")
    if request.error is not None:
        updates['error'] = request.error
        logger.info(f"[STEP 2] Updating error: {request.error}")
    
    if not updates:
        logger.warning(f"⚠️ [STEP 2] No updates provided for document: {document_id}")
        raise HTTPException(status_code=400, detail="No update fields provided")
    
    # Merge updates with existing document
    updated_doc = {**doc, **updates}
    
    # Update in registry
    try:
        logger.info(f"[STEP 3] Saving updated document to registry")
        service.add_document(document_id, updated_doc)
        logger.info(f"✅ [STEP 4] Document updated: {document_id}")
        return DocumentMetadata(**updated_doc)
    except Exception as e:
        logger.error(f"❌ [STEP 3] Error updating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")


@app.get("/documents/{document_id}/images")
async def get_document_images(
    document_id: str,
    limit: int = 100,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get all images for a specific document.
    
    Args:
        document_id: Document ID
        limit: Maximum number of images to return (default: 100)
    
    Returns:
        List of images for the document
    """
    logger.info(f"[STEP 1] GET /documents/{document_id}/images - Retrieving document images")
    
    # Get document metadata to find document name
    doc = service.get_document(document_id)
    if doc is None:
        logger.warning(f"⚠️ [STEP 1] Document not found: {document_id}")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    document_name = doc.get('document_name', '')
    if not document_name:
        logger.warning(f"⚠️ [STEP 1] Document name not found for: {document_id}")
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        logger.warning("⚠️ [STEP 1] Image retrieval attempted but OpenSearch not configured")
        raise HTTPException(
            status_code=400,
            detail="Image retrieval requires OpenSearch vector store. Current vector store type: " + 
                   getattr(service.rag_system, 'vector_store_type', 'unknown')
        )
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        logger.info(f"[STEP 2] Initializing OpenSearchImagesStore for document: {document_name}")
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=service.rag_system.opensearch_domain,
            region=getattr(service.rag_system, 'region', None)
        )
        
        logger.info(f"[STEP 3] Retrieving images for source: {document_name}")
        images = images_store.get_images_by_source(document_name, limit=limit)
        
        # Convert to ImageResult models
        image_results = []
        for img in images:
            image_results.append(ImageResult(
                image_id=img.get('image_id', ''),
                source=img.get('source', ''),
                image_number=img.get('image_number', 0),
                page=img.get('page'),
                ocr_text=img.get('ocr_text', ''),
                metadata=img.get('metadata', {}),
                score=None
            ))
        
        logger.info(f"✅ [STEP 4] Retrieved {len(image_results)} images for document: {document_id}")
        return {
            "document_id": document_id,
            "document_name": document_name,
            "images": image_results,
            "total": len(image_results)
        }
    except ImportError as e:
        logger.error(f"❌ [STEP 2] OpenSearch images store not available: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenSearch images store not available: {str(e)}")
    except Exception as e:
        logger.error(f"❌ [STEP 2] Error retrieving document images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving document images: {str(e)}")


@app.get("/images/{image_id}")
async def get_image(
    image_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Get a single image by ID.
    
    Args:
        image_id: Image ID
    
    Returns:
        Image details
    """
    logger.info(f"[STEP 1] GET /images/{image_id} - Retrieving image")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        logger.warning("⚠️ [STEP 1] Image retrieval attempted but OpenSearch not configured")
        raise HTTPException(
            status_code=400,
            detail="Image retrieval requires OpenSearch vector store. Current vector store type: " + 
                   getattr(service.rag_system, 'vector_store_type', 'unknown')
        )
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        logger.info(f"[STEP 2] Initializing OpenSearchImagesStore")
        # Initialize images store
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=service.rag_system.embedding_model
        )
        
        images_store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=service.rag_system.opensearch_domain,
            region=getattr(service.rag_system, 'region', None)
        )
        
        logger.info(f"[STEP 3] Retrieving image: {image_id}")
        image = images_store.get_image_by_id(image_id)
        
        if image is None:
            logger.warning(f"⚠️ [STEP 3] Image not found: {image_id}")
            raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
        
        # Convert to ImageResult model
        image_result = ImageResult(
            image_id=image.get('image_id', image_id),
            source=image.get('source', ''),
            image_number=image.get('image_number', 0),
            page=image.get('page'),
            ocr_text=image.get('ocr_text', ''),
            metadata=image.get('metadata', {}),
            score=None
        )
        
        logger.info(f"✅ [STEP 4] Image retrieved: {image_id}")
        return image_result
    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"❌ [STEP 2] OpenSearch images store not available: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OpenSearch images store not available: {str(e)}")
    except Exception as e:
        logger.error(f"❌ [STEP 2] Error retrieving image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving image: {str(e)}")


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
    if not document_name:
        logger.warning(f"⚠️ [STEP 1] Document name not found for: {document_id}")
        raise HTTPException(status_code=400, detail=f"Document {document_id} has no document name")
    
    vector_store_type = service.rag_system.vector_store_type.lower()
    
    try:
        # Step 2: Delete from vectorstore
        logger.info(f"[STEP 2] Deleting document from vectorstore: {vector_store_type}")
        
        if vector_store_type == 'opensearch':
            # Delete OpenSearch index for this document
            if hasattr(service.rag_system, 'document_index_map'):
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
                            
                            # Remove from document_index_map
                            if document_name in service.rag_system.document_index_map:
                                del service.rag_system.document_index_map[document_name]
                                service.rag_system._save_document_index_map()
                                logger.info(f"✅ [STEP 2.2] Removed from document_index_map")
                        else:
                            logger.warning(f"⚠️ [STEP 2.1] Index {index_name} does not exist")
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 2] Error deleting OpenSearch index: {e}", exc_info=True)
                        # Continue with deletion even if index deletion fails
                else:
                    logger.warning(f"⚠️ [STEP 2] No index found for document: {document_name}")
            else:
                logger.warning(f"⚠️ [STEP 2] document_index_map not found in RAG system")
        
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
                
                # Initialize images store
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
    """Query the RAG system"""
    query_preview = request.question[:50] + "..." if len(request.question) > 50 else request.question
    logger.info(f"[STEP 1] POST /query - Query validation: '{query_preview}' (k={request.k}, mmr={request.use_mmr}, document_id={request.document_id})")
    """
    Query the RAG system with a question.
    
    Args:
        request: Query request with question and parameters
            - document_id (optional): If provided, queries only the specified document.
                                     If not provided, queries all documents in the RAG system.
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
    
    # Handle document_id filtering if provided (optional feature)
    # If document_id is provided, filter to that document only
    # If document_id is NOT provided, query all documents (normal RAG behavior)
    original_active_sources = None
    document_name = None
    if request.document_id:
        logger.info(f"[STEP 1.5] Document ID provided: {request.document_id} - filtering to specific document")
        doc = service.get_document(request.document_id)
        if doc is None:
            logger.warning(f"⚠️ [STEP 1.5] Document ID not found: {request.document_id}")
            raise HTTPException(status_code=404, detail=f"Document {request.document_id} not found")
        
        document_name = doc.get('document_name')
        if not document_name:
            logger.warning(f"⚠️ [STEP 1.5] Document has no document_name: {request.document_id}")
            raise HTTPException(status_code=400, detail=f"Document {request.document_id} has no document name")
        
        # Save original active_sources and set filter
        original_active_sources = service.rag_system.active_sources
        service.rag_system.active_sources = [document_name]
        logger.info(f"✅ [STEP 1.5] Filtering query to document: {document_name}")
    else:
        logger.info(f"[STEP 1.5] No document_id provided - querying all documents in RAG system")
    
    try:
        logger.info(f"[STEP 2] Executing vector store retrieval: k={request.k}, mmr={request.use_mmr}, hybrid={request.use_hybrid_search}, agentic={request.use_agentic_rag}, temperature={request.temperature}, max_tokens={request.max_tokens}, document_id={request.document_id}")
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [STEP 2] Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    finally:
        # Restore original active_sources if we modified it
        if request.document_id and original_active_sources is not None:
            service.rag_system.active_sources = original_active_sources
            logger.info(f"[STEP 5] Restored original active_sources filter")


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


@app.get("/stats/chunks")
async def get_chunk_stats(service: ServiceContainer = Depends(get_service)):
    """
    Get chunk token statistics.
    
    Returns:
        Chunk token statistics from RAG system
    """
    logger.info("[STEP 1] GET /stats/chunks - Retrieving chunk statistics")
    try:
        logger.info("[STEP 2] Collecting chunk token stats...")
        chunk_stats = service.rag_system.get_chunk_token_stats()
        logger.info(f"✅ [STEP 3] Chunk stats retrieved successfully")
        return chunk_stats
    except Exception as e:
        logger.error(f"❌ Error retrieving chunk stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving chunk stats: {str(e)}")


@app.post("/query/images", response_model=ImageQueryResponse)
async def query_images(
    request: ImageQueryRequest,
    service: ServiceContainer = Depends(get_service)
):
    """
    Query images in the RAG system.
    
    Args:
        request: Image query request with question and optional source filter
        service: Service container dependency
    
    Returns:
        Image query response with matching images
    """
    query_preview = request.question[:50] + "..." if len(request.question) > 50 else request.question
    logger.info(f"[STEP 1] POST /query/images - Image query: '{query_preview}' (source={request.source}, k={request.k})")
    
    # Check if OpenSearch is configured
    if (not hasattr(service.rag_system, 'vector_store_type') or 
        service.rag_system.vector_store_type.lower() != 'opensearch'):
        logger.warning("⚠️ [STEP 1] Image query attempted but OpenSearch not configured")
        raise HTTPException(
            status_code=400,
            detail="Image queries require OpenSearch vector store. Current vector store type: " + 
                   getattr(service.rag_system, 'vector_store_type', 'unknown')
        )
    
    try:
        logger.info(f"[STEP 2] Executing image search...")
        results = service.rag_system.query_images(
            question=request.question,
            source=request.source,
            k=request.k
        )
        logger.info(f"✅ [STEP 2] Image search completed: {len(results)} images found")
        
        # Convert results to ImageResult models
        image_results = []
        for img in results:
            image_results.append(ImageResult(
                image_id=img.get('image_id', ''),
                source=img.get('source', ''),
                image_number=img.get('image_number', 0),
                page=img.get('page'),
                ocr_text=img.get('ocr_text', ''),
                metadata=img.get('metadata', {}),
                score=img.get('score')
            ))
        
        logger.info(f"✅ [STEP 3] Image query completed successfully: {len(image_results)} images")
        return ImageQueryResponse(
            images=image_results,
            total=len(image_results)
        )
    except Exception as e:
        logger.error(f"❌ [STEP 2] Error processing image query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing image query: {str(e)}")


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

