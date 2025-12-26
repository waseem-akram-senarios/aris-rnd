"""
Focused Endpoints - Minimal, clean API structure
5 focused endpoints instead of 20+
"""
from fastapi import APIRouter, HTTPException, Query
from config.settings import ARISConfig
from typing import Dict, Any, Optional
import os
import json

router = APIRouter(prefix="/v1", tags=["Focused API"])


@router.get("/config")
async def get_config(section: Optional[str] = None):
    """
    **Configuration Endpoint**
    
    Get all system configuration or specific section with complete UI details.
    
    **Sections:** api, model, parser, chunking, vector_store, retrieval, upload
    
    **Examples:**
    - `GET /v1/config` - All config with descriptions
    - `GET /v1/config?section=model` - Model config only
    """
    config = {
        "api": {
            "label": "⚙️ Settings - Choose API",
            "current_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
            "options": [
                {"value": "openai", "label": "OpenAI"},
                {"value": "cerebras", "label": "Cerebras"}
            ]
        },
        "model": {
            "label": "🤖 Model Settings",
            "openai_model": {
                "value": ARISConfig.OPENAI_MODEL,
                "label": "OpenAI Model",
                "description": "Latest GPT-4o model with vision capabilities and advanced reasoning"
            },
            "embedding_model": {
                "value": ARISConfig.EMBEDDING_MODEL,
                "label": "Embedding Model",
                "description": "High-quality 3072-dimension embeddings for semantic search"
            },
            "cerebras_model": {
                "value": ARISConfig.CEREBRAS_MODEL,
                "label": "Cerebras Model",
                "description": "Fast inference with Llama 3.3 70B model"
            },
            "temperature": {
                "value": ARISConfig.DEFAULT_TEMPERATURE,
                "label": "Temperature",
                "description": "Controls randomness (0.0 = deterministic, 1.0 = creative)"
            },
            "max_tokens": {
                "value": ARISConfig.DEFAULT_MAX_TOKENS,
                "label": "Max Tokens",
                "description": "Maximum length of generated responses"
            }
        },
        "parser": {
            "label": "🔧 Parser Settings - Choose Parser",
            "current_parser": "docling",
            "options": [
                {
                    "value": "pymupdf",
                    "label": "PyMuPDF",
                    "description": "Fast parser for text-based PDFs (recommended for speed)"
                },
                {
                    "value": "docling",
                    "label": "Docling",
                    "description": "Extracts the most content, processes all pages automatically. Takes 5-10 minutes but extracts more text than PyMuPDF"
                },
                {
                    "value": "textract",
                    "label": "Textract",
                    "description": "AWS OCR for scanned/image PDFs (requires AWS credentials)"
                }
            ]
        },
        "chunking": {
            "label": "✂️ Chunking Strategy - Choose Chunking Strategy",
            "current_strategy": ARISConfig.CHUNKING_STRATEGY,
            "options": [
                {
                    "value": "comprehensive",
                    "label": "Comprehensive",
                    "description": "Smaller chunks (384 tokens) with more overlap (120 tokens) for detailed retrieval"
                },
                {
                    "value": "balanced",
                    "label": "Balanced",
                    "description": "Medium chunks (512 tokens) with moderate overlap (100 tokens) for balanced performance"
                },
                {
                    "value": "fast",
                    "label": "Fast",
                    "description": "Larger chunks (768 tokens) with less overlap (50 tokens) for faster processing"
                }
            ],
            "current_config": {
                "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP,
                "description": "Token-aware chunking for optimal retrieval"
            }
        },
        "vector_store": {
            "label": "💾 Vector Store Settings - Choose Vector Store",
            "current_type": ARISConfig.VECTOR_STORE_TYPE,
            "options": [
                {
                    "value": "faiss",
                    "label": "FAISS",
                    "description": "Local vector store, fast, no cloud dependencies"
                },
                {
                    "value": "opensearch",
                    "label": "OpenSearch",
                    "description": "AWS OpenSearch for scalable, distributed vector search"
                }
            ],
            "opensearch_config": {
                "domain": ARISConfig.AWS_OPENSEARCH_DOMAIN,
                "index": ARISConfig.AWS_OPENSEARCH_INDEX,
                "region": ARISConfig.AWS_OPENSEARCH_REGION
            }
        },
        "retrieval": {
            "label": "🔍 Retrieval Settings",
            "default_k": {
                "value": ARISConfig.DEFAULT_RETRIEVAL_K,
                "label": "Number of chunks to retrieve",
                "description": "How many relevant chunks to fetch for each query"
            },
            "search_mode": {
                "value": ARISConfig.DEFAULT_SEARCH_MODE,
                "label": "Search Mode",
                "options": ["semantic", "keyword", "hybrid"],
                "description": "Hybrid combines semantic and keyword search"
            },
            "use_mmr": {
                "value": ARISConfig.DEFAULT_USE_MMR,
                "label": "Use MMR (Maximal Marginal Relevance)",
                "description": "Reduces redundancy in retrieved chunks"
            }
        },
        "upload": {
            "label": "📄 Upload Documents",
            "supported_formats": ["PDF", "TXT", "DOCX", "DOC"],
            "max_file_size": "100MB per file",
            "drag_drop_text": "Drag and drop files here",
            "features": [
                "Token-aware chunking (512 tokens per chunk)",
                "Real-time processing with progress tracking",
                "Source attribution",
                "Long-term storage: documents persist across restarts"
            ],
            "format_details": {
                "pdf": "Uses PyMuPDF, Docling, or Textract",
                "txt": "Plain text files",
                "docx": "Word documents",
                "doc": "Legacy Word documents"
            }
        }
    }
    
    if section:
        # Handle both 'vectorstore' and 'vector_store' for backward compatibility
        if section == "vectorstore":
            section = "vector_store"
        
        if section not in config:
            raise HTTPException(status_code=400, detail=f"Invalid section: {section}. Valid sections: {', '.join(config.keys())}")
        return {section: config[section]}
    
    return config


