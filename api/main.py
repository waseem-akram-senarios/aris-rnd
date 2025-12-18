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
            total=len(image_results)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing image query: {e}", exc_info=True)
        return ImageQueryResponse(images=[], total=0)


# Sync endpoints removed - these are internal operations
# If needed, use service methods directly for internal operations


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

