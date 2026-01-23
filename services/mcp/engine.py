"""
MCP Engine - Core logic for MCP server operations

This module contains the MCPEngine class that provides the core functionality
for document ingestion and semantic search, used by the MCP server tools.
"""

import os
import re
import io
import logging
import tempfile
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class MCPEngine:
    """
    Core engine for MCP server operations.
    
    Provides high-accuracy document ingestion and search capabilities
    with all the advanced features of the ARIS RAG system.
    """
    
    def __init__(self):
        """Initialize the MCP Engine with required services."""
        from shared.config.settings import ARISConfig
        
        self.config = ARISConfig
        self._ingestion_engine = None
        self._retrieval_engine = None
        self._document_registry = None
        self._s3_service = None
        self._parser_factory = None
    
    @property
    def ingestion_engine(self):
        """Lazy load ingestion engine."""
        if self._ingestion_engine is None:
            from services.ingestion.engine import IngestionEngine
            self._ingestion_engine = IngestionEngine(
                use_cerebras=self.config.USE_CEREBRAS,
                embedding_model=self.config.EMBEDDING_MODEL,
                vector_store_type=self.config.VECTOR_STORE_TYPE,
                opensearch_domain=self.config.AWS_OPENSEARCH_DOMAIN,
                opensearch_index=self.config.AWS_OPENSEARCH_INDEX,
                chunk_size=self.config.DEFAULT_CHUNK_SIZE,
                chunk_overlap=self.config.DEFAULT_CHUNK_OVERLAP
            )
        return self._ingestion_engine
    
    @property
    def retrieval_engine(self):
        """Lazy load retrieval engine."""
        if self._retrieval_engine is None:
            from services.retrieval.engine import RetrievalEngine
            self._retrieval_engine = RetrievalEngine(
                use_cerebras=self.config.USE_CEREBRAS,
                embedding_model=self.config.EMBEDDING_MODEL,
                vector_store_type=self.config.VECTOR_STORE_TYPE,
                opensearch_domain=self.config.AWS_OPENSEARCH_DOMAIN,
                opensearch_index=self.config.AWS_OPENSEARCH_INDEX
            )
        return self._retrieval_engine
    
    @property
    def document_registry(self):
        """Lazy load document registry."""
        if self._document_registry is None:
            from storage.document_registry import DocumentRegistry
            self._document_registry = DocumentRegistry(
                self.config.DOCUMENT_REGISTRY_PATH
            )
        return self._document_registry
    
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
            return min(100.0, max(0.0, rerank_score * 100))
        
        if total == 0:
            return 0.0
        
        base_score = 100.0
        decay_rate = 0.15
        position_score = base_score * (1 - decay_rate) ** rank
        
        return round(max(0.0, min(100.0, position_score)), 1)
    
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
            raise ValueError(
                "S3 service is not configured. Please set AWS credentials."
            )
        
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
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def ingest(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest content into the RAG system.
        
        Args:
            content: Raw text or S3 URI
            metadata: Optional metadata for the document
            
        Returns:
            Dictionary with ingestion results
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        content = content.strip()
        metadata = metadata or {}
        
        accuracy_info = {
            "chunk_size": self.config.DEFAULT_CHUNK_SIZE,
            "chunk_overlap": self.config.DEFAULT_CHUNK_OVERLAP,
            "embedding_model": self.config.EMBEDDING_MODEL
        }
        
        try:
            if self.is_s3_uri(content):
                logger.info(f"Detected S3 URI: {content}")
                
                language = metadata.get("language", "eng")
                language = self.convert_language_code(language)
                
                text, doc_metadata, filename = self.fetch_and_parse_s3_document(
                    content, language
                )
                
                final_metadata = {**doc_metadata, **metadata}
                final_metadata["s3_uri"] = content
                final_metadata["source"] = filename
                
                accuracy_info["parser_used"] = doc_metadata.get("parser_used", "unknown")
                accuracy_info["extraction_confidence"] = doc_metadata.get("confidence", 0.0)
                accuracy_info["pages_extracted"] = doc_metadata.get("pages", 0)
                
                if not text or not text.strip():
                    raise ValueError(f"No text extracted from document: {content}")
            else:
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
                    final_metadata["language"] = self.convert_language_code(detected_lang)
                    accuracy_info["language_detected"] = True
                except:
                    final_metadata["language"] = "eng"
                    accuracy_info["language_detected"] = False
            
            # Generate document ID
            document_id = self.generate_document_id(text, final_metadata.get("source"))
            final_metadata["document_id"] = document_id
            
            # Determine index name
            index_name = metadata.get("index_name") or self.config.AWS_OPENSEARCH_INDEX
            
            # Process and ingest
            logger.info(f"Ingesting document: {document_id} ({len(text)} chars)")
            
            result = self.ingestion_engine.add_documents_incremental(
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
            self.document_registry.add_document(document_id, registry_entry)
            
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
        Search the RAG system with accuracy-optimized retrieval.
        
        Args:
            query: The search query
            filters: Optional metadata filters
            k: Number of results to return
            search_mode: Search strategy (semantic, keyword, hybrid)
            use_agentic_rag: Enable query decomposition
            include_answer: Generate LLM answer
            
        Returns:
            Dictionary with search results
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
            # Build active sources filter
            active_sources = None
            if "source" in filters:
                source_filter = filters.pop("source")
                if isinstance(source_filter, str):
                    active_sources = [source_filter]
                elif isinstance(source_filter, list):
                    active_sources = source_filter
            
            # Get language filter
            filter_language = filters.pop("language", None)
            if filter_language:
                filter_language = self.convert_language_code(filter_language)
            
            # Accuracy settings
            use_hybrid = search_mode == "hybrid"
            semantic_weight = self.config.DEFAULT_SEMANTIC_WEIGHT if use_hybrid else (
                1.0 if search_mode == "semantic" else 0.0
            )
            
            retrieval_k = min(k * 3, self.config.DEFAULT_RETRIEVAL_K)
            
            accuracy_info = {
                "search_mode": search_mode,
                "semantic_weight": semantic_weight,
                "keyword_weight": 1.0 - semantic_weight if use_hybrid else (
                    0.0 if search_mode == "semantic" else 1.0
                ),
                "reranking_enabled": self.config.ENABLE_RERANKING,
                "agentic_rag_enabled": use_agentic_rag,
                "retrieval_k": retrieval_k,
                "final_k": k,
                "auto_translate": self.config.ENABLE_AUTO_TRANSLATE
            }
            
            logger.info(f"Searching RAG: query='{query[:50]}...', mode={search_mode}, k={k}")
            
            if include_answer:
                result = self.retrieval_engine.query_with_rag(
                    question=query,
                    k=retrieval_k,
                    use_mmr=self.config.DEFAULT_USE_MMR,
                    active_sources=active_sources,
                    use_hybrid_search=use_hybrid,
                    semantic_weight=semantic_weight,
                    search_mode=search_mode,
                    use_agentic_rag=use_agentic_rag,
                    temperature=self.config.DEFAULT_TEMPERATURE,
                    max_tokens=self.config.DEFAULT_MAX_TOKENS,
                    filter_language=filter_language,
                    auto_translate=self.config.ENABLE_AUTO_TRANSLATE
                )
            else:
                result = {
                    "answer": "",
                    "citations": self.retrieval_engine._retrieve_chunks_for_query(
                        query=query,
                        k=retrieval_k,
                        use_mmr=self.config.DEFAULT_USE_MMR,
                        use_hybrid_search=use_hybrid,
                        semantic_weight=semantic_weight,
                        keyword_weight=1.0 - semantic_weight,
                        search_mode=search_mode,
                        active_sources=active_sources,
                        filter_language=filter_language
                    ) if hasattr(self.retrieval_engine, '_retrieve_chunks_for_query') else []
                }
            
            # Format results
            formatted_results = []
            citations = result.get("citations", [])
            
            if citations and hasattr(citations[0], 'page_content'):
                for i, doc in enumerate(citations[:k]):
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    rerank_score = metadata.get('rerank_score')
                    
                    chunk_result = {
                        "content": doc.page_content,
                        "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        "source": metadata.get("source", "unknown"),
                        "page": metadata.get("page", 1),
                        "confidence": self.calculate_confidence_score(i, len(citations), rerank_score),
                        "metadata": {k: v for k, v in metadata.items() if k not in {"page_content"}}
                    }
                    formatted_results.append(chunk_result)
            else:
                for i, citation in enumerate(citations[:k]):
                    if isinstance(citation, dict):
                        rerank_score = citation.get("rerank_score") or citation.get("similarity_score")
                        
                        chunk_result = {
                            "content": citation.get("full_text", citation.get("snippet", "")),
                            "snippet": citation.get("snippet", "")[:200],
                            "source": citation.get("source", "unknown"),
                            "page": citation.get("page", 1),
                            "confidence": self.calculate_confidence_score(i, len(citations), rerank_score),
                            "metadata": {
                                k: v for k, v in citation.items()
                                if k not in {"full_text", "snippet", "source", "page", "rerank_score", "similarity_score"}
                            }
                        }
                    else:
                        rerank_score = getattr(citation, "rerank_score", None) or getattr(citation, "similarity_score", None)
                        
                        chunk_result = {
                            "content": getattr(citation, "full_text", getattr(citation, "snippet", "")),
                            "snippet": getattr(citation, "snippet", "")[:200],
                            "source": getattr(citation, "source", "unknown"),
                            "page": getattr(citation, "page", 1),
                            "confidence": self.calculate_confidence_score(i, len(citations), rerank_score),
                            "metadata": {}
                        }
                    
                    # Apply remaining filters
                    if filters:
                        chunk_metadata = chunk_result.get("metadata", {})
                        match = all(
                            chunk_metadata.get(fk) == fv
                            for fk, fv in filters.items()
                        )
                        if not match:
                            continue
                    
                    formatted_results.append(chunk_result)
            
            answer = result.get("answer", "")
            
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
                "message": f"Found {len(formatted_results)} relevant results" + (
                    f" with synthesized answer" if include_answer and answer else ""
                )
            }
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            raise ValueError(f"Search failed: {str(e)}")

