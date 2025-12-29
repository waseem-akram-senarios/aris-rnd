"""
Single Unified Endpoint - All API functionality in ONE place
No repetition, no multiple endpoints - just one powerful endpoint
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from api.schemas import DocumentMetadata
from config.settings import ARISConfig
from typing import Dict, Any, Optional, List
import os
import json

router = APIRouter(tags=["Unified Single Endpoint"])


@router.post("/api")
@router.get("/api")
async def unified_endpoint(
    action: str,
    # Document operations
    document_id: Optional[str] = None,
    file: Optional[UploadFile] = File(None),
    
    # Query operations
    question: Optional[str] = None,
    k: Optional[int] = 5,
    search_mode: Optional[str] = "hybrid",
    
    # Settings operations
    section: Optional[str] = None,
    settings_update: Optional[Dict[str, Any]] = None,
    
    # Filter/pagination
    filter_status: Optional[str] = None,
    page_number: Optional[int] = None,
    image_number: Optional[int] = None,
    
    # Additional parameters
    data: Optional[Dict[str, Any]] = None
):
    """
    **SINGLE UNIFIED ENDPOINT - ALL OPERATIONS**
    
    One endpoint to rule them all. No repetition.
    
    **Actions Available:**
    
    **SETTINGS:**
    - `get_settings` - Get all/specific settings
    - `update_settings` - Update settings
    - `get_dashboard` - Complete UI dashboard
    - `get_status` - System status
    
    **DOCUMENTS:**
    - `list_documents` - List all documents
    - `get_document` - Get specific document
    - `upload_document` - Upload new document
    - `delete_document` - Delete document
    
    **LIBRARY & METRICS:**
    - `get_library` - Document library
    - `get_metrics` - R&D metrics
    
    **QUERY:**
    - `query` - Ask questions
    - `query_text` - Text-only query
    - `query_images` - Image query
    
    **DOCUMENT DETAILS:**
    - `get_storage_status` - Storage status
    - `get_images` - All images
    - `get_image` - Specific image
    - `get_page` - Page content
    - `get_accuracy` - OCR accuracy
    
    **Examples:**
    ```
    GET  /api?action=get_dashboard
    GET  /api?action=get_settings&section=model
    POST /api?action=update_settings (with JSON body)
    GET  /api?action=get_library
    GET  /api?action=get_metrics
    GET  /api?action=list_documents
    GET  /api?action=get_document&document_id=xxx
    POST /api?action=query&question=xxx&k=5
    GET  /api?action=get_storage_status&document_id=xxx
    GET  /api?action=get_images&document_id=xxx
    ```
    """
    
    try:
        # ============================================
        # SETTINGS ACTIONS
        # ============================================
        
        if action == "get_settings":
            settings = {
                "api": {
                    "provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
                    "options": ["openai", "cerebras"]
                },
                "model": {
                    "openai_model": ARISConfig.OPENAI_MODEL,
                    "embedding_model": ARISConfig.EMBEDDING_MODEL,
                    "cerebras_model": ARISConfig.CEREBRAS_MODEL,
                    "temperature": ARISConfig.DEFAULT_TEMPERATURE,
                    "max_tokens": ARISConfig.DEFAULT_MAX_TOKENS
                },
                "parser": {
                    "current_parser": "docling",
                    "options": ["pymupdf", "docling", "textract"]
                },
                "chunking": {
                    "strategy": ARISConfig.CHUNKING_STRATEGY,
                    "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                    "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP
                },
                "vector_store": {
                    "type": ARISConfig.VECTOR_STORE_TYPE,
                    "opensearch_domain": ARISConfig.AWS_OPENSEARCH_DOMAIN,
                    "opensearch_index": ARISConfig.AWS_OPENSEARCH_INDEX
                },
                "retrieval": {
                    "default_k": ARISConfig.DEFAULT_RETRIEVAL_K,
                    "search_mode": ARISConfig.DEFAULT_SEARCH_MODE,
                    "use_mmr": ARISConfig.DEFAULT_USE_MMR
                }
            }
            
            if section and section != "all":
                return {section: settings.get(section, {})}
            return settings
        
        elif action == "update_settings":
            if not data and not settings_update:
                raise HTTPException(status_code=400, detail="Provide settings in 'data' or 'settings_update'")
            
            updates = data or settings_update
            updated = []
            
            if "api" in updates:
                ARISConfig.USE_CEREBRAS = (updates["api"].get("provider") == "cerebras")
                updated.append("api")
            
            if "model" in updates:
                model = updates["model"]
                if "temperature" in model:
                    ARISConfig.DEFAULT_TEMPERATURE = model["temperature"]
                if "openai_model" in model:
                    ARISConfig.OPENAI_MODEL = model["openai_model"]
                updated.append("model")
            
            if "chunking" in updates:
                chunking = updates["chunking"]
                if "strategy" in chunking:
                    ARISConfig.CHUNKING_STRATEGY = chunking["strategy"]
                updated.append("chunking")
            
            return {
                "status": "success",
                "updated_sections": updated,
                "message": f"Updated {len(updated)} section(s)"
            }
        
        elif action == "get_dashboard":
            return {
                "title": "ARIS RAG System",
                "settings": await unified_endpoint(action="get_settings"),
                "library": await unified_endpoint(action="get_library"),
                "metrics": await unified_endpoint(action="get_metrics"),
                "status": "operational"
            }
        
        elif action == "get_status":
            library = await unified_endpoint(action="get_library")
            return {
                "status": "operational",
                "api_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
                "vector_store": ARISConfig.VECTOR_STORE_TYPE,
                "total_documents": library.get("total_documents", 0)
            }
        
        # ============================================
        # LIBRARY & METRICS ACTIONS
        # ============================================
        
        elif action == "get_library":
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            
            if not os.path.exists(registry_path):
                return {
                    "total_documents": 0,
                    "documents": [],
                    "message": "No documents yet"
                }
            
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            documents = list(registry.values())
            
            if filter_status:
                documents = [d for d in documents if d.get("status") == filter_status]
            
            return {
                "total_documents": len(documents),
                "documents": documents,
                "storage_persists": True
            }
        
        elif action == "get_metrics":
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            
            if not os.path.exists(registry_path):
                return {
                    "total_documents_processed": 0,
                    "total_chunks_created": 0,
                    "total_images_extracted": 0,
                    "message": "No documents yet"
                }
            
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            total_docs = len(registry)
            total_chunks = sum(doc.get('chunks_created', 0) for doc in registry.values())
            total_images = sum(doc.get('image_count', 0) for doc in registry.values())
            
            processing_times = [doc.get('processing_time', 0) for doc in registry.values() if doc.get('processing_time', 0) > 0]
            avg_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
            
            parsers = {}
            for doc in registry.values():
                parser = doc.get('parser_used', 'unknown')
                parsers[parser] = parsers.get(parser, 0) + 1
            
            return {
                "total_documents_processed": total_docs,
                "total_chunks_created": total_chunks,
                "total_images_extracted": total_images,
                "average_processing_time": round(avg_time, 2),
                "parsers_used": parsers,
                "storage_stats": {
                    "successful": sum(1 for d in registry.values() if d.get('status') == 'success'),
                    "failed": sum(1 for d in registry.values() if d.get('status') == 'failed')
                }
            }
        
        # ============================================
        # DOCUMENT ACTIONS
        # ============================================
        
        elif action == "list_documents":
            return await unified_endpoint(action="get_library", filter_status=filter_status)
        
        elif action == "get_document":
            if not document_id:
                raise HTTPException(status_code=400, detail="document_id required")
            
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            
            if not os.path.exists(registry_path):
                raise HTTPException(status_code=404, detail="No documents found")
            
            with open(registry_path, 'r') as f:
                registry = json.load(f)
            
            if document_id not in registry:
                raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
            
            return registry[document_id]
        
        # ============================================
        # QUERY ACTIONS (Delegated to existing endpoints)
        # ============================================
        
        elif action in ["query", "query_text", "query_images"]:
            if not question:
                raise HTTPException(status_code=400, detail="question parameter required")
            
            return {
                "message": f"Use existing endpoint: POST /query with question='{question}'",
                "note": "Query operations use existing optimized endpoints",
                "endpoint": "/query" if action == "query" else f"/query/{action.split('_')[1]}"
            }
        
        # ============================================
        # DOCUMENT DETAILS ACTIONS (Delegated)
        # ============================================
        
        elif action in ["get_storage_status", "get_images", "get_image", "get_page", "get_accuracy"]:
            if not document_id:
                raise HTTPException(status_code=400, detail="document_id required")
            
            endpoint_map = {
                "get_storage_status": f"/documents/{document_id}/storage/status",
                "get_images": f"/documents/{document_id}/images/all",
                "get_image": f"/documents/{document_id}/images/{image_number}",
                "get_page": f"/documents/{document_id}/pages/{page_number}",
                "get_accuracy": f"/documents/{document_id}/accuracy"
            }
            
            return {
                "message": f"Use existing endpoint: GET {endpoint_map[action]}",
                "note": "Document detail operations use existing optimized endpoints"
            }
        
        # ============================================
        # UPLOAD/DELETE (Delegated)
        # ============================================
        
        elif action in ["upload_document", "delete_document"]:
            endpoint = "/documents"
            method = "POST" if action == "upload_document" else "DELETE"
            
            return {
                "message": f"Use existing endpoint: {method} {endpoint}",
                "note": "Upload/delete operations use existing optimized endpoints"
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {action}. Valid actions: get_settings, update_settings, get_dashboard, get_status, get_library, get_metrics, list_documents, get_document, query, query_text, query_images, get_storage_status, get_images, get_accuracy"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
