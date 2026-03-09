"""
Qdrant vector store implementation for ARIS RAG.
Uses LangChain's Qdrant backend.
"""
import os
import logging
from typing import List, Optional, Dict, Any, Tuple

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class QdrantStore:
    """Qdrant wrapper with an interface similar to other vector stores in this repo."""

    def __init__(
        self,
        embeddings,
        url: Optional[str] = None,
        collection_name: str = "aris_rag_index",
        api_key: Optional[str] = None,
        prefer_grpc: bool = False,
    ):
        self.embeddings = embeddings
        self.url = url or os.getenv("QDRANT_URL")
        self.collection_name = collection_name
        self.index_name = collection_name  # compatibility with existing engine logic
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.prefer_grpc = prefer_grpc
        self.client = None
        self.vectorstore = None
        self._init_client()

    def _init_client(self):
        if not self.url:
            raise ValueError("Qdrant URL is required. Set QDRANT_URL or pass url parameter.")
        try:
            from qdrant_client import QdrantClient

            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=self.prefer_grpc,
                timeout=60.0,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    def _init_vectorstore(self):
        try:
            from langchain_community.vectorstores import Qdrant

            if self.client is None:
                self._init_client()
            self.vectorstore = Qdrant(
                client=self.client,
                collection_name=self.collection_name,
                embeddings=self.embeddings,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant vectorstore wrapper: {e}")
            raise

    def _ensure_collection_exists(self):
        """
        Ensure collection exists before writes.
        Avoids incompatible code path in Qdrant.from_documents with newer qdrant-client.
        """
        from qdrant_client.models import Distance, VectorParams

        if self.client is None:
            self._init_client()

        try:
            self.client.get_collection(collection_name=self.collection_name)
            return
        except Exception:
            pass

        # Create collection with embedding dimension discovered from model.
        dim = len(self.embeddings.embed_query("dimension_probe"))
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def from_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True) -> "QdrantStore":
        """Create/store vectors from documents in Qdrant collection."""
        if not documents:
            return self
        try:
            self._ensure_collection_exists()
            if self.vectorstore is None:
                self._init_vectorstore()
            # Use add_documents path to avoid qdrant-client/langchain incompatible args.
            self.vectorstore.add_documents(documents)
            return self
        except Exception as e:
            logger.error(f"Failed to build Qdrant collection from documents: {e}")
            raise

    def add_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True):
        """Add documents to Qdrant collection."""
        if not documents:
            return
        self._ensure_collection_exists()
        if self.vectorstore is None:
            self._init_vectorstore()
        self.vectorstore.add_documents(documents)

    def as_retriever(self, search_type: str = "similarity", search_kwargs: Optional[Dict] = None):
        """Return retriever interface."""
        kwargs = search_kwargs or {}
        store = self

        class _QdrantRetriever:
            def __init__(self, qdrant_store, retriever_kwargs):
                self.qdrant_store = qdrant_store
                self.retriever_kwargs = retriever_kwargs

            def invoke(self, query: str):
                return self.qdrant_store.similarity_search(
                    query=query,
                    k=int(self.retriever_kwargs.get("k", 4) or 4),
                    filter=self.retriever_kwargs.get("filter"),
                )

            def get_relevant_documents(self, query: str):
                return self.invoke(query)

        if search_type != "similarity":
            logger.info("Qdrant retriever search_type '%s' requested; using 'similarity' for compatibility.", search_type)
        return _QdrantRetriever(store, kwargs)

    def _to_document(self, payload: Dict[str, Any], point_id: Any = None, score: Optional[float] = None) -> Document:
        page_content = payload.get("page_content") or payload.get("text") or ""
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        if point_id is not None and "_id" not in metadata:
            metadata["_id"] = str(point_id)
        if score is not None:
            metadata.setdefault("_qdrant_score", float(score))
        # Preserve simple top-level payload fields in metadata.
        for k, v in payload.items():
            if k in ("page_content", "text", "metadata"):
                continue
            metadata.setdefault(k, v)
        return Document(page_content=page_content, metadata=metadata)

    def _query_points_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict] = None,
    ) -> List[Tuple[Document, float]]:
        self._ensure_collection_exists()
        if self.client is None:
            self._init_client()

        query_vector = self.embeddings.embed_query(query)
        k = max(1, int(k or 4))

        query_filter = None
        if filter is not None:
            # Support native qdrant filter object; ignore unknown dict filter shapes.
            try:
                from qdrant_client.models import Filter as QdrantFilter
                if isinstance(filter, QdrantFilter):
                    query_filter = filter
                elif isinstance(filter, dict):
                    query_filter = QdrantFilter(**filter)
            except Exception:
                logger.debug("Ignoring non-Qdrant filter for Qdrant search: %s", type(filter).__name__)

        points = None
        if hasattr(self.client, "search"):
            points = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=k,
                with_payload=True,
                with_vectors=False,
            )
        elif hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=k,
                with_payload=True,
                with_vectors=False,
            )
            points = getattr(response, "points", response)
        else:
            raise AttributeError("Qdrant client has neither 'search' nor 'query_points' method.")

        results: List[Tuple[Document, float]] = []
        for p in points or []:
            payload = getattr(p, "payload", None) or {}
            point_id = getattr(p, "id", None)
            score = float(getattr(p, "score", 0.0) or 0.0)
            results.append((self._to_document(payload=payload, point_id=point_id, score=score), score))
        return results

    def similarity_search_with_score(self, query: str, k: int = 4, filter: Optional[Dict] = None):
        return self._query_points_with_score(query=query, k=k, filter=filter)

    def similarity_search(self, query: str, k: int = 4, filter: Optional[Dict] = None):
        """Run semantic similarity search."""
        return [doc for doc, _ in self._query_points_with_score(query=query, k=k, filter=filter)]

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
        Qdrant fallback for hybrid_search API compatibility.
        Uses semantic similarity search only.
        """
        results = self.similarity_search(query=query, k=k, filter=filter)
        for d in results:
            if hasattr(d, "metadata") and isinstance(d.metadata, dict):
                d.metadata.setdefault("_qdrant_semantic_only", True)
        return results

    def count_documents(self) -> int:
        """Count stored embeddings in this collection."""
        try:
            if self.client is None:
                self._init_client()
            info = self.client.get_collection(self.collection_name)
            points_count = getattr(info, "points_count", None)
            if points_count is not None:
                return int(points_count)
            # Fallback for client/model variants
            return int(getattr(info, "vectors_count", 0) or 0)
        except Exception as e:
            logger.warning(f"Could not count Qdrant points for '{self.collection_name}': {e}")
            return 0
