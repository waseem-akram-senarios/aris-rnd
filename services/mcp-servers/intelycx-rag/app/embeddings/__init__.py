"""Embedding service abstraction layer for RAG system."""

from .base import EmbeddingService, EmbeddingServiceFactory
from .bedrock import BedrockEmbeddingService
from .openai_embeddings import OpenAIEmbeddingService
from .local import LocalEmbeddingService

__all__ = [
    "EmbeddingService",
    "EmbeddingServiceFactory",
    "BedrockEmbeddingService",
    "OpenAIEmbeddingService",
    "LocalEmbeddingService",
]

