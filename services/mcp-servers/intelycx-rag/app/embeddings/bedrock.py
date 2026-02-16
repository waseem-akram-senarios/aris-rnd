"""AWS Bedrock embedding service implementation."""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError

from .base import EmbeddingService, EmbeddingModel, EmbeddingServiceFactory

logger = logging.getLogger(__name__)


class BedrockEmbeddingService(EmbeddingService):
    """
    AWS Bedrock embedding service implementation.
    
    Supports multiple Bedrock embedding models:
    - Amazon Titan Text Embeddings v1 (1536 dim)
    - Amazon Titan Text Embeddings v2 (1024/512/256 dim, configurable)
    - Cohere Embed English v3 (1024 dim)
    - Cohere Embed Multilingual v3 (1024 dim)
    """
    
    # Model configurations
    MODEL_CONFIGS = {
        "amazon.titan-embed-text-v1": {
            "dimension": 1536,
            "max_tokens": 8192,
            "cost_per_1k": 0.0001,
            "request_format": "titan"
        },
        "amazon.titan-embed-text-v2:0": {
            "dimension": 1024,  # Default, can be 256/512/1024
            "max_tokens": 8192,
            "cost_per_1k": 0.00002,
            "request_format": "titan_v2"
        },
        "cohere.embed-english-v3": {
            "dimension": 1024,
            "max_tokens": 512,
            "cost_per_1k": 0.0001,
            "request_format": "cohere"
        },
        "cohere.embed-multilingual-v3": {
            "dimension": 1024,
            "max_tokens": 512,
            "cost_per_1k": 0.0001,
            "request_format": "cohere"
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Bedrock embedding service.
        
        Config parameters:
            model_id: Bedrock model ID
            region: AWS region
            dimension: Vector dimension (for models that support it)
            batch_size: Number of texts to process concurrently
            max_retries: Maximum retry attempts for failed requests
        """
        super().__init__(config)
        self.model_id = config.get("model_id", "amazon.titan-embed-text-v2:0")
        self.region = config.get("region", "us-east-2")
        self.dimension = config.get("dimension")
        self.batch_size = config.get("batch_size", 20)
        self.max_retries = config.get("max_retries", 3)
        
        # Validate model
        if self.model_id not in self.MODEL_CONFIGS:
            raise ValueError(f"Unsupported Bedrock model: {self.model_id}")
        
        self.model_config = self.MODEL_CONFIGS[self.model_id]
        
        # Override dimension if specified and supported
        if self.dimension:
            if self.model_id == "amazon.titan-embed-text-v2:0":
                if self.dimension not in [256, 512, 1024]:
                    raise ValueError("Titan v2 dimension must be 256, 512, or 1024")
                self.model_config["dimension"] = self.dimension
        
        self.client = None
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    async def initialize(self) -> bool:
        """Initialize Bedrock client."""
        try:
            self.client = boto3.client(
                'bedrock-runtime',
                region_name=self.region
            )
            
            # Test connection
            if await self.health_check():
                self.logger.info(
                    f"✅ Bedrock embedding service initialized: {self.model_id} "
                    f"(dimension={self.get_dimension()})"
                )
                return True
            else:
                self.logger.error("Bedrock health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Bedrock: {e}")
            return False
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Truncate if needed
        text = await self.truncate_text(text)
        
        try:
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self.executor,
                self._embed_text_sync,
                text
            )
            return embedding
            
        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    def _embed_text_sync(self, text: str) -> List[float]:
        """Synchronous embedding generation with retries."""
        request_format = self.model_config["request_format"]
        
        # Prepare request body based on model
        if request_format == "titan":
            body = json.dumps({"inputText": text})
        elif request_format == "titan_v2":
            body = json.dumps({
                "inputText": text,
                "dimensions": self.model_config["dimension"],
                "normalize": True
            })
        elif request_format == "cohere":
            body = json.dumps({
                "texts": [text],
                "input_type": "search_document"  # or "search_query" for queries
            })
        else:
            raise ValueError(f"Unknown request format: {request_format}")
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.invoke_model(
                    body=body,
                    modelId=self.model_id,
                    accept='application/json',
                    contentType='application/json'
                )
                
                response_body = json.loads(response.get('body').read())
                
                # Extract embedding based on model
                if request_format in ["titan", "titan_v2"]:
                    embedding = response_body.get('embedding', [])
                elif request_format == "cohere":
                    embeddings = response_body.get('embeddings', [[]])
                    embedding = embeddings[0] if embeddings else []
                else:
                    raise ValueError(f"Unknown response format for model: {self.model_id}")
                
                if not embedding:
                    raise ValueError("Empty embedding returned")
                
                # Validate dimension
                expected_dim = self.model_config["dimension"]
                if len(embedding) != expected_dim:
                    self.logger.warning(
                        f"Embedding dimension mismatch: got {len(embedding)}, expected {expected_dim}"
                    )
                
                return embedding
                
            except ClientError as e:
                last_error = e
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                # Don't retry on certain errors
                if error_code in ['ValidationException', 'AccessDeniedException']:
                    raise
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Bedrock API error, retrying in {wait_time}s: {error_code}")
                    import time
                    time.sleep(wait_time)
                    
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Embedding error, retrying in {wait_time}s: {e}")
                    import time
                    time.sleep(wait_time)
        
        raise RuntimeError(f"Failed after {self.max_retries} attempts: {last_error}")
    
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
            
            # Generate embeddings concurrently within batch
            batch_tasks = [self.embed_text(text) for text in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle results and exceptions
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to embed text {i + j}: {result}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * self.get_dimension())
                else:
                    embeddings.append(result)
            
            # Small delay between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
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
            provider="bedrock",
            dimension=self.get_dimension(),
            max_tokens=self.get_max_tokens(),
            cost_per_1k_tokens=self.model_config["cost_per_1k"]
        )
    
    async def health_check(self) -> bool:
        """Check if Bedrock service is available."""
        try:
            # Test with a simple embedding
            await self.embed_text("health check test")
            return True
        except Exception as e:
            self.logger.warning(f"Bedrock health check failed: {e}")
            return False
    
    async def close(self):
        """Cleanup resources."""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.logger.info("Bedrock embedding service closed")


# Register with factory
EmbeddingServiceFactory.register_service("bedrock", BedrockEmbeddingService)

