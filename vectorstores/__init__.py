"""
Vector store implementations for RAG system.
Supports FAISS (local), OpenSearch (cloud), and PGVector (PostgreSQL) backends.
"""

from .vector_store_factory import VectorStoreFactory, create_vector_store

__all__ = ['VectorStoreFactory', 'create_vector_store']
