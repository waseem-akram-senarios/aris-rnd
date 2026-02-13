"""Qdrant vector store implementation."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    SearchParams
)
from qdrant_client.http.exceptions import UnexpectedResponse

from .base import VectorStore, ChunkWithEmbedding, SearchResult, BatchIndexResult, VectorStoreFactory

logger = logging.getLogger(__name__)


class QdrantVectorStore(VectorStore):
    """
    Qdrant vector store implementation.
    
    Supports both Qdrant Cloud and self-hosted Qdrant.
    Modern vector database with excellent performance and features.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Qdrant store.
        
        Config parameters:
            url: Qdrant server URL (e.g., http://localhost:6333)
            api_key: API key for Qdrant Cloud (optional for self-hosted)
            collection_name: Collection name for embeddings
            timeout: Request timeout in seconds
            prefer_grpc: Use gRPC instead of HTTP (better performance)
        """
        super().__init__(config)
        self.client: Optional[AsyncQdrantClient] = None
        self.collection_name = config.get("collection_name", "aris_knowledge_base")
        self._initialized_collections = set()
    
    async def initialize(self) -> bool:
        """Initialize Qdrant client."""
        try:
            url = self.config.get("url")
            if not url:
                raise ValueError("Qdrant URL is required")
            
            api_key = self.config.get("api_key")
            timeout = self.config.get("timeout", 30)
            prefer_grpc = self.config.get("prefer_grpc", False)
            
            # Create client
            self.client = AsyncQdrantClient(
                url=url,
                api_key=api_key,
                timeout=timeout,
                prefer_grpc=prefer_grpc
            )
            
            # Test connection
            if await self.health_check():
                self.logger.info(f"✅ Qdrant connected successfully: {url}")
                return True
            else:
                self.logger.error("Qdrant health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Qdrant: {e}")
            return False
    
    async def create_index(
        self,
        index_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> bool:
        """
        Create Qdrant collection.
        
        Args:
            index_name: Collection name
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, euclidean, dot_product)
            **kwargs: Additional options (on_disk_payload, replication_factor)
        """
        try:
            collection = index_name if index_name != "default" else self.collection_name
            
            # Check if collection already exists
            if await self.index_exists(collection):
                self.logger.info(f"Collection '{collection}' already exists")
                return True
            
            # Map distance metric to Qdrant Distance
            distance_map = {
                "cosine": Distance.COSINE,
                "euclidean": Distance.EUCLID,
                "l2": Distance.EUCLID,
                "dot_product": Distance.DOT,
                "inner_product": Distance.DOT,
                "manhattan": Distance.MANHATTAN,
                "l1": Distance.MANHATTAN
            }
            distance = distance_map.get(distance_metric, Distance.COSINE)
            
            # Create collection
            await self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=distance,
                    on_disk=kwargs.get("on_disk", False)  # Store vectors on disk to save RAM
                ),
                # Optional: configure HNSW indexing parameters
                hnsw_config={
                    "m": kwargs.get("hnsw_m", 16),
                    "ef_construct": kwargs.get("hnsw_ef_construct", 100),
                    "full_scan_threshold": kwargs.get("full_scan_threshold", 10000)
                },
                # Optional: configure quantization for memory efficiency
                quantization_config=kwargs.get("quantization_config"),
                # Optional: replication factor for high availability
                replication_factor=kwargs.get("replication_factor", 1),
                # Optional: write ahead log
                wal_config=kwargs.get("wal_config"),
                # Optional: optimization settings
                optimizers_config=kwargs.get("optimizers_config"),
                on_disk_payload=kwargs.get("on_disk_payload", False)
            )
            
            # Create payload indexes for fast filtering
            await self.client.create_payload_index(
                collection_name=collection,
                field_name="document_id",
                field_schema="keyword"
            )
            
            await self.client.create_payload_index(
                collection_name=collection,
                field_name="chunk_index",
                field_schema="integer"
            )
            
            self._initialized_collections.add(collection)
            self.logger.info(
                f"✅ Created Qdrant collection: {collection} "
                f"(dimension={dimension}, metric={distance_metric})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error creating collection: {e}")
            return False
    
    async def index_exists(self, index_name: str) -> bool:
        """Check if collection exists."""
        try:
            collection = index_name if index_name != "default" else self.collection_name
            
            if collection in self._initialized_collections:
                return True
            
            collections = await self.client.get_collections()
            exists = any(c.name == collection for c in collections.collections)
            
            if exists:
                self._initialized_collections.add(collection)
            
            return exists
            
        except Exception as e:
            self.logger.error(f"Error checking collection existence: {e}")
            return False
    
    async def index_chunks(
        self,
        index_name: str,
        chunks: List[ChunkWithEmbedding],
        batch_size: int = 100
    ) -> BatchIndexResult:
        """
        Index chunks using batch upsert.
        
        Args:
            index_name: Target collection
            chunks: List of chunks with embeddings
            batch_size: Batch size for bulk indexing
        """
        if not chunks:
            return BatchIndexResult(success=True, indexed_count=0, failed_count=0, errors=[])
        
        collection = index_name if index_name != "default" else self.collection_name
        indexed_count = 0
        failed_count = 0
        errors = []
        
        try:
            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Prepare points for batch upsert
                points = []
                for chunk in batch:
                    try:
                        # Create Qdrant point
                        point = PointStruct(
                            id=chunk.chunk_id,  # Qdrant accepts string IDs
                            vector=chunk.embedding,
                            payload={
                                "chunk_id": chunk.chunk_id,
                                "document_id": chunk.document_id,
                                "chunk_index": chunk.chunk_index,
                                "content": chunk.content,
                                "metadata": chunk.metadata,
                                "created_at": chunk.created_at.isoformat()
                            }
                        )
                        points.append(point)
                    except Exception as e:
                        failed_count += 1
                        errors.append(f"Chunk {chunk.chunk_id}: {str(e)}")
                
                if not points:
                    continue
                
                # Batch upsert
                try:
                    await self.client.upsert(
                        collection_name=collection,
                        points=points,
                        wait=True  # Wait for indexing to complete
                    )
                    
                    indexed_count += len(points)
                    self.logger.info(f"Indexed batch {i//batch_size + 1}: {len(points)} chunks")
                    
                except Exception as e:
                    failed_count += len(points)
                    errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
                    self.logger.error(f"Error indexing batch: {e}")
            
            success = failed_count == 0
            self.logger.info(f"Indexing complete: {indexed_count} success, {failed_count} failed")
            
            return BatchIndexResult(
                success=success,
                indexed_count=indexed_count,
                failed_count=failed_count,
                errors=errors
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error indexing chunks: {e}")
            return BatchIndexResult(
                success=False,
                indexed_count=indexed_count,
                failed_count=len(chunks) - indexed_count,
                errors=[str(e)]
            )
    
    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search using vector similarity.
        
        Args:
            index_name: Collection to search
            query_vector: Query embedding
            limit: Maximum results
            threshold: Minimum similarity score
            filters: Optional payload filters
        """
        try:
            collection = index_name if index_name != "default" else self.collection_name
            
            # Build filter conditions
            query_filter = None
            if filters:
                conditions = [
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                    for key, value in filters.items()
                ]
                if conditions:
                    query_filter = Filter(must=conditions)
            
            # Perform search
            results = await self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=threshold,  # Qdrant handles threshold filtering
                with_payload=True,
                with_vectors=False  # Don't return vectors to save bandwidth
            )
            
            # Parse results
            search_results = []
            for result in results:
                payload = result.payload
                search_results.append(SearchResult(
                    chunk_id=payload["chunk_id"],
                    document_id=payload["document_id"],
                    content=payload["content"],
                    score=result.score,
                    metadata=payload.get("metadata", {}),
                    chunk_index=payload.get("chunk_index", 0)
                ))
            
            self.logger.info(f"Search returned {len(search_results)} results (threshold={threshold})")
            return search_results
            
        except Exception as e:
            self.logger.error(f"❌ Search error: {e}")
            return []
    
    async def delete_by_document_id(self, index_name: str, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            collection = index_name if index_name != "default" else self.collection_name
            
            # Delete points with matching document_id
            await self.client.delete(
                collection_name=collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                wait=True
            )
            
            self.logger.info(f"Deleted chunks for document: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error deleting document chunks: {e}")
            return False
    
    async def get_document_count(
        self,
        index_name: str,
        document_id: Optional[str] = None
    ) -> int:
        """Get count of chunks."""
        try:
            collection = index_name if index_name != "default" else self.collection_name
            
            if document_id:
                # Count with filter
                result = await self.client.count(
                    collection_name=collection,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=document_id)
                            )
                        ]
                    )
                )
                return result.count
            else:
                # Total count
                info = await self.client.get_collection(collection_name=collection)
                return info.points_count
                
        except Exception as e:
            self.logger.error(f"Error getting document count: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Qdrant service health."""
        try:
            # Simple health check - try to list collections
            await self.client.get_collections()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Close Qdrant client."""
        if self.client:
            await self.client.close()
            self.logger.info("Qdrant client closed")


# Register with factory
VectorStoreFactory.register_store("qdrant", QdrantVectorStore)

