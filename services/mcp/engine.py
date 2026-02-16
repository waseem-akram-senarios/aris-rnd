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

# Configurable limits (Phase 2)
MAX_SEARCH_K = int(os.getenv("MCP_MAX_SEARCH_K", "50"))
MAX_CHUNK_LIMIT = int(os.getenv("MCP_MAX_CHUNK_LIMIT", "100"))
HTTP_TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "300"))
HTTP_CONNECT_TIMEOUT = float(os.getenv("MCP_HTTP_CONNECT_TIMEOUT", "10"))
RETRY_ATTEMPTS = int(os.getenv("MCP_RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF = [1, 2, 4]  # seconds between retries


def _get_http_client():
    """Get or create HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        import httpx
        _http_client = httpx.Client(
            timeout=httpx.Timeout(HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        logger.info("✅ HTTP client initialized for MCP service calls")
    return _http_client


def _http_with_retry(client, method: str, url: str, **kwargs):
    """
    Execute an HTTP request with exponential backoff retry.
    
    Retries on connection errors and 5xx server errors.
    Does NOT retry on 4xx client errors (bad request, not found, etc.).
    """
    import httpx
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = client.request(method, url, **kwargs)
            # Don't retry client errors (4xx) — they won't succeed on retry
            if response.status_code < 500:
                return response
            # 5xx server errors — worth retrying
            last_error = Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            logger.warning(f"Retry {attempt+1}/{RETRY_ATTEMPTS} for {method} {url} (HTTP {response.status_code})")
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, ConnectionError, OSError) as e:
            last_error = e
            logger.warning(f"Retry {attempt+1}/{RETRY_ATTEMPTS} for {method} {url}: {type(e).__name__}")
        except Exception as e:
            # Non-retriable error — raise immediately
            raise

        if attempt < RETRY_ATTEMPTS - 1:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            time_module.sleep(wait)

    raise last_error


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
        self._check_service_connectivity()
    
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
    
    def _check_service_connectivity(self):
        """Verify downstream services are reachable on startup (non-blocking)."""
        services = {
            "Ingestion": f"{INGESTION_SERVICE_URL}/health",
            "Retrieval": f"{RETRIEVAL_SERVICE_URL}/health",
            "Gateway": f"{GATEWAY_URL}/health",
        }
        for name, url in services.items():
            try:
                resp = self.http_client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    logger.info(f"  ✅ {name} service reachable at {url}")
                else:
                    logger.warning(f"  ⚠️ {name} service returned HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"  ⚠️ {name} service not reachable at {url}: {type(e).__name__}")

    def _call_ingestion_service(self, endpoint: str, data: Dict[str, Any], files: Dict = None) -> Dict[str, Any]:
        """Call the Ingestion microservice via HTTP with retry."""
        url = f"{INGESTION_SERVICE_URL}{endpoint}"
        try:
            if files:
                clean_data = {k: str(v) for k, v in data.items() if v is not None}
                response = _http_with_retry(self.http_client, "POST", url, data=clean_data, files=files)
            else:
                response = _http_with_retry(self.http_client, "POST", url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ingestion service call failed: {e}")
            raise ValueError(f"Ingestion service error: {str(e)}")
    
    def _call_retrieval_service(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call the Retrieval microservice via HTTP with retry."""
        url = f"{RETRIEVAL_SERVICE_URL}{endpoint}"
        try:
            response = _http_with_retry(self.http_client, "POST", url, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Retrieval service call failed: {e}")
            raise ValueError(f"Retrieval service error: {str(e)}")
    
    def _broadcast_sync_after_ingestion(self):
        """
        Trigger sync broadcast to all services after successful ingestion.
        
        Gateway is the sole sync coordinator. MCP syncs itself locally, then
        asks Gateway to broadcast to the other services with ?exclude=mcp
        to avoid a circular callback (Gateway would otherwise call MCP /sync/force).
        """
        try:
            # First, instant sync locally (MCP's own state)
            self.sync_manager.instant_sync()
            
            # Ask Gateway to broadcast to ingestion + retrieval (exclude MCP to break cycle)
            response = self.http_client.post(
                f"{GATEWAY_URL}/sync/broadcast?exclude=mcp",
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info("📡 [MCP] Sync broadcast triggered (self excluded)")
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
        except Exception as e:
            logger.debug(f"is_base64: {type(e).__name__}: {e}")
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
        
        REFACTORED: Calls /process endpoint on Ingestion service for synchronous processing.
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
                    except Exception as e:
                        logger.debug(f"operation: {type(e).__name__}: {e}")
                        file_bytes = file_content.encode("utf-8")
                else:
                    file_bytes = file_content.encode("utf-8")
            
            logger.info(f"📤 MCP Upload (via Ingestion service): {filename} ({len(file_bytes)} bytes)")
            
            language = metadata.get("language", "eng")
            language = self.convert_language_code(language)
            
            # Call Ingestion microservice via /process endpoint (synchronous)
            files = {"file": (filename, io.BytesIO(file_bytes), "application/octet-stream")}
            form_data = {
                "language": language,
                "parser_preference": metadata.get("parser", None)
            }
            
            result = self._call_ingestion_service("/process", form_data, files=files)
            
            # Check for processing failure in response body
            if not result.get("success", True) and result.get("error"):
                raise ValueError(result.get("error"))
            
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
                "parser_used": result.get("parser_used", ""),
                "message": result.get("message", f"Successfully uploaded '{filename}'"),
                "accuracy_info": {
                    "parser_used": result.get("parser_used"),
                    "confidence": result.get("confidence", 0),
                    "extraction_percentage": result.get("extraction_percentage", 0),
                    "processing_time": result.get("processing_time", 0),
                    "via_http": True,
                    "upload_method": "ingestion_service"
                },
                "sync_triggered": sync_triggered
            }
            
        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to upload document: {str(e)}")
    
    def _fetch_s3_bytes(self, s3_uri: str) -> tuple:
        """
        Fetch raw document bytes from S3 without parsing.
        
        Returns:
            Tuple of (file_bytes, filename, extension)
        """
        from shared.utils.s3_service import S3Service
        
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
                file_bytes = f.read()
            
            return file_bytes, filename, extension
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def ingest(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ingest content into the RAG system via HTTP call to Ingestion microservice.
        
        REFACTORED: Uses /process endpoint with multipart file upload.
        For S3 URIs, fetches raw bytes from S3 and uploads to ingestion service.
        For plain text, wraps as a .txt file and uploads.
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        content = content.strip()
        metadata = metadata or {}
        
        try:
            if self.is_s3_uri(content):
                logger.info(f"📥 MCP Ingest: Detected S3 URI: {content}")
                
                language = metadata.get("language", "eng")
                language = self.convert_language_code(language)
                
                # Fetch raw document bytes from S3
                file_bytes, filename, extension = self._fetch_s3_bytes(content)
                
                # Upload raw document to Ingestion service for proper parsing
                files = {"file": (filename, io.BytesIO(file_bytes), "application/octet-stream")}
                form_data = {
                    "language": language,
                    "parser_preference": metadata.get("parser", None)
                }
                
                result = self._call_ingestion_service("/process", form_data, files=files)
            else:
                # Plain text content - wrap as .txt file for upload
                logger.info(f"📥 MCP Ingest (via Ingestion service): {len(content)} chars")
                
                source = metadata.get("source", "text_input")
                filename = source if source.endswith('.txt') else f"{source}.txt"
                text_bytes = content.encode('utf-8')
                
                language = metadata.get("language", "eng")
                language = self.convert_language_code(language)
                
                files = {"file": (filename, io.BytesIO(text_bytes), "text/plain")}
                form_data = {
                    "language": language,
                    "parser_preference": None  # Let ingestion auto-detect for text
                }
                
                result = self._call_ingestion_service("/process", form_data, files=files)
            
            # Check for processing failure in response body
            if not result.get("success", True) and result.get("error"):
                raise ValueError(result.get("error"))
            
            # Trigger sync after successful ingestion
            sync_triggered = self._broadcast_sync_after_ingestion()
            
            return {
                "success": True,
                "document_id": result.get("document_id", ""),
                "chunks_created": result.get("chunks_created", 0),
                "tokens_added": result.get("tokens_extracted", 0),
                "pages": result.get("pages", 0),
                "parser_used": result.get("parser_used", ""),
                "message": result.get("message", "Successfully ingested content"),
                "accuracy_info": {
                    "parser_used": result.get("parser_used"),
                    "confidence": result.get("confidence", 0),
                    "extraction_percentage": result.get("extraction_percentage", 0),
                    "processing_time": result.get("processing_time", 0),
                    "via_http": True
                },
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
        include_answer: bool = True,
        response_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search the RAG system via HTTP call to Retrieval microservice.
        
        REFACTORED: Calls existing Retrieval service instead of duplicate engine.
        Benefits: Shared cache, lower memory, consistent behavior.
        
        Args:
            response_language: Explicit language for the answer (e.g. "English", "Spanish").
                If not set, defaults to "English" to prevent auto-detection errors
                on short queries.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        query = query.strip()
        filters = dict(filters) if filters else {}  # Copy to avoid mutating caller's dict
        k = min(max(1, k), MAX_SEARCH_K)
        
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
            
            # Explicit response language — prevents langdetect misidentifying
            # short English queries as Swedish, Norwegian, etc.
            if response_language:
                request_data["response_language"] = response_language
            else:
                # Default to English for MCP API consumers (AI agents, Streamlit UI)
                request_data["response_language"] = "English"
            
            # Add source filter if provided
            if "source" in filters:
                source_filter = filters.pop("source")
                if isinstance(source_filter, str):
                    request_data["active_sources"] = [source_filter]
                elif isinstance(source_filter, list):
                    request_data["active_sources"] = source_filter
            
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
    
    # ========================================================================
    # CRUD OPERATIONS - Document Management
    # ========================================================================
    
    def list_documents(self) -> Dict[str, Any]:
        """
        List all documents in the RAG system via Gateway service.
        """
        url = f"{GATEWAY_URL}/documents"
        try:
            response = _http_with_retry(self.http_client, "GET", url)
            response.raise_for_status()
            data = response.json()
            
            documents = data.get("documents", [])
            
            # Format documents for clear MCP response
            formatted_docs = []
            for doc in documents:
                formatted_docs.append({
                    "document_id": doc.get("document_id", ""),
                    "document_name": doc.get("document_name", ""),
                    "status": doc.get("status", "unknown"),
                    "chunks_created": doc.get("chunks_created", 0),
                    "images_stored": doc.get("images_stored", 0),
                    "language": doc.get("language", ""),
                    "text_index": doc.get("text_index", ""),
                    "images_index": doc.get("images_index", ""),
                    "created_at": doc.get("created_at", ""),
                    "updated_at": doc.get("updated_at", ""),
                    "metadata": doc.get("metadata", {})
                })
            
            return {
                "success": True,
                "documents": formatted_docs,
                "total": data.get("total", len(formatted_docs)),
                "total_chunks": data.get("total_chunks", 0),
                "total_images": data.get("total_images", 0),
                "message": f"Found {len(formatted_docs)} documents in the system"
            }
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise ValueError(f"Failed to list documents: {str(e)}")
    
    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific document by ID.
        """
        if not document_id or not document_id.strip():
            raise ValueError("document_id is required")
        
        document_id = document_id.strip()
        url = f"{GATEWAY_URL}/documents/{document_id}"
        try:
            response = _http_with_retry(self.http_client, "GET", url)
            response.raise_for_status()
            doc = response.json()
            
            return {
                "success": True,
                "document": {
                    "document_id": doc.get("document_id", ""),
                    "document_name": doc.get("document_name", ""),
                    "status": doc.get("status", "unknown"),
                    "chunks_created": doc.get("chunks_created", 0),
                    "images_stored": doc.get("images_stored", 0),
                    "language": doc.get("language", ""),
                    "text_index": doc.get("text_index", ""),
                    "images_index": doc.get("images_index", ""),
                    "created_at": doc.get("created_at", ""),
                    "updated_at": doc.get("updated_at", ""),
                    "metadata": doc.get("metadata", {})
                },
                "message": f"Document '{doc.get('document_name', document_id)}' retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {e}")
            raise ValueError(f"Failed to get document: {str(e)}")
    
    def update_document(self, document_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update metadata/properties of an existing document via Gateway service.
        """
        if not document_id or not document_id.strip():
            raise ValueError("document_id is required")
        if not updates:
            raise ValueError("At least one field to update must be provided")
        
        document_id = document_id.strip()
        url = f"{GATEWAY_URL}/documents/{document_id}"
        try:
            response = _http_with_retry(self.http_client, "PUT", url, json=updates)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "document_id": document_id,
                "updated_fields": list(updates.keys()),
                "document": result,
                "message": f"Document '{document_id}' updated successfully"
            }
        except Exception as e:
            logger.error(f"Failed to update document {document_id}: {e}")
            raise ValueError(f"Failed to update document: {str(e)}")
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and all its data (vectors, S3, registry) via Gateway.
        """
        if not document_id or not document_id.strip():
            raise ValueError("document_id is required")
        
        document_id = document_id.strip()
        url = f"{GATEWAY_URL}/documents/{document_id}"
        try:
            response = _http_with_retry(self.http_client, "DELETE", url)
            response.raise_for_status()
            result = response.json()
            
            # Trigger sync after deletion
            sync_triggered = self._broadcast_sync_after_ingestion()
            
            return {
                "success": result.get("success", True),
                "document_id": document_id,
                "document_name": result.get("document_name", ""),
                "vector_deleted": result.get("vector_deleted", False),
                "s3_deleted": result.get("s3_deleted", False),
                "registry_deleted": result.get("registry_deleted", False),
                "message": result.get("message", f"Document '{document_id}' deleted"),
                "sync_triggered": sync_triggered
            }
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise ValueError(f"Failed to delete document: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall system statistics.
        
        Combines:
        1. Persistent document stats from DocumentRegistry (survives restarts)
        2. Live query/cost metrics from Gateway (ephemeral, reset on restart)
        """
        # ----- 1. Persistent processing stats from DocumentRegistry -----
        processing_stats = {}
        try:
            docs = self.document_registry.list_documents()
            if docs:
                total_documents = len(docs)
                total_chunks = sum(d.get("chunks_created", 0) for d in docs)
                total_images = sum(d.get("images_stored", 0) for d in docs)
                total_pages = sum(d.get("pages", d.get("pages_extracted", 0)) or 0 for d in docs)
                
                # Compute language distribution
                lang_dist = {}
                for d in docs:
                    lang = d.get("language", "unknown") or "unknown"
                    lang_dist[lang] = lang_dist.get(lang, 0) + 1
                
                processing_stats = {
                    "total_documents": total_documents,
                    "total_chunks": total_chunks,
                    "total_pages": total_pages,
                    "total_images": total_images,
                    "language_distribution": lang_dist,
                }
        except Exception as e:
            logger.warning(f"Could not compute processing stats from registry: {e}")
        
        # ----- 2. Live metrics from Gateway (queries, costs) -----
        gateway_stats = {}
        try:
            response = _http_with_retry(self.http_client, "GET", f"{GATEWAY_URL}/stats")
            response.raise_for_status()
            gateway_stats = response.json()
        except Exception as e:
            logger.warning(f"Could not fetch gateway stats: {e}")
        
        # Merge: prefer our persistent processing stats over Gateway's ephemeral ones
        queries = gateway_stats.get("queries", {})
        costs = gateway_stats.get("costs", {})
        
        # Normalise field names so UI can always read the same keys
        if queries:
            # Ensure both avg_response_time AND average_response_time exist
            art = queries.get("avg_response_time", queries.get("average_response_time", 0))
            queries["avg_response_time"] = art
            queries["average_response_time"] = art
        
        return {
            "success": True,
            "stats": {
                "processing": processing_stats,
                "queries": queries,
                "costs": costs,
                "error_summary": gateway_stats.get("error_summary", {}),
            },
            "message": "System statistics retrieved successfully"
        }
    
    # ========================================================================
    # CRUD OPERATIONS - Vector Index Management
    # ========================================================================
    
    def list_indexes(self) -> Dict[str, Any]:
        """
        List all vector indexes in the system via Retrieval service.
        """
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes"
        try:
            response = _http_with_retry(self.http_client, "GET", url)
            response.raise_for_status()
            data = response.json()
            
            indexes = data.get("indexes", [])
            formatted_indexes = []
            for idx in indexes:
                formatted_indexes.append({
                    "index_name": idx.get("index_name", ""),
                    "document_count": idx.get("document_count", 0),
                    "chunk_count": idx.get("chunk_count", 0),
                    "index_type": idx.get("index_type", ""),
                    "created_at": idx.get("created_at", ""),
                    "size_bytes": idx.get("size_bytes", 0)
                })
            
            return {
                "success": True,
                "indexes": formatted_indexes,
                "total": data.get("total", len(formatted_indexes)),
                "message": f"Found {len(formatted_indexes)} vector indexes"
            }
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            raise ValueError(f"Failed to list indexes: {str(e)}")
    
    def get_index_info(self, index_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific vector index.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        
        index_name = index_name.strip()
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}"
        try:
            response = _http_with_retry(self.http_client, "GET", url)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "index": data,
                "message": f"Index '{index_name}' info retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Failed to get index info for {index_name}: {e}")
            raise ValueError(f"Failed to get index info: {str(e)}")
    
    def delete_index(self, index_name: str) -> Dict[str, Any]:
        """
        Delete a vector index and all its chunks via Gateway to ensure registry sync.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        
        index_name = index_name.strip()
        # Route through Gateway for synchronized deletion (registry cleanup)
        url = f"{GATEWAY_URL}/admin/indexes/{index_name}"
        try:
            response = _http_with_retry(self.http_client, "DELETE", url)
            response.raise_for_status()
            result = response.json()
            
            sync_triggered = self._broadcast_sync_after_ingestion()
            
            return {
                "success": result.get("success", True),
                "index_name": index_name,
                "chunks_deleted": result.get("chunks_deleted", 0),
                "documents_removed_from_registry": result.get("documents_removed_from_registry", 0),
                "message": result.get("message", f"Index '{index_name}' deleted and registry synced"),
                "synced": result.get("synced", True),
                "sync_triggered": sync_triggered
            }
        except Exception as e:
            logger.error(f"Failed to delete index {index_name} via Gateway: {e}")
            # Fallback to direct Retrieval deletion if Gateway fails or doesn't have the endpoint yet
            logger.info(f"Attempting fallback deletion for index {index_name} via Retrieval service...")
            fallback_url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}?confirm=true"
            try:
                response = _http_with_retry(self.http_client, "DELETE", fallback_url)
                response.raise_for_status()
                result = response.json()
                
                # Trigger sync so registry knows about the deletion
                sync_triggered = self._broadcast_sync_after_ingestion()
                
                return {
                    "success": result.get("success", True),
                    "index_name": index_name,
                    "chunks_deleted": result.get("chunks_deleted", 0),
                    "message": result.get("message", f"Index '{index_name}' deleted (fallback, registry synced)"),
                    "sync_triggered": sync_triggered
                }
            except Exception as fe:
                logger.error(f"Fallback deletion failed: {fe}")
                raise ValueError(f"Failed to delete index: {str(e)}")
    
    # ========================================================================
    # CRUD OPERATIONS - Chunk-level Management
    # ========================================================================
    
    def list_chunks(self, index_name: str, source: Optional[str] = None, 
                    offset: int = 0, limit: int = 20) -> Dict[str, Any]:
        """
        List chunks in a vector index with optional filtering.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        
        index_name = index_name.strip()
        params = {"offset": offset, "limit": min(limit, MAX_CHUNK_LIMIT)}
        if source:
            params["source"] = source
        
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}/chunks"
        try:
            response = _http_with_retry(self.http_client, "GET", url, params=params)
            response.raise_for_status()
            data = response.json()
            
            chunks = data.get("chunks", [])
            formatted_chunks = []
            for chunk in chunks:
                formatted_chunks.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "text_preview": chunk.get("text", "")[:300] + ("..." if len(chunk.get("text", "")) > 300 else ""),
                    "source": chunk.get("source", ""),
                    "page": chunk.get("page", None),
                    "metadata": chunk.get("metadata", {})
                })
            
            return {
                "success": True,
                "chunks": formatted_chunks,
                "total": data.get("total", len(formatted_chunks)),
                "offset": offset,
                "limit": limit,
                "index_name": index_name,
                "message": f"Found {data.get('total', len(formatted_chunks))} chunks in index '{index_name}'"
            }
        except Exception as e:
            logger.error(f"Failed to list chunks for {index_name}: {e}")
            raise ValueError(f"Failed to list chunks: {str(e)}")
    
    def get_chunk(self, index_name: str, chunk_id: str) -> Dict[str, Any]:
        """
        Get a specific chunk by ID from a vector index.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        if not chunk_id or not chunk_id.strip():
            raise ValueError("chunk_id is required")
        
        index_name = index_name.strip()
        chunk_id = chunk_id.strip()
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}/chunks/{chunk_id}"
        try:
            response = _http_with_retry(self.http_client, "GET", url)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "chunk": {
                    "chunk_id": data.get("chunk_id", chunk_id),
                    "text": data.get("text", ""),
                    "source": data.get("source", ""),
                    "page": data.get("page", None),
                    "metadata": data.get("metadata", {})
                },
                "index_name": index_name,
                "message": f"Chunk '{chunk_id}' retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_id} from {index_name}: {e}")
            raise ValueError(f"Failed to get chunk: {str(e)}")
    
    def create_chunk(self, index_name: str, text: str, source: str = "manual_entry",
                     page: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new chunk in a vector index.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        if not text or not text.strip():
            raise ValueError("text content is required")
        
        index_name = index_name.strip()
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}/chunks"
        
        request_data = {
            "text": text.strip(),
            "index_name": index_name,
            "source": source,
            "metadata": metadata or {}
        }
        if page is not None:
            request_data["page"] = page
        
        try:
            response = _http_with_retry(self.http_client, "POST", url, json=request_data)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "chunk_id": result.get("chunk_id", ""),
                "index_name": index_name,
                "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                "source": source,
                "page": page,
                "message": result.get("message", f"Chunk created in index '{index_name}'")
            }
        except Exception as e:
            logger.error(f"Failed to create chunk in {index_name}: {e}")
            raise ValueError(f"Failed to create chunk: {str(e)}")
    
    def update_chunk(self, index_name: str, chunk_id: str, 
                     text: Optional[str] = None, page: Optional[int] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update an existing chunk in a vector index.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        if not chunk_id or not chunk_id.strip():
            raise ValueError("chunk_id is required")
        
        update_data = {}
        if text is not None:
            update_data["text"] = text.strip()
        if page is not None:
            update_data["page"] = page
        if metadata is not None:
            update_data["metadata"] = metadata
        
        if not update_data:
            raise ValueError("At least one field to update must be provided (text, page, or metadata)")
        
        index_name = index_name.strip()
        chunk_id = chunk_id.strip()
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}/chunks/{chunk_id}"
        try:
            response = _http_with_retry(self.http_client, "PUT", url, json=update_data)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "chunk_id": chunk_id,
                "index_name": index_name,
                "updated_fields": list(update_data.keys()),
                "embedding_regenerated": "text" in update_data,
                "message": result.get("message", f"Chunk '{chunk_id}' updated in index '{index_name}'")
            }
        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id} in {index_name}: {e}")
            raise ValueError(f"Failed to update chunk: {str(e)}")
    
    def delete_chunk(self, index_name: str, chunk_id: str) -> Dict[str, Any]:
        """
        Delete a specific chunk from a vector index.
        """
        if not index_name or not index_name.strip():
            raise ValueError("index_name is required")
        if not chunk_id or not chunk_id.strip():
            raise ValueError("chunk_id is required")
        
        index_name = index_name.strip()
        chunk_id = chunk_id.strip()
        url = f"{RETRIEVAL_SERVICE_URL}/admin/indexes/{index_name}/chunks/{chunk_id}"
        try:
            response = _http_with_retry(self.http_client, "DELETE", url)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "chunk_id": chunk_id,
                "index_name": index_name,
                "message": result.get("message", f"Chunk '{chunk_id}' deleted from index '{index_name}'")
            }
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id} from {index_name}: {e}")
            raise ValueError(f"Failed to delete chunk: {str(e)}")
    
    def _format_citations(self, citations: list, k: int) -> List[Dict[str, Any]]:
        """
        Format citations for MCP consumers (AI agents, Streamlit UI).
        
        ACCURACY FIX (v5): Trust the retrieval service's ranking order and
        similarity_percentage. The retrieval service uses FlashRank reranking,
        content-relevance analysis, and sophisticated score normalization.
        Re-sorting here was destroying that careful ranking. Now we preserve
        the order and use similarity_percentage directly as confidence.
        """
        if not citations:
            return []
        
        # DO NOT re-sort. The retrieval service already ranked citations using
        # FlashRank rerank_score → content relevance → similarity_score.
        # Re-sorting here was Bug #2 — it overwrote the retrieval service's
        # more sophisticated ranking with a simple positional decay formula.
        
        # Fields surfaced as top-level keys for AI agent consumption
        TOP_LEVEL_KEYS = {
            "full_text", "snippet", "source_location", "content_type", 
            "page_confidence", "page_extraction_method", "source_confidence",
            "rerank_score", "similarity_score", "relevance_score",
            "content_relevance", "similarity_percentage"
        }
        
        formatted = []
        for i, citation in enumerate(citations[:k]):
            if hasattr(citation, 'page_content'):
                # LangChain Document objects (from direct engine calls — rare in HTTP mode)
                metadata = citation.metadata if hasattr(citation, 'metadata') else {}
                
                # Use similarity_percentage from retrieval if available, else fallback
                sim_pct = metadata.get("similarity_percentage", 0)
                if sim_pct and sim_pct > 0:
                    confidence = min(100.0, max(0.0, sim_pct))
                else:
                    # Fallback: use rerank_score (0-1) or positional decay
                    rs = metadata.get('rerank_score')
                    if rs and rs > 0:
                        confidence = min(100.0, rs * 100.0)
                    else:
                        confidence = self.calculate_confidence_score(i, len(citations), metadata.get('similarity_score'))
                
                page = metadata.get("page", 1)
                if page is None or (isinstance(page, int) and page < 1):
                    page = 1
                
                formatted.append({
                    "content": citation.page_content,
                    "snippet": citation.page_content[:200] + "..." if len(citation.page_content) > 200 else citation.page_content,
                    "source": metadata.get("source", "unknown"),
                    "document_id": metadata.get("document_id"),
                    "page": page,
                    "source_location": metadata.get("source_location", f"Page {page}"),
                    "content_type": metadata.get("content_type", "text"),
                    "page_confidence": metadata.get("page_confidence"),
                    "page_extraction_method": metadata.get("page_extraction_method"),
                    "source_confidence": metadata.get("source_confidence"),
                    "rerank_score": metadata.get("rerank_score"),
                    "confidence": confidence,
                    "confidence_percentage": round(confidence),
                    "metadata": {mk: mv for mk, mv in metadata.items()
                                if mk not in TOP_LEVEL_KEYS and mk != "page_content"}
                })
            elif isinstance(citation, dict):
                # Dict citations (from retrieval service HTTP response — normal path)
                # TRUST similarity_percentage from retrieval service
                sim_pct = citation.get("similarity_percentage")
                if sim_pct and sim_pct > 0:
                    confidence = min(100.0, max(0.0, sim_pct))
                else:
                    # Fallback: use rerank_score (0-1 from FlashRank)
                    rs = citation.get("rerank_score")
                    if rs and rs > 0:
                        confidence = min(100.0, rs * 100.0)
                    else:
                        # Last resort: positional decay (rarely hit now)
                        confidence = self.calculate_confidence_score(i, len(citations), citation.get("similarity_score"))
                
                page = citation.get("page", 1)
                if page is None or (isinstance(page, int) and page < 1):
                    page = 1
                
                formatted.append({
                    "content": citation.get("full_text", citation.get("snippet", "")),
                    "snippet": citation.get("snippet", "")[:200],
                    "source": citation.get("source", "unknown"),
                    "document_id": citation.get("document_id"),
                    "page": page,
                    "source_location": citation.get("source_location", f"Page {page}"),
                    "content_type": citation.get("content_type", "text"),
                    "page_confidence": citation.get("page_confidence"),
                    "page_extraction_method": citation.get("page_extraction_method"),
                    "source_confidence": citation.get("source_confidence"),
                    "rerank_score": citation.get("rerank_score"),
                    "confidence": confidence,
                    "confidence_percentage": round(confidence),
                    "metadata": {mk: mv for mk, mv in citation.items()
                                if mk not in TOP_LEVEL_KEYS and mk not in {"full_text", "snippet", "metadata"}}
                })
        
        return formatted
