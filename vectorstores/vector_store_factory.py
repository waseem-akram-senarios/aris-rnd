"""
Vector Store Factory for creating and managing different vector store backends.
Supports FAISS (local) and OpenSearch (cloud).
"""
import os
import logging
from typing import List, Optional, Dict, Any, Tuple
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
        self._embedding_dimension: Optional[int] = None
    
    def _get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings dynamically."""
        if self._embedding_dimension is None:
            # Use a small test text to get embedding dimension
            test_text = "test"
            test_embedding = self.embeddings.embed_query(test_text)
            self._embedding_dimension = len(test_embedding)
            logger.info(f"Detected embedding dimension: {self._embedding_dimension} (model: {getattr(self.embeddings, 'model', 'unknown')})")
        return self._embedding_dimension
    
    def _get_existing_dimension(self) -> Optional[int]:
        """Get the dimension of the existing FAISS index."""
        if self.vectorstore is None or not hasattr(self.vectorstore, 'index'):
            return None
        try:
            return self.vectorstore.index.d if hasattr(self.vectorstore.index, 'd') else None
        except Exception as e:
            logger.warning(f"_get_existing_dimension: {type(e).__name__}: {e}")
            return None
    
    def _check_dimension_compatibility(self) -> Tuple[bool, Optional[int], Optional[int]]:
        """
        Check if embedding dimensions are compatible.
        
        Returns:
            (is_compatible, existing_dim, new_dim)
        """
        existing_dim = self._get_existing_dimension()
        if existing_dim is None:
            return True, None, None  # No existing index, compatible
        
        new_dim = self._get_embedding_dimension()
        is_compatible = existing_dim == new_dim
        
        return is_compatible, existing_dim, new_dim
    
    def from_documents(self, documents: List[Document]) -> 'FAISSVectorStore':
        """Create vector store from documents."""
        logger.info(f"Creating FAISS vectorstore from {len(documents)} documents...")
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        logger.info("FAISS vectorstore created successfully")
        return self
    
    def add_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True):
        """
        Add documents to existing vector store.
        
        Args:
            documents: Documents to add
            auto_recreate_on_mismatch: If True, automatically recreate vectorstore when dimension mismatch is detected
        """
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
        
        # Check dimension compatibility before adding
        is_compatible, existing_dim, new_dim = self._check_dimension_compatibility()
        
        if not is_compatible:
            error_msg = (
                f"❌ Embedding dimension mismatch detected!\n"
                f"   Existing vectorstore dimension: {existing_dim}\n"
                f"   New embeddings dimension: {new_dim}\n"
                f"   Embedding model: {getattr(self.embeddings, 'model', 'unknown')}"
            )
            
            if auto_recreate_on_mismatch:
                logger.warning(f"{error_msg}")
                logger.warning("⚠️ Automatically recreating vectorstore with correct dimension...")
                # Clear the existing vectorstore
                self.vectorstore = None
                # Recreate with new documents
                logger.info(f"Recreating FAISS vectorstore with {len(valid_docs)} documents (dimension: {new_dim})...")
                self.vectorstore = FAISS.from_documents(valid_docs, self.embeddings)
                logger.info("✅ Vectorstore recreated successfully with correct dimension")
                return
            else:
                logger.error(error_msg)
                raise ValueError(
                    f"Dimension mismatch: existing={existing_dim}, new={new_dim}. "
                    f"Set auto_recreate_on_mismatch=True to automatically fix this."
                )
        
        logger.info(f"Adding {len(valid_docs)} documents to FAISS vectorstore (dimension: {new_dim or self._get_embedding_dimension()})...")
        try:
            self.vectorstore.add_documents(valid_docs)
            logger.info("Documents added to FAISS vectorstore successfully")
        except AssertionError as e:
            # Catch FAISS dimension assertion error
            error_str = str(e) if str(e) else "AssertionError"
            if "d == self.d" in error_str or "dimension" in error_str.lower():
                # This is a dimension mismatch error
                existing_dim = self._get_existing_dimension()
                new_dim = self._get_embedding_dimension()
                
                if auto_recreate_on_mismatch:
                    logger.warning(
                        f"⚠️ Dimension mismatch detected during add_documents: "
                        f"existing={existing_dim}, new={new_dim}. Auto-recreating..."
                    )
                    # Get all existing documents from the vectorstore
                    try:
                        # Try to retrieve existing documents (if possible)
                        existing_docs = []
                        # Note: FAISS doesn't easily allow retrieving all documents, so we'll just recreate with new ones
                        logger.warning("⚠️ Existing documents in vectorstore will be lost. Recreating with new documents only.")
                    except Exception:
                        pass
                    
                    # Clear and recreate
                    self.vectorstore = None
                    self.vectorstore = FAISS.from_documents(valid_docs, self.embeddings)
                    logger.info(f"✅ Vectorstore recreated with {len(valid_docs)} documents (dimension: {new_dim})")
                    return
                else:
                    detailed_error = (
                        f"❌ FAISS Dimension Mismatch!\n"
                        f"   Existing index dimension: {existing_dim}\n"
                        f"   New embedding dimension: {new_dim}\n"
                        f"   Embedding model: {getattr(self.embeddings, 'model', 'unknown')}\n\n"
                        f"   Solution: Delete the existing vectorstore or set auto_recreate_on_mismatch=True"
                    )
                    logger.error(detailed_error)
                    raise ValueError(detailed_error) from e
            else:
                # Other AssertionError, re-raise as-is
                raise
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
        """Load vector store from local disk with dimension validation."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Vector store path not found: {path}")
        
        try:
            self.vectorstore = FAISS.load_local(path, self.embeddings, allow_dangerous_deserialization=True)
            
            # Validate dimension after loading
            is_compatible, existing_dim, new_dim = self._check_dimension_compatibility()
            if not is_compatible:
                logger.warning(
                    f"⚠️ Dimension mismatch detected after loading:\n"
                    f"   Loaded index dimension: {existing_dim}\n"
                    f"   Current embedding dimension: {new_dim}\n"
                    f"   This vectorstore was created with a different embedding model.\n"
                    f"   The vectorstore will be recreated on next document addition."
                )
                # Don't fail here, let add_documents handle the recreation
            else:
                logger.info(f"FAISS vectorstore loaded from {path} (dimension: {existing_dim})")
        except Exception as e:
            # If loading fails due to dimension mismatch, log and re-raise
            error_msg = str(e)
            if "dimension" in error_msg.lower() or "assert" in error_msg.lower():
                new_dim = self._get_embedding_dimension()
                logger.error(
                    f"❌ Cannot load vectorstore: dimension mismatch.\n"
                    f"   Current embedding dimension: {new_dim}\n"
                    f"   Vectorstore at {path} was created with a different dimension.\n"
                    f"   Solution: Delete {path} and recreate, or use a different embedding model."
                )
            raise


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

