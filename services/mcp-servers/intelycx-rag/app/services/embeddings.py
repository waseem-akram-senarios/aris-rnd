"""Embedding service using AWS Bedrock Titan models."""

import json
import logging
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.exceptions import ClientError

from ..config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using AWS Bedrock."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.bedrock_client = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def initialize(self):
        """Initialize the Bedrock client."""
        try:
            # Create Bedrock Runtime client
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=self.settings.bedrock_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key
            )
            
            # Test the connection
            await self.health_check()
            logger.info(f"✅ Bedrock embedding service initialized with model: {self.settings.embedding_model}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Bedrock client: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if Bedrock service is available."""
        try:
            # Test with a simple embedding request
            await self.generate_embedding("test")
            return True
        except Exception as e:
            logger.warning(f"Bedrock health check failed: {e}")
            return False
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Truncate text if too long (Titan has token limits)
        max_chars = 8000  # Conservative limit for Titan
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} characters for embedding")
        
        try:
            # Run the synchronous Bedrock call in a thread pool
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                self.executor, 
                self._generate_embedding_sync, 
                text
            )
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    def _generate_embedding_sync(self, text: str) -> List[float]:
        """Synchronous embedding generation."""
        try:
            # Prepare the request body based on model type
            if "titan-embed" in self.settings.embedding_model:
                body = json.dumps({
                    "inputText": text
                })
            else:
                raise ValueError(f"Unsupported embedding model: {self.settings.embedding_model}")
            
            # Call Bedrock
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.settings.embedding_model,
                accept='application/json',
                contentType='application/json'
            )
            
            # Parse response
            response_body = json.loads(response.get('body').read())
            
            if "titan-embed" in self.settings.embedding_model:
                embedding = response_body.get('embedding', [])
            else:
                raise ValueError(f"Unknown response format for model: {self.settings.embedding_model}")
            
            if not embedding:
                raise ValueError("Empty embedding returned from Bedrock")
            
            # Validate embedding dimensions
            expected_dims = self.settings.embedding_dimensions
            if len(embedding) != expected_dims:
                logger.warning(
                    f"Embedding dimension mismatch: got {len(embedding)}, expected {expected_dims}"
                )
            
            return embedding
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Bedrock API error [{error_code}]: {error_message}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in embedding generation: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process concurrently
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing embedding batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            # Generate embeddings concurrently within the batch
            batch_tasks = [self.generate_embedding(text) for text in batch]
            batch_embeddings = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle results and exceptions
            for j, result in enumerate(batch_embeddings):
                if isinstance(result, Exception):
                    logger.error(f"Failed to embed text {i + j}: {result}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * self.settings.embedding_dimensions)
                else:
                    embeddings.append(result)
            
            # Small delay between batches to be respectful to the API
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    
    def get_embedding_dimensions(self) -> int:
        """Get the dimensionality of the embedding model."""
        return self.settings.embedding_dimensions
    
    def get_model_info(self) -> dict:
        """Get information about the current embedding model."""
        return {
            "model_id": self.settings.embedding_model,
            "dimensions": self.settings.embedding_dimensions,
            "region": self.settings.bedrock_region
        }
