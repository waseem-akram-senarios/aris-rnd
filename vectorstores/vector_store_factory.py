"""
Vector Store Factory for creating and managing different vector store backends.
Supports FAISS (local) and OpenSearch (cloud).
"""
import os
import logging
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for creating and managing vector stores."""
    
    @staticmethod
    def create_vector_store(
        store_type: str,
        embeddings: OpenAIEmbeddings,
        opensearch_domain: Optional[str] = None,
        opensearch_index: Optional[str] = None,
        opensearch_endpoint: Optional[str] = None
    ):
        """
        Create a vector store instance.
        
        Args:
            store_type: Type of vector store ("faiss" or "opensearch")
            embeddings: Embeddings model to use
            opensearch_domain: OpenSearch domain name (required for OpenSearch)
            opensearch_index: OpenSearch index name (optional, defaults to "aris-rag-index")
        
        Returns:
            Vector store instance (FAISS or OpenSearch wrapper)
        """
        if store_type.lower() == "faiss":
            return FAISSVectorStore(embeddings)
        elif store_type.lower() == "opensearch":
            if not opensearch_domain and not opensearch_endpoint:
                # Try to get from environment variable
                opensearch_domain = os.getenv('AWS_OPENSEARCH_DOMAIN')
                if not opensearch_domain and not opensearch_endpoint:
                    raise ValueError("OpenSearch domain or endpoint is required when using OpenSearch vector store. Set AWS_OPENSEARCH_DOMAIN in .env or pass opensearch_domain parameter.")
            from .opensearch_store import OpenSearchVectorStore
            return OpenSearchVectorStore(
                embeddings=embeddings,
                domain=opensearch_domain or os.getenv('AWS_OPENSEARCH_DOMAIN', 'intelycx-waseem-os'),
                index_name=opensearch_index or "aris-rag-index",
                endpoint=opensearch_endpoint
            )
        else:
            raise ValueError(f"Unknown vector store type: {store_type}. Supported types: 'faiss', 'opensearch'")
    
    @staticmethod
    def load_vector_store(
        store_type: str,
        embeddings: OpenAIEmbeddings,
        path: str,
        opensearch_domain: Optional[str] = None,
        opensearch_index: Optional[str] = None
    ):
        """
        Load an existing vector store from disk or cloud.
        
        Args:
            store_type: Type of vector store ("faiss" or "opensearch")
            embeddings: Embeddings model to use
            path: Path to load from (for FAISS) or index name (for OpenSearch)
            opensearch_domain: OpenSearch domain name (required for OpenSearch)
            opensearch_index: OpenSearch index name (optional)
        
        Returns:
            Loaded vector store instance
        """
        if store_type.lower() == "faiss":
            store = FAISSVectorStore(embeddings)
            store.load_local(path)
            return store
        elif store_type.lower() == "opensearch":
            if not opensearch_domain:
                raise ValueError("OpenSearch domain is required when using OpenSearch vector store")
            from .opensearch_store import OpenSearchVectorStore
            store = OpenSearchVectorStore(
                embeddings=embeddings,
                domain=opensearch_domain,
                index_name=opensearch_index or path or "aris-rag-index"
            )
            # OpenSearch loads from the index automatically
            return store
        else:
            raise ValueError(f"Unknown vector store type: {store_type}")


class FAISSVectorStore:
    """Wrapper for FAISS vector store to provide consistent interface."""
    
    def __init__(self, embeddings: OpenAIEmbeddings):
        self.embeddings = embeddings
        self.vectorstore: Optional[FAISS] = None
    
    def from_documents(self, documents: List[Document]) -> 'FAISSVectorStore':
        """Create vector store from documents."""
        logger.info(f"Creating FAISS vectorstore from {len(documents)} documents...")
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        logger.info("FAISS vectorstore created successfully")
        return self
    
    def add_documents(self, documents: List[Document]):
        """Add documents to existing vector store."""
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Call from_documents() first.")
        
        if not documents:
            raise ValueError("Cannot add empty document list to vectorstore.")
        
        # Validate documents before adding
        valid_docs = []
        for doc in documents:
            if doc is None:
                continue
            if not hasattr(doc, 'page_content'):
                continue
            if not doc.page_content or not str(doc.page_content).strip():
                continue
            valid_docs.append(doc)
        
        if not valid_docs:
            raise ValueError("No valid documents to add to vectorstore. All documents are empty or None.")
        
        logger.info(f"Adding {len(valid_docs)} documents to FAISS vectorstore...")
        try:
            self.vectorstore.add_documents(valid_docs)
            logger.info("Documents added to FAISS vectorstore successfully")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error(f"FAISS: Error adding documents: {error_msg}")
            logger.error(f"FAISS: Full traceback:\n{error_details}")
            raise
    
    def as_retriever(self, search_type: str = "similarity", search_kwargs: Optional[Dict] = None):
        """Get retriever for querying."""
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Process documents first.")
        return self.vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs or {}
        )
    
    def save_local(self, path: str):
        """Save vector store to local disk."""
        if self.vectorstore is None:
            raise ValueError("No vector store to save")
        self.vectorstore.save_local(path)
        logger.info(f"FAISS vectorstore saved to {path}")
    
    def load_local(self, path: str):
        """Load vector store from local disk."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Vector store path not found: {path}")
        self.vectorstore = FAISS.load_local(path, self.embeddings, allow_dangerous_deserialization=True)
        logger.info(f"FAISS vectorstore loaded from {path}")


# Convenience function
def create_vector_store(
    store_type: str,
    embeddings: OpenAIEmbeddings,
    opensearch_domain: Optional[str] = None,
    opensearch_index: Optional[str] = None
):
    """Convenience function to create a vector store."""
    return VectorStoreFactory.create_vector_store(
        store_type=store_type,
        embeddings=embeddings,
        opensearch_domain=opensearch_domain,
        opensearch_index=opensearch_index
    )

