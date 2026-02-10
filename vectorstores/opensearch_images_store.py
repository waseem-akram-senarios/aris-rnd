"""
OpenSearch Images Store for storing image OCR content separately from document chunks.
Uses a dedicated index (aris-rag-images-index) for image information.
"""
import os
import re
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

from langchain_openai import OpenAIEmbeddings
from vectorstores.opensearch_store import OpenSearchVectorStore
from shared.config.settings import ARISConfig
import hashlib
import time

load_dotenv()

logger = logging.getLogger(__name__)

# Query result cache for performance optimization
_query_cache = {}
_cache_timestamps = {}


def clear_image_search_cache(source: Optional[str] = None):
    """
    Clear the image search cache.
    
    Args:
        source: If provided, only clear cache entries related to this source.
                If None, clear entire cache.
    """
    global _query_cache, _cache_timestamps
    if source is None:
        _query_cache.clear()
        _cache_timestamps.clear()
        logger.info("🗑️ Cleared entire image search cache")
    else:
        # Clear entries that might contain this source
        keys_to_remove = [k for k in _query_cache.keys() if source.lower() in str(_query_cache.get(k, [])).lower()]
        for key in keys_to_remove:
            _query_cache.pop(key, None)
            _cache_timestamps.pop(key, None)
        logger.info(f"🗑️ Cleared {len(keys_to_remove)} cache entries for source: {source}")


