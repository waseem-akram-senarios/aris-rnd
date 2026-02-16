"""OpenSearch vector store implementation."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from opensearchpy import AsyncOpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from requests_aws4auth import AWS4Auth
import boto3

from .base import VectorStore, ChunkWithEmbedding, SearchResult, BatchIndexResult, VectorStoreFactory

logger = logging.getLogger(__name__)


class OpenSearchVectorStore(VectorStore):
    """
    OpenSearch vector store implementation.
    
    Supports both AWS OpenSearch Service and self-hosted OpenSearch.
    Uses k-NN plugin for vector similarity search.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OpenSearch vector store.
        
        Config parameters:
            endpoint: OpenSearch endpoint URL
            region: AWS region (for AWS OpenSearch Service)
            use_aws_auth: Whether to use AWS IAM authentication
            username: Basic auth username (alternative to AWS auth)
            password: Basic auth password
            use_ssl: Whether to use SSL
            verify_certs: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        super().__init__(config)
        self.client: Optional[AsyncOpenSearch] = None
        self._index_cache = set()  # Cache of known indexes
    
    async def initialize(self) -> bool:
        """Initialize OpenSearch connection."""
        try:
            endpoint = self.config.get("endpoint")
            if not endpoint:
                raise ValueError("OpenSearch endpoint is required")
            
            # Remove protocol from endpoint if present
            endpoint = endpoint.replace("https://", "").replace("http://", "")
            
            # Determine authentication method
            auth = None
            if self.config.get("use_aws_auth", False):
                # AWS IAM authentication
                region = self.config.get("region", "us-east-2")
                credentials = boto3.Session().get_credentials()
                auth = AWS4Auth(
                    credentials.access_key,
                    credentials.secret_key,
                    region,
                    'es',
                    session_token=credentials.token
                )
                self.logger.info(f"Using AWS IAM authentication for region: {region}")
            elif self.config.get("username") and self.config.get("password"):
                # Basic authentication
                auth = (self.config["username"], self.config["password"])
                self.logger.info("Using basic authentication")
            
            # Create client
            self.client = AsyncOpenSearch(
                hosts=[{'host': endpoint, 'port': 443 if self.config.get("use_ssl", True) else 80}],
                http_auth=auth,
                use_ssl=self.config.get("use_ssl", True),
                verify_certs=self.config.get("verify_certs", True),
                connection_class=RequestsHttpConnection,
                timeout=self.config.get("timeout", 30),
            )
            
            # Test connection
            if await self.health_check():
                self.logger.info(f"✅ OpenSearch connected successfully: {endpoint}")
                return True
            else:
                self.logger.error("OpenSearch health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize OpenSearch: {e}")
            return False
    
    async def create_index(
        self,
        index_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> bool:
        """
        Create OpenSearch index with k-NN settings.
        
        Args:
            index_name: Name of the index
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, l2, l1, linf)
            **kwargs: Additional settings (shards, replicas, etc.)
        """
        try:
            # Check if index already exists
            if await self.index_exists(index_name):
                self.logger.info(f"Index '{index_name}' already exists")
                return True
            
            # Map distance metric to OpenSearch space_type
            space_type_map = {
                "cosine": "cosinesimil",
                "euclidean": "l2",
                "l2": "l2",
                "manhattan": "l1",
                "l1": "l1",
                "dot_product": "innerproduct"
            }
            space_type = space_type_map.get(distance_metric, "cosinesimil")
            
            # Index settings with k-NN enabled
            settings = {
                "settings": {
                    "index": {
                        "number_of_shards": kwargs.get("shards", 2),
                        "number_of_replicas": kwargs.get("replicas", 1),
                        "knn": True,  # Enable k-NN plugin
                        "knn.algo_param.ef_search": 100,  # Search quality parameter
                    }
                },
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "document_id": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "content": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": dimension,
                            "method": {
                                "name": "hnsw",
                                "space_type": space_type,
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 16
                                }
                            }
                        },
                        "metadata": {"type": "object", "enabled": True},
                        "created_at": {"type": "date"}
                    }
                }
            }
            
            # Create index
            response = await self.client.indices.create(index=index_name, body=settings)
            
            if response.get("acknowledged"):
                self._index_cache.add(index_name)
                self.logger.info(f"✅ Created OpenSearch index: {index_name} (dimension={dimension}, metric={distance_metric})")
                return True
            else:
                self.logger.error(f"Failed to create index: {response}")
                return False
                
        except RequestError as e:
            if "resource_already_exists_exception" in str(e):
                self.logger.info(f"Index '{index_name}' already exists")
                self._index_cache.add(index_name)
                return True
            self.logger.error(f"❌ Error creating index: {e}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Unexpected error creating index: {e}")
            return False
    
    async def index_exists(self, index_name: str) -> bool:
        """Check if index exists."""
        try:
            if index_name in self._index_cache:
                return True
            
            exists = await self.client.indices.exists(index=index_name)
            if exists:
                self._index_cache.add(index_name)
            return exists
        except Exception as e:
            self.logger.error(f"Error checking index existence: {e}")
            return False
    
    async def index_chunks(
        self,
        index_name: str,
        chunks: List[ChunkWithEmbedding],
        batch_size: int = 100
    ) -> BatchIndexResult:
        """
        Index chunks using bulk API.
        
        Args:
            index_name: Target index
            chunks: List of chunks with embeddings
            batch_size: Batch size for bulk indexing
        """
        if not chunks:
            return BatchIndexResult(success=True, indexed_count=0, failed_count=0, errors=[])
        
        indexed_count = 0
        failed_count = 0
        errors = []
        
        try:
            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Prepare bulk request
                bulk_body = []
                for chunk in batch:
                    # Index action
                    bulk_body.append({
                        "index": {
                            "_index": index_name,
                            "_id": chunk.chunk_id
                        }
                    })
                    # Document
                    bulk_body.append({
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "embedding": chunk.embedding,
                        "metadata": chunk.metadata,
                        "created_at": chunk.created_at.isoformat()
                    })
                
                # Execute bulk request
                response = await self.client.bulk(body=bulk_body)
                
                # Process results
                if response.get("errors"):
                    for item in response.get("items", []):
                        if "error" in item.get("index", {}):
                            failed_count += 1
                            error = item["index"]["error"]
                            errors.append(f"Chunk {item['index'].get('_id')}: {error.get('reason', 'Unknown error')}")
                        else:
                            indexed_count += 1
                else:
                    indexed_count += len(batch)
                
                self.logger.info(f"Indexed batch {i//batch_size + 1}: {len(batch)} chunks")
            
            success = failed_count == 0
            self.logger.info(f"Indexing complete: {indexed_count} success, {failed_count} failed")
            
            return BatchIndexResult(
                success=success,
                indexed_count=indexed_count,
                failed_count=failed_count,
                errors=errors
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error indexing chunks: {e}")
            return BatchIndexResult(
                success=False,
                indexed_count=indexed_count,
                failed_count=len(chunks) - indexed_count,
                errors=[str(e)]
            )
    
    async def search(
        self,
        index_name: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Search using k-NN vector similarity.
        
        Args:
            index_name: Index to search
            query_vector: Query embedding
            limit: Maximum results
            threshold: Minimum similarity score
            filters: Optional metadata filters
        """
        try:
            # Build k-NN query
            query = {
                "size": limit,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_vector,
                            "k": limit
                        }
                    }
                },
                "_source": ["chunk_id", "document_id", "content", "metadata", "chunk_index"]
            }
            
            # Add filters if provided
            if filters:
                query["query"] = {
                    "bool": {
                        "must": [query["query"]],
                        "filter": [{"term": {k: v}} for k, v in filters.items()]
                    }
                }
            
            # Execute search
            response = await self.client.search(index=index_name, body=query)
            
            # Parse results
            results = []
            for hit in response["hits"]["hits"]:
                score = hit["_score"]
                
                # Apply threshold filter
                if score < threshold:
                    continue
                
                source = hit["_source"]
                results.append(SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    content=source["content"],
                    score=score,
                    metadata=source.get("metadata", {}),
                    chunk_index=source.get("chunk_index", 0)
                ))
            
            self.logger.info(f"Search returned {len(results)} results (threshold={threshold})")
            return results
            
        except NotFoundError:
            self.logger.warning(f"Index '{index_name}' not found")
            return []
        except Exception as e:
            self.logger.error(f"❌ Search error: {e}")
            return []
    
    async def delete_by_document_id(self, index_name: str, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            query = {
                "query": {
                    "term": {"document_id": document_id}
                }
            }
            
            response = await self.client.delete_by_query(index=index_name, body=query)
            deleted = response.get("deleted", 0)
            
            self.logger.info(f"Deleted {deleted} chunks for document: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error deleting document chunks: {e}")
            return False
    
    async def get_document_count(
        self,
        index_name: str,
        document_id: Optional[str] = None
    ) -> int:
        """Get count of chunks."""
        try:
            query = {}
            if document_id:
                query = {
                    "query": {
                        "term": {"document_id": document_id}
                    }
                }
            
            response = await self.client.count(index=index_name, body=query)
            return response.get("count", 0)
            
        except Exception as e:
            self.logger.error(f"Error getting document count: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check OpenSearch cluster health."""
        try:
            health = await self.client.cluster.health()
            status = health.get("status")
            
            if status in ["green", "yellow"]:
                return True
            else:
                self.logger.warning(f"OpenSearch cluster status: {status}")
                return False
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Close OpenSearch client."""
        if self.client:
            await self.client.close()
            self.logger.info("OpenSearch client closed")


# Register with factory
VectorStoreFactory.register_store("opensearch", OpenSearchVectorStore)

