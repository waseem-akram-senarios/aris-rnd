"""OpenAI embedding service implementation."""

import logging
import asyncio
from typing import List, Dict, Any, Optional

import httpx

from .base import EmbeddingService, EmbeddingModel, EmbeddingServiceFactory

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService(EmbeddingService):
    """
    OpenAI embedding service implementation.
    
    Supports:
    - text-embedding-3-small (1536 dim, $0.02/1M tokens)
    - text-embedding-3-large (3072 dim, $0.13/1M tokens)
    - text-embedding-ada-002 (1536 dim, legacy)
    """
    
    MODEL_CONFIGS = {
        "text-embedding-3-small": {
            "dimension": 1536,
            "max_tokens": 8191,
            "cost_per_1k": 0.00002
        },
        "text-embedding-3-large": {
            "dimension": 3072,
            "max_tokens": 8191,
            "cost_per_1k": 0.00013
        },
        "text-embedding-ada-002": {
            "dimension": 1536,
            "max_tokens": 8191,
            "cost_per_1k": 0.0001
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenAI embedding service.
        
        Config parameters:
            api_key: OpenAI API key
            model_id: Model identifier
            batch_size: Batch size for API calls (max 2048)
            max_retries: Maximum retry attempts
        """
        super().__init__(config)
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model_id = config.get("model_id", "text-embedding-3-small")
        if self.model_id not in self.MODEL_CONFIGS:
            raise ValueError(f"Unsupported OpenAI model: {self.model_id}")
        
        self.model_config = self.MODEL_CONFIGS[self.model_id]
        self.batch_size = min(config.get("batch_size", 100), 2048)  # OpenAI limit
        self.max_retries = config.get("max_retries", 3)
        
        self.client: Optional[httpx.AsyncClient] = None
        self.api_url = "https://api.openai.com/v1/embeddings"
    
    async def initialize(self) -> bool:
        """Initialize OpenAI client."""
        try:
            self.client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=60.0
            )
            
            if await self.health_check():
                self.logger.info(
                    f"✅ OpenAI embedding service initialized: {self.model_id} "
                    f"(dimension={self.get_dimension()})"
                )
                return True
            else:
                self.logger.error("OpenAI health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize OpenAI: {e}")
            return False
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        text = await self.truncate_text(text)
        
        try:
            response = await self.client.post(
                self.api_url,
                json={
                    "model": self.model_id,
                    "input": text
                }
            )
            response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            return embedding
            
        except httpx.HTTPStatusError as e:
            self.logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"OpenAI API error: {e.response.status_code}")
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Generate embeddings using OpenAI's batch API.
        
        OpenAI allows up to 2048 inputs per request, much more efficient than individual calls.
        """
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            self.logger.info(
                f"Processing embedding batch {i//batch_size + 1}/"
                f"{(len(texts) + batch_size - 1)//batch_size}"
            )
            
            try:
                # Truncate texts in batch
                truncated_batch = [
                    await self.truncate_text(text) for text in batch
                ]
                
                # Call OpenAI batch API
                response = await self.client.post(
                    self.api_url,
                    json={
                        "model": self.model_id,
                        "input": truncated_batch
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                batch_embeddings = [item["embedding"] for item in data["data"]]
                embeddings.extend(batch_embeddings)
                
            except Exception as e:
                self.logger.error(f"Batch embedding error: {e}")
                # Fallback to zero vectors for failed batch
                embeddings.extend([[0.0] * self.get_dimension()] * len(batch))
            
            # Small delay between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.05)
        
        self.logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.model_config["dimension"]
    
    def get_max_tokens(self) -> int:
        """Get maximum token limit."""
        return self.model_config["max_tokens"]
    
    def get_model_info(self) -> EmbeddingModel:
        """Get model information."""
        return EmbeddingModel(
            model_id=self.model_id,
            provider="openai",
            dimension=self.get_dimension(),
            max_tokens=self.get_max_tokens(),
            cost_per_1k_tokens=self.model_config["cost_per_1k"]
        )
    
    async def health_check(self) -> bool:
        """Check if OpenAI service is available."""
        try:
            await self.embed_text("health check test")
            return True
        except Exception as e:
            self.logger.warning(f"OpenAI health check failed: {e}")
            return False
    
    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.logger.info("OpenAI embedding service closed")


# Register with factory
EmbeddingServiceFactory.register_service("openai", OpenAIEmbeddingService)

