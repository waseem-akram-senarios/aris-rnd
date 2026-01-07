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
from fastapi import BackgroundTasks, FastAPI, UploadFile, File, HTTPException, Form, Depends
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
    file: UploadFile = File(...),
    parser_preference: Optional[str] = Form(default=None),
    index_name: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default="eng"),
    background_tasks: BackgroundTasks = None,
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    Ingest a document (asynchronous).
    """
    logger.info(f"POST /ingest - File: {file.filename}")
    
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
        
        # Read content
        content = await file.read()
        
        # Save locally for reference/fallback
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{document_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
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
                language=language or "eng"
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
                language=language or "eng"
            )
            
        return DocumentMetadata(
            document_id=document_id,
            document_name=file.filename,
            status="processing"
        )
        
    except Exception as e:
        logger.error(f"Error ingesting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")

@app.post("/process", response_model=ProcessingResult)
async def process_document_sync(
    file: UploadFile = File(...),
    parser_preference: Optional[str] = Form(default=None),
    index_name: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default="eng"),
    processor: DocumentProcessor = Depends(get_processor)
):
    """
    Synchronously process a document and return results.
    """
    logger.info(f"POST /process - File: {file.filename}")
    
    try:
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Read content
        content = await file.read()
        
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
            language=language or "eng"
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
