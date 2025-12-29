"""
Settings API endpoints for ARIS RAG System
Provides API access to all UI configuration settings
"""
from fastapi import APIRouter, HTTPException
from api.schemas import (
    SystemSettings, ModelSettings, ParserSettings, ChunkingSettings,
    VectorStoreSettings, RetrievalSettings, AgenticRAGSettings,
    DocumentLibraryInfo, MetricsInfo, DocumentMetadata
)
from config.settings import ARISConfig
from typing import Dict, Any
import os
import json

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/", response_model=SystemSettings)
async def get_all_settings():
    """
    Get all system settings (equivalent to UI settings panel)
    
    Returns complete configuration including:
    - Model settings (API provider, models, temperature, etc.)
    - Parser settings (parser choice, timeout)
    - Chunking settings (strategy, chunk size, overlap)
    - Vector store settings (type, OpenSearch config)
    - Retrieval settings (k, MMR, search mode, weights)
    - Agentic RAG settings (sub-queries, chunks, deduplication)
    """
    try:
        # Model Settings
        model_settings = ModelSettings(
            api_provider='cerebras' if ARISConfig.USE_CEREBRAS else 'openai',
            openai_model=ARISConfig.OPENAI_MODEL,
            cerebras_model=ARISConfig.CEREBRAS_MODEL,
            embedding_model=ARISConfig.EMBEDDING_MODEL,
            temperature=ARISConfig.DEFAULT_TEMPERATURE,
            max_tokens=ARISConfig.DEFAULT_MAX_TOKENS
        )
        
        # Parser Settings
        parser_settings = ParserSettings(
            parser='docling',  # Default, can be made configurable
            docling_timeout=ARISConfig.DOCLING_MAX_TIMEOUT
        )
        
        # Chunking Settings
        chunking_settings = ChunkingSettings(
            strategy=ARISConfig.CHUNKING_STRATEGY,
            chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
            chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
        )
        
        # Vector Store Settings
        vector_store_settings = VectorStoreSettings(
            vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
            opensearch_region=ARISConfig.AWS_OPENSEARCH_REGION
        )
        
        # Retrieval Settings
        retrieval_settings = RetrievalSettings(
            default_k=ARISConfig.DEFAULT_RETRIEVAL_K,
            use_mmr=ARISConfig.DEFAULT_USE_MMR,
            mmr_fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K,
            mmr_lambda=ARISConfig.DEFAULT_MMR_LAMBDA,
            search_mode=ARISConfig.DEFAULT_SEARCH_MODE,
            semantic_weight=ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
            keyword_weight=ARISConfig.DEFAULT_KEYWORD_WEIGHT
        )
        
        # Agentic RAG Settings
        agentic_rag_settings = AgenticRAGSettings(
            use_agentic_rag=ARISConfig.DEFAULT_USE_AGENTIC_RAG,
            max_sub_queries=ARISConfig.DEFAULT_MAX_SUB_QUERIES,
            chunks_per_subquery=ARISConfig.DEFAULT_CHUNKS_PER_SUBQUERY,
            max_total_chunks=ARISConfig.DEFAULT_MAX_TOTAL_CHUNKS,
            deduplication_threshold=ARISConfig.DEFAULT_DEDUPLICATION_THRESHOLD
        )
        
        return SystemSettings(
            model_settings=model_settings,
            parser_settings=parser_settings,
            chunking_settings=chunking_settings,
            vector_store_settings=vector_store_settings,
            retrieval_settings=retrieval_settings,
            agentic_rag_settings=agentic_rag_settings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving settings: {str(e)}")


@router.get("/model", response_model=ModelSettings)
async def get_model_settings():
    """Get model configuration settings"""
    return ModelSettings(
        api_provider='cerebras' if ARISConfig.USE_CEREBRAS else 'openai',
        openai_model=ARISConfig.OPENAI_MODEL,
        cerebras_model=ARISConfig.CEREBRAS_MODEL,
        embedding_model=ARISConfig.EMBEDDING_MODEL,
        temperature=ARISConfig.DEFAULT_TEMPERATURE,
        max_tokens=ARISConfig.DEFAULT_MAX_TOKENS
    )


@router.get("/parser", response_model=ParserSettings)
async def get_parser_settings():
    """Get parser configuration settings"""
    return ParserSettings(
        parser='docling',
        docling_timeout=ARISConfig.DOCLING_MAX_TIMEOUT
    )


@router.get("/chunking", response_model=ChunkingSettings)
async def get_chunking_settings():
    """Get chunking strategy settings"""
    return ChunkingSettings(
        strategy=ARISConfig.CHUNKING_STRATEGY,
        chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
        chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
    )


@router.get("/vector-store", response_model=VectorStoreSettings)
async def get_vector_store_settings():
    """Get vector store configuration settings"""
    return VectorStoreSettings(
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
        opensearch_region=ARISConfig.AWS_OPENSEARCH_REGION
    )


@router.get("/retrieval", response_model=RetrievalSettings)
async def get_retrieval_settings():
    """Get retrieval configuration settings"""
    return RetrievalSettings(
        default_k=ARISConfig.DEFAULT_RETRIEVAL_K,
        use_mmr=ARISConfig.DEFAULT_USE_MMR,
        mmr_fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K,
        mmr_lambda=ARISConfig.DEFAULT_MMR_LAMBDA,
        search_mode=ARISConfig.DEFAULT_SEARCH_MODE,
        semantic_weight=ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
        keyword_weight=ARISConfig.DEFAULT_KEYWORD_WEIGHT
    )


@router.get("/agentic-rag", response_model=AgenticRAGSettings)
async def get_agentic_rag_settings():
    """Get Agentic RAG configuration settings"""
    return AgenticRAGSettings(
        use_agentic_rag=ARISConfig.DEFAULT_USE_AGENTIC_RAG,
        max_sub_queries=ARISConfig.DEFAULT_MAX_SUB_QUERIES,
        chunks_per_subquery=ARISConfig.DEFAULT_CHUNKS_PER_SUBQUERY,
        max_total_chunks=ARISConfig.DEFAULT_MAX_TOTAL_CHUNKS,
        deduplication_threshold=ARISConfig.DEFAULT_DEDUPLICATION_THRESHOLD
    )


@router.get("/library", response_model=DocumentLibraryInfo)
async def get_document_library():
    """
    Get document library information (equivalent to UI Document Library section)
    
    Returns:
    - Total number of documents
    - List of all documents with metadata
    - Storage persistence status
    """
    try:
        # Read document registry
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        
        if not os.path.exists(registry_path):
            return DocumentLibraryInfo(
                total_documents=0,
                documents=[],
                storage_persists=True
            )
        
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        
        documents = []
        for doc_id, doc_data in registry.items():
            documents.append(DocumentMetadata(**doc_data))
        
        return DocumentLibraryInfo(
            total_documents=len(documents),
            documents=documents,
            storage_persists=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document library: {str(e)}")


@router.get("/metrics", response_model=MetricsInfo)
async def get_metrics():
    """
    Get R&D metrics and analytics (equivalent to UI Metrics section)
    
    Returns:
    - Total documents processed
    - Total chunks created
    - Total images extracted
    - Average processing time
    - Parser usage statistics
    - Storage statistics
    """
    try:
        # Read document registry
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        
        if not os.path.exists(registry_path):
            return MetricsInfo(
                total_documents_processed=0,
                total_chunks_created=0,
                total_images_extracted=0,
                average_processing_time=0.0,
                total_queries=0,
                average_query_time=0.0,
                parsers_used={},
                storage_stats={}
            )
        
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        
        # Calculate metrics
        total_docs = len(registry)
        total_chunks = sum(doc.get('chunks_created', 0) for doc in registry.values())
        total_images = sum(doc.get('image_count', 0) for doc in registry.values())
        
        processing_times = [doc.get('processing_time', 0) for doc in registry.values() if doc.get('processing_time', 0) > 0]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
        
        # Parser usage
        parsers_used = {}
        for doc in registry.values():
            parser = doc.get('parser_used', 'unknown')
            if parser:
                parsers_used[parser] = parsers_used.get(parser, 0) + 1
        
        # Storage stats
        successful_docs = sum(1 for doc in registry.values() if doc.get('status') == 'success')
        failed_docs = sum(1 for doc in registry.values() if doc.get('status') == 'failed')
        
        storage_stats = {
            'successful_documents': successful_docs,
            'failed_documents': failed_docs,
            'total_text_chunks_stored': sum(doc.get('text_chunks_stored', 0) for doc in registry.values()),
            'total_images_stored': sum(doc.get('images_stored', 0) for doc in registry.values())
        }
        
        return MetricsInfo(
            total_documents_processed=total_docs,
            total_chunks_created=total_chunks,
            total_images_extracted=total_images,
            average_processing_time=avg_processing_time,
            total_queries=0,  # Would need query tracking
            average_query_time=0.0,  # Would need query tracking
            parsers_used=parsers_used,
            storage_stats=storage_stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving metrics: {str(e)}")


@router.post("/model", response_model=ModelSettings)
async def update_model_settings(settings: ModelSettings):
    """
    Update model configuration settings
    
    Note: This updates runtime configuration. To persist changes,
    update the .env file with the new values.
    """
    try:
        # Update runtime configuration
        ARISConfig.USE_CEREBRAS = (settings.api_provider == 'cerebras')
        ARISConfig.OPENAI_MODEL = settings.openai_model
        ARISConfig.CEREBRAS_MODEL = settings.cerebras_model
        ARISConfig.EMBEDDING_MODEL = settings.embedding_model
        ARISConfig.DEFAULT_TEMPERATURE = settings.temperature
        ARISConfig.DEFAULT_MAX_TOKENS = settings.max_tokens
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating model settings: {str(e)}")


@router.post("/chunking", response_model=ChunkingSettings)
async def update_chunking_settings(settings: ChunkingSettings):
    """
    Update chunking strategy settings
    
    Note: This updates runtime configuration. To persist changes,
    update the .env file with the new values.
    """
    try:
        ARISConfig.CHUNKING_STRATEGY = settings.strategy
        ARISConfig.DEFAULT_CHUNK_SIZE = settings.chunk_size
        ARISConfig.DEFAULT_CHUNK_OVERLAP = settings.chunk_overlap
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating chunking settings: {str(e)}")


@router.post("/retrieval", response_model=RetrievalSettings)
async def update_retrieval_settings(settings: RetrievalSettings):
    """
    Update retrieval configuration settings
    
    Note: This updates runtime configuration. To persist changes,
    update the .env file with the new values.
    """
    try:
        ARISConfig.DEFAULT_RETRIEVAL_K = settings.default_k
        ARISConfig.DEFAULT_USE_MMR = settings.use_mmr
        ARISConfig.DEFAULT_MMR_FETCH_K = settings.mmr_fetch_k
        ARISConfig.DEFAULT_MMR_LAMBDA = settings.mmr_lambda
        ARISConfig.DEFAULT_SEARCH_MODE = settings.search_mode
        ARISConfig.DEFAULT_SEMANTIC_WEIGHT = settings.semantic_weight
        ARISConfig.DEFAULT_KEYWORD_WEIGHT = settings.keyword_weight
        
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating retrieval settings: {str(e)}")
