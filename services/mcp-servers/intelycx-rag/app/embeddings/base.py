"""Abstract base class for embedding services."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingModel:
    """Embedding model information."""
    model_id: str
    provider: str  # bedrock, openai, local
    dimension: int
    max_tokens: int
    cost_per_1k_tokens: float  # For cost estimation


class EmbeddingService(ABC):
    """
    Abstract base class for embedding service implementations.
    
    Supports multiple providers:
    - AWS Bedrock (Titan, Cohere)
    - OpenAI (text-embedding-3-small, text-embedding-3-large)
    - Local (sentence-transformers for budget clients)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize embedding service with configuration.
        
        Args:
            config: Configuration dictionary specific to the provider
        """
        self.config = config
        self.logger = logger
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the embedding service.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
            
        Raises:
            ValueError: If text is empty or too long
            RuntimeError: If embedding generation fails
        """
        pass
    
    @abstractmethod
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch (None = provider default)
            
        Returns:
            List of embedding vectors
            
        Note:
            Failed embeddings are replaced with zero vectors and logged as errors.
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the dimensionality of embeddings.
        
        Returns:
            Vector dimension
        """
        pass
    
    @abstractmethod
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for input text.
        
        Returns:
            Maximum number of tokens
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> EmbeddingModel:
        """
        Get information about the embedding model.
        
        Returns:
            EmbeddingModel with details
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if embedding service is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    async def truncate_text(self, text: str, max_chars: Optional[int] = None) -> str:
        """
        Truncate text to fit model constraints.
        
        Args:
            text: Input text
            max_chars: Maximum characters (None = use model default)
            
        Returns:
            Truncated text
        """
        if not max_chars:
            # Estimate chars from tokens (rough approximation: 4 chars per token)
            max_chars = self.get_max_tokens() * 4
        
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        self.logger.warning(f"Text truncated from {len(text)} to {max_chars} characters")
        return truncated
    
    async def close(self):
        """Close connections and cleanup resources."""
        pass


class EmbeddingServiceFactory:
    """
    Factory for creating embedding service instances based on configuration.
    
    Supports:
    - bedrock: AWS Bedrock (Titan, Cohere)
    - openai: OpenAI embeddings
    - local: Local sentence-transformers
    """
    
    _service_types = {}
    
    @classmethod
    def register_service(cls, service_type: str, service_class):
        """Register an embedding service implementation."""
        cls._service_types[service_type] = service_class
        logger.info(f"Registered embedding service type: {service_type}")
    
    @classmethod
    def create(cls, service_type: str, config: Dict[str, Any]) -> EmbeddingService:
        """
        Create an embedding service instance.
        
        Args:
            service_type: Type of service (bedrock, openai, local)
            config: Configuration dictionary for the service
            
        Returns:
            EmbeddingService instance
            
        Raises:
            ValueError: If service_type is not supported
        """
        if service_type not in cls._service_types:
            supported = ", ".join(cls._service_types.keys())
            raise ValueError(
                f"Unsupported embedding service type: {service_type}. "
                f"Supported types: {supported}"
            )
        
        service_class = cls._service_types[service_type]
        logger.info(f"Creating embedding service: {service_type}")
        return service_class(config)
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported embedding service types."""
        return list(cls._service_types.keys())
    
    @classmethod
    def get_recommended_config(cls, service_type: str, profile: str = "standard") -> Dict[str, Any]:
        """
        Get recommended configuration for a service type and profile.
        
        Args:
            service_type: Type of service
            profile: Configuration profile (economy, standard, premium)
            
        Returns:
            Recommended configuration dictionary
        """
        configs = {
            "bedrock": {
                "economy": {
                    "model_id": "amazon.titan-embed-text-v1",
                    "dimension": 1536,
                    "batch_size": 10
                },
                "standard": {
                    "model_id": "amazon.titan-embed-text-v2:0",
                    "dimension": 1024,
                    "batch_size": 20
                },
                "premium": {
                    "model_id": "cohere.embed-english-v3",
                    "dimension": 1024,
                    "batch_size": 50
                }
            },
            "openai": {
                "economy": {
                    "model_id": "text-embedding-3-small",
                    "dimension": 1536,
                    "batch_size": 100
                },
                "standard": {
                    "model_id": "text-embedding-3-small",
                    "dimension": 1536,
                    "batch_size": 100
                },
                "premium": {
                    "model_id": "text-embedding-3-large",
                    "dimension": 3072,
                    "batch_size": 100
                }
            },
            "local": {
                "economy": {
                    "model_name": "all-MiniLM-L6-v2",
                    "dimension": 384,
                    "batch_size": 32
                },
                "standard": {
                    "model_name": "all-mpnet-base-v2",
                    "dimension": 768,
                    "batch_size": 32
                },
                "premium": {
                    "model_name": "all-mpnet-base-v2",
                    "dimension": 768,
                    "batch_size": 64
                }
            }
        }
        
        return configs.get(service_type, {}).get(profile, {})

