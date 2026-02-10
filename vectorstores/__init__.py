"""
Vector store implementations for RAG system.
Supports both FAISS (local) and OpenSearch (cloud) backends.
"""

from .vector_store_factory import VectorStoreFactory, create_vector_store

__all__ = ['VectorStoreFactory', 'create_vector_store']