@router.post("/config")
async def update_config(updates: Dict[str, Any]):
    """
    **Update Configuration**
    
    Update any configuration settings.
    
    **Example:**
    ```json
    {
      "api": {"provider": "cerebras"},
      "model": {"temperature": 0.5},
      "chunking": {"strategy": "balanced"}
    }
    ```
    """
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
        if "chunk_size" in chunking:
            ARISConfig.DEFAULT_CHUNK_SIZE = chunking["chunk_size"]
        updated.append("chunking")
    
    if "retrieval" in updates:
        retrieval = updates["retrieval"]
        if "default_k" in retrieval:
            ARISConfig.DEFAULT_RETRIEVAL_K = retrieval["default_k"]
        if "search_mode" in retrieval:
            ARISConfig.DEFAULT_SEARCH_MODE = retrieval["search_mode"]
        updated.append("retrieval")
    
    return {
        "status": "success",
        "updated": updated,
        "message": f"Updated {len(updated)} section(s)"
    }


@router.get("/library")
async def get_library(status: Optional[str] = None):
    """
    **Document Library**
    
    Get all documents with metadata.
    
    **Query params:**
    - `status` - Filter by status (success, failed, processing)
    
    **Examples:**
    - `GET /v1/library` - All documents
    - `GET /v1/library?status=success` - Successful only
    """
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    
    if not os.path.exists(registry_path):
        return {
            "total": 0,
            "documents": [],
            "message": "No documents yet"
        }
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    documents = list(registry.values())
    
    if status:
        documents = [d for d in documents if d.get("status") == status]
    
    return {
        "total": len(documents),
        "documents": documents,
        "successful": sum(1 for d in documents if d.get("status") == "success"),
        "failed": sum(1 for d in documents if d.get("status") == "failed")
    }


@router.get("/library/{document_id}")
async def get_document(document_id: str):
    """
    **Get Document Details**
    
    Get detailed information about a specific document.
    """
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    
    if not os.path.exists(registry_path):
        raise HTTPException(status_code=404, detail="No documents found")
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    if document_id not in registry:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    
    return registry[document_id]


@router.get("/metrics")
async def get_metrics():
    """
    **System Metrics**
    
    Get processing metrics and analytics.
    
    **Returns:**
    - Total documents processed
    - Total chunks created
    - Total images extracted
    - Average processing time
    - Parser usage stats
    - Storage stats
    """
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    
    if not os.path.exists(registry_path):
        return {
            "total_documents": 0,
            "total_chunks": 0,
            "total_images": 0,
            "avg_processing_time": 0.0,
            "parsers": {},
            "storage": {}
        }
    
    with open(registry_path, 'r') as f:
        registry = json.load(f)
    
    total_docs = len(registry)
    total_chunks = sum(doc.get('chunks_created', 0) for doc in registry.values())
    total_images = sum(doc.get('image_count', 0) for doc in registry.values())
    
    times = [doc.get('processing_time', 0) for doc in registry.values() if doc.get('processing_time', 0) > 0]
    avg_time = sum(times) / len(times) if times else 0.0
    
    parsers = {}
    for doc in registry.values():
        parser = doc.get('parser_used', 'unknown')
        parsers[parser] = parsers.get(parser, 0) + 1
    
    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "total_images": total_images,
        "avg_processing_time": round(avg_time, 2),
        "parsers": parsers,
        "storage": {
            "successful": sum(1 for d in registry.values() if d.get('status') == 'success'),
            "failed": sum(1 for d in registry.values() if d.get('status') == 'failed'),
            "text_chunks": sum(d.get('text_chunks_stored', 0) for d in registry.values()),
            "images_stored": sum(d.get('images_stored', 0) for d in registry.values())
        }
    }


@router.get("/status")
async def get_status():
    """
    **System Status**
    
    Quick health check and system overview.
    """
    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
    total_docs = 0
    
    if os.path.exists(registry_path):
        with open(registry_path, 'r') as f:
            registry = json.load(f)
            total_docs = len(registry)
    
    return {
        "status": "operational",
        "api_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
        "vector_store": ARISConfig.VECTOR_STORE_TYPE,
        "total_documents": total_docs,
        "endpoints": {
            "config": "GET/POST /v1/config",
            "library": "GET /v1/library",
            "metrics": "GET /v1/metrics",
            "status": "GET /v1/status",
            "upload": "POST /documents",
            "query": "POST /query"
        }
    }
