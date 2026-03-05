"""
PGVector vector store implementation for ARIS RAG.
Uses LangChain's PostgreSQL pgvector backend.
"""
import os
import logging
from typing import List, Optional, Dict, Any

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


class PgVectorStore:
    """PGVector wrapper with an interface similar to other vector stores in this repo."""

    def __init__(
        self,
        embeddings,
        connection_string: Optional[str] = None,
        collection_name: str = "aris_rag_index",
    ):
        self.embeddings = embeddings
        self.connection_string = connection_string or self._build_connection_string_from_env()
        self.collection_name = collection_name
        self.index_name = collection_name  # compatibility with OpenSearch code paths
        self.vectorstore = None
        self._initialize_vectorstore()

    @staticmethod
    def _build_connection_string_from_env() -> str:
        """Resolve PG connection from env, preferring a full URI."""
        conn = os.getenv("PGVECTOR_CONNECTION_STRING")
        if conn:
            return conn

        host = os.getenv("PGVECTOR_HOST")
        port = os.getenv("PGVECTOR_PORT", "5432")
        database = os.getenv("PGVECTOR_DATABASE")
        user = os.getenv("PGVECTOR_USER")
        password = os.getenv("PGVECTOR_PASSWORD")

        if host and database and user and password:
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"

        raise ValueError(
            "PGVector connection is required. Set PGVECTOR_CONNECTION_STRING "
            "or PGVECTOR_HOST/PGVECTOR_PORT/PGVECTOR_DATABASE/PGVECTOR_USER/PGVECTOR_PASSWORD."
        )

    def _initialize_vectorstore(self):
        """Initialize PGVector collection (creates collection metadata if missing)."""
        try:
            from langchain_community.vectorstores import PGVector
        except ImportError as e:
            raise ImportError(
                "PGVector support requires langchain-community with pgvector deps. "
                "Install psycopg2-binary and pgvector."
            ) from e

        self.vectorstore = PGVector(
            connection_string=self.connection_string,
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
            use_jsonb=True,
        )

    def from_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True) -> "PgVectorStore":
        """Create/store vectors from documents in PGVector collection."""
        if not documents:
            return self
        try:
            from langchain_community.vectorstores import PGVector
            self.vectorstore = PGVector.from_documents(
                documents=documents,
                embedding=self.embeddings,
                connection_string=self.connection_string,
                collection_name=self.collection_name,
                pre_delete_collection=False,
                use_jsonb=True,
            )
            return self
        except Exception as e:
            logger.error(f"Failed to build PGVector collection from documents: {e}")
            raise

    def add_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True):
        """Add documents to PGVector collection."""
        if not documents:
            return
        if self.vectorstore is None:
            self.from_documents(documents, auto_recreate_on_mismatch=auto_recreate_on_mismatch)
            return
        self.vectorstore.add_documents(documents)

    def as_retriever(self, search_type: str = "similarity", search_kwargs: Optional[Dict] = None):
        """Return retriever interface."""
        if self.vectorstore is None:
            raise ValueError("PGVector store not initialized")
        return self.vectorstore.as_retriever(search_type=search_type, search_kwargs=search_kwargs or {})

    def similarity_search(self, query: str, k: int = 4, filter: Optional[Dict] = None):
        """Run semantic similarity search."""
        if self.vectorstore is None:
            raise ValueError("PGVector store not initialized")
        kwargs = {"k": k}
        if filter:
            kwargs["filter"] = filter
        return self.vectorstore.similarity_search(query, **kwargs)

    def hybrid_search(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        k: int = 10,
        semantic_weight: float = 1.0,
        keyword_weight: float = 0.0,
        filter: Optional[Dict[str, Any]] = None,
    ):
        """
        PGVector fallback for hybrid_search API compatibility.
        Uses semantic similarity search only.
        """
        results = self.similarity_search(query=query, k=k, filter=filter)
        for d in results:
            if hasattr(d, "metadata") and isinstance(d.metadata, dict):
                d.metadata.setdefault("_pgvector_semantic_only", True)
        return results

    def count_documents(self) -> int:
        """Count stored embeddings in this collection."""
        try:
            engine = create_engine(self.connection_string)
            with engine.begin() as conn:
                result = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM langchain_pg_embedding e
                        JOIN langchain_pg_collection c ON e.collection_id = c.uuid
                        WHERE c.name = :collection_name
                        """
                    ),
                    {"collection_name": self.collection_name},
                )
                count = result.scalar()
                return int(count or 0)
        except Exception as e:
            logger.warning(f"Could not count PGVector documents for '{self.collection_name}': {e}")
            return 0
