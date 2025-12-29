"""
Unified API - Complete UI functionality via REST API
Provides all Streamlit UI features through a single, comprehensive API
"""
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from api.schemas import DocumentMetadata
from config.settings import ARISConfig
from typing import Dict, Any, Optional, List
import os
import json

router = APIRouter(prefix="/ui", tags=["Unified UI API"])


@router.get("/settings")
async def get_all_settings(
    section: Optional[str] = Query(None, description="Specific section or 'all'")
):
    """
    **Complete UI Settings**
    
    Get all settings exactly as shown in the UI sidebar.
    
    **Sections available:**
    - `api` - API provider (OpenAI/Cerebras)
    - `model` - Model settings (OpenAI model, embedding model)
    - `parser` - Parser settings (Docling/PyMuPDF/Textract)
    - `chunking` - Chunking strategy (Comprehensive/Balanced/Fast)
    - `vector_store` - Vector store (FAISS/OpenSearch)
    - `library` - Document library (8 documents stored)
    - `metrics` - R&D metrics & analytics
    - `all` - Everything (default)
    
    **Example:**
    ```
    GET /ui/settings
    GET /ui/settings?section=model
    GET /ui/settings?section=library
    ```
    """
    try:
        settings = {
            "api": {
                "provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
                "options": ["openai", "cerebras"]
            },
            "model": {
                "openai_model": ARISConfig.OPENAI_MODEL,
                "openai_model_description": "Latest GPT-4o model with vision capabilities",
                "embedding_model": ARISConfig.EMBEDDING_MODEL,
                "embedding_model_description": "High-quality 3072-dimension embeddings",
                "cerebras_model": ARISConfig.CEREBRAS_MODEL,
                "temperature": ARISConfig.DEFAULT_TEMPERATURE,
                "max_tokens": ARISConfig.DEFAULT_MAX_TOKENS
            },
            "parser": {
                "current_parser": "docling",
                "options": ["pymupdf", "docling", "textract"],
                "descriptions": {
                    "pymupdf": "Fast parser for text-based PDFs (recommended for speed)",
                    "docling": "Extracts the most content, processes all pages automatically. Takes 5-10 minutes but extracts more text than PyMuPDF",
                    "textract": "AWS OCR for scanned/image PDFs (requires AWS credentials)"
                },
                "docling_timeout": ARISConfig.DOCLING_MAX_TIMEOUT
            },
            "chunking": {
                "strategy": ARISConfig.CHUNKING_STRATEGY,
                "options": ["comprehensive", "balanced", "fast"],
                "current_config": {
                    "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                    "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP
                },
                "description": "Token-aware chunking for optimal retrieval"
            },
            "vector_store": {
                "type": ARISConfig.VECTOR_STORE_TYPE,
                "options": ["faiss", "opensearch"],
                "opensearch_domain": ARISConfig.AWS_OPENSEARCH_DOMAIN,
                "opensearch_index": ARISConfig.AWS_OPENSEARCH_INDEX,
                "opensearch_region": ARISConfig.AWS_OPENSEARCH_REGION,
                "faiss_path": ARISConfig.VECTORSTORE_PATH
            },
            "library": await _get_library_info(),
            "metrics": await _get_metrics_info(),
            "upload": {
                "supported_formats": ["pdf", "txt", "docx", "doc"],
                "max_file_size": "100MB",
                "features": [
                    "Token-aware chunking (512 tokens per chunk)",
                    "Real-time processing with progress tracking",
                    "Source attribution",
                    "Long-term storage: documents persist across restarts"
                ]
            }
        }
        
        if section and section != "all":
            if section not in settings:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid section. Valid: {', '.join(settings.keys())}"
                )
            return {section: settings[section]}
        
        return settings
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/settings")
async def update_settings(updates: Dict[str, Any]):
    """
    **Update UI Settings**
    
    Update any UI settings (same as changing dropdowns/inputs in UI).
    
    **Example:**
    ```json
    {
      "api": {"provider": "cerebras"},
      "model": {"temperature": 0.5},
      "chunking": {"strategy": "balanced"},
      "parser": {"current_parser": "pymupdf"}
    }
    ```
    """
    try:
        updated = []
        
        if "api" in updates:
            ARISConfig.USE_CEREBRAS = (updates["api"].get("provider") == "cerebras")
            updated.append("api")
        
        if "model" in updates:
            model = updates["model"]
            if "openai_model" in model:
                ARISConfig.OPENAI_MODEL = model["openai_model"]
            if "embedding_model" in model:
                ARISConfig.EMBEDDING_MODEL = model["embedding_model"]
            if "temperature" in model:
                ARISConfig.DEFAULT_TEMPERATURE = model["temperature"]
            if "max_tokens" in model:
                ARISConfig.DEFAULT_MAX_TOKENS = model["max_tokens"]
            updated.append("model")
        
        if "chunking" in updates:
            chunking = updates["chunking"]
            if "strategy" in chunking:
                ARISConfig.CHUNKING_STRATEGY = chunking["strategy"]
            if "chunk_size" in chunking:
                ARISConfig.DEFAULT_CHUNK_SIZE = chunking["chunk_size"]
            if "chunk_overlap" in chunking:
                ARISConfig.DEFAULT_CHUNK_OVERLAP = chunking["chunk_overlap"]
            updated.append("chunking")
        
        return {
            "status": "success",
            "updated_sections": updated,
            "message": f"Updated {len(updated)} section(s)",
            "note": "Runtime changes only. Update .env to persist."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/library")
async def get_document_library(
    filter_status: Optional[str] = Query(None, description="Filter by status: success, failed, processing")
):
    """
    **Document Library**
    
    Get all stored documents (same as "📚 Document Library" in UI).
    
    **Response includes:**
    - Total documents stored
    - Document list with metadata
    - Storage persistence status
    - Processing status for each document
    
    **Example:**
    ```
    GET /ui/library
    GET /ui/library?filter_status=success
    ```
    """
    try:
        library = await _get_library_info()
        
        if filter_status:
            library["documents"] = [
                doc for doc in library["documents"]
                if doc.get("status") == filter_status
            ]
            library["filtered_count"] = len(library["documents"])
        
        return library
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/library/{document_id}")
async def get_document_details(document_id: str):
    """
    **Document Details**
    
    Get detailed information about a specific document.
    
    **Example:**
    ```
    GET /ui/library/a1064075-218c-4e7b-8cde-d54337b9c491
    ```
    """
    try:
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        
        if not os.path.exists(registry_path):
            raise HTTPException(status_code=404, detail="Document registry not found")
        
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        
        if document_id not in registry:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        return registry[document_id]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/metrics")
async def get_metrics(
    metric_type: Optional[str] = Query(None, description="Specific metric: processing, storage, parsers, all")
):
    """
    **R&D Metrics & Analytics**
    
    Get processing metrics and analytics (same as "📊 R&D Metrics & Analytics" in UI).
    
    **Metrics include:**
    - Total documents processed
    - Total chunks created
    - Total images extracted
    - Average processing time
    - Parser usage statistics
    - Storage statistics
    
    **Example:**
    ```
    GET /ui/metrics
    GET /ui/metrics?metric_type=processing
    ```
    """
    try:
        metrics = await _get_metrics_info()
        
        if metric_type and metric_type != "all":
            if metric_type == "processing":
                return {
                    "total_documents_processed": metrics["total_documents_processed"],
                    "average_processing_time": metrics["average_processing_time"]
                }
            elif metric_type == "storage":
                return {"storage_stats": metrics["storage_stats"]}
            elif metric_type == "parsers":
                return {"parsers_used": metrics["parsers_used"]}
            else:
                raise HTTPException(status_code=400, detail="Invalid metric_type")
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/dashboard")
async def get_dashboard():
    """
    **Complete UI Dashboard**
    
    Get all UI information in one call (settings + library + metrics).
    
    This is equivalent to loading the entire Streamlit UI.
    
    **Example:**
    ```
    GET /ui/dashboard
    ```
    """
    try:
        return {
            "title": "ARIS R&D - RAG Document Q&A System",
            "description": "Upload documents and ask questions about them using AI with advanced parsers!",
            "settings": await get_all_settings(section="all"),
            "library": await _get_library_info(),
            "metrics": await _get_metrics_info(),
            "features": [
                "Token-aware chunking (512 tokens per chunk)",
                "Real-time processing with progress tracking",
                "Source attribution",
                "Long-term storage: documents persist across restarts"
            ],
            "how_to_use": {
                "steps": [
                    "Load Stored Documents (if any): Use GET /ui/library",
                    "Or Upload New Documents: Use POST /documents (existing endpoint)",
                    "Process: Documents auto-process on upload",
                    "Ask Questions: Use POST /query (existing endpoint)"
                ],
                "supported_formats": ["PDF files (.pdf)", "Text files (.txt)", "Word documents (.docx, .doc)"],
                "parser_options": {
                    "pymupdf": "Fast parser for text-based PDFs (recommended for speed)",
                    "docling": "Extracts the most content, processes all pages automatically. Takes 5-10 minutes",
                    "textract": "AWS OCR for scanned/image PDFs (requires AWS credentials)"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/status")
async def get_system_status():
    """
    **System Status**
    
    Quick health check and status overview.
    
    **Example:**
    ```
    GET /ui/status
    ```
    """
    try:
        library = await _get_library_info()
        
        return {
            "status": "operational",
            "api_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
            "vector_store": ARISConfig.VECTOR_STORE_TYPE,
            "total_documents": library["total_documents"],
            "storage_persists": True,
            "endpoints_available": {
                "settings": "GET /ui/settings",
                "library": "GET /ui/library",
                "metrics": "GET /ui/metrics",
                "dashboard": "GET /ui/dashboard",
                "upload": "POST /documents (existing)",
                "query": "POST /query (existing)"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# Helper functions
async def _get_library_info() -> Dict[str, Any]:
    """Get document library information"""
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    
    if not os.path.exists(registry_path):
        return {
            "total_documents": 0,
            "documents": [],
            "storage_persists": True,
            "message": "No documents processed yet. Upload and process documents to see them here."
        }
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    documents = []
    for doc_id, doc_data in registry.items():
        documents.append(doc_data)
    
    return {
        "total_documents": len(documents),
        "documents": documents,
        "storage_persists": True,
        "successful_documents": sum(1 for d in documents if d.get("status") == "success"),
        "failed_documents": sum(1 for d in documents if d.get("status") == "failed")
    }


async def _get_metrics_info() -> Dict[str, Any]:
    """Get metrics information"""
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    
    if not os.path.exists(registry_path):
        return {
            "total_documents_processed": 0,
            "total_chunks_created": 0,
            "total_images_extracted": 0,
            "average_processing_time": 0.0,
            "parsers_used": {},
            "storage_stats": {},
            "message": "No documents processed yet. Upload and process documents to see metrics."
        }
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    total_docs = len(registry)
    total_chunks = sum(doc.get('chunks_created', 0) for doc in registry.values())
    total_images = sum(doc.get('image_count', 0) for doc in registry.values())
    
    processing_times = [
        doc.get('processing_time', 0) 
        for doc in registry.values() 
        if doc.get('processing_time', 0) > 0
    ]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
    
    parsers_used = {}
    for doc in registry.values():
        parser = doc.get('parser_used', 'unknown')
        if parser:
            parsers_used[parser] = parsers_used.get(parser, 0) + 1
    
    successful_docs = sum(1 for doc in registry.values() if doc.get('status') == 'success')
    failed_docs = sum(1 for doc in registry.values() if doc.get('status') == 'failed')
    
    return {
        "total_documents_processed": total_docs,
        "total_chunks_created": total_chunks,
        "total_images_extracted": total_images,
        "average_processing_time": round(avg_processing_time, 2),
        "parsers_used": parsers_used,
        "storage_stats": {
            "successful_documents": successful_docs,
            "failed_documents": failed_docs,
            "total_text_chunks_stored": sum(doc.get('text_chunks_stored', 0) for doc in registry.values()),
            "total_images_stored": sum(doc.get('images_stored', 0) for doc in registry.values())
        }
    }
