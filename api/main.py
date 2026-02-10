"""
Unified FastAPI application for ARIS RAG System
All UI options available via REST API + S3 document storage
"""
import os
import uuid
import logging
import hashlib
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Depends, Form, Request, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from scripts.setup_logging import setup_logging

logger = setup_logging(
    name="aris_rag.fastapi",
    level=logging.INFO,
    log_file="logs/fastapi.log"
)

from shared.schemas import (
    QueryRequest, QueryResponse, DocumentMetadata, DocumentListResponse,
    Citation, ImageQueryRequest, ImageQueryResponse, ImageResult,
    ModelSettings, ParserSettings, ChunkingSettings, VectorStoreSettings,
    RetrievalSettings, AgenticRAGSettings, SystemSettings, MetricsInfo
)
from shared.utils.pdf_metadata_extractor import extract_pdf_metadata
from api.service import ServiceContainer, create_service_container
from shared.config.settings import ARISConfig
from storage.s3_storage import S3DocumentStorage, get_s3_storage


load_dotenv()

service_container: Optional[ServiceContainer] = None
s3_storage: Optional[S3DocumentStorage] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global service_container, s3_storage
    
    logger.info("=" * 60)
    logger.info("[STARTUP STEP 1] Initializing ARIS RAG System")
    logger.info("=" * 60)
    
    service_container = create_service_container()
    
    # Initialize S3 storage
    try:
        s3_storage = get_s3_storage()
        logger.info(f"✅ [STARTUP STEP 2] S3 Storage initialized: {s3_storage.bucket_name}")
    except Exception as e:
        logger.warning(f"⚠️ S3 Storage not available: {e}")
        s3_storage = None
    
    logger.info("=" * 60)
    logger.info("✅ [STARTUP STEP 3] FastAPI Application Ready")
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
    title="ARIS RAG API - Unified",
    description="Complete API with all UI options + S3 document storage",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """Root endpoint with API overview"""
    return {
        "name": "ARIS RAG API - Unified",
        "version": "3.0.0",
        "description": "Complete API with all UI options + S3 document storage",
        "endpoints": {
            "core": ["/", "/health", "/documents", "/query"],
            "documents_s3": ["/documents/upload-s3", "/documents/{id}/download"],
            "settings": ["/settings", "/settings?section=models"],
            "library": ["/library", "/library/load"],
            "metrics": ["/metrics", "/metrics/dashboard"]
        },
        "docs": "/docs",
        "status": "operational",
        "s3_enabled": s3_storage is not None
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


# ============================================================================
# S3 DOCUMENT STORAGE ENDPOINTS
# ============================================================================

@app.post("/documents/upload-s3", response_model=DocumentMetadata, status_code=201, tags=["Documents + S3"])
async def upload_document_with_s3(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    parser_preference: Optional[str] = Form(default=None, description="Parser: docling, pymupdf, ocrmypdf, textract, llamascan"),
    store_in_s3: bool = Form(default=True, description="Store original document in S3"),
    chunk_size: Optional[int] = Form(default=None, description="Custom chunk size (tokens)"),
    chunk_overlap: Optional[int] = Form(default=None, description="Custom chunk overlap (tokens)"),
    # LlamaScan specific settings
    llama_model: Optional[str] = Form(default=None, description="LlamaScan: Ollama model name (e.g. qwen2.5vl:latest)"),
    ollama_url: Optional[str] = Form(default=None, description="LlamaScan: Ollama server URL"),
    llama_include_diagrams: bool = Form(default=True, description="LlamaScan: Include diagram descriptions"),
    llama_start_page: int = Form(default=0, description="LlamaScan: Start page (0=first)"),
    llama_end_page: int = Form(default=0, description="LlamaScan: End page (0=last)"),
    llama_resize_width: int = Form(default=0, description="LlamaScan: Resize width (0=no resize)"),
    llama_custom_instructions: Optional[str] = Form(default=None, description="LlamaScan: Custom instructions"),
    service: ServiceContainer = Depends(get_service)
):
    """
    Upload and process a document with S3 storage.
    
    **Features:**
    - Stores original document in S3 for retrieval
    - Processes document with selected parser
    - Stores text chunks in OpenSearch/FAISS
    
    **Parameters:**
    - `file` - Document file (PDF, TXT, DOCX, DOC)
    - `parser_preference` - Parser to use: docling, pymupdf, ocrmypdf, textract, llamascan
    - `store_in_s3` - Whether to store original in S3 (default: true)
    - `chunk_size` - Custom chunk size in tokens
    - `chunk_overlap` - Custom chunk overlap in tokens
    """
    logger.info(f"POST /documents/upload-s3 - File: {file.filename}, S3: {store_in_s3}")
    
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
        content = await file.read()
        
        # Calculate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Configure LlamaScan environment variables if settings provided
        if parser_preference and parser_preference.lower() == 'llamascan':
            if llama_model: os.environ["LLAMA_SCAN_MODEL"] = str(llama_model).strip()
            if ollama_url: os.environ["OLLAMA_SERVER_URL"] = str(ollama_url).strip()
            os.environ["LLAMA_SCAN_INCLUDE_DIAGRAMS"] = "true" if llama_include_diagrams else "false"
            if llama_start_page: os.environ["LLAMA_SCAN_START_PAGE"] = str(int(llama_start_page))
            if llama_end_page: os.environ["LLAMA_SCAN_END_PAGE"] = str(int(llama_end_page))
            if llama_resize_width: os.environ["LLAMA_SCAN_WIDTH"] = str(int(llama_resize_width))
            if llama_custom_instructions: os.environ["LLAMA_SCAN_CUSTOM_INSTRUCTIONS"] = str(llama_custom_instructions).strip()
            
            logger.info(f"configured LlamaScan: model={os.getenv('LLAMA_SCAN_MODEL')}, url={os.getenv('OLLAMA_SERVER_URL')}")

        # Upload to S3 if enabled
        s3_info = None
        if store_in_s3 and s3_storage:
            s3_result = s3_storage.upload_document(
                file_content=content,
                document_id=document_id,
                filename=file.filename,
                content_type=file.content_type or "application/pdf",
                metadata={'parser': parser_preference or 'auto'}
            )
            if s3_result.get('success'):
                s3_info = {
                    's3_key': s3_result['s3_key'],
                    's3_url': s3_result['s3_url'],
                    'bucket': s3_result['bucket']
                }
                logger.info(f"✅ Document uploaded to S3: {s3_result['s3_key']}")
            else:
                logger.warning(f"⚠️ S3 upload failed: {s3_result.get('error')}")
        
        # Save file locally for processing
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Extract PDF metadata
        pdf_metadata = None
        if file_ext == '.pdf':
            try:
                pdf_metadata = extract_pdf_metadata(file_path)
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {e}")
        
        # Create document metadata
        doc_metadata = {
            'document_id': document_id,
            'document_name': file.filename,
            'status': 'processing',
            'chunks_created': 0,
            'file_hash': file_hash,
            'pdf_metadata': pdf_metadata,
            's3_storage': s3_info,
            'parser_preference': parser_preference
        }
        
        # Save to registry
        service.document_registry.save_document(document_id, doc_metadata)
        
        # Process document
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
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@app.get("/documents/{document_id}/download", tags=["Documents + S3"])
async def download_document_from_s3(
    document_id: str,
    service: ServiceContainer = Depends(get_service)
):
    """
    Download original document from S3.
    
    Returns the original file that was uploaded.
    """
    logger.info(f"GET /documents/{document_id}/download")
    
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    if not s3_storage:
        raise HTTPException(status_code=503, detail="S3 storage not configured")
    
    s3_info = doc.get('s3_storage')
    if not s3_info:
        raise HTTPException(status_code=404, detail="Document not stored in S3")
    
    filename = doc.get('document_name', 'document.pdf')
    content = s3_storage.download_document(document_id, filename)
    
    if content is None:
        raise HTTPException(status_code=404, detail="Document not found in S3")
    
    # Determine content type
    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword'
    }
    content_type = content_types.get(ext, 'application/octet-stream')
    
    from io import BytesIO
    return StreamingResponse(
        BytesIO(content),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# SETTINGS ENDPOINTS - All UI Options
# ============================================================================

@app.get("/settings", tags=["Settings"])
async def get_all_settings(
    section: Optional[str] = Query(None, description="Section: models, parser, chunking, vector_store, retrieval, agentic_rag, s3, or all"),
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Get all system settings (same as UI sidebar options).
    
    **Sections:**
    - `models` - API provider, model names, temperature, max_tokens
    - `parser` - Current parser, available parsers, OCR settings
    - `chunking` - Strategy, chunk_size, chunk_overlap
    - `vector_store` - Type (FAISS/OpenSearch), domain, index
    - `retrieval` - k, MMR, search_mode, weights
    - `agentic_rag` - Agentic RAG settings
    - `s3` - S3 storage configuration
    """
    rag = service.rag_system
    
    # Build complete settings
    settings = {
        "models": {
            "api_provider": "cerebras" if rag.use_cerebras else "openai",
            "openai_model": rag.openai_model,
            "cerebras_model": rag.cerebras_model,
            "embedding_model": rag.embedding_model,
            "temperature": getattr(rag, 'temperature', ARISConfig.DEFAULT_TEMPERATURE),
            "max_tokens": getattr(rag, 'max_tokens', ARISConfig.DEFAULT_MAX_TOKENS),
            "available_openai_models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview", "gpt-4o", "gpt-4o-mini"],
            "available_cerebras_models": ["llama3.1-8b", "llama-3.3-70b", "qwen-3-32b"],
            "available_embedding_models": ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
        },
        "parser": {
            "current_parser": getattr(rag, 'parser_preference', 'auto'),
            "available_parsers": ["docling", "pymupdf", "ocrmypdf", "textract", "llamascan"],
            "ocr_languages": os.getenv("OCR_LANGUAGES", "eng"),
            "ocr_dpi": int(os.getenv("OCR_DPI", "300")),
            "llamascan": {
                "model": os.getenv("LLAMA_SCAN_MODEL", "qwen2.5vl:latest"),
                "ollama_url": os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434"),
                "include_diagrams": os.getenv("LLAMA_SCAN_INCLUDE_DIAGRAMS", "true").lower() == "true",
                "start_page": int(os.getenv("LLAMA_SCAN_START_PAGE", "0")),
                "end_page": int(os.getenv("LLAMA_SCAN_END_PAGE", "0")),
                "resize_width": int(os.getenv("LLAMA_SCAN_WIDTH", "0"))
            }
        },
        "chunking": {
            "strategy": ARISConfig.CHUNKING_STRATEGY,
            "chunk_size": rag.chunk_size,
            "chunk_overlap": rag.chunk_overlap,
            "available_strategies": ["precise", "balanced", "comprehensive", "custom"]
        },
        "vector_store": {
            "type": rag.vector_store_type,
            "opensearch_domain": getattr(rag, 'opensearch_domain', None),
            "opensearch_index": getattr(rag, 'opensearch_index', None),
            "region": os.getenv("AWS_OPENSEARCH_REGION", "us-east-2")
        },
        "retrieval": {
            "default_k": ARISConfig.DEFAULT_RETRIEVAL_K,
            "use_mmr": ARISConfig.DEFAULT_USE_MMR,
            "mmr_fetch_k": ARISConfig.DEFAULT_MMR_FETCH_K,
            "mmr_lambda": ARISConfig.DEFAULT_MMR_LAMBDA,
            "search_mode": "hybrid",
            "semantic_weight": ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
            "keyword_weight": 1.0 - ARISConfig.DEFAULT_SEMANTIC_WEIGHT
        },
        "agentic_rag": {
            "enabled": ARISConfig.DEFAULT_USE_AGENTIC_RAG,
            "max_sub_queries": ARISConfig.DEFAULT_MAX_SUB_QUERIES,
            "chunks_per_subquery": ARISConfig.DEFAULT_CHUNKS_PER_SUBQUERY,
            "max_total_chunks": ARISConfig.DEFAULT_MAX_TOTAL_CHUNKS,
            "deduplication_threshold": ARISConfig.DEFAULT_DEDUPLICATION_THRESHOLD
        },
        "s3": s3_storage.get_storage_info() if s3_storage else {"enabled": False}
    }
    
    if section and section != "all":
        if section in settings:
            return {section: settings[section]}
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")
    
    return settings


@app.put("/settings", tags=["Settings"])
async def update_settings(
    updates: Dict[str, Any] = Body(...),
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Update system settings (same as changing UI dropdowns/inputs).
    
    **Example:**
    ```json
    {
      "models": {"api_provider": "cerebras", "temperature": 0.5},
      "chunking": {"strategy": "balanced"},
      "retrieval": {"k": 10, "search_mode": "hybrid"}
    }
    ```
    """
    rag = service.rag_system
    updated = []
    
    if "models" in updates:
        model_updates = updates["models"]
        if "api_provider" in model_updates:
            rag.use_cerebras = model_updates["api_provider"].lower() == "cerebras"
            updated.append("api_provider")
        if "openai_model" in model_updates:
            rag.openai_model = model_updates["openai_model"]
            updated.append("openai_model")
        if "cerebras_model" in model_updates:
            rag.cerebras_model = model_updates["cerebras_model"]
            updated.append("cerebras_model")
        if "temperature" in model_updates:
            rag.temperature = model_updates["temperature"]
            updated.append("temperature")
        if "max_tokens" in model_updates:
            rag.max_tokens = model_updates["max_tokens"]
            updated.append("max_tokens")
    
    if "chunking" in updates:
        chunk_updates = updates["chunking"]
        if "chunk_size" in chunk_updates:
            rag.chunk_size = chunk_updates["chunk_size"]
            updated.append("chunk_size")
        if "chunk_overlap" in chunk_updates:
            rag.chunk_overlap = chunk_updates["chunk_overlap"]
            updated.append("chunk_overlap")
    
    if "retrieval" in updates:
        ret_updates = updates["retrieval"]
        if "search_mode" in ret_updates:
            rag.search_mode = ret_updates["search_mode"]
            updated.append("search_mode")
    
    return {"updated": updated, "message": f"Updated {len(updated)} settings"}


# ============================================================================
# DOCUMENT LIBRARY ENDPOINTS
# ============================================================================

@app.get("/library", tags=["Library"])
async def get_document_library(
    filter_status: Optional[str] = Query(None, description="Filter by status: success, failed, processing"),
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Get document library (same as '📚 Document Library' in UI).
    
    Returns all stored documents with metadata and storage status.
    """
    docs = service.list_documents()
    
    if filter_status:
        docs = [d for d in docs if d.get('status') == filter_status]
    
    return {
        "total_documents": len(docs),
        "documents": docs,
        "storage_persists": True,
        "s3_enabled": s3_storage is not None
    }


@app.post("/library/load", tags=["Library"])
async def load_document_for_qa(
    document_name: str = Body(..., embed=True, description="Document name to load for Q&A"),
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Load a specific document for Q&A (same as 'Load Selected Document' in UI).
    
    This sets the document as active for subsequent queries.
    """
    rag = service.rag_system
    
    # Set active source
    rag.active_sources = [document_name]
    
    # Try to load the document
    try:
        result = rag.load_selected_documents(
            document_names=[document_name],
            path=ARISConfig.VECTORSTORE_PATH
        )
        
        if result.get("loaded"):
            return {
                "loaded": True,
                "document_name": document_name,
                "chunks_loaded": result.get("chunks_loaded", 0),
                "message": result.get("message", "Document loaded for Q&A")
            }
        else:
            return {
                "loaded": False,
                "document_name": document_name,
                "message": result.get("message", "Could not load document")
            }
    except Exception as e:
        logger.error(f"Error loading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# METRICS ENDPOINTS
# ============================================================================

@app.get("/metrics", tags=["Metrics"])
async def get_metrics(
    metric_type: Optional[str] = Query(None, description="Type: processing, queries, parsers, storage, all"),
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Get R&D metrics and analytics (same as '📊 R&D Metrics & Analytics' in UI).
    
    **Metric Types:**
    - `processing` - Document processing stats
    - `queries` - Query performance stats
    - `parsers` - Parser comparison
    - `storage` - Storage statistics
    - `all` (default) - All metrics
    """
    metrics = service.metrics_collector.get_all_metrics() if hasattr(service, 'metrics_collector') else {}
    
    result = {
        "processing": metrics.get("processing", {}),
        "queries": metrics.get("queries", {}),
        "parsers": metrics.get("parser_comparison", {}),
        "storage": {
            "vector_store_type": service.rag_system.vector_store_type,
            "documents_count": len(service.list_documents()),
            "s3_enabled": s3_storage is not None
        }
    }
    
    if metric_type and metric_type != "all":
        if metric_type in result:
            return {metric_type: result[metric_type]}
        raise HTTPException(status_code=400, detail=f"Invalid metric type: {metric_type}")
    
    return result


@app.get("/metrics/dashboard", tags=["Metrics"])
async def get_dashboard(
    service: ServiceContainer = Depends(get_service)
) -> Dict[str, Any]:
    """
    Get complete dashboard data (settings + library + metrics).
    
    This is equivalent to loading the entire Streamlit UI.
    """
    rag = service.rag_system
    docs = service.list_documents()
    metrics = service.metrics_collector.get_all_metrics() if hasattr(service, 'metrics_collector') else {}
    
    return {
        "system": {
            "api_provider": "cerebras" if rag.use_cerebras else "openai",
            "model": rag.cerebras_model if rag.use_cerebras else rag.openai_model,
            "embedding_model": rag.embedding_model,
            "vector_store": rag.vector_store_type,
            "chunk_size": rag.chunk_size,
            "chunk_overlap": rag.chunk_overlap
        },
        "library": {
            "total_documents": len(docs),
            "total_chunks": sum(d.get('chunks_created', 0) for d in docs),
            "total_images": sum(d.get('image_count', 0) for d in docs),
            "s3_enabled": s3_storage is not None
        },
        "metrics": {
            "documents_processed": metrics.get("processing", {}).get("total_documents", 0),
            "total_queries": metrics.get("queries", {}).get("total_queries", 0),
            "avg_response_time": metrics.get("queries", {}).get("avg_response_time", 0)
        },
        "active_sources": rag.active_sources if hasattr(rag, 'active_sources') else None
    }
