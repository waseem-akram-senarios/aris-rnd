"""
ARIS RAG MCP Server - FastMCP Implementation (Accuracy-Optimized)

This module provides an MCP (Model Context Protocol) server that exposes two tools
for interacting with the ARIS RAG system:
- rag_ingest: Adds content to the RAG system for indexing
- rag_search: Queries the RAG system with optional metadata filtering

ACCURACY FEATURES:
- Hybrid search (semantic + keyword)
- FlashRank reranking for precision
- Agentic RAG with query decomposition
- Cross-language support with auto-translation
- Confidence scoring for results

Usage:
    # Start the server
    python mcp_server.py

    # Or run with uvicorn for production
    uvicorn mcp_server:mcp --host 0.0.0.0 --port 8001
"""

import os
import re
import io
import logging
import tempfile
import hashlib
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import FastMCP
try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "FastMCP is not installed. Install it with: pip install fastmcp"
    )

# Import ARIS RAG components
from shared.config.settings import ARISConfig
from shared.utils.s3_service import S3Service
from services.ingestion.engine import IngestionEngine
from services.ingestion.parsers.parser_factory import ParserFactory
from storage.document_registry import DocumentRegistry

# Initialize the MCP server
mcp = FastMCP(
    name="ARIS RAG MCP Server",
    instructions="""MCP server for ARIS RAG system - document ingestion and semantic search.

ACCURACY FEATURES:
- Hybrid search combining semantic (vector) and keyword (BM25) search
- FlashRank cross-encoder reranking for precision
- Agentic RAG with automatic query decomposition for complex questions
- Multi-language support with auto-translation
- Confidence scores for result quality assessment

TOOLS:
1. rag_ingest - Add documents (text or S3 URI) with metadata
2. rag_search - Query with filters, returns ranked results with confidence scores
"""
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_s3_uri(content: str) -> bool:
    """Check if the content is an S3 URI."""
    if not content:
        return False
    content = content.strip()
    return content.startswith("s3://") or content.startswith("s3a://")


def parse_s3_uri(uri: str) -> tuple:
    """
    Parse an S3 URI into bucket and key components.
    
    Args:
        uri: S3 URI (e.g., s3://bucket-name/path/to/file.pdf)
        
    Returns:
        Tuple of (bucket_name, key)
        
    Raises:
        ValueError: If URI is invalid
    """
    uri = uri.strip()
    if uri.startswith("s3://"):
        path = uri[5:]
    elif uri.startswith("s3a://"):
        path = uri[6:]
    else:
        raise ValueError(f"Invalid S3 URI format: {uri}")
    
    if "/" not in path:
        raise ValueError(f"Invalid S3 URI - missing key: {uri}")
    
    parts = path.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    
    if not bucket:
        raise ValueError(f"Invalid S3 URI - empty bucket name: {uri}")
    if not key:
        raise ValueError(f"Invalid S3 URI - empty key: {uri}")
    
    return bucket, key


def get_file_extension(filename: str) -> str:
    """Get the file extension from a filename."""
    if not filename:
        return ""
    _, ext = os.path.splitext(filename.lower())
    return ext.lstrip(".")


def generate_document_id(content: str, source: str = None) -> str:
    """Generate a unique document ID based on content hash."""
    hash_input = content[:10000] if len(content) > 10000 else content
    if source:
        hash_input += source
    content_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"doc-{timestamp}-{content_hash}"


def convert_language_code(lang: str) -> str:
    """Convert ISO 639-1 (2-letter) to ISO 639-3 (3-letter) language codes."""
    if not lang or len(lang) == 3:
        return lang
    
    lang_map = {
        "en": "eng", "es": "spa", "de": "deu", "fr": "fra",
        "it": "ita", "pt": "por", "ru": "rus", "ja": "jpn",
        "ko": "kor", "zh": "zho", "ar": "ara", "nl": "nld",
        "pl": "pol", "tr": "tur", "vi": "vie", "th": "tha"
    }
    return lang_map.get(lang.lower(), lang)


def fetch_and_parse_s3_document(s3_uri: str, language: str = "eng") -> tuple:
    """
    Fetch a document from S3 and parse it.
    
    Args:
        s3_uri: S3 URI pointing to the document
        language: Language code for OCR (default: "eng")
        
    Returns:
        Tuple of (text, metadata, filename)
        
    Raises:
        ValueError: If S3 URI is invalid or document cannot be parsed
    """
    bucket, key = parse_s3_uri(s3_uri)
    filename = os.path.basename(key)
    extension = get_file_extension(filename)
    
    # Supported formats
    supported_formats = {"pdf", "docx", "doc", "txt", "md", "html", "htm"}
    if extension not in supported_formats:
        raise ValueError(
            f"Unsupported document format: .{extension}. "
            f"Supported formats: {', '.join(supported_formats)}"
        )
    
    # Initialize S3 service with the specific bucket
    s3_service = S3Service(bucket_name=bucket)
    
    if not s3_service.enabled:
        raise ValueError(
            "S3 service is not configured. Please set AWS credentials in environment."
        )
    
    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        success = s3_service.download_file(key, tmp_path)
        if not success:
            raise ValueError(f"Failed to download file from S3: {s3_uri}")
        
        # Read file content
        with open(tmp_path, "rb") as f:
            file_content = f.read()
        
        # Parse document based on type
        if extension == "txt":
            text = file_content.decode("utf-8", errors="replace")
            metadata = {
                "source": filename,
                "s3_uri": s3_uri,
                "file_type": "txt",
                "parser_used": "text"
            }
        elif extension in {"md", "html", "htm"}:
            text = file_content.decode("utf-8", errors="replace")
            metadata = {
                "source": filename,
                "s3_uri": s3_uri,
                "file_type": extension,
                "parser_used": "text"
            }
        else:
            # Use parser factory for PDF, DOCX, etc.
            parsed = ParserFactory.parse_with_fallback(
                file_path=tmp_path,
                file_content=file_content,
                preferred_parser="auto",
                language=language
            )
            text = parsed.text
            metadata = {
                "source": filename,
                "s3_uri": s3_uri,
                "file_type": extension,
                "pages": parsed.pages,
                "parser_used": parsed.parser_used,
                "images_detected": parsed.images_detected,
                "image_count": parsed.image_count,
                "confidence": parsed.confidence,
                **parsed.metadata
            }
        
        return text, metadata, filename
        
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def calculate_confidence_score(rank: int, total: int, rerank_score: float = None) -> float:
    """
    Calculate confidence score for a search result.
    
    Args:
        rank: Position in results (0-indexed)
        total: Total number of results
        rerank_score: Optional reranking score from FlashRank
        
    Returns:
        Confidence score between 0 and 100
    """
    if rerank_score is not None:
        # FlashRank scores are typically 0-1, convert to percentage
        return min(100.0, max(0.0, rerank_score * 100))
    
    # Fallback: position-based scoring with decay
    if total == 0:
        return 0.0
    
    # Exponential decay based on position
    base_score = 100.0
    decay_rate = 0.15  # 15% decay per position
    position_score = base_score * (1 - decay_rate) ** rank
    
    return round(max(0.0, min(100.0, position_score)), 1)


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
def rag_ingest(
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add content to the RAG system for indexing with high accuracy parsing.
    
    This tool ingests content into the RAG vector database. The content can be:
    - Plain text: Raw text data to be indexed directly
    - S3 URI: A URI pointing to a document in S3 (e.g., s3://bucket/path/to/file.pdf)
    
    When an S3 URI is provided, the document is automatically fetched and parsed
    using the best available parser (Docling for accuracy, PyMuPDF for speed).
    
    ACCURACY FEATURES:
    - Automatic parser selection for optimal text extraction
    - Token-aware chunking (512 tokens, 128 overlap) for better retrieval
    - Page-level metadata for accurate citations
    - OCR support for scanned documents
    
    Supported formats for S3 documents: PDF, DOCX, DOC, TXT, MD, HTML
    
    Args:
        content: Raw text data OR an S3 URI pointing to a document.
                For S3, use format: s3://bucket-name/path/to/document.pdf
        metadata: Optional key-value pairs for categorization. Examples:
                 - language: Document language code (e.g., "en", "es", "de")
                 - domain: Content domain (e.g., "ticket", "machine_manual", "policy")
                 - source: Identifier for origin system
                 - Any custom fields as needed
    
    Returns:
        Dictionary containing:
        - success: Whether ingestion was successful
        - document_id: Unique identifier for the ingested document
        - chunks_created: Number of chunks created
        - tokens_added: Approximate token count
        - message: Status message
        - metadata: The metadata attached to the document
        - accuracy_info: Information about parsing quality
    
    Raises:
        ValueError: If content is empty, S3 URI is invalid, or format is unsupported
    
    Examples:
        # Ingest plain text
        rag_ingest(
            content="This is the content of my document...",
            metadata={"domain": "policy", "language": "en"}
        )
        
        # Ingest from S3
        rag_ingest(
            content="s3://my-bucket/documents/manual.pdf",
            metadata={"domain": "machine_manual", "language": "de"}
        )
    """
    # Validate content
    if not content or not content.strip():
        raise ValueError("Content cannot be empty")
    
    content = content.strip()
    metadata = metadata or {}
    
    # Initialize components with accuracy-optimized settings
    ingestion_engine = IngestionEngine(
        use_cerebras=ARISConfig.USE_CEREBRAS,
        embedding_model=ARISConfig.EMBEDDING_MODEL,
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
        chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,  # 512 tokens for accuracy
        chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP  # 128 overlap for context
    )
    
    document_registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
    
    accuracy_info = {
        "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
        "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP,
        "embedding_model": ARISConfig.EMBEDDING_MODEL
    }
    
    try:
        # Check if content is an S3 URI
        if is_s3_uri(content):
            logger.info(f"Detected S3 URI: {content}")
            
            # Get language from metadata for OCR
            language = metadata.get("language", "eng")
            language = convert_language_code(language)
            
            # Fetch and parse the S3 document
            text, doc_metadata, filename = fetch_and_parse_s3_document(content, language)
            
            # Merge user metadata with document metadata
            final_metadata = {**doc_metadata, **metadata}
            final_metadata["s3_uri"] = content
            final_metadata["source"] = filename
            
            # Add accuracy info
            accuracy_info["parser_used"] = doc_metadata.get("parser_used", "unknown")
            accuracy_info["extraction_confidence"] = doc_metadata.get("confidence", 0.0)
            accuracy_info["pages_extracted"] = doc_metadata.get("pages", 0)
            
            if not text or not text.strip():
                raise ValueError(f"No text could be extracted from document: {content}")
            
        else:
            # Plain text content
            text = content
            filename = metadata.get("source", "text_input")
            final_metadata = {
                "source": filename,
                "content_type": "text",
                **metadata
            }
            accuracy_info["parser_used"] = "direct_text"
            accuracy_info["extraction_confidence"] = 1.0
        
        # Detect language if not specified
        if "language" not in final_metadata:
            try:
                from langdetect import detect
                detected_lang = detect(text[:1000])
                final_metadata["language"] = convert_language_code(detected_lang)
                accuracy_info["language_detected"] = True
            except:
                final_metadata["language"] = "eng"
                accuracy_info["language_detected"] = False
        
        # Generate document ID
        document_id = generate_document_id(text, final_metadata.get("source"))
        final_metadata["document_id"] = document_id
        
        # Determine index name
        index_name = metadata.get("index_name") or ARISConfig.AWS_OPENSEARCH_INDEX
        
        # Process and ingest the document
        logger.info(f"Ingesting document: {document_id} ({len(text)} chars)")
        
        result = ingestion_engine.add_documents_incremental(
            texts=[text],
            metadatas=[final_metadata],
            index_name=index_name
        )
        
        # Register the document
        registry_entry = {
            "document_id": document_id,
            "document_name": final_metadata.get("source", filename),
            "status": "completed",
            "chunks_created": result.get("chunks_created", 0),
            "tokens_extracted": result.get("tokens_added", 0),
            "language": final_metadata.get("language", "eng"),
            "metadata": final_metadata,
            "accuracy_info": accuracy_info,
            "ingested_at": datetime.now().isoformat()
        }
        document_registry.add_document(document_id, registry_entry)
        
        return {
            "success": True,
            "document_id": document_id,
            "chunks_created": result.get("chunks_created", 0),
            "tokens_added": result.get("tokens_added", 0),
            "total_chunks": result.get("total_chunks", 0),
            "message": f"Successfully ingested document with {result.get('chunks_created', 0)} chunks",
            "metadata": final_metadata,
            "accuracy_info": accuracy_info
        }
        
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to ingest content: {str(e)}")


@mcp.tool()
def rag_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 10,
    search_mode: str = "hybrid",
    use_agentic_rag: bool = True,
    include_answer: bool = True
) -> Dict[str, Any]:
    """
    Query the RAG system with high-accuracy retrieval and answer generation.
    
    This tool searches the RAG vector database using multiple accuracy-enhancing
    techniques to provide the most relevant results.
    
    ACCURACY FEATURES:
    - Hybrid Search: Combines semantic (vector) and keyword (BM25) search
    - FlashRank Reranking: Cross-encoder reranking for precision
    - Agentic RAG: Automatic query decomposition for complex questions
    - Confidence Scores: Each result includes a confidence percentage
    - Cross-language Support: Auto-translates queries for better matching
    
    Args:
        query: The search query/prompt. Should be a clear question or description
               of what you're looking for. Works best with specific questions.
        filters: Optional metadata constraints to narrow results. Examples:
                - {"domain": "ticket"} - Only search ticket-related content
                - {"language": "en"} - Only search English documents
                - {"source": "manual.pdf"} - Only search a specific document
                Can combine multiple filters: {"domain": "policy", "language": "es"}
        k: Number of results to return (default: 10, max: 50)
        search_mode: Search strategy (default: "hybrid" for best accuracy)
                    - "hybrid": Combined semantic + keyword (recommended)
                    - "semantic": Pure vector similarity search
                    - "keyword": Pure BM25 text matching
        use_agentic_rag: Enable query decomposition for complex questions (default: True)
                        Breaks complex queries into sub-queries for better coverage.
        include_answer: Generate an LLM-synthesized answer (default: True)
    
    Returns:
        Dictionary containing:
        - success: Whether search was successful
        - query: The original query
        - answer: LLM-generated answer (if include_answer=True)
        - results: List of ranked results, each with:
            - content: The text content of the chunk
            - snippet: Brief excerpt
            - source: Source document name
            - page: Page number (if available)
            - confidence: Relevance score (0-100, higher is better)
            - metadata: All metadata associated with the chunk
        - total_results: Number of results returned
        - search_mode: The search mode used
        - accuracy_info: Details about search accuracy settings
    
    Raises:
        ValueError: If query is empty
    
    Examples:
        # Basic search with answer
        rag_search(query="How do I reset the machine?")
        
        # Search without answer generation (faster)
        rag_search(query="error codes", include_answer=False)
        
        # Search with domain filter
        rag_search(
            query="What is the warranty policy?",
            filters={"domain": "policy"}
        )
        
        # Complex question with Agentic RAG
        rag_search(
            query="Compare the maintenance procedures for Model X and Model Y",
            use_agentic_rag=True
        )
        
        # Precise keyword search
        rag_search(
            query="ERR-5042",
            search_mode="keyword",
            use_agentic_rag=False
        )
    """
    # Validate query
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    
    query = query.strip()
    filters = filters or {}
    k = min(max(1, k), 50)  # Clamp k between 1 and 50
    
    # Validate search mode
    valid_modes = {"semantic", "keyword", "hybrid"}
    if search_mode not in valid_modes:
        search_mode = "hybrid"
    
    # Import retrieval engine
    from services.retrieval.engine import RetrievalEngine
    
    try:
        # Initialize retrieval engine with accuracy settings
        retrieval_engine = RetrievalEngine(
            use_cerebras=ARISConfig.USE_CEREBRAS,
            embedding_model=ARISConfig.EMBEDDING_MODEL,
            vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Build active sources filter if source is specified
        active_sources = None
        if "source" in filters:
            source_filter = filters.pop("source")
            if isinstance(source_filter, str):
                active_sources = [source_filter]
            elif isinstance(source_filter, list):
                active_sources = source_filter
        
        # Get language filter and convert if needed
        filter_language = filters.pop("language", None)
        if filter_language:
            filter_language = convert_language_code(filter_language)
        
        # Accuracy settings
        use_hybrid = search_mode == "hybrid"
        semantic_weight = ARISConfig.DEFAULT_SEMANTIC_WEIGHT if use_hybrid else (1.0 if search_mode == "semantic" else 0.0)
        
        # Retrieve more chunks initially for reranking
        retrieval_k = min(k * 3, ARISConfig.DEFAULT_RETRIEVAL_K)  # Get 3x for reranking
        
        accuracy_info = {
            "search_mode": search_mode,
            "semantic_weight": semantic_weight,
            "keyword_weight": 1.0 - semantic_weight if use_hybrid else (0.0 if search_mode == "semantic" else 1.0),
            "reranking_enabled": ARISConfig.ENABLE_RERANKING,
            "agentic_rag_enabled": use_agentic_rag,
            "retrieval_k": retrieval_k,
            "final_k": k,
            "auto_translate": ARISConfig.ENABLE_AUTO_TRANSLATE
        }
        
        logger.info(f"Searching RAG: query='{query[:50]}...', mode={search_mode}, k={k}, agentic={use_agentic_rag}")
        
        # Execute search with all accuracy features
        if include_answer:
            # Full RAG query with answer generation
            result = retrieval_engine.query_with_rag(
                question=query,
                k=retrieval_k,
                use_mmr=ARISConfig.DEFAULT_USE_MMR,
                active_sources=active_sources,
                use_hybrid_search=use_hybrid,
                semantic_weight=semantic_weight,
                search_mode=search_mode,
                use_agentic_rag=use_agentic_rag,
                temperature=ARISConfig.DEFAULT_TEMPERATURE,
                max_tokens=ARISConfig.DEFAULT_MAX_TOKENS,
                filter_language=filter_language,
                auto_translate=ARISConfig.ENABLE_AUTO_TRANSLATE
            )
        else:
            # Chunks-only retrieval (faster, no LLM call)
            result = {
                "answer": "",
                "citations": retrieval_engine._retrieve_chunks_for_query(
                    query=query,
                    k=retrieval_k,
                    use_mmr=ARISConfig.DEFAULT_USE_MMR,
                    use_hybrid_search=use_hybrid,
                    semantic_weight=semantic_weight,
                    keyword_weight=1.0 - semantic_weight,
                    search_mode=search_mode,
                    active_sources=active_sources,
                    filter_language=filter_language
                ) if hasattr(retrieval_engine, '_retrieve_chunks_for_query') else []
            }
        
        # Format results with confidence scores
        formatted_results = []
        citations = result.get("citations", [])
        
        # Handle different citation formats
        if citations and hasattr(citations[0], 'page_content'):
            # Raw Document objects from retrieval
            for i, doc in enumerate(citations[:k]):
                metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                rerank_score = metadata.get('rerank_score')
                
                chunk_result = {
                    "content": doc.page_content,
                    "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "source": metadata.get("source", "unknown"),
                    "page": metadata.get("page", 1),
                    "confidence": calculate_confidence_score(i, len(citations), rerank_score),
                    "metadata": {k: v for k, v in metadata.items() if k not in {"page_content"}}
                }
                formatted_results.append(chunk_result)
        else:
            # Citation dictionaries
            for i, citation in enumerate(citations[:k]):
                if isinstance(citation, dict):
                    rerank_score = citation.get("rerank_score") or citation.get("similarity_score")
                    
                    chunk_result = {
                        "content": citation.get("full_text", citation.get("snippet", "")),
                        "snippet": citation.get("snippet", "")[:200],
                        "source": citation.get("source", "unknown"),
                        "page": citation.get("page", 1),
                        "confidence": calculate_confidence_score(i, len(citations), rerank_score),
                        "metadata": {
                            k: v for k, v in citation.items() 
                            if k not in {"full_text", "snippet", "source", "page", "rerank_score", "similarity_score"}
                        }
                    }
                else:
                    # Handle object-style citation
                    rerank_score = getattr(citation, "rerank_score", None) or getattr(citation, "similarity_score", None)
                    
                    chunk_result = {
                        "content": getattr(citation, "full_text", getattr(citation, "snippet", "")),
                        "snippet": getattr(citation, "snippet", "")[:200],
                        "source": getattr(citation, "source", "unknown"),
                        "page": getattr(citation, "page", 1),
                        "confidence": calculate_confidence_score(i, len(citations), rerank_score),
                        "metadata": {}
                    }
                
                # Apply additional metadata filters if any remain
                if filters:
                    chunk_metadata = chunk_result.get("metadata", {})
                    match = all(
                        chunk_metadata.get(fk) == fv 
                        for fk, fv in filters.items()
                    )
                    if not match:
                        continue
                
                formatted_results.append(chunk_result)
        
        # Get the LLM-generated answer
        answer = result.get("answer", "")
        
        # Add query analysis info if available
        if use_agentic_rag:
            sub_queries = result.get("sub_queries", [])
            if sub_queries:
                accuracy_info["sub_queries_generated"] = len(sub_queries)
                accuracy_info["sub_queries"] = sub_queries
        
        return {
            "success": True,
            "query": query,
            "answer": answer if include_answer else None,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "search_mode": search_mode,
            "filters_applied": filters,
            "accuracy_info": accuracy_info,
            "message": f"Found {len(formatted_results)} relevant results" + (f" with synthesized answer" if include_answer and answer else "")
        }
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}", exc_info=True)
        raise ValueError(f"Search failed: {str(e)}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    
    # Determine transport mode from environment
    transport = os.getenv("MCP_TRANSPORT", "sse")  # Default to SSE for production
    
    logger.info(f"Starting ARIS RAG MCP Server on {host}:{port}")
    logger.info("Available tools: rag_ingest, rag_search")
    logger.info(f"Transport: {transport}")
    logger.info(f"Accuracy features: Hybrid Search, FlashRank Reranking, Agentic RAG")
    
    # Run the MCP server with appropriate transport
    if transport == "stdio":
        # For local CLI/agent usage
        mcp.run(transport="stdio")
    else:
        # For production HTTP/SSE mode
        mcp.run(transport="sse", host=host, port=port)
