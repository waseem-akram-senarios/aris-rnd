"""Abstract base class for vector stores."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChunkWithEmbedding:
    """Document chunk with its embedding vector."""
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class SearchResult:
    """Search result from vector store."""
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    chunk_index: int


@dataclass
class BatchIndexResult:
    """Result of batch indexing operation."""
    success: bool
    indexed_count: int
    failed_count: int
    errors: List[str]


class VectorStore(ABC):
    """
    Abstract base class for vector store implementations.
    
    Provides a unified interface for different vector databases:
    - OpenSearch (AWS managed or self-hosted)
    - PGVector (PostgreSQL extension)
    - Qdrant (Cloud or self-hosted)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize vector store with configuration.
        
        Args:
            config: Configuration dictionary specific to the vector store
        """
        self.config = config
        self.logger = logger
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize connection to vector store.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def create_index(
        self,
        index_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> bool:
        """
        Create a vector index/collection.
        
        Args:
            index_name: Name of the index/collection
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, euclidean, dot_product)
            **kwargs: Additional store-specific parameters
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def index_exists(self, index_name: str) -> bool:
        """
        Check if an index/collection exists.
        
        Args:
            index_name: Name of the index/collection
            
        Returns:
            True if exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def index_chunks(
        self,
        index_name: str,
        chunks: List[ChunkWithEmbedding],
        batch_size: int = 100
    ) -> BatchIndexResult:
        """
        Index document chunks with embeddings.
        
        Args:
            index_name: Target index/collection name
            chunks: List of chunks with embeddings to index
            batch_size: Number of chunks to index per batch
            
        Returns:
            BatchIndexResult with success status and counts
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            index_name: Index/collection to search
            query_vector: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0.0-1.0)
            filters: Optional metadata filters
            
        Returns:
            List of search results sorted by relevance
        """
        pass
    
    @abstractmethod
    async def delete_by_document_id(
        self,
        index_name: str,
        document_id: str
    ) -> bool:
        """
        Delete all chunks for a document.
        
        Args:
            index_name: Index/collection name
            document_id: Document ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_document_count(
        self,
        index_name: str,
        document_id: Optional[str] = None
    ) -> int:
        """
        Get count of indexed chunks.
        
        Args:
            index_name: Index/collection name
            document_id: Optional document ID to count chunks for specific document
            
        Returns:
            Number of chunks
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if vector store is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close connections and cleanup resources."""
        pass


class VectorStoreFactory:
    """
    Factory for creating vector store instances based on configuration.
    
    Supports:
    - opensearch: AWS OpenSearch or OpenSearch self-hosted
    - pgvector: PostgreSQL with pgvector extension
    - qdrant: Qdrant Cloud or self-hosted
    """
    
    _store_types = {}
    
    @classmethod
    def register_store(cls, store_type: str, store_class):
        """Register a vector store implementation."""
        cls._store_types[store_type] = store_class
        logger.info(f"Registered vector store type: {store_type}")
    
    @classmethod
    def create(cls, store_type: str, config: Dict[str, Any]) -> VectorStore:
        """
        Create a vector store instance.
        
        Args:
            store_type: Type of vector store (opensearch, pgvector, qdrant)
            config: Configuration dictionary for the store
            
        Returns:
            VectorStore instance
            
        Raises:
            ValueError: If store_type is not supported
        """
        if store_type not in cls._store_types:
            supported = ", ".join(cls._store_types.keys())
            raise ValueError(
                f"Unsupported vector store type: {store_type}. "
                f"Supported types: {supported}"
            )
        
        store_class = cls._store_types[store_type]
        logger.info(f"Creating vector store: {store_type}")
        return store_class(config)
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported vector store types."""
        return list(cls._store_types.keys())

