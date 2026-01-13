"""
FastAPI Entrypoint for ARIS Ingestion Service
Handles document upload, parsing, and indexing.
"""
import os
import uuid
import logging
import hashlib
import time as time_module
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Form, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from scripts.setup_logging import setup_logging
from shared.config.settings import ARISConfig
from shared.schemas import DocumentMetadata, ProcessingResult
from .engine import IngestionEngine
from .processor import DocumentProcessor

logger = setup_logging(
    name="aris_rag.ingestion",
    level=logging.INFO,
    log_file="logs/ingestion_service.log"
)

load_dotenv()

# Global instances
engine: Optional[IngestionEngine] = None
processor: Optional[DocumentProcessor] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global engine, processor
    
    logger.info("=" * 60)
    logger.info("[STARTUP] Initializing ARIS Ingestion Service")
    logger.info("=" * 60)
    
    # Initialize engine with ingestion-relevant settings
    engine = IngestionEngine(
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
        chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
    )
    
    # Initialize processor
    processor = DocumentProcessor(engine)
    
    logger.info("✅ [STARTUP] Ingestion Service Ready")
    yield
    
    logger.info("[SHUTDOWN] Ingestion Service Shutting Down")

app = FastAPI(
    title="ARIS Ingestion Service",
    description="Microservice for document ingestion, parsing, and indexing",
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
    logger.info(f"Ingestion: [ReqID: {request_id}] Incoming {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

def get_processor() -> DocumentProcessor:
    if processor is None:
        raise HTTPException(status_code=500, detail="Processor not initialized")
    return processor

@app.get("/health")
async def health_check():
    """Health check with registry and index map sync verification"""
    try:
        # Verify document registry and index map are accessible
        from shared.config.settings import ARISConfig
        import os
        import json
        
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        registry_accessible = os.path.exists(registry_path) or os.path.exists(os.path.dirname(registry_path))
        
        # Get document count from registry
        doc_count = 0
        try:
            if os.path.exists(registry_path):
                with open(registry_path, 'r') as f:
                    registry_data = json.load(f)
                    doc_count = len(registry_data) if isinstance(registry_data, dict) else 0
        except Exception:
            pass
        
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        index_map_accessible = os.path.exists(index_map_path) or os.path.exists(ARISConfig.VECTORSTORE_PATH)
        
        # Get index map count
        index_map_count = 0
        try:
            if os.path.exists(index_map_path):
                with open(index_map_path, 'r') as f:
                    index_map = json.load(f)
                    index_map_count = len(index_map) if isinstance(index_map, dict) else 0
        except Exception:
            pass
        
        return {
            "status": "healthy",
            "service": "ingestion",
            "registry_accessible": registry_accessible,
            "registry_document_count": doc_count,
            "index_map_accessible": index_map_accessible,
            "index_map_entries": index_map_count
        }
    except Exception as e:
        return {
            "status": "healthy",
            "service": "ingestion",
            "registry_accessible": False,
            "index_map_accessible": False,
            "error": str(e)
        }

@app.post("/ingest", response_model=DocumentMetadata, status_code=201)
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    parser_preference: Optional[str] = Form(default=None),
    index_name: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default="eng"),
    background_tasks: BackgroundTasks = None,
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    Ingest a document (asynchronous).
    Detects duplicates and updates existing documents instead of creating new ones.
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.info(f"POST /ingest - [ReqID: {request_id}] File: {file.filename}")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.txt', '.docx', '.doc'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Read content first for hash calculation
        content = await file.read()
        
        # Calculate file hash for duplicate detection
        import hashlib
        file_hash = hashlib.md5(content).hexdigest()
        
        # Check for existing document with same name and parser
        from storage.document_registry import DocumentRegistry
        registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
        
        # Determine parser preference for duplicate check
        effective_parser = parser_preference.lower() if parser_preference else 'pymupdf'
        
        # Check if document with same name and parser already exists
        existing_doc = registry.find_document_by_name_and_parser(file.filename, effective_parser)
        is_update = False
        old_document_id = None
        old_index_name = None
        
        if existing_doc:
            # Check if content is actually different (by hash)
            if existing_doc.get('file_hash') == file_hash:
                # Same exact file - no need to re-process
                logger.info(f"POST /ingest - [ReqID: {request_id}] Document '{file.filename}' with parser '{effective_parser}' already exists with identical content. Skipping.")
                return DocumentMetadata(
                    document_id=existing_doc['document_id'],
                    document_name=file.filename,
                    status="already_exists",
                    message=f"Document already exists with ID {existing_doc['document_id']}. Content is identical."
                )
            else:
                # Same name/parser but different content - UPDATE existing
                is_update = True
                old_document_id = existing_doc['document_id']
                old_index_name = existing_doc.get('index_name')
                logger.info(f"POST /ingest - [ReqID: {request_id}] Updating existing document '{file.filename}' (ID: {old_document_id}) with new content")
                
                # Use the existing document ID for the update
                document_id = old_document_id
        else:
            # Check if same filename exists with any parser
            all_versions = registry.find_documents_by_name(file.filename)
            if all_versions:
                logger.info(f"POST /ingest - [ReqID: {request_id}] Document '{file.filename}' exists with other parsers: {[d.get('parser_used') for d in all_versions]}. Creating new version with parser '{effective_parser}'")
            
            # Generate new document ID for new document
            document_id = str(uuid.uuid4())
        
        # Save locally for reference/fallback
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Immediate registry registration for status tracking
        try:
            # Registry already initialized above for duplicate check
            registration_data = {
                'document_id': document_id,
                'document_name': file.filename,
                'status': 'processing',
                'progress': 0.0,
                'file_hash': file_hash,
                'is_update': is_update,
                'created_at': time_module.time() if not is_update else existing_doc.get('created_at', time_module.time())
            }
            
            if is_update:
                registration_data['previous_version'] = {
                    'chunks_created': existing_doc.get('chunks_created'),
                    'parser_used': existing_doc.get('parser_used'),
                    'updated_at': existing_doc.get('updated_at')
                }
                registration_data['update_reason'] = 'content_changed'
            
            registry.add_document(document_id, registration_data)
            
            if is_update:
                logger.info(f"Ingestion: Updating document {document_id} ({file.filename}) - new content detected")
            else:
                logger.info(f"Ingestion: Registered new document {document_id} in registry before background processing")
        except Exception as e:
            logger.warning(f"Ingestion: [ReqID: {request_id}] Could not pre-register document: {e}")
            
        # Start background processing
        if background_tasks:
            background_tasks.add_task(
                processor.process_document,
                file_path=file_path,
                file_content=content,
                file_name=file.filename,
                parser_preference=parser_preference,
                document_id=document_id,
                index_name=index_name,
                language=language or "eng",
                is_update=is_update,
                old_index_name=old_index_name
            )
        else:
            # Synchronous processing if background_tasks is not available (unlikely in FastAPI)
            processor.process_document(
                file_path=file_path,
                file_content=content,
                file_name=file.filename,
                parser_preference=parser_preference,
                document_id=document_id,
                index_name=index_name,
                language=language or "eng",
                is_update=is_update,
                old_index_name=old_index_name
            )
        
        status_msg = "updating" if is_update else "processing"
        return DocumentMetadata(
            document_id=document_id,
            document_name=file.filename,
            status=status_msg,
            message=f"{'Updating existing' if is_update else 'Processing new'} document"
        )
        
    except Exception as e:
        logger.error(f"Error ingesting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")

@app.post("/process", response_model=ProcessingResult)
async def process_document_sync(
    request: Request,
    file: UploadFile = File(...),
    parser_preference: Optional[str] = Form(default=None),
    index_name: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default="eng"),
    force_update: Optional[bool] = Form(default=False),
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    Synchronously process a document and return results.
    Detects duplicates and updates existing documents when content changes.
    
    Args:
        force_update: If True, force re-processing even if content is identical
    """
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.info(f"POST /process - [ReqID: {request_id}] File: {file.filename}")
    
    try:
        # Read content first for hash calculation
        content = await file.read()
        
        # Calculate file hash for duplicate detection
        import hashlib
        file_hash = hashlib.md5(content).hexdigest()
        
        # Check for existing document with same name and parser
        from storage.document_registry import DocumentRegistry
        registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
        
        # Determine parser preference for duplicate check
        effective_parser = parser_preference.lower() if parser_preference else 'pymupdf'
        
        # Check if document with same name and parser already exists
        existing_doc = registry.find_document_by_name_and_parser(file.filename, effective_parser)
        is_update = False
        old_index_name = None
        
        if existing_doc and not force_update:
            # Check if content is actually different (by hash)
            if existing_doc.get('file_hash') == file_hash:
                # Same exact file - return existing without re-processing
                logger.info(f"POST /process - [ReqID: {request_id}] Document '{file.filename}' already exists with identical content. Returning existing.")
                return ProcessingResult(
                    document_id=existing_doc['document_id'],
                    document_name=file.filename,
                    file_size=len(content),
                    file_type=os.path.splitext(file.filename)[1].lower(),
                    parser_used=existing_doc.get('parser_used', effective_parser),
                    pages=existing_doc.get('pages', 0),
                    chunks_created=existing_doc.get('chunks_created', 0),
                    tokens_extracted=existing_doc.get('tokens_extracted', 0),
                    extraction_percentage=existing_doc.get('extraction_percentage', 0.0),
                    confidence=existing_doc.get('confidence', 0.0),
                    processing_time=0.0,
                    success=True,
                    error=None,
                    message="Document already exists with identical content. No re-processing needed."
                )
            else:
                # Different content - update existing
                is_update = True
                document_id = existing_doc['document_id']
                old_index_name = existing_doc.get('index_name')
                logger.info(f"POST /process - [ReqID: {request_id}] Updating existing document '{file.filename}' (ID: {document_id})")
        else:
            # New document
            document_id = str(uuid.uuid4())
        
        # Save temp
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        # Process synchronously
        result = processor.process_document(
            file_path=file_path,
            file_content=content,
            file_name=file.filename,
            parser_preference=parser_preference,
            document_id=document_id,
            index_name=index_name,
            language=language or "eng",
            is_update=is_update,
            old_index_name=old_index_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        return ProcessingResult(
            status="failed",
            document_name=file.filename,
            error=str(e)
        )

def get_engine() -> IngestionEngine:
    if engine is None:
        raise HTTPException(status_code=500, detail="Ingestion Engine not initialized")
    return engine

@app.get("/indexes/{index_name}/exists")
async def check_index_exists(
    index_name: str,
    engine: IngestionEngine = Depends(get_engine)
):
    """
    Check if an index exists.
    """
    exists = engine.check_index_exists(index_name)
    return {"exists": exists}

@app.get("/metrics")
async def get_metrics(processor: DocumentProcessor = Depends(get_processor)):
    """
    Get aggregated processing metrics.
    """
    if hasattr(processor.rag_system, 'metrics_collector') and processor.rag_system.metrics_collector:
        return processor.rag_system.metrics_collector.get_all_metrics()
    return {"processing": {}, "queries": {}, "costs": {}, "parser_comparison": {}}

@app.get("/status/{document_id}")
async def get_processing_status(
    document_id: str,
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    Get processing status for a document.
    """
    state = processor.get_processing_state(document_id)
    if not state:
        raise HTTPException(status_code=404, detail="Document processing state not found")
    return state

@app.get("/indexes/{base_name}/next-available")
async def get_next_available_index(
    base_name: str,
    engine: IngestionEngine = Depends(get_engine)
):
    """
    Get the next available index name (auto-incremented).
    """
    next_name = engine.get_next_index_name(base_name)
    return {"index_name": next_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
