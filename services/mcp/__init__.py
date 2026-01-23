"""
MCP (Model Context Protocol) Microservice

This service provides an MCP server for AI agents to interact with the ARIS RAG system.
It exposes tools for document ingestion and semantic search with accuracy-optimized features.

Tools:
- rag_ingest: Add documents to the RAG system
- rag_search: Query documents with advanced search capabilities

Features:
- Hybrid search (semantic + keyword)
- FlashRank reranking
- Agentic RAG query decomposition
- Confidence scoring
- Cross-language support
"""

from .engine import MCPEngine

__all__ = ['MCPEngine']

