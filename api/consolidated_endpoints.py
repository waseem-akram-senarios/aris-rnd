"""
Consolidated API endpoints for ARIS RAG System
Combines related functionality into fewer, more powerful endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from api.schemas import (
    SystemSettings, ModelSettings, ParserSettings, ChunkingSettings,
    VectorStoreSettings, RetrievalSettings, AgenticRAGSettings,
    DocumentLibraryInfo, MetricsInfo, DocumentMetadata
)
from config.settings import ARISConfig
from typing import Dict, Any, Optional, List
import os
import json

router = APIRouter(prefix="/api", tags=["Consolidated API"])


@router.get("/config")
async def get_configuration(
    section: Optional[str] = Query(None, description="Specific section: model, parser, chunking, vector_store, retrieval, agentic_rag, or 'all' for everything")
):
    """
    **Unified Configuration Endpoint**
    
    Get all system configuration or specific sections.
    
    **Query Parameters:**
    - `section` (optional): Specify which config section to get
      - `model` - Model settings (API provider, models, temperature)
      - `parser` - Parser settings
      - `chunking` - Chunking strategy
      - `vector_store` - Vector store configuration
      - `retrieval` - Retrieval settings
      - `agentic_rag` - Agentic RAG settings
      - `all` or omit - Get everything
    
    **Examples:**
    - `GET /api/config` - Get all configuration
    - `GET /api/config?section=model` - Get only model settings
    - `GET /api/config?section=chunking` - Get only chunking settings
    """
    try:
        # Build all settings
        all_settings = {
            "model": {
                "api_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
                "openai_model": ARISConfig.OPENAI_MODEL,
                "cerebras_model": ARISConfig.CEREBRAS_MODEL,
                "embedding_model": ARISConfig.EMBEDDING_MODEL,
                "temperature": ARISConfig.DEFAULT_TEMPERATURE,
                "max_tokens": ARISConfig.DEFAULT_MAX_TOKENS
            },
            "parser": {
                "parser": "docling",
                "docling_timeout": ARISConfig.DOCLING_MAX_TIMEOUT
            },
            "chunking": {
                "strategy": ARISConfig.CHUNKING_STRATEGY,
                "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP
            },
            "vector_store": {
                "vector_store_type": ARISConfig.VECTOR_STORE_TYPE,
                "opensearch_domain": ARISConfig.AWS_OPENSEARCH_DOMAIN,
                "opensearch_index": ARISConfig.AWS_OPENSEARCH_INDEX,
                "opensearch_region": ARISConfig.AWS_OPENSEARCH_REGION
            },
            "retrieval": {
                "default_k": ARISConfig.DEFAULT_RETRIEVAL_K,
                "use_mmr": ARISConfig.DEFAULT_USE_MMR,
                "mmr_fetch_k": ARISConfig.DEFAULT_MMR_FETCH_K,
                "mmr_lambda": ARISConfig.DEFAULT_MMR_LAMBDA,
                "search_mode": ARISConfig.DEFAULT_SEARCH_MODE,
                "semantic_weight": ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
                "keyword_weight": ARISConfig.DEFAULT_KEYWORD_WEIGHT
            },
            "agentic_rag": {
                "use_agentic_rag": ARISConfig.DEFAULT_USE_AGENTIC_RAG,
                "max_sub_queries": ARISConfig.DEFAULT_MAX_SUB_QUERIES,
                "chunks_per_subquery": ARISConfig.DEFAULT_CHUNKS_PER_SUBQUERY,
                "max_total_chunks": ARISConfig.DEFAULT_MAX_TOTAL_CHUNKS,
                "deduplication_threshold": ARISConfig.DEFAULT_DEDUPLICATION_THRESHOLD
            }
        }
        
        # Return specific section or all
        if section and section != "all":
            if section not in all_settings:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid section. Valid options: {', '.join(all_settings.keys())}, all"
                )
            return {section: all_settings[section]}
        
        return all_settings
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving configuration: {str(e)}")


@router.post("/config")
async def update_configuration(config_updates: Dict[str, Any]):
    """
    **Unified Configuration Update Endpoint**
    
    Update any configuration settings in one call.
    
    **Request Body:** JSON object with configuration sections to update
    
    **Example:**
    ```json
    {
      "model": {
        "api_provider": "cerebras",
        "temperature": 0.5
      },
      "chunking": {
        "strategy": "balanced",
        "chunk_size": 512
      },
      "retrieval": {
        "default_k": 15,
        "search_mode": "semantic"
      }
    }
    ```
    
    **Note:** Only updates the fields you provide. Other fields remain unchanged.
    """
    try:
        updated_sections = []
        
        # Update model settings
        if "model" in config_updates:
            model = config_updates["model"]
            if "api_provider" in model:
                ARISConfig.USE_CEREBRAS = (model["api_provider"] == "cerebras")
            if "openai_model" in model:
                ARISConfig.OPENAI_MODEL = model["openai_model"]
            if "cerebras_model" in model:
                ARISConfig.CEREBRAS_MODEL = model["cerebras_model"]
            if "embedding_model" in model:
                ARISConfig.EMBEDDING_MODEL = model["embedding_model"]
            if "temperature" in model:
                ARISConfig.DEFAULT_TEMPERATURE = model["temperature"]
            if "max_tokens" in model:
                ARISConfig.DEFAULT_MAX_TOKENS = model["max_tokens"]
            updated_sections.append("model")
        
        # Update chunking settings
        if "chunking" in config_updates:
            chunking = config_updates["chunking"]
            if "strategy" in chunking:
                ARISConfig.CHUNKING_STRATEGY = chunking["strategy"]
            if "chunk_size" in chunking:
                ARISConfig.DEFAULT_CHUNK_SIZE = chunking["chunk_size"]
            if "chunk_overlap" in chunking:
                ARISConfig.DEFAULT_CHUNK_OVERLAP = chunking["chunk_overlap"]
            updated_sections.append("chunking")
        
        # Update retrieval settings
        if "retrieval" in config_updates:
            retrieval = config_updates["retrieval"]
            if "default_k" in retrieval:
                ARISConfig.DEFAULT_RETRIEVAL_K = retrieval["default_k"]
            if "use_mmr" in retrieval:
                ARISConfig.DEFAULT_USE_MMR = retrieval["use_mmr"]
            if "mmr_fetch_k" in retrieval:
                ARISConfig.DEFAULT_MMR_FETCH_K = retrieval["mmr_fetch_k"]
            if "mmr_lambda" in retrieval:
                ARISConfig.DEFAULT_MMR_LAMBDA = retrieval["mmr_lambda"]
            if "search_mode" in retrieval:
                ARISConfig.DEFAULT_SEARCH_MODE = retrieval["search_mode"]
            if "semantic_weight" in retrieval:
                ARISConfig.DEFAULT_SEMANTIC_WEIGHT = retrieval["semantic_weight"]
            if "keyword_weight" in retrieval:
                ARISConfig.DEFAULT_KEYWORD_WEIGHT = retrieval["keyword_weight"]
            updated_sections.append("retrieval")
        
        return {
            "status": "success",
            "message": f"Updated {len(updated_sections)} configuration section(s)",
            "updated_sections": updated_sections,
            "note": "Changes are runtime only. Update .env file to persist across restarts."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {str(e)}")


@router.get("/system")
async def get_system_info(
    include: Optional[str] = Query("all", description="What to include: library, metrics, config, all")
):
    """
    **Unified System Information Endpoint**
    
    Get complete system information including library, metrics, and configuration.
    
    **Query Parameters:**
    - `include` (optional): What information to include
      - `library` - Document library only
      - `metrics` - Metrics only
      - `config` - Configuration only
      - `all` (default) - Everything
    
    **Examples:**
    - `GET /api/system` - Get everything
    - `GET /api/system?include=library` - Get only document library
    - `GET /api/system?include=metrics` - Get only metrics
    """
    try:
        result = {}
        
        # Document Library
        if include in ["library", "all"]:
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            if os.path.exists(registry_path):
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                
                documents = [DocumentMetadata(**doc_data) for doc_data in registry.values()]
                result["library"] = {
                    "total_documents": len(documents),
                    "documents": documents,
                    "storage_persists": True
                }
            else:
                result["library"] = {
                    "total_documents": 0,
                    "documents": [],
                    "storage_persists": True
                }
        
        # Metrics
        if include in ["metrics", "all"]:
            registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
            if os.path.exists(registry_path):
                with open(registry_path, 'r') as f:
                    registry = json.load(f)
                
                total_docs = len(registry)
                total_chunks = sum(doc.get('chunks_created', 0) for doc in registry.values())
                total_images = sum(doc.get('image_count', 0) for doc in registry.values())
                
                processing_times = [doc.get('processing_time', 0) for doc in registry.values() if doc.get('processing_time', 0) > 0]
                avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
                
                parsers_used = {}
                for doc in registry.values():
                    parser = doc.get('parser_used', 'unknown')
                    if parser:
                        parsers_used[parser] = parsers_used.get(parser, 0) + 1
                
                successful_docs = sum(1 for doc in registry.values() if doc.get('status') == 'success')
                failed_docs = sum(1 for doc in registry.values() if doc.get('status') == 'failed')
                
                result["metrics"] = {
                    "total_documents_processed": total_docs,
                    "total_chunks_created": total_chunks,
                    "total_images_extracted": total_images,
                    "average_processing_time": avg_processing_time,
                    "parsers_used": parsers_used,
                    "storage_stats": {
                        "successful_documents": successful_docs,
                        "failed_documents": failed_docs,
                        "total_text_chunks_stored": sum(doc.get('text_chunks_stored', 0) for doc in registry.values()),
                        "total_images_stored": sum(doc.get('images_stored', 0) for doc in registry.values())
                    }
                }
            else:
                result["metrics"] = {
                    "total_documents_processed": 0,
                    "total_chunks_created": 0,
                    "total_images_extracted": 0,
                    "average_processing_time": 0.0,
                    "parsers_used": {},
                    "storage_stats": {}
                }
        
        # Configuration
        if include in ["config", "all"]:
            result["config"] = {
                "model": {
                    "api_provider": "cerebras" if ARISConfig.USE_CEREBRAS else "openai",
                    "openai_model": ARISConfig.OPENAI_MODEL,
                    "embedding_model": ARISConfig.EMBEDDING_MODEL,
                    "temperature": ARISConfig.DEFAULT_TEMPERATURE
                },
                "chunking": {
                    "strategy": ARISConfig.CHUNKING_STRATEGY,
                    "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE
                },
                "vector_store": {
                    "type": ARISConfig.VECTOR_STORE_TYPE,
                    "opensearch_domain": ARISConfig.AWS_OPENSEARCH_DOMAIN,
                    "opensearch_index": ARISConfig.AWS_OPENSEARCH_INDEX
                },
                "retrieval": {
                    "default_k": ARISConfig.DEFAULT_RETRIEVAL_K,
                    "search_mode": ARISConfig.DEFAULT_SEARCH_MODE
                }
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving system information: {str(e)}")