class OpenSearchImagesStore:
    """
    OpenSearch store specifically for image OCR content.
    Uses separate index from document chunks for better organization.
    """
    
    def __init__(
        self,
        embeddings: OpenAIEmbeddings,
        domain: str = "intelycx-os-dev",
        index_name: str = None,
        region: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        """
        Initialize OpenSearch images store.
        
        Args:
            embeddings: Embeddings model to use (same as main RAG system)
            domain: OpenSearch domain name
            index_name: Name of the OpenSearch index (defaults to aris-rag-images-index)
            region: AWS region
            endpoint: Optional OpenSearch endpoint URL
        """
        self.embeddings = embeddings
        self.domain = domain
        self.index_name = index_name or os.getenv('OPENSEARCH_IMAGES_INDEX', 'aris-rag-images-index')
        self.region = region or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        # Initialize underlying OpenSearchVectorStore
        self.vectorstore = OpenSearchVectorStore(
            embeddings=embeddings,
            domain=domain,
            index_name=self.index_name,
            region=region,
            endpoint=endpoint
        )
        
        logger.info(f"OpenSearchImagesStore initialized with index: {self.index_name}")
    
    def _create_image_id(self, source: str, image_number: int) -> str:
        """
        Create unique image ID from source and image number.
        
        Args:
            source: Document source name
            image_number: Image number within document
            
        Returns:
            Unique image ID string
        """
        # Sanitize source name for ID
        sanitized_source = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.basename(source))
        return f"{sanitized_source}_image_{image_number}"
    
    def _extract_image_metadata(self, ocr_text: str) -> Dict[str, Any]:
        """
        Extract metadata from OCR text (drawer refs, part numbers, tools, etc.).
        
        Args:
            ocr_text: OCR text from image
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'drawer_references': [],
            'part_numbers': [],
            'tools_found': [],
            'has_structured_content': False
        }
        
        if not ocr_text:
            return metadata
        
        # Extract drawer references
        drawer_pattern = r'DRAWER\s+(\d+)'
        drawer_matches = re.findall(drawer_pattern, ocr_text, re.IGNORECASE)
        metadata['drawer_references'] = list(set(drawer_matches))
        
        # Extract part numbers (5+ digits)
        part_number_pattern = r'\b\d{5,}\b'
        part_numbers = re.findall(part_number_pattern, ocr_text)
        metadata['part_numbers'] = list(set(part_numbers))[:50]  # Limit to 50
        
        # Extract tool names
        tool_keywords = ['mallet', 'wrench', 'socket', 'ratchet', 'extension', 'allen', 
                        'snips', 'cutter', 'hammer', 'pliers', 'drill', 'screwdriver']
        found_tools = [tool for tool in tool_keywords if tool.lower() in ocr_text.lower()]
        metadata['tools_found'] = list(set(found_tools))
        
        # Check for structured content patterns
        has_structured = any([
            '___' in ocr_text or '____' in ocr_text,
            '|' in ocr_text and 'YES' in ocr_text and 'NO' in ocr_text,
            re.search(r'Quantity:\s*\d+', ocr_text, re.IGNORECASE),
            re.search(r'DRAWER', ocr_text, re.IGNORECASE)
        ])
        metadata['has_structured_content'] = has_structured
        
        return metadata
    
    def store_image(
        self,
        source: str,
        image_number: int,
        ocr_text: str,
        page: int = 0,
        marker_detected: bool = True,
        extraction_method: str = "unknown",
        full_chunk: str = None,
        context_before: str = None
    ) -> str:
        """
        Store a single image in OpenSearch.
        
        Args:
            source: Document source name
            image_number: Image number within document
            ocr_text: OCR text extracted from image
            page: Page number where image appears
            marker_detected: Whether image marker was detected
            extraction_method: Method used (docling_ocr, pymupdf, textract, query_time)
            full_chunk: Full chunk text containing image marker
            context_before: Text before image marker
            
        Returns:
            Image ID of stored image
        """
        # Ensure image_number is always a positive integer (avoid 0 which breaks API consumers)
        try:
            image_number = int(image_number) if image_number is not None else 1
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            image_number = 1
        if image_number <= 0:
            image_number = 1

        image_id = self._create_image_id(source, image_number)
        
        # Extract metadata from OCR text
        metadata = self._extract_image_metadata(ocr_text)
        
        # Create document for OpenSearch
        # Use OCR text as the main content for embedding
        doc_content = ocr_text if ocr_text else f"Image {image_number} from {os.path.basename(source)}"
        
        # Create document with image-specific structure
        doc_metadata = {
            'source': source,
            'image_number': image_number,
            'page': page,
            'ocr_text_length': len(ocr_text) if ocr_text else 0,
            'marker_detected': marker_detected,
            'extraction_method': extraction_method,
            'extraction_timestamp': datetime.utcnow().isoformat() + 'Z',
            # Keep nested metadata for backward compatibility
            'metadata': metadata,
            # Also expose commonly-used fields at top-level to avoid nested-dict mapping issues
            'drawer_references': metadata.get('drawer_references', []),
            'part_numbers': metadata.get('part_numbers', []),
            'tools_found': metadata.get('tools_found', []),
            'has_structured_content': metadata.get('has_structured_content', False),
            'full_chunk': full_chunk[:5000] if full_chunk else None,  # Limit size
            'context_before': context_before[:1000] if context_before else None,  # Limit size
            'content_type': 'image_ocr',  # Indicate this is image OCR content
            # OCR quality metrics
            'ocr_quality_metrics': {
                'extraction_method': extraction_method,
                'ocr_text_length': len(ocr_text) if ocr_text else 0,
                'has_content': bool(ocr_text and len(ocr_text.strip()) > 0)
            }
        }
        
        # Create LangChain Document
        doc = Document(
            page_content=doc_content,
            metadata=doc_metadata
        )
        
        try:
            # Store in OpenSearch (will create index if needed)
            # Use add_documents which handles duplicates by updating
            self.vectorstore.add_documents([doc])
            logger.info(f"✅ Stored image {image_number} from {os.path.basename(source)} in OpenSearch (ID: {image_id})")
            return image_id
        except Exception as e:
            logger.error(f"❌ Failed to store image {image_number} from {os.path.basename(source)}: {str(e)}")
            raise
    
    def store_images_batch(self, images: List[Dict[str, Any]]) -> List[str]:
        """
        Store multiple images in batch.
        
        Args:
            images: List of image dictionaries with keys:
                - source: Document source name
                - image_number: Image number
                - ocr_text: OCR text
                - page: Page number (optional)
                - marker_detected: Whether marker detected (optional)
                - extraction_method: Extraction method (optional)
                - full_chunk: Full chunk text (optional)
                - context_before: Context before marker (optional)
        
        Returns:
            List of image IDs
        """
        if not images:
            logger.warning("No images to store in batch")
            return []
        
        logger.info(f"Storing {len(images)} images in batch...")
        
        # Convert to Document objects
        documents = []
        image_ids = []
        
        for img_data in images:
            source = img_data.get('source', 'unknown')
            image_number = img_data.get('image_number')
            try:
                image_number = int(image_number) if image_number is not None else None
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                image_number = None
            ocr_text = img_data.get('ocr_text', '')

            # Ensure image_number is always 1..N (never 0)
            if not image_number or image_number <= 0:
                image_number = len(image_ids) + 1
            
            image_id = self._create_image_id(source, image_number)
            image_ids.append(image_id)
            
            # Extract metadata
            metadata = self._extract_image_metadata(ocr_text)
            
            # Create document
            doc_content = ocr_text if ocr_text else f"Image {image_number} from {os.path.basename(source)}"
            
            extraction_method = img_data.get('extraction_method', 'unknown')
            doc_metadata = {
                'source': source,
                'image_number': image_number,
                'page': img_data.get('page', 0),
                'ocr_text_length': len(ocr_text) if ocr_text else 0,
                'marker_detected': img_data.get('marker_detected', True),
                'extraction_method': extraction_method,
                'extraction_timestamp': datetime.utcnow().isoformat() + 'Z',
                # Keep nested metadata for backward compatibility
                'metadata': metadata,
                # Also expose commonly-used fields at top-level to avoid nested-dict mapping issues
                'drawer_references': metadata.get('drawer_references', []),
                'part_numbers': metadata.get('part_numbers', []),
                'tools_found': metadata.get('tools_found', []),
                'has_structured_content': metadata.get('has_structured_content', False),
                'full_chunk': (img_data.get('full_chunk', '') or '')[:5000],
                'context_before': (img_data.get('context_before', '') or '')[:1000],
                'content_type': 'image_ocr',  # Indicate this is image OCR content
                # OCR quality metrics
                'ocr_quality_metrics': {
                    'extraction_method': extraction_method,
                    'ocr_text_length': len(ocr_text) if ocr_text else 0,
                    'has_content': bool(ocr_text and len(ocr_text.strip()) > 0),
                    'confidence_score': img_data.get('ocr_confidence'),  # If provided
                    'character_accuracy': img_data.get('character_accuracy')  # If provided
                }
            }
            
            doc = Document(
                page_content=doc_content,
                metadata=doc_metadata
            )
            documents.append(doc)
        
        try:
            # Store all in batch
            self.vectorstore.add_documents(documents)
            logger.info(f"✅ Stored {len(images)} images in batch")
            return image_ids
        except Exception as e:
            logger.error(f"❌ Failed to store images batch: {str(e)}")
            raise
    
    def get_images_by_source(self, source: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve all images for a specific document source.
        
        Args:
            source: Document source name
            limit: Maximum number of images to return
            
        Returns:
            List of image dictionaries
        """
        if not self.vectorstore or not self.vectorstore.vectorstore:
            logger.warning("Vector store not initialized")
            return []
        
        try:
            client = self.vectorstore.vectorstore.client
            
            # Build flexible source match (handles basename, lowercase, keyword fields)
            source_variants = {
                source,
                os.path.basename(source or ""),
                (source or "").lower(),
                os.path.basename(source or "").lower()
            }
            should_clauses = []
            for variant in source_variants:
                if not variant:
                    continue
                should_clauses.extend([
                    {"term": {"metadata.source.keyword": variant}},
                    {"term": {"metadata.source": variant}},
                    {"match_phrase": {"metadata.source": variant}}
                ])
            
            query = {
                "size": limit,
                "query": {
                    "bool": {
                        "must": [{"term": {"metadata.content_type.keyword": "image_ocr"}}],
                        "should": should_clauses or [{"match_all": {}}],
                        "minimum_should_match": 1
                    }
                },
                "sort": [
                    {"metadata.image_number": {"order": "asc"}}
                ]
            }
            
            try:
                response = client.search(index=self.index_name, body=query)
            except Exception as e:
                logger.warning(f"Search with sort by metadata.image_number failed ({e}); retrying without sort")
                query_no_sort = dict(query)
                query_no_sort.pop("sort", None)
                response = client.search(index=self.index_name, body=query_no_sort)
            hits = response.get("hits", {}).get("hits", [])
            
            images = []
            seq_number = 0
            for hit in hits:
                seq_number += 1
                source_data = hit.get("_source", {})
                meta = source_data.get('metadata', {}) or {}
                # OpenSearch/LangChain may store our metadata in nested structures.
                # Common shapes observed:
                # - _source.metadata = {source, image_number, page, metadata={drawer_references...}}
                # - _source.metadata = {metadata={source, image_number, ...}, ...}
                nested_meta = {}
                if isinstance(meta, dict):
                    nested_meta = meta.get('metadata', {}) or {}

                def _pick(*vals):
                    for v in vals:
                        if v is None:
                            continue
                        # preserve 0 only if caller explicitly passed 0
                        if isinstance(v, str) and v.strip() == "":
                            continue
                        return v
                    return None

                image_number = _pick(
                    meta.get('image_number') if isinstance(meta, dict) else None,
                    nested_meta.get('image_number') if isinstance(nested_meta, dict) else None,
                    meta.get('imageNumber') if isinstance(meta, dict) else None,
                    nested_meta.get('imageNumber') if isinstance(nested_meta, dict) else None,
                )
                page = _pick(
                    meta.get('page') if isinstance(meta, dict) else None,
                    nested_meta.get('page') if isinstance(nested_meta, dict) else None,
                )

                ocr_text = source_data.get('text', '') or ''

                # Extract structured OCR metadata (drawer_references, part_numbers, tools_found, etc.)
                # NOTE: Some OpenSearch mappings drop nested metadata keys.
                # If not present, recompute from OCR text so API callers still get useful metadata.
                structured_metadata = {}
                if isinstance(nested_meta, dict) and isinstance(nested_meta.get('metadata'), dict):
                    structured_metadata = nested_meta.get('metadata') or {}
                elif isinstance(meta, dict) and isinstance(meta.get('metadata'), dict):
                    structured_metadata = meta.get('metadata') or {}
                if not structured_metadata:
                    structured_metadata = self._extract_image_metadata(ocr_text)

                # If image_number is missing, try to parse from the document ID suffix '*_image_<n>'
                if image_number is None:
                    hit_id = hit.get('_id') or ''
                    m = re.search(r'_image_(\d+)$', str(hit_id))
                    if m:
                        image_number = m.group(1)
                    else:
                        image_number = seq_number

                images.append({
                    'image_id': hit.get("_id"),
                    'source': _pick(
                        meta.get('source') if isinstance(meta, dict) else None,
                        nested_meta.get('source') if isinstance(nested_meta, dict) else None,
                    ),
                    'image_number': int(image_number) if image_number is not None else 0,
                    'page': int(page) if page is not None else None,
                    'ocr_text': ocr_text,
                    'ocr_text_length': _pick(
                        meta.get('ocr_text_length', 0) if isinstance(meta, dict) else 0,
                        nested_meta.get('ocr_text_length', 0) if isinstance(nested_meta, dict) else 0,
                    ) or 0,
                    'metadata': structured_metadata or {},
                    'extraction_method': _pick(
                        meta.get('extraction_method') if isinstance(meta, dict) else None,
                        nested_meta.get('extraction_method') if isinstance(nested_meta, dict) else None,
                    ),
                    'extraction_timestamp': _pick(
                        meta.get('extraction_timestamp') if isinstance(meta, dict) else None,
                        nested_meta.get('extraction_timestamp') if isinstance(nested_meta, dict) else None,
                    )
                })
            
            logger.info(f"Retrieved {len(images)} images for source: {os.path.basename(source)}")
            return images
        except Exception as e:
            logger.error(f"Failed to retrieve images for source {source}: {str(e)}")
            return []

    def count_images_by_source(self, source: str) -> int:
        if not self.vectorstore or not self.vectorstore.vectorstore:
            return 0

        try:
            client = self.vectorstore.vectorstore.client

            source_variants = {
                source,
                os.path.basename(source or ""),
                (source or "").lower(),
                os.path.basename(source or "").lower(),
            }

            should_clauses = []
            for variant in source_variants:
                if not variant:
                    continue
                should_clauses.extend([
                    {"term": {"metadata.source.keyword": variant}},
                    {"term": {"metadata.source": variant}},
                    {"match_phrase": {"metadata.source": variant}},
                ])

            query = {
                "bool": {
                    "should": should_clauses or [{"match_all": {}}],
                    "minimum_should_match": 1,
                }
            }

            resp = client.count(index=self.index_name, body={"query": query})
            return int(resp.get("count", 0) or 0)
        except Exception as e:
            logger.warning(f"Failed to count images for source {source}: {str(e)}")
            return 0
    
    def get_image_by_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific image by ID.
        
        Args:
            image_id: Image ID
            
        Returns:
            Image dictionary or None if not found
        """
        if not self.vectorstore or not self.vectorstore.vectorstore:
            logger.warning("Vector store not initialized")
            return None
        
        try:
            client = self.vectorstore.vectorstore.client
            response = client.get(index=self.index_name, id=image_id)
            source_data = response.get("_source", {})
            meta = source_data.get('metadata', {}) or {}
            nested_meta = meta.get('metadata', {}) if isinstance(meta, dict) else {}

            def _pick(*vals):
                for v in vals:
                    if v is None:
                        continue
                    if isinstance(v, str) and v.strip() == "":
                        continue
                    return v
                return None

            image_number = _pick(
                meta.get('image_number') if isinstance(meta, dict) else None,
                nested_meta.get('image_number') if isinstance(nested_meta, dict) else None,
            )
            if image_number is None:
                m = re.search(r'_image_(\d+)$', str(image_id))
                if m:
                    image_number = m.group(1)

            page = _pick(
                meta.get('page') if isinstance(meta, dict) else None,
                nested_meta.get('page') if isinstance(nested_meta, dict) else None,
            )

            ocr_text = source_data.get('text', '') or ''

            structured_metadata = {}
            if isinstance(nested_meta, dict) and isinstance(nested_meta.get('metadata'), dict):
                structured_metadata = nested_meta.get('metadata') or {}
            elif isinstance(meta, dict) and isinstance(meta.get('metadata'), dict):
                structured_metadata = meta.get('metadata') or {}
            if not structured_metadata:
                structured_metadata = self._extract_image_metadata(ocr_text)

            return {
                'image_id': response.get("_id"),
                'source': _pick(
                    meta.get('source') if isinstance(meta, dict) else None,
                    nested_meta.get('source') if isinstance(nested_meta, dict) else None,
                ),
                'image_number': int(image_number) if image_number is not None else 0,
                'page': int(page) if page is not None else None,
                'ocr_text': ocr_text,
                'ocr_text_length': _pick(
                    meta.get('ocr_text_length', 0) if isinstance(meta, dict) else 0,
                    nested_meta.get('ocr_text_length', 0) if isinstance(nested_meta, dict) else 0,
                ) or 0,
                'metadata': structured_metadata or {},
                'extraction_method': _pick(
                    meta.get('extraction_method') if isinstance(meta, dict) else None,
                    nested_meta.get('extraction_method') if isinstance(nested_meta, dict) else None,
                ),
                'extraction_timestamp': _pick(
                    meta.get('extraction_timestamp') if isinstance(meta, dict) else None,
                    nested_meta.get('extraction_timestamp') if isinstance(nested_meta, dict) else None,
                ),
                'full_chunk': _pick(
                    meta.get('full_chunk') if isinstance(meta, dict) else None,
                    nested_meta.get('full_chunk') if isinstance(nested_meta, dict) else None,
                ),
                'context_before': _pick(
                    meta.get('context_before') if isinstance(meta, dict) else None,
                    nested_meta.get('context_before') if isinstance(nested_meta, dict) else None,
                )
            }
        except Exception as e:
            logger.warning(f"Image {image_id} not found: {str(e)}")
            return None
    
    def search_images(
        self,
        query: str,
        source: Optional[str] = None,
        sources: Optional[List[str]] = None,
        k: int = 5,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform optimized semantic search in images using OpenSearch k-NN query.
        
        Performance optimizations:
        - Query result caching (configurable TTL)
        - ef_search parameter for HNSW speed/accuracy tradeoff
        - min_score threshold to skip irrelevant results
        - Pre-filtering to reduce search space
        - Reduced over-fetching with smart k multiplier
        
        Args:
            query: Search query text
            source: Optional single source filter (deprecated, use sources)
            sources: Optional list of document names to filter by
            k: Number of results to return
            min_score: Minimum similarity score threshold (default from config)
            
        Returns:
            List of matching image dictionaries
        """
        if not self.vectorstore or not self.vectorstore.vectorstore:
            logger.warning("Vector store not initialized")
            return []
        
        search_start_time = time.time()
        
        # Get performance config
        knn_config = ARISConfig.get_knn_performance_config()
        ef_search = knn_config['ef_search']
        if min_score is None:
            min_score = knn_config['min_score']
        cache_ttl = knn_config['cache_ttl_seconds']
        max_fetch_multiplier = knn_config['max_fetch_multiplier']
        
        # Determine effective sources
        effective_sources = sources if sources else ([source] if source else None)
        
        # Build cache key
        cache_key = hashlib.md5(
            f"{query}:{effective_sources}:{k}:{min_score}".encode()
        ).hexdigest()
        
        # Check cache
        if cache_ttl > 0 and cache_key in _query_cache:
            cache_time = _cache_timestamps.get(cache_key, 0)
            if time.time() - cache_time < cache_ttl:
                logger.info(f"🚀 Cache hit for image search query (saved ~2-3 min)")
                return _query_cache[cache_key]
        
        try:
            client = self.vectorstore.vectorstore.client
            
            # Generate query embedding
            embed_start = time.time()
            query_vector = self.embeddings.embed_query(query)
            embed_time = time.time() - embed_start
            logger.debug(f"Embedding generation took {embed_time:.2f}s")
            
            # Calculate optimized fetch size (don't over-fetch)
            fetch_k = int(k * max_fetch_multiplier)
            
            # Build optimized k-NN query with performance parameters
            try:
                # Build source filter if specified
                source_filter = None
                if effective_sources and len(effective_sources) > 0:
                    should_clauses = []
                    for src in effective_sources:
                        if not src:
                            continue
                        source_variants = [
                            src,
                            os.path.basename(src),
                            src.lower(),
                            os.path.basename(src).lower()
                        ]
                        for variant in source_variants:
                            if not variant:
                                continue
                            should_clauses.extend([
                                {"term": {"metadata.source.keyword": variant}},
                                {"term": {"metadata.source": variant}},
                                {"match_phrase": {"metadata.source": variant}}
                            ])
                    
                    source_filter = {
                        "bool": {
                            "must": [{"term": {"metadata.content_type.keyword": "image_ocr"}}],
                            "should": should_clauses,
                            "minimum_should_match": 1
                        }
                    }
                    logger.info(f"Image search filtered to {len(effective_sources)} document(s)")
                else:
                    source_filter = {"term": {"metadata.content_type.keyword": "image_ocr"}}
                    logger.info(f"Image search across ALL documents (filtered by content_type=image_ocr)")
                
                # Optimized k-NN query with ef_search and min_score
                knn_query = {
                    "size": fetch_k,
                    "_source": ["text", "metadata"],  # Only fetch needed fields
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "knn": {
                                        "vector_field": {
                                            "vector": query_vector,
                                            "k": fetch_k,
                                            "method_parameters": {
                                                "ef_search": ef_search
                                            }
                                        }
                                    }
                                }
                            ],
                            "filter": source_filter
                        }
                    }
                }
                
                # Add min_score threshold if specified
                if min_score and min_score > 0:
                    knn_query["min_score"] = min_score
                
                search_exec_start = time.time()
                response = client.search(index=self.index_name, body=knn_query)
                search_exec_time = time.time() - search_exec_start
                
                hits = response.get('hits', {}).get('hits', [])
                logger.info(f"k-NN search completed in {search_exec_time:.2f}s with {len(hits)} results (ef_search={ef_search})")
            except Exception as knn_error:
                # k-NN not supported or failed - fallback to optimized text search
                logger.warning(f"k-NN search failed, using text search fallback: {knn_error}")
                
                text_query: Dict[str, Any] = {
                    "size": fetch_k,
                    "_source": ["text", "metadata"],  # Only fetch needed fields
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["text^2", "metadata.source"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    }
                }
                
                # Add source filter if specified
                if source:
                    source_variants = [
                        source,
                        os.path.basename(source or ""),
                        (source or "").lower(),
                        os.path.basename(source or "").lower()
                    ]
                    should_clauses = []
                    for variant in source_variants:
                        if not variant:
                            continue
                        should_clauses.extend([
                            {"term": {"metadata.source.keyword": variant}},
                            {"term": {"metadata.source": variant}},
                            {"match_phrase": {"metadata.source": variant}}
                        ])
                    if should_clauses:
                        text_query["query"] = {
                            "bool": {
                                "must": [text_query["query"]],
                                "filter": {
                                    "bool": {
                                        "must": [{"term": {"metadata.content_type.keyword": "image_ocr"}}],
                                        "should": should_clauses,
                                        "minimum_should_match": 1
                                    }
                                }
                            }
                        }
                    else:
                        text_query["query"] = {
                            "bool": {
                                "must": [text_query["query"]],
                                "filter": {
                                    "term": {"metadata.content_type.keyword": "image_ocr"}
                                }
                            }
                        }
                
                response = client.search(index=self.index_name, body=text_query)
                hits = response.get("hits", {}).get("hits", [])
            
            images = []
            for idx, hit in enumerate(hits, start=1):
                source_data = hit.get("_source", {})
                metadata = source_data.get("metadata", {})
                ocr_text = source_data.get('text', '') or ''
                
                # CRITICAL: Ensure image_number is never 0 - use 1-based indexing
                stored_image_number = metadata.get('image_number')
                if stored_image_number is None or stored_image_number == 0:
                    # Fallback to index-based numbering (1-based)
                    image_number = idx
                else:
                    image_number = stored_image_number
                
                # Get page - try to extract from OCR text if not in metadata
                page = metadata.get('page')
                if page is None or page == 0:
                    # Try to extract page from OCR text
                    import re
                    # Pattern: "DOCNAME Page X" at end (most reliable - actual page marker)
                    page_match = re.search(r'Page\s+(\d+)\s*$', ocr_text, re.IGNORECASE | re.MULTILINE)
                    if page_match:
                        extracted_page = int(page_match.group(1))
                        if extracted_page > 0:
                            page = extracted_page
                            logger.debug(f"Extracted page {page} from end of OCR text for image {image_number}")
                    # NOTE: Do NOT use "Figure X" as page - Figure numbers are NOT page numbers!
                    if page is None or page == 0:
                        page = 1  # Default to page 1 if not found
                
                images.append({
                    'image_id': self._create_image_id(
                        metadata.get('source', 'unknown'),
                        image_number
                    ),
                    'source': metadata.get('source'),
                    'image_number': image_number,
                    'page': page,
                    'ocr_text': ocr_text,
                    'ocr_text_length': metadata.get('ocr_text_length', 0),
                    'metadata': metadata,
                    'extraction_method': metadata.get('extraction_method'),
                    'score': hit.get('_score')  # k-NN similarity score
                })
            
            # Limit to requested k
            images = images[:k]
            
            # Cache results for future queries
            if cache_ttl > 0:
                _query_cache[cache_key] = images
                _cache_timestamps[cache_key] = time.time()
                # Clean old cache entries (keep max 100)
                if len(_query_cache) > 100:
                    oldest_keys = sorted(_cache_timestamps.keys(), key=lambda x: _cache_timestamps[x])[:50]
                    for old_key in oldest_keys:
                        _query_cache.pop(old_key, None)
                        _cache_timestamps.pop(old_key, None)
            
            total_time = time.time() - search_start_time
            logger.info(f"✅ Found {len(images)} images matching query in {total_time:.2f}s: {query[:50]}")
            return images
        except Exception as e:
            logger.error(f"Failed to search images: {str(e)}", exc_info=True)
            return []
    
    def update_image(self, image_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing image document.
        
        Args:
            image_id: Image ID to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        if not self.vectorstore or not self.vectorstore.vectorstore:
            logger.warning("Vector store not initialized")
            return False
        
        try:
            client = self.vectorstore.vectorstore.client
            
            # Get existing document
            existing = client.get(index=self.index_name, id=image_id)
            source_data = existing.get("_source", {})
            
            # Update metadata
            if 'metadata' in source_data:
                source_data['metadata'].update(updates)
            else:
                source_data['metadata'] = updates
            
            # Update document
            client.index(
                index=self.index_name,
                id=image_id,
                body=source_data
            )
            
            logger.info(f"Updated image {image_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update image {image_id}: {str(e)}")
            return False

