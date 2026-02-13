"""PostgreSQL with pgvector extension vector store implementation."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

import asyncpg
from asyncpg.pool import Pool

from .base import VectorStore, ChunkWithEmbedding, SearchResult, BatchIndexResult, VectorStoreFactory

logger = logging.getLogger(__name__)


class PGVectorStore(VectorStore):
    """
    PostgreSQL with pgvector extension vector store implementation.
    
    Uses a separate PostgreSQL database (not the agent's database) for:
    - Isolation from agent operations
    - Independent scaling and backups
    - Specialized configuration for vector operations
    
    Requires pgvector extension to be installed in PostgreSQL.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PGVector store.
        
        Config parameters:
            connection_string: PostgreSQL connection string
            or individual params:
                host: Database host
                port: Database port
                database: Database name
                user: Database user
                password: Database password
            table_name: Table name for embeddings (default: document_embeddings)
            min_pool_size: Minimum connection pool size
            max_pool_size: Maximum connection pool size
        """
        super().__init__(config)
        self.pool: Optional[Pool] = None
        self.table_name = config.get("table_name", "document_embeddings")
        self._initialized_tables = set()
    
    async def initialize(self) -> bool:
        """Initialize PostgreSQL connection pool and create table if needed."""
        try:
            # Build connection string
            conn_str = self.config.get("connection_string")
            if not conn_str:
                host = self.config.get("host", "localhost")
                port = self.config.get("port", 5432)
                database = self.config.get("database", "aris_vectors")
                user = self.config.get("user", "aris")
                password = self.config.get("password")
                
                if not password:
                    raise ValueError("PostgreSQL password is required")
                
                conn_str = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                conn_str,
                min_size=self.config.get("min_pool_size", 2),
                max_size=self.config.get("max_pool_size", 10),
                command_timeout=60
            )
            
            # Verify pgvector extension
            async with self.pool.acquire() as conn:
                # Check and enable pgvector extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Verify extension is loaded
                result = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                )
                if not result:
                    raise RuntimeError("pgvector extension could not be enabled")
            
            # Test connection
            if await self.health_check():
                self.logger.info(f"✅ PGVector connected successfully (table: {self.table_name})")
                return True
            else:
                self.logger.error("PGVector health check failed")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize PGVector: {e}")
            return False
    
    async def create_index(
        self,
        index_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> bool:
        """
        Create table for vector embeddings.
        
        Args:
            index_name: Table name (will use self.table_name if not in multi-index mode)
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, l2, inner_product)
            **kwargs: Additional options (index_type: ivfflat or hnsw)
        """
        try:
            # Use configured table name unless explicitly overridden
            table = kwargs.get("use_table_name", True) and self.table_name or index_name
            
            # Check if table already exists
            if await self.index_exists(table):
                self.logger.info(f"Table '{table}' already exists")
                return True
            
            async with self.pool.acquire() as conn:
                # Create table with vector column
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector({dimension}),
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                # Create index on document_id for fast lookups
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_document_id
                    ON {table}(document_id)
                """)
                
                # Create vector index based on distance metric
                index_type = kwargs.get("index_type", "ivfflat")  # ivfflat or hnsw
                
                if distance_metric in ["cosine", "cosinesimil"]:
                    ops = "vector_cosine_ops"
                elif distance_metric in ["l2", "euclidean"]:
                    ops = "vector_l2_ops"
                elif distance_metric in ["inner_product", "dot_product"]:
                    ops = "vector_ip_ops"
                else:
                    ops = "vector_cosine_ops"  # default
                
                # Create vector index
                if index_type == "hnsw":
                    # HNSW index (better for high-dimensional vectors)
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table}_embedding_hnsw
                        ON {table}
                        USING hnsw (embedding {ops})
                        WITH (m = 16, ef_construction = 64)
                    """)
                else:
                    # IVFFlat index (faster build, good for most use cases)
                    lists = kwargs.get("lists", 100)  # Number of clusters
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{table}_embedding_ivfflat
                        ON {table}
                        USING ivfflat (embedding {ops})
                        WITH (lists = {lists})
                    """)
                
                self._initialized_tables.add(table)
                self.logger.info(
                    f"✅ Created PGVector table: {table} "
                    f"(dimension={dimension}, metric={distance_metric}, index={index_type})"
                )
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error creating table: {e}")
            return False
    
    async def index_exists(self, index_name: str) -> bool:
        """Check if table exists."""
        try:
            table = index_name if index_name != "default" else self.table_name
            
            if table in self._initialized_tables:
                return True
            
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = $1
                    )
                """, table)
                
                if result:
                    self._initialized_tables.add(table)
                return result
                
        except Exception as e:
            self.logger.error(f"Error checking table existence: {e}")
            return False
    
    async def index_chunks(
        self,
        index_name: str,
        chunks: List[ChunkWithEmbedding],
        batch_size: int = 100
    ) -> BatchIndexResult:
        """
        Index chunks using COPY for maximum performance.
        
        Args:
            index_name: Target table
            chunks: List of chunks with embeddings
            batch_size: Batch size for bulk indexing
        """
        if not chunks:
            return BatchIndexResult(success=True, indexed_count=0, failed_count=0, errors=[])
        
        table = index_name if index_name != "default" else self.table_name
        indexed_count = 0
        failed_count = 0
        errors = []
        
        try:
            async with self.pool.acquire() as conn:
                # Process in batches for better error handling
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    
                    # Prepare batch data
                    records = []
                    for chunk in batch:
                        try:
                            # Convert embedding to pgvector format
                            embedding_str = f"[{','.join(map(str, chunk.embedding))}]"
                            
                            records.append((
                                chunk.chunk_id,
                                chunk.document_id,
                                chunk.chunk_index,
                                chunk.content,
                                embedding_str,
                                json.dumps(chunk.metadata),
                                chunk.created_at
                            ))
                        except Exception as e:
                            failed_count += 1
                            errors.append(f"Chunk {chunk.chunk_id}: {str(e)}")
                    
                    if not records:
                        continue
                    
                    # Use INSERT ... ON CONFLICT for upsert behavior
                    try:
                        await conn.executemany(f"""
                            INSERT INTO {table} 
                            (chunk_id, document_id, chunk_index, content, embedding, metadata, created_at)
                            VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb, $7)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata,
                                created_at = EXCLUDED.created_at
                        """, records)
                        
                        indexed_count += len(records)
                        self.logger.info(f"Indexed batch {i//batch_size + 1}: {len(records)} chunks")
                        
                    except Exception as e:
                        failed_count += len(records)
                        errors.append(f"Batch {i//batch_size + 1}: {str(e)}")
                        self.logger.error(f"Error indexing batch: {e}")
            
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
        Search using vector similarity.
        
        Uses pgvector's distance operators:
        - <-> for L2 distance
        - <#> for inner product
        - <=> for cosine distance
        """
        try:
            table = index_name if index_name != "default" else self.table_name
            
            # Convert vector to pgvector format
            vector_str = f"[{','.join(map(str, query_vector))}]"
            
            # Build query with cosine similarity (1 - cosine distance)
            # This gives us a similarity score from 0 to 1
            query = f"""
                SELECT 
                    chunk_id,
                    document_id,
                    content,
                    chunk_index,
                    metadata,
                    1 - (embedding <=> $1::vector) as score
                FROM {table}
            """
            
            params = [vector_str]
            param_idx = 2
            
            # Add metadata filters
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append(f"metadata->>'{key}' = ${param_idx}")
                    params.append(str(value))
                    param_idx += 1
                
                if filter_conditions:
                    query += " WHERE " + " AND ".join(filter_conditions)
            
            # Add similarity threshold and ordering
            query += f"""
                ORDER BY embedding <=> $1::vector
                LIMIT {limit}
            """
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            
            # Parse results and apply threshold
            results = []
            for row in rows:
                score = float(row["score"])
                
                # Apply threshold filter
                if score < threshold:
                    continue
                
                results.append(SearchResult(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    content=row["content"],
                    score=score,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    chunk_index=row["chunk_index"]
                ))
            
            self.logger.info(f"Search returned {len(results)} results (threshold={threshold})")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Search error: {e}")
            return []
    
    async def delete_by_document_id(self, index_name: str, document_id: str) -> bool:
        """Delete all chunks for a document."""
        try:
            table = index_name if index_name != "default" else self.table_name
            
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    f"DELETE FROM {table} WHERE document_id = $1",
                    document_id
                )
                
                # Parse delete count from result string like "DELETE 5"
                deleted = int(result.split()[-1]) if result else 0
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
            table = index_name if index_name != "default" else self.table_name
            
            async with self.pool.acquire() as conn:
                if document_id:
                    count = await conn.fetchval(
                        f"SELECT COUNT(*) FROM {table} WHERE document_id = $1",
                        document_id
                    )
                else:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                
                return count or 0
                
        except Exception as e:
            self.logger.error(f"Error getting document count: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check PostgreSQL connection health."""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.logger.info("PGVector connection pool closed")


# Register with factory
VectorStoreFactory.register_store("pgvector", PGVectorStore)

