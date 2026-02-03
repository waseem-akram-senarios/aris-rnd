"""
MCP Engine - Core logic for MCP server operations

This module contains the MCPEngine class that provides the core functionality
for document ingestion and semantic search, used by the MCP server tools.

REFACTORED: Now uses HTTP calls to existing Ingestion/Retrieval microservices
instead of creating duplicate engine instances. This reduces memory usage and
ensures consistent caching across all services.
"""

import os
import re
import io
import logging
import tempfile
import hashlib
import time as time_module
from typing import Optional, Dict, Any, List
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE URLs - Use existing microservices instead of duplicate engines
# ============================================================================
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://ingestion:8501")
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://retrieval:8502")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8500")

# HTTP client with connection pooling for efficiency
_http_client = None

def _get_http_client():
    """Get or create HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        import httpx
        _http_client = httpx.Client(
            timeout=httpx.Timeout(300.0, connect=10.0),  # 5 min timeout for long queries
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        logger.info("✅ HTTP client initialized for MCP service calls")
    return _http_client


def _get_cached_document_registry():
    """Get or create cached document registry (singleton)."""
    from shared.config.settings import ARISConfig
    from storage.document_registry import DocumentRegistry
    
    # Use a simple module-level cache
    if not hasattr(_get_cached_document_registry, '_registry'):
        _get_cached_document_registry._registry = DocumentRegistry(
            ARISConfig.DOCUMENT_REGISTRY_PATH
        )
        logger.info("✅ DocumentRegistry initialized (cached)")
    
    return _get_cached_document_registry._registry


class MCPEngine:
    """
    Core engine for MCP server operations.
    
    Provides high-accuracy document ingestion and search capabilities
    by calling existing Ingestion and Retrieval microservices via HTTP.
    
    REFACTORED: No longer creates duplicate engine instances. Instead, uses
    HTTP calls to existing services for:
    - Shared query cache (faster repeated queries)
    - Lower memory usage (single engine instance)
    - Consistent behavior across all entry points
    """
    
    def __init__(self):
        """Initialize the MCP Engine with HTTP client for service calls."""
        from shared.config.settings import ARISConfig
        self.config = ARISConfig
        self._http_client = None
        logger.info("✅ MCPEngine initialized (using HTTP calls to existing services)")
    
    @property
    def http_client(self):
        """Get HTTP client for service calls."""
        return _get_http_client()
    
    @property
    def document_registry(self):
        """Get cached document registry (singleton)."""
        return _get_cached_document_registry()
    
    @property
    def sync_manager(self):
        """Get sync manager for MCP service."""
        from shared.utils.sync_manager import get_sync_manager
        return get_sync_manager("mcp")
    
    def _call_ingestion_service(self, endpoint: str, data: Dict[str, Any], files: Dict = None) -> Dict[str, Any]:
        """Call the Ingestion microservice via HTTP."""
        url = f"{INGESTION_SERVICE_URL}{endpoint}"
        try:
            if files:
                response = self.http_client.post(url, data=data, files=files)
            else:
                response = self.http_client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ingestion service call failed: {e}")
            raise ValueError(f"Ingestion service error: {str(e)}")
    
    def _call_retrieval_service(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call the Retrieval microservice via HTTP."""
        url = f"{RETRIEVAL_SERVICE_URL}{endpoint}"
        try:
            response = self.http_client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Retrieval service call failed: {e}")
            raise ValueError(f"Retrieval service error: {str(e)}")
    
    def _broadcast_sync_after_ingestion(self):
        """
        Trigger sync broadcast to all services after successful ingestion.
        This ensures all services (Gateway, Retrieval, UI) see the new document immediately.
        """
        try:
            # First, instant sync locally
            self.sync_manager.instant_sync()
            
            # Then trigger gateway to broadcast to all services
            response = self.http_client.post(f"{GATEWAY_URL}/sync/broadcast", timeout=5.0)
            if response.status_code == 200:
                logger.info("📡 [MCP] Sync broadcast triggered successfully")
                return True
            else:
                logger.warning(f"📡 [MCP] Sync broadcast returned status: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"📡 [MCP] Sync broadcast failed (non-critical): {e}")
            return False
    
    @staticmethod
    def is_s3_uri(content: str) -> bool:
        """Check if the content is an S3 URI."""
        if not content:
            return False
        content = content.strip()
        return content.startswith("s3://") or content.startswith("s3a://")
    
    @staticmethod
    def parse_s3_uri(uri: str) -> tuple:
        """Parse an S3 URI into bucket and key components."""
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
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get the file extension from a filename."""
        if not filename:
            return ""
        _, ext = os.path.splitext(filename.lower())
        return ext.lstrip(".")
    
    @staticmethod
    def generate_document_id(content: str, source: str = None) -> str:
        """Generate a unique document ID based on content hash."""
        hash_input = content[:10000] if len(content) > 10000 else content
        if source:
            hash_input += source
        content_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"doc-{timestamp}-{content_hash}"
    
    @staticmethod
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
    
    @staticmethod
    def calculate_confidence_score(rank: int, total: int, rerank_score: float = None) -> float:
        """Calculate confidence score for a search result."""
        if rerank_score is not None:
            if rerank_score > 1.0:
                return min(100.0, max(0.0, rerank_score))
            elif rerank_score > 0:
                return min(100.0, max(0.0, rerank_score * 100))
        
        if total == 0:
            return 0.0
        
        base_score = 95.0
        decay_rate = 0.08
        position_score = base_score * (1 - decay_rate) ** rank
        
        return round(max(5.0, min(100.0, position_score)), 1)
    
    def fetch_and_parse_s3_document(self, s3_uri: str, language: str = "eng") -> tuple:
        """Fetch a document from S3 and parse it."""
        from shared.utils.s3_service import S3Service
        from services.ingestion.parsers.parser_factory import ParserFactory
        
        bucket, key = self.parse_s3_uri(s3_uri)
        filename = os.path.basename(key)
        extension = self.get_file_extension(filename)
        
        supported_formats = {"pdf", "docx", "doc", "txt", "md", "html", "htm"}
        if extension not in supported_formats:
            raise ValueError(
                f"Unsupported document format: .{extension}. "
                f"Supported formats: {', '.join(supported_formats)}"
            )
        
        s3_service = S3Service(bucket_name=bucket)
        
        if not s3_service.enabled:
            raise ValueError("S3 service is not configured. Please set AWS credentials.")
        
        with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            success = s3_service.download_file(key, tmp_path)
            if not success:
                raise ValueError(f"Failed to download file from S3: {s3_uri}")
            
            with open(tmp_path, "rb") as f:
                file_content = f.read()
            
            if extension == "txt":
                text = file_content.decode("utf-8", errors="replace")
                metadata = {"source": filename, "s3_uri": s3_uri, "file_type": "txt", "parser_used": "text"}
            elif extension in {"md", "html", "htm"}:
                text = file_content.decode("utf-8", errors="replace")
                metadata = {"source": filename, "s3_uri": s3_uri, "file_type": extension, "parser_used": "text"}
            else:
                parsed = ParserFactory.parse_with_fallback(
                    file_path=tmp_path, file_content=file_content,
                    preferred_parser="auto", language=language
                )
                text = parsed.text
                metadata = {
                    "source": filename, "s3_uri": s3_uri, "file_type": extension,
                    "pages": parsed.pages, "parser_used": parsed.parser_used,
                    "images_detected": parsed.images_detected, "image_count": parsed.image_count,
                    "confidence": parsed.confidence, **parsed.metadata
                }
            
            return text, metadata, filename
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    @staticmethod
    def is_base64(content: str) -> bool:
        """Check if content appears to be base64 encoded."""
        import base64
        if not content or len(content) < 8:
            return False
        
        clean_content = content.replace('\n', '').replace('\r', '').replace(' ', '')
        
        plain_text_indicators = [
            ' the ', ' is ', ' a ', ' an ', ' to ', ' and ', ' of ', ' in ',
            '. ', ', ', '! ', '? ', ': ', '; ', '\n\n', '  ',
        ]
        lower_content = content.lower()
        for indicator in plain_text_indicators:
            if indicator in lower_content:
                return False
        
        base64_pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
        if not base64_pattern.match(clean_content):
            return False
        
        if len(clean_content) % 4 != 0:
            return False
        
        try:
            base64.b64decode(clean_content)
            return True
        except Exception:
            return False
    
    def parse_uploaded_document(self, file_content: bytes, filename: str, language: str = "eng") -> tuple:
        """Parse an uploaded document from bytes."""
        from services.ingestion.parsers.parser_factory import ParserFactory
        
        extension = self.get_file_extension(filename)
        supported_formats = {"pdf", "docx", "doc", "txt", "md", "html", "htm"}
        if extension not in supported_formats:
            raise ValueError(f"Unsupported document format: .{extension}")
        
        with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            if extension == "txt":
                text = file_content.decode("utf-8", errors="replace")
                metadata = {"source": filename, "file_type": "txt", "parser_used": "text", "upload_method": "direct"}
            elif extension in {"md", "html", "htm"}:
                text = file_content.decode("utf-8", errors="replace")
                metadata = {"source": filename, "file_type": extension, "parser_used": "text", "upload_method": "direct"}
            else:
                parsed = ParserFactory.parse_with_fallback(
                    file_path=tmp_path, file_content=file_content,
                    preferred_parser="auto", language=language
                )
                text = parsed.text
                metadata = {
                    "source": filename, "file_type": extension, "pages": parsed.pages,
                    "parser_used": parsed.parser_used, "images_detected": parsed.images_detected,
                    "image_count": parsed.image_count, "confidence": parsed.confidence,
                    "upload_method": "direct", **parsed.metadata
                }
            
            return text, metadata
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def upload_document(self, file_content: str, filename: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload and ingest a document via HTTP call to Ingestion microservice.
        
        REFACTORED: Calls existing Ingestion service instead of duplicate engine.
        """
        import base64
        
        if not file_content or not file_content.strip():
            raise ValueError("File content cannot be empty")
        if not filename or not filename.strip():
            raise ValueError("Filename is required")
        
        filename = filename.strip()
        extension = self.get_file_extension(filename)
        metadata = metadata or {}
        
        supported_formats = {"pdf", "docx", "doc", "txt", "md", "html", "htm"}
        if extension not in supported_formats:
            raise ValueError(f"Unsupported document format: .{extension}")
        
        try:
            # Prepare file bytes
            binary_formats = {"pdf", "docx", "doc"}
            if extension in binary_formats:
                clean_content = file_content.replace('\n', '').replace('\r', '').replace(' ', '')
                file_bytes = base64.b64decode(clean_content)
            else:
                if self.is_base64(file_content):
                    try:
                        clean_content = file_content.replace('\n', '').replace('\r', '').replace(' ', '')
                        file_bytes = base64.b64decode(clean_content)
                    except:
                        file_bytes = file_content.encode("utf-8")
                else:
                    file_bytes = file_content.encode("utf-8")
            
            logger.info(f"📤 MCP Upload (via Ingestion service): {filename} ({len(file_bytes)} bytes)")
            
            # Call Ingestion microservice via HTTP with file upload
            files = {"file": (filename, io.BytesIO(file_bytes), "application/octet-stream")}
            form_data = {
                "language": metadata.get("language", "eng"),
                "parser": metadata.get("parser", "auto")
            }
            
            result = self._call_ingestion_service("/upload", form_data, files=files)
            
            # Trigger sync after successful ingestion
            sync_triggered = self._broadcast_sync_after_ingestion()
            
            return {
                "success": True,
                "document_id": result.get("document_id", ""),
                "filename": filename,
                "file_type": extension,
                "file_size_bytes": len(file_bytes),
                "chunks_created": result.get("chunks_created", 0),
                "tokens_added": result.get("tokens_extracted", 0),
                "pages_extracted": result.get("pages", 0),
                "message": result.get("message", f"Successfully uploaded '{filename}'"),
                "accuracy_info": {"via_http": True, "upload_method": "ingestion_service"},
                "sync_triggered": sync_triggered
            }
            
        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to upload document: {str(e)}")
    
    def ingest(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingest content into the RAG system via HTTP call to Ingestion microservice.
        
        REFACTORED: Calls existing Ingestion service instead of duplicate engine.
        For S3 URIs, still handles locally then calls ingestion service.
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        content = content.strip()
        metadata = metadata or {}
        
        try:
            # Handle S3 URIs - fetch and convert to text first
            if self.is_s3_uri(content):
                logger.info(f"📥 MCP Ingest: Detected S3 URI: {content}")
                
                language = metadata.get("language", "eng")
                language = self.convert_language_code(language)
                
                text, doc_metadata, filename = self.fetch_and_parse_s3_document(content, language)
                
                if not text or not text.strip():
                    raise ValueError(f"No text extracted from document: {content}")
                
                # Call ingestion service with the extracted text
                request_data = {
                    "content": text,
                    "source": filename,
                    "language": language,
                    "s3_uri": content,
                    "metadata": {**doc_metadata, **metadata}
                }
            else:
                # Plain text content
                logger.info(f"📥 MCP Ingest (via Ingestion service): {len(content)} chars")
                
                request_data = {
                    "content": content,
                    "source": metadata.get("source", "text_input"),
                    "language": metadata.get("language", "eng"),
                    "metadata": metadata
                }
            
            # Call Ingestion microservice via HTTP
            result = self._call_ingestion_service("/ingest", request_data)
            
            # Trigger sync after successful ingestion
            sync_triggered = self._broadcast_sync_after_ingestion()
            
            return {
                "success": True,
                "document_id": result.get("document_id", ""),
                "chunks_created": result.get("chunks_created", 0),
                "tokens_added": result.get("tokens_extracted", 0),
                "total_chunks": result.get("total_chunks", 0),
                "message": result.get("message", "Successfully ingested content"),
                "accuracy_info": {"via_http": True},
                "sync_triggered": sync_triggered
            }
            
        except Exception as e:
            logger.error(f"Ingestion failed: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to ingest content: {str(e)}")
    
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        k: int = 10,
        search_mode: str = "hybrid",
        use_agentic_rag: bool = True,
        include_answer: bool = True
    ) -> Dict[str, Any]:
        """
        Search the RAG system via HTTP call to Retrieval microservice.
        
        REFACTORED: Calls existing Retrieval service instead of duplicate engine.
        Benefits: Shared cache, lower memory, consistent behavior.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        query = query.strip()
        filters = filters or {}
        k = min(max(1, k), 50)
        
        valid_modes = {"semantic", "keyword", "hybrid"}
        if search_mode not in valid_modes:
            search_mode = "hybrid"
        
        try:
            search_start = time_module.time()
            
            # Build request for Retrieval service
            request_data = {
                "question": query,
                "k": k,
                "search_mode": search_mode,
                "use_agentic_rag": use_agentic_rag
            }
            
            # Add source filter if provided
            if "source" in filters:
                source_filter = filters.pop("source")
                if isinstance(source_filter, str):
                    request_data["sources"] = [source_filter]
                elif isinstance(source_filter, list):
                    request_data["sources"] = source_filter
            
            # Add language filter if provided
            if "language" in filters:
                request_data["filter_language"] = self.convert_language_code(filters.pop("language"))
            
            logger.info(f"🔍 MCP Search (via Retrieval service): query='{query[:50]}...', mode={search_mode}, k={k}")
            
            # Call Retrieval microservice via HTTP
            result = self._call_retrieval_service("/query", request_data)
            
            retrieval_time = time_module.time() - search_start
            logger.info(f"⏱️ Retrieval service responded in {retrieval_time:.2f}s")
            
            # Format response
            citations = result.get("citations", [])
            formatted_results = self._format_citations(citations, k)
            
            total_time = time_module.time() - search_start
            
            accuracy_info = {
                "search_mode": search_mode,
                "agentic_rag_enabled": use_agentic_rag,
                "final_k": k,
                "retrieval_time_seconds": round(retrieval_time, 2),
                "total_time_seconds": round(total_time, 2),
                "via_http": True  # Indicates using shared service
            }
            
            if use_agentic_rag:
                sub_queries = result.get("sub_queries", [])
                if sub_queries:
                    accuracy_info["sub_queries_generated"] = len(sub_queries)
                    accuracy_info["sub_queries"] = sub_queries
            
            return {
                "success": True,
                "query": query,
                "answer": result.get("answer", "") if include_answer else None,
                "results": formatted_results,
                "citations": formatted_results,
                "sources": result.get("sources", []),
                "total_results": len(formatted_results),
                "search_mode": search_mode,
                "filters_applied": filters,
                "accuracy_info": accuracy_info,
                "message": f"Found {len(formatted_results)} relevant results" + (
                    f" with synthesized answer" if include_answer and result.get("answer") else ""
                )
            }
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            raise ValueError(f"Search failed: {str(e)}")
    
    def _format_citations(self, citations: list, k: int) -> List[Dict[str, Any]]:
        """Format citations efficiently."""
        if not citations:
            return []
        
        # Sort by score
        def get_score(c):
            if isinstance(c, dict):
                sim_pct = c.get("similarity_percentage", 0)
                if sim_pct and sim_pct > 0:
                    return sim_pct / 100.0
                score = c.get("rerank_score") or c.get("similarity_score") or c.get("relevance_score") or 0
                return score / 100.0 if score > 1 else score
            elif hasattr(c, 'metadata'):
                meta = c.metadata
                sim_pct = meta.get("similarity_percentage", 0)
                if sim_pct and sim_pct > 0:
                    return sim_pct / 100.0
                return meta.get("rerank_score") or meta.get("similarity_score") or 0
            return 0
        
        citations = sorted(citations, key=get_score, reverse=True)
        
        formatted = []
        for i, citation in enumerate(citations[:k]):
            if hasattr(citation, 'page_content'):
                metadata = citation.metadata if hasattr(citation, 'metadata') else {}
                rerank_score = metadata.get('rerank_score') or metadata.get('similarity_score')
                
                formatted.append({
                    "content": citation.page_content,
                    "snippet": citation.page_content[:200] + "..." if len(citation.page_content) > 200 else citation.page_content,
                    "source": metadata.get("source", "unknown"),
                    "page": metadata.get("page", 1),
                    "confidence": self.calculate_confidence_score(i, len(citations), rerank_score),
                    "metadata": {k: v for k, v in metadata.items() if k != "page_content"}
                })
            elif isinstance(citation, dict):
                sim_pct = citation.get("similarity_percentage")
                if sim_pct and sim_pct > 0:
                    confidence = min(100.0, max(0.0, sim_pct))
                else:
                    rerank_score = citation.get("rerank_score") or citation.get("similarity_score") or citation.get("relevance_score")
                    if rerank_score and rerank_score > 1:
                        rerank_score = rerank_score / 100.0
                    confidence = self.calculate_confidence_score(i, len(citations), rerank_score)
                
                formatted.append({
                    "content": citation.get("full_text", citation.get("snippet", "")),
                    "snippet": citation.get("snippet", "")[:200],
                    "source": citation.get("source", "unknown"),
                    "page": citation.get("page", 1),
                    "confidence": confidence,
                    "metadata": {k: v for k, v in citation.items() 
                                if k not in {"full_text", "snippet", "source", "page", "rerank_score", 
                                           "similarity_score", "relevance_score", "content_relevance", "similarity_percentage"}}
                })
        
        return formatted
