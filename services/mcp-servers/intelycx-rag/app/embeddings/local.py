"""Local sentence-transformers embedding service implementation."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from .base import EmbeddingService, EmbeddingModel, EmbeddingServiceFactory

logger = logging.getLogger(__name__)


class LocalEmbeddingService(EmbeddingService):
    """
    Local embedding service using sentence-transformers.
    
    Best for budget-conscious deployments - no API costs, just compute.
    
    Recommended models:
    - all-MiniLM-L6-v2 (384 dim, fast, good quality)
    - all-mpnet-base-v2 (768 dim, slower, best quality)
    - paraphrase-multilingual-MiniLM-L12-v2 (384 dim, multilingual)
    """
    
    MODEL_CONFIGS = {
        "all-MiniLM-L6-v2": {
            "dimension": 384,
            "max_tokens": 256,
            "cost_per_1k": 0.0  # Compute only
        },
        "all-mpnet-base-v2": {
            "dimension": 768,
            "max_tokens": 384,
            "cost_per_1k": 0.0
        },
        "paraphrase-multilingual-MiniLM-L12-v2": {
            "dimension": 384,
            "max_tokens": 128,
            "cost_per_1k": 0.0
        },
        "all-MiniLM-L12-v2": {
            "dimension": 384,
            "max_tokens": 256,
            "cost_per_1k": 0.0
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local embedding service.
        
        Config parameters:
            model_name: Sentence-transformers model name
            device: Device to use (cpu, cuda, mps)
            batch_size: Batch size for encoding
            normalize_embeddings: Whether to normalize vectors
        """
        super().__init__(config)
        self.model_name = config.get("model_name", "all-MiniLM-L6-v2")
        if self.model_name not in self.MODEL_CONFIGS:
            self.logger.warning(
                f"Unknown model {self.model_name}, using default config. "
                f"Known models: {list(self.MODEL_CONFIGS.keys())}"
            )
            # Use default config for unknown models
            self.model_config = {
                "dimension": 768,
                "max_tokens": 256,
                "cost_per_1k": 0.0
            }
        else:
            self.model_config = self.MODEL_CONFIGS[self.model_name]
        
        self.device = config.get("device", "cpu")
        self.batch_size = config.get("batch_size", 32)
        self.normalize = config.get("normalize_embeddings", True)
        
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def initialize(self) -> bool:
        """Initialize sentence-transformers model."""
        try:
            # Import here to make it optional dependency
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                self.executor,
                lambda: SentenceTransformer(self.model_name, device=self.device)
            )
            
            if await self.health_check():
                self.logger.info(
                    f"✅ Local embedding service initialized: {self.model_name} "
                    f"(dimension={self.get_dimension()}, device={self.device})"
                )
                return True
            else:
                self.logger.error("Local model health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize local model: {e}")
            return False
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        text = await self.truncate_text(text)
        
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self.executor,
                lambda: self.model.encode(
                    [text],
                    normalize_embeddings=self.normalize,
                    convert_to_numpy=True
                )[0]
            )
            
            # Convert numpy array to list
            return embedding.tolist()
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        embeddings = []
        
        # Process in batches
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
                
                # Encode batch in thread pool
                loop = asyncio.get_event_loop()
                batch_embeddings = await loop.run_in_executor(
                    self.executor,
                    lambda: self.model.encode(
                        truncated_batch,
                        batch_size=len(truncated_batch),
                        normalize_embeddings=self.normalize,
                        convert_to_numpy=True,
                        show_progress_bar=False
                    )
                )
                
                # Convert numpy arrays to lists
                embeddings.extend([emb.tolist() for emb in batch_embeddings])
                
            except Exception as e:
                self.logger.error(f"Batch embedding error: {e}")
                # Fallback to zero vectors
                embeddings.extend([[0.0] * self.get_dimension()] * len(batch))
        
        self.logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        if self.model:
            # Get actual dimension from loaded model
            return self.model.get_sentence_embedding_dimension()
        return self.model_config["dimension"]
    
    def get_max_tokens(self) -> int:
        """Get maximum token limit."""
        return self.model_config["max_tokens"]
    
    def get_model_info(self) -> EmbeddingModel:
        """Get model information."""
        return EmbeddingModel(
            model_id=self.model_name,
            provider="local",
            dimension=self.get_dimension(),
            max_tokens=self.get_max_tokens(),
            cost_per_1k_tokens=0.0  # No API cost
        )
    
    async def health_check(self) -> bool:
        """Check if model is loaded and working."""
        try:
            if not self.model:
                return False
            await self.embed_text("health check test")
            return True
        except Exception as e:
            self.logger.warning(f"Local model health check failed: {e}")
            return False
    
    async def close(self):
        """Cleanup resources."""
        if self.executor:
            self.executor.shutdown(wait=True)
        self.model = None
        self.logger.info("Local embedding service closed")


# Register with factory
EmbeddingServiceFactory.register_service("local", LocalEmbeddingService)

