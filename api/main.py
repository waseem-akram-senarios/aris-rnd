"""
Minimal FastAPI application for ARIS RAG System
10 endpoints total - clean and focused
"""
import os
import uuid
import logging
import hashlib
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Depends, Form, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from scripts.setup_logging import setup_logging

logger = setup_logging(
    name="aris_rag.fastapi",
    level=logging.INFO,
    log_file="logs/fastapi.log"
)

from api.schemas import (
    QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse,
    Citation, ImageQueryRequest, ImageQueryResponse, ImageResult
)
from utils.pdf_metadata_extractor import extract_pdf_metadata
from api.service import ServiceContainer, create_service_container
from config.settings import ARISConfig

# Import focused endpoints router
from api.focused_endpoints import router as focused_router

load_dotenv()

service_container: Optional[ServiceContainer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global service_container
    
    logger.info("=" * 60)
    logger.info("[STARTUP STEP 1] Initializing ARIS RAG System")
    logger.info("=" * 60)
    
    service_container = create_service_container()
    
    logger.info("=" * 60)
    logger.info("✅ [STARTUP STEP 2] FastAPI Application Ready")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("[SHUTDOWN] FastAPI Application Shutting Down")
    logger.info("=" * 60)
    
    if service_container and service_container.rag_system.vector_store_type.lower() == 'faiss':
        vectorstore_path = ARISConfig.get_vectorstore_path()
        try:
            logger.info(f"Saving vectorstore to: {vectorstore_path}")
            service_container.rag_system.save_vectorstore(vectorstore_path)
            logger.info("✅ Vectorstore saved successfully")
        except Exception as e:
            logger.error(f"❌ Could not save vectorstore: {e}", exc_info=True)
    
    logger.info("✅ FastAPI Application Shutdown Complete")


app = FastAPI(
    title="ARIS RAG API - Minimal",
    description="Minimal API with 10 endpoints - Clean and focused",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include focused API router
app.include_router(focused_router, tags=["Settings & Info"])


def get_service() -> ServiceContainer:
    """Dependency to get service container"""
    if service_container is None:
        raise HTTPException(status_code=500, detail="Service container not initialized")
    return service_container


# ============================================================================
# CORE ENDPOINTS (5)
# ============================================================================

@app.get("/", tags=["Core"])
async def root():
    """Root endpoint"""
    return {
        "name": "ARIS RAG API - Minimal",
        "version": "2.0.0",
        "endpoints": 10,
        "docs": "/docs",
        "status": "operational"
    }


@app.get("/health", tags=["Core"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/documents", response_model=DocumentListResponse, tags=["Core"])
async def list_documents(service: ServiceContainer = Depends(get_service)):
    """List all processed documents"""
    logger.info("GET /documents - Listing documents")
    
    try:
        docs = service.list_documents()
        
        total_chunks = sum(doc.get('chunks_created', 0) for doc in docs)
        total_images = sum(doc.get('image_count', 0) for doc in docs)
        
        return DocumentListResponse(
            documents=[DocumentMetadata(**doc) for doc in docs],
            total=len(docs),
            total_chunks=total_chunks,
            total_images=total_images
        )
    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.post("/documents", response_model=DocumentMetadata, status_code=201, tags=["Core"])
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    parser_preference: Optional[str] = Form(default=None),
    service: ServiceContainer = Depends(get_service)
):
    """
    Upload and process a document (PDF, TXT, DOCX, DOC)
    
    Supports multipart form upload with optional parser selection.
    """
    logger.info(f"POST /documents - Uploading: {file.filename}")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.txt', '.docx', '.doc'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Save uploaded file
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicates
        existing_docs = service.list_documents()
        for doc in existing_docs:
            if doc.get('file_hash') == file_hash:
                logger.warning(f"Duplicate file detected: {file.filename}")
                os.remove(file_path)
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate file. Already exists as: {doc.get('document_name')}"
                )
        
        # Extract PDF metadata if applicable
        pdf_metadata = None
        if file_ext == '.pdf':
            try:
                pdf_metadata = extract_pdf_metadata(file_path)
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {e}")
        
        # Create initial document metadata
        doc_metadata = {
            'document_id': document_id,
            'document_name': file.filename,
            'status': 'processing',
            'chunks_created': 0,
            'file_hash': file_hash,
            'pdf_metadata': pdf_metadata
        }
        
        # Save to registry
        service.document_registry.save_document(document_id, doc_metadata)
        
        # Process document in background
        if background_tasks:
            background_tasks.add_task(
                service.document_processor.process_document,
                file_path,
                document_id,
                file.filename,
                parser_preference
            )
        
        logger.info(f"✅ Document uploaded: {document_id}")
        return DocumentMetadata(**doc_metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.delete("/documents/{document_id}", status_code=204, tags=["Core"])
async def delete_document(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """Delete a document and all its data"""
    logger.info(f"DELETE /documents/{document_id}")
    
    try:
        doc = service.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        # Delete from vector stores
        vector_store_type = service.rag_system.vector_store_type.lower()
        
        if vector_store_type == 'opensearch':
            # Delete from OpenSearch indexes
            from vectorstores.opensearch_store import OpenSearchVectorStore
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=service.rag_system.embedding_model
            )
            
            # Delete text chunks
            text_index = doc.get('text_index', 'aris-rag-index')
            text_store = OpenSearchVectorStore(
                embeddings=embeddings,
                domain=service.rag_system.opensearch_domain,
                index_name=text_index
            )
            
            doc_name = doc.get('document_name')
            text_store.delete_by_source(doc_name)
            
            # Delete images
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=service.rag_system.opensearch_domain
            )
            images_store.delete_by_source(doc_name)
        
        # Remove from registry
        service.document_registry.remove_document(document_id)
        
        logger.info(f"✅ Document deleted: {document_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


# ============================================================================
# UNIFIED QUERY ENDPOINT (1)
# ============================================================================

@app.post("/query", tags=["Query"])
async def query_unified(
    request: QueryRequest,
    type: str = Query(default="text", description="Query type: text or image"),
    document_id: Optional[str] = Query(default=None, description="Filter to specific document"),
    focus: str = Query(default="all", description="Focus area: all, important, summary, specific"),
    k: Optional[int] = Query(default=None, ge=1, le=50, description="Number of chunks to retrieve (overrides body)"),
    use_mmr: Optional[bool] = Query(default=None, description="Use Maximum Marginal Relevance (overrides body)"),
    search_mode: Optional[str] = Query(default=None, description="Search mode: semantic, keyword, or hybrid (overrides body)"),
    temperature: Optional[float] = Query(default=None, ge=0.0, le=2.0, description="LLM temperature 0.0-2.0 (overrides body)"),
    max_tokens: Optional[int] = Query(default=None, ge=1, le=4000, description="Max tokens for response (overrides body)"),
    use_agentic_rag: Optional[bool] = Query(default=None, description="Use Agentic RAG with query decomposition (overrides body)"),
    semantic_weight: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Semantic search weight 0.0-1.0 (overrides body)"),
    service: ServiceContainer = Depends(get_service),
):
    """
    **Unified Query Endpoint - Enhanced with Importance Focus**
    
    Query documents with text or images using parameters.
    
    **Parameters:**
    - `type=text` (default) - Query text chunks
    - `type=image` - Query images with OCR
    - `document_id=xxx` - Filter to specific document
    - `focus=all|important|summary|specific` - What to focus on
    
    **Focus Options:**
    - `all` (default) - Query all content
    - `important` - Focus on most important/relevant parts (higher k, better ranking)
    - `summary` - Get summary of document key points
    - `specific` - Precise answer from most relevant section
    
    **Examples:**
    - `POST /query` - Query all text
    - `POST /query?focus=important` - Focus on important parts
    - `POST /query?focus=summary` - Get document summary
    - `POST /query?type=image` - Query all images
    - `POST /query?document_id=abc123` - Query specific document
    - `POST /query?document_id=abc123&focus=important` - Important parts of specific doc
    """
    logger.info(f"POST /query?type={type}&document_id={document_id}&focus={focus}")
    
    try:
        # Override request body with query parameters if provided
        if k is not None:
            request.k = k
        if use_mmr is not None:
            request.use_mmr = use_mmr
        if search_mode is not None:
            request.search_mode = search_mode
        if temperature is not None:
            request.temperature = temperature
        if max_tokens is not None:
            request.max_tokens = max_tokens
        if use_agentic_rag is not None:
            request.use_agentic_rag = use_agentic_rag
        if semantic_weight is not None:
            request.semantic_weight = semantic_weight
        if document_id is not None:
            request.document_id = document_id
        
        # Route to appropriate handler
        if type == "image":
            # Image query
            # Use query param k if provided, otherwise use request.k, otherwise default to 5
            # FastAPI passes the actual value, not the Query object
            image_k = 5  # Default from ImageQueryRequest schema
            if k is not None:
                image_k = int(k) if isinstance(k, str) else k
            elif hasattr(request, 'k') and request.k is not None:
                # Ensure request.k is an integer, not a Query object or tuple
                req_k = request.k
                if isinstance(req_k, tuple):
                    # Handle tuple case - take first element if it's not a Query object
                    req_k = req_k[0] if len(req_k) > 0 and not hasattr(req_k[0], 'default') else None
                if req_k is not None:
                    image_k = int(req_k) if isinstance(req_k, str) else req_k
            
            image_request = ImageQueryRequest(
                question=request.question,
                source=document_id,
                k=image_k
            )
            
            vector_store_type = getattr(service.rag_system, 'vector_store_type', None)
            if not vector_store_type or vector_store_type.lower() != 'opensearch':
                return ImageQueryResponse(
                    images=[],
                    total=0,
                    content_type="image_ocr",
                    images_index="aris-rag-images-index",
                    message="Image queries require OpenSearch vector store"
                )
            
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=service.rag_system.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=service.rag_system.opensearch_domain
            )
            
            results = service.rag_system.query_images(
                question=request.question or "all images",
                source=document_id,
                k=request.k
            )
            
            # Build image results - ensure page is always set
            image_results = []
            for img in results:
                page = img.get('page')
                # Ensure page is always set (fallback to 1 if None)
                if page is None:
                    page = 1
                    logger.warning(f"ImageResult: page was None for image {img.get('image_id', 'unknown')}, using fallback page 1")
                
                image_results.append(
                    ImageResult(
                        image_id=img.get('image_id', ''),
                        source=img.get('source', ''),
                        image_number=img.get('image_number', 0),
                        page=page,  # Always guaranteed to be an integer >= 1
                        ocr_text=img.get('ocr_text', ''),
                        metadata=img.get('metadata', {}),
                        score=img.get('score')
                    )
                )
            
            return ImageQueryResponse(
                images=image_results,
                total=len(image_results),
                content_type="image_ocr",
                images_index=images_store.index_name
            )
        
        else:
            # Text query (default)
            if document_id:
                request.document_id = document_id
            
            # Check if documents exist
            has_documents = len(service.list_documents()) > 0
            if not has_documents:
                raise HTTPException(
                    status_code=400,
                    detail="No documents have been processed yet. Please upload documents first."
                )
            
            # Adjust query parameters based on focus
            if focus == "important":
                # Focus on most important parts - retrieve more chunks, use MMR for diversity
                current_k = request.k if isinstance(request.k, int) else 12
                request.k = min(current_k * 2, 25)  # Double retrieval, max 25
                request.search_mode = "hybrid"  # Best of both worlds
            elif focus == "summary":
                # Get broad overview - more chunks, diverse results
                request.k = 20
                request.use_mmr = True
                request.search_mode = "hybrid"
                # Modify question to request summary
                if "summary" not in request.question.lower():
                    request.question = f"Provide a comprehensive summary: {request.question}"
            elif focus == "specific":
                # Precise answer - fewer chunks, semantic search
                current_k = request.k if isinstance(request.k, int) else 12
                request.k = min(current_k, 6)  # Limit to 6 most relevant
                request.search_mode = "semantic"
            
            # Execute query
            result = service.query_text_only(
                question=request.question,
                k=request.k,
                document_id=request.document_id,
                use_mmr=request.use_mmr
            )
            
            # Build citations - ensure page is always set
            citations = []
            for i, src in enumerate(result.get("sources", [])):
                page = src.get("page")
                # Ensure page is always set (fallback to 1 if None)
                if page is None:
                    page = 1
                    logger.warning(f"Citation {i}: page was None in API response, using fallback page 1")
                
                # Ensure source_location always includes page number
                source_location = src.get("source_location", "")
                if not source_location or source_location == "Text content":
                    source_location = f"Page {page}"
                
                citations.append(
                    Citation(
                        id=str(i),
                        source=src.get("source", ""),
                        page=page,  # Always guaranteed to be an integer >= 1
                        snippet=src.get("snippet", ""),
                        full_text=src.get("full_text", ""),
                        source_location=source_location  # Always includes "Page X"
                    )
                )
            
            return QueryResponse(
                answer=result["answer"],
                sources=result.get("source_names", []),
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
