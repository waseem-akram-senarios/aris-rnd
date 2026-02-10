"""
OpenSearch Vector Store implementation for RAG system.
Uses AWS OpenSearch Service with LangChain integration.
"""
import os
import re
import logging
import time
import hashlib
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

from langchain_openai import OpenAIEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)

# Query result cache for hybrid search performance
_hybrid_cache = {}
_hybrid_cache_timestamps = {}


def clear_hybrid_search_cache(index_name: Optional[str] = None):
    """
    Clear the hybrid search cache.
    
    Args:
        index_name: If provided, only clear cache entries for this index.
                    If None, clear entire cache.
    """
    global _hybrid_cache, _hybrid_cache_timestamps
    if index_name is None:
        _hybrid_cache.clear()
        _hybrid_cache_timestamps.clear()
        logger.info("🗑️ Cleared entire hybrid search cache")
    else:
        # Clear entries that contain this index name in the cache key
        keys_to_remove = [k for k in _hybrid_cache.keys() if index_name in str(k)]
        for key in keys_to_remove:
            _hybrid_cache.pop(key, None)
            _hybrid_cache_timestamps.pop(key, None)
        logger.info(f"🗑️ Cleared {len(keys_to_remove)} cache entries for index: {index_name}")


class OpenSearchVectorStore:
    """OpenSearch vector store wrapper for LangChain compatibility."""
    
    def __init__(
        self,
        embeddings: OpenAIEmbeddings,
        domain: str = "intelycx-os-dev",
        index_name: str = "aris-rag-index",
        region: Optional[str] = None,
        endpoint: Optional[str] = None
    ):
        """
        Initialize OpenSearch vector store.
        
        Args:
            embeddings: Embeddings model to use
            domain: OpenSearch domain name
            index_name: Name of the OpenSearch index
            region: AWS region (defaults to AWS_OPENSEARCH_REGION from .env)
        """
        self.embeddings = embeddings
        # Validate domain - must be at least 3 characters (AWS requirement)
        if not domain or len(str(domain).strip()) < 3:
            raise ValueError(
                f"Invalid OpenSearch domain: '{domain}'. Domain name must be at least 3 characters. "
                f"Please set AWS_OPENSEARCH_DOMAIN in .env file or pass a valid domain parameter. "
                f"You may want to use FAISS instead for local storage."
            )
        self.domain = str(domain).strip()
        self.index_name = index_name
        self.region = region or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        # Get AWS credentials
        self.access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "OpenSearch credentials not found. Please set AWS_OPENSEARCH_ACCESS_KEY_ID "
                "and AWS_OPENSEARCH_SECRET_ACCESS_KEY in .env file. "
                "You may want to use FAISS instead for local storage."
            )
        
        # If endpoint is provided directly, use it; otherwise get from AWS
        if endpoint:
            self.endpoint = endpoint
            if not self.endpoint.startswith('http'):
                self.endpoint = f"https://{self.endpoint}"
            logger.info(f"Using provided OpenSearch endpoint: {self.endpoint}")
        else:
            # Initialize OpenSearch client and get endpoint
            self._initialize_opensearch()
        
        # Initialize LangChain OpenSearch vector store
        self._initialize_langchain_store()
    
    def _initialize_opensearch(self):
        """Initialize OpenSearch connection and get endpoint."""
        try:
            # Get OpenSearch domain endpoint
            opensearch_client = boto3.client(
                'opensearch',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # Get domain info
            domain_info = opensearch_client.describe_domain(DomainName=self.domain)
            domain_status = domain_info.get('DomainStatus', {})
            
            # Get endpoint
            if 'Endpoint' in domain_status:
                self.endpoint = domain_status['Endpoint']
            elif 'Endpoints' in domain_status:
                # Use the first endpoint if multiple available
                endpoints = domain_status['Endpoints']
                self.endpoint = list(endpoints.values())[0] if endpoints else None
            else:
                raise ValueError(f"Could not find endpoint for OpenSearch domain: {self.domain}")
            
            # Ensure endpoint has protocol
            if not self.endpoint.startswith('http'):
                self.endpoint = f"https://{self.endpoint}"
            
            logger.info(f"OpenSearch endpoint: {self.endpoint}")
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            raise ValueError(
                f"Failed to connect to OpenSearch domain '{self.domain}': {error_code} - {error_msg}. "
                f"Please check your credentials and domain name."
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenSearch connection: {str(e)}")
    
    def _initialize_langchain_store(self):
        """Initialize LangChain OpenSearchVectorSearch."""
        try:
            from langchain_community.vectorstores import OpenSearchVectorSearch
            
            # Try multiple authentication methods
            auth_methods = []
            
            # Method 1: Try AWS4Auth (for AWS signature v4)
            try:
                from requests_aws4auth import AWS4Auth
                from opensearchpy import RequestsHttpConnection
                
                awsauth = AWS4Auth(
                    self.access_key,
                    self.secret_key,
                    self.region,
                    'es'
                )
                auth_methods.append(('AWS4Auth', awsauth, RequestsHttpConnection))
            except Exception as e:
                logger.warning(f"AWS4Auth setup failed: {str(e)}")
            
            # Method 2: HTTP Basic Auth (for some OpenSearch configs)
            http_auth = (self.access_key, self.secret_key)
            auth_methods.append(('HTTP Basic Auth', http_auth, None))
            
            # Try each auth method
            last_error = None
            last_error_str = None
            for auth_name, auth, conn_class in auth_methods:
                try:
                    logger.info(f"Trying {auth_name} authentication with endpoint: {self.endpoint}, domain: {self.domain}, index: {self.index_name}")
                    
                    from shared.config.settings import ARISConfig
                    kwargs = {
                        'opensearch_url': self.endpoint,
                        'index_name': self.index_name,
                        'embedding_function': self.embeddings,
                        'http_auth': auth,
                        'use_ssl': True,
                        'verify_certs': True,
                        'ssl_assert_hostname': False,
                        'ssl_show_warn': False,
                        'bulk_size': ARISConfig.OPENSEARCH_BULK_SIZE,
                        'engine': 'lucene'  # Use lucene engine for OpenSearch 3.0+ (nmslib is deprecated)
                    }
                    
                    if conn_class:
                        kwargs['connection_class'] = conn_class
                    
                    self.vectorstore = OpenSearchVectorSearch(**kwargs)
                    
                    # Test connection by trying to get cluster info
                    try:
                        # This will fail if auth doesn't work
                        test_client = self.vectorstore.client
                        cluster_info = test_client.info()
                        
                        # Validate embedding dimension matches index
                        self._validate_embedding_dimension(test_client)
                        
                        logger.info(f"✅ OpenSearch vector store initialized with {auth_name} (index: {self.index_name}, cluster: {cluster_info.get('cluster_name', 'Unknown')})")
                        return
                    except Exception as test_e:
                        error_str = str(test_e)
                        last_error = test_e
                        last_error_str = error_str
                        logger.warning(f"{auth_name} connection test failed: {error_str[:200]}")
                        # Clear the vectorstore if test failed
                        self.vectorstore = None
                        continue
                        
                except Exception as e:
                    import traceback
                    error_str = str(e)
                    error_trace = traceback.format_exc()
                    last_error = e
                    last_error_str = f"{error_str}\n{traceback.format_exc()[:500]}"
                    logger.warning(f"{auth_name} initialization failed: {error_str[:200]}")
                    logger.debug(f"Full traceback: {error_trace[:500]}")
                    continue
            
            # If all methods failed
            error_details = last_error_str or (str(last_error) if last_error else "Unknown error - no exceptions were caught")
            raise ValueError(
                f"Failed to initialize OpenSearch with any authentication method. "
                f"Endpoint: {self.endpoint}, Domain: {self.domain}, Index: {self.index_name}. "
                f"Last error: {error_details[:500]}. "
                f"Please check your credentials and OpenSearch domain configuration."
            )
            
        except ImportError as e:
            raise ImportError(
                f"OpenSearch support requires langchain-community and opensearch-py. "
                f"Install with: pip install langchain-community opensearch-py requests-aws4auth. "
                f"Error: {str(e)}"
            )
        except Exception as e:
            raise ValueError(f"Failed to initialize LangChain OpenSearch store: {str(e)}")
    
    def _validate_embedding_dimension(self, client):
        """
        Validate that the embedding model dimension matches the OpenSearch index dimension.
        
        Args:
            client: OpenSearch client
        """
        try:
            # Check if index exists
            if not client.indices.exists(index=self.index_name):
                logger.info(f"Index {self.index_name} does not exist yet - will be created with current embedding model")
                return
            
            # Get index mapping to find vector dimension
            mapping = client.indices.get_mapping(index=self.index_name)
            index_mapping = mapping.get(self.index_name, {}).get('mappings', {})
            
            # Find vector field dimension
            vector_dimension = None
            properties = index_mapping.get('properties', {})
            
            # Check for common vector field names
            for field_name, field_config in properties.items():
                if field_config.get('type') == 'knn_vector':
                    vector_dimension = field_config.get('dimension')
                    if vector_dimension:
                        logger.info(f"Found vector field '{field_name}' with dimension {vector_dimension}")
                        break
            
            if vector_dimension is None:
                # Try to find in nested properties
                for field_name, field_config in properties.items():
                    if isinstance(field_config, dict) and 'properties' in field_config:
                        nested_props = field_config.get('properties', {})
                        for nested_field, nested_config in nested_props.items():
                            if nested_config.get('type') == 'knn_vector':
                                vector_dimension = nested_config.get('dimension')
                                if vector_dimension:
                                    logger.info(f"Found vector field '{field_name}.{nested_field}' with dimension {vector_dimension}")
                                    break
                        if vector_dimension:
                            break
            
            if vector_dimension:
                # Get current embedding model dimension
                # Try to get dimension from embeddings model
                try:
                    # Test embedding to get dimension
                    test_embedding = self.embeddings.embed_query("test")
                    current_dimension = len(test_embedding)
                    
                    if current_dimension != vector_dimension:
                        # Map dimensions to models
                        dimension_to_model = {
                            1536: 'text-embedding-3-small',
                            3072: 'text-embedding-3-large',
                            1536: 'text-embedding-ada-002'  # Also 1536
                        }
                        
                        expected_model = dimension_to_model.get(vector_dimension, f"model with {vector_dimension} dimensions")
                        current_model = getattr(self.embeddings, 'model', 'unknown')
                        
                        error_msg = (
                            f"Embedding dimension mismatch! "
                            f"Index '{self.index_name}' was created with {vector_dimension} dimensions "
                            f"(likely {expected_model}), but current embedding model '{current_model}' "
                            f"produces {current_dimension} dimensions. "
                            f"Please use the same embedding model that was used to create the index, "
                            f"or recreate the index with the current model."
                        )
                        
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                    else:
                        logger.info(f"✅ Embedding dimension validated: {current_dimension} dimensions match index")
                except Exception as e:
                    logger.warning(f"Could not validate embedding dimension: {e}")
            else:
                logger.info(f"Could not determine vector dimension from index mapping - skipping validation")
                
        except Exception as e:
            # Don't fail initialization if validation fails, just log warning
            logger.warning(f"Could not validate embedding dimension: {e}")
    
    def _clean_metadata_for_opensearch(self, documents: List[Document]) -> List[Document]:
        """
        Clean metadata to ensure it's compatible with OpenSearch limits.
        Removes large nested structures and keeps only essential fields.
        """
        cleaned_documents = []
        for doc in documents:
            # Create a copy of the document
            from langchain_core.documents import Document
            cleaned_metadata = {}
            
            # Keep only essential metadata fields
            essential_fields = [
                'source', 'page', 'source_page', 'chunk_index', 'total_chunks',
                'parser_used', 'pages', 'images_detected', 'extraction_percentage',
                'start_char', 'end_char', 'token_count',
                'has_image', 'image_ref', 'image_index', 'image_bbox', 'image_info',
                # Page citation accuracy fields
                'page_extraction_method', 'page_confidence', 'image_page',
                # Multilingual support fields (MANDATORY for language-isolated search)
                'language', 'language_detected', 'primary_language', 'secondary_language',
                'text_original', 'text_english', 'script_type',
                # Document tracking
                'document_id'
            ]
            
            if doc.metadata:
                for key in essential_fields:
                    if key in doc.metadata:
                        value = doc.metadata[key]
                        # Skip None values
                        if value is not None:
                            # Truncate string values if too long
                            if isinstance(value, str) and len(value) > 1000:
                                cleaned_metadata[key] = value[:1000]
                            else:
                                cleaned_metadata[key] = value

                # Add source if not already present (required for filtering)
                if 'source' not in cleaned_metadata and 'source' in doc.metadata:
                    cleaned_metadata['source'] = doc.metadata['source']
            
            # Add content_type to indicate this is text content (not image OCR)
            cleaned_metadata['content_type'] = 'text'
            
            # Create cleaned document
            cleaned_doc = Document(
                page_content=doc.page_content,
                metadata=cleaned_metadata
            )
            cleaned_documents.append(cleaned_doc)
        
        return cleaned_documents
    
    def from_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True) -> 'OpenSearchVectorStore':
        """
        Create vector store from documents.
        
        Args:
            documents: Documents to create vector store from
            auto_recreate_on_mismatch: If True, automatically delete and recreate index on dimension mismatch
        """
        if not documents:
            raise ValueError("Cannot create vector store from empty document list")
        
        logger.info(f"Creating OpenSearch vectorstore from {len(documents)} documents...")
        
        try:
            # Clean metadata before adding to OpenSearch (remove large nested structures)
            cleaned_documents = self._clean_metadata_for_opensearch(documents)
            logger.info(f"Cleaned metadata for {len(cleaned_documents)} documents (removed large nested structures)")
            
            # Check if index exists and validate dimensions before adding
            try:
                client = self.vectorstore.client
                if client.indices.exists(index=self.index_name):
                    # Validate dimension before attempting to add
                    self._validate_embedding_dimension(client)
            except ValueError as ve:
                # Dimension mismatch detected during validation
                if auto_recreate_on_mismatch:
                    error_str = str(ve)
                    logger.warning(
                        f"⚠️ Dimension mismatch detected: {error_str}\n"
                        f"   Auto-recreating index '{self.index_name}' with current embedding model..."
                    )
                    
                    # Delete the old index
                    if client.indices.exists(index=self.index_name):
                        logger.info(f"Deleting old index '{self.index_name}' with mismatched dimensions...")
                        client.indices.delete(index=self.index_name)
                        logger.info(f"✅ Old index deleted successfully")
                    
                    # Recreate the vectorstore (which will create a new index with correct dimensions)
                    test_embedding = self.embeddings.embed_query("test")
                    current_dimension = len(test_embedding)
                    logger.info(f"Recreating index '{self.index_name}' with {current_dimension} dimensions...")
                    self._initialize_langchain_store()
                else:
                    # Re-raise the validation error if auto-recreate is disabled
                    raise
            
            # Add documents to the index
            # OpenSearchVectorSearch will create the index if it doesn't exist
            # Get bulk_size from config to ensure we don't exceed it
            from shared.config.settings import ARISConfig
            bulk_size = ARISConfig.OPENSEARCH_BULK_SIZE
            
            # Split into batches if documents exceed bulk_size
            if len(cleaned_documents) > bulk_size:
                logger.info(f"Splitting {len(cleaned_documents)} documents into batches of {bulk_size}...")
                total_added = 0
                for i in range(0, len(cleaned_documents), bulk_size):
                    batch = cleaned_documents[i:i + bulk_size]
                    batch_num = (i // bulk_size) + 1
                    total_batches = (len(cleaned_documents) + bulk_size - 1) // bulk_size
                    logger.info(f"Adding batch {batch_num}/{total_batches} ({len(batch)} documents)...")
                    self.vectorstore.add_documents(batch)
                    total_added += len(batch)
                logger.info(f"OpenSearch vectorstore created successfully with {total_added} documents in {total_batches} batches")
            else:
                self.vectorstore.add_documents(cleaned_documents)
                logger.info(f"OpenSearch vectorstore created successfully with {len(cleaned_documents)} documents")
        except Exception as e:
            error_str = str(e)
            error_lower = error_str.lower()
            
            # Check if this is a bulk_size exceeded error
            is_bulk_size_error = (
                "bulk_size" in error_lower and 
                ("more than" in error_lower or "exceed" in error_lower or "greater than" in error_lower)
            )
            
            if is_bulk_size_error:
                logger.warning(f"⚠️ Bulk size exceeded during from_documents. Splitting into smaller batches...")
                # Extract the count from error if possible, otherwise use a safe default
                safe_batch_size = min(bulk_size - 100, 1000)  # Use smaller batch size
                logger.info(f"Retrying with batch size of {safe_batch_size}...")
                
                total_added = 0
                for i in range(0, len(cleaned_documents), safe_batch_size):
                    batch = cleaned_documents[i:i + safe_batch_size]
                    batch_num = (i // safe_batch_size) + 1
                    total_batches = (len(cleaned_documents) + safe_batch_size - 1) // safe_batch_size
                    logger.info(f"Adding batch {batch_num}/{total_batches} ({len(batch)} documents)...")
                    self.vectorstore.add_documents(batch)
                    total_added += len(batch)
                logger.info(f"OpenSearch vectorstore created successfully with {total_added} documents in {total_batches} batches")
                return  # Successfully handled, exit early
            
            # Continue with other error handling
            error_str = str(e)
            error_lower = error_str.lower()
            
            # Check if this is a dimension mismatch error (in case validation didn't catch it)
            is_dimension_mismatch = (
                "dimension mismatch" in error_lower or
                "vector dimension mismatch" in error_lower or
                "mapper_parsing_exception" in error_lower and "knn_vector" in error_lower or
                "illegal_argument_exception" in error_lower and "dimension" in error_lower
            )
            
            if is_dimension_mismatch and auto_recreate_on_mismatch:
                logger.warning(
                    f"⚠️ Dimension mismatch detected during from_documents. "
                    f"Index '{self.index_name}' was created with a different embedding dimension. "
                    f"Auto-recreating index with current embedding model..."
                )
                
                try:
                    # Get current embedding dimension
                    test_embedding = self.embeddings.embed_query("test")
                    current_dimension = len(test_embedding)
                    
                    # Delete the old index
                    client = self.vectorstore.client
                    if client.indices.exists(index=self.index_name):
                        logger.info(f"Deleting old index '{self.index_name}' with mismatched dimensions...")
                        client.indices.delete(index=self.index_name)
                        logger.info(f"✅ Old index deleted successfully")
                    
                    # Recreate the vectorstore (which will create a new index with correct dimensions)
                    logger.info(f"Recreating index '{self.index_name}' with {current_dimension} dimensions...")
                    self._initialize_langchain_store()
                    
                    # Retry adding documents
                    logger.info(f"Retrying to add {len(cleaned_documents)} documents to recreated index...")
                    self.vectorstore.add_documents(cleaned_documents)
                    logger.info(f"✅ OpenSearch vectorstore created successfully with {len(cleaned_documents)} documents")
                    return self
                    
                except Exception as recreate_error:
                    logger.error(
                        f"❌ Failed to auto-recreate index on dimension mismatch: {str(recreate_error)}\n"
                        f"   Original error: {error_str}\n"
                        f"   Please manually delete the index '{self.index_name}' and try again."
                    )
                    raise ValueError(
                        f"Dimension mismatch error and auto-recreation failed: {str(recreate_error)}. "
                        f"Original error: {error_str}. "
                        f"Please manually delete the index '{self.index_name}' and try again."
                    )
            else:
                logger.error(f"Failed to create OpenSearch vectorstore: {error_str}")
                raise ValueError(f"Failed to create OpenSearch vectorstore: {error_str}")
        
        return self
    
    def add_documents(self, documents: List[Document], auto_recreate_on_mismatch: bool = True):
        """
        Add documents to existing vector store.
        
        Args:
            documents: Documents to add
            auto_recreate_on_mismatch: If True, automatically delete and recreate index on dimension mismatch
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Call from_documents() first.")
        
        logger.info(f"Adding {len(documents)} documents to OpenSearch vectorstore...")
        
        try:
            # Clean metadata before adding to OpenSearch (remove large nested structures)
            cleaned_documents = self._clean_metadata_for_opensearch(documents)
            logger.info(f"Cleaned metadata for {len(cleaned_documents)} documents (removed large nested structures)")
            
            # Get bulk_size from config to ensure we don't exceed it
            from shared.config.settings import ARISConfig
            bulk_size = ARISConfig.OPENSEARCH_BULK_SIZE
            
            # Split into batches if documents exceed bulk_size
            if len(cleaned_documents) > bulk_size:
                logger.info(f"Splitting {len(cleaned_documents)} documents into batches of {bulk_size}...")
                total_added = 0
                for i in range(0, len(cleaned_documents), bulk_size):
                    batch = cleaned_documents[i:i + bulk_size]
                    batch_num = (i // bulk_size) + 1
                    total_batches = (len(cleaned_documents) + bulk_size - 1) // bulk_size
                    logger.info(f"Adding batch {batch_num}/{total_batches} ({len(batch)} documents)...")
                    self.vectorstore.add_documents(batch)
                    total_added += len(batch)
                logger.info(f"Successfully added {total_added} documents to OpenSearch vectorstore in {total_batches} batches")
            else:
                self.vectorstore.add_documents(cleaned_documents)
                logger.info(f"Successfully added {len(cleaned_documents)} documents to OpenSearch vectorstore")
        except Exception as e:
            error_str = str(e)
            error_lower = error_str.lower()
            
            # Check if this is a bulk_size exceeded error
            is_bulk_size_error = (
                "bulk_size" in error_lower and 
                ("more than" in error_lower or "exceed" in error_lower or "greater than" in error_lower)
            )
            
            if is_bulk_size_error:
                logger.warning(f"⚠️ Bulk size exceeded. Splitting into smaller batches...")
                # Use a safe batch size (smaller than configured)
                from shared.config.settings import ARISConfig
                safe_batch_size = min(ARISConfig.OPENSEARCH_BULK_SIZE - 100, 1000)
                logger.info(f"Retrying with batch size of {safe_batch_size}...")
                
                cleaned_documents = self._clean_metadata_for_opensearch(documents)
                total_added = 0
                for i in range(0, len(cleaned_documents), safe_batch_size):
                    batch = cleaned_documents[i:i + safe_batch_size]
                    batch_num = (i // safe_batch_size) + 1
                    total_batches = (len(cleaned_documents) + safe_batch_size - 1) // safe_batch_size
                    logger.info(f"Adding batch {batch_num}/{total_batches} ({len(batch)} documents)...")
                    self.vectorstore.add_documents(batch)
                    total_added += len(batch)
                logger.info(f"Successfully added {total_added} documents to OpenSearch vectorstore in {total_batches} batches")
                return  # Successfully handled, exit early
            
            # Check if this is a dimension mismatch error
            is_dimension_mismatch = (
                "dimension mismatch" in error_lower or
                "vector dimension mismatch" in error_lower or
                "mapper_parsing_exception" in error_lower and "knn_vector" in error_lower or
                "illegal_argument_exception" in error_lower and "dimension" in error_lower
            )
            
            if is_dimension_mismatch and auto_recreate_on_mismatch:
                logger.warning(
                    f"⚠️ Dimension mismatch detected during add_documents. "
                    f"Index '{self.index_name}' was created with a different embedding dimension. "
                    f"Auto-recreating index with current embedding model..."
                )
                
                try:
                    # Get current embedding dimension
                    test_embedding = self.embeddings.embed_query("test")
                    current_dimension = len(test_embedding)
                    
                    # Delete the old index
                    client = self.vectorstore.client
                    if client.indices.exists(index=self.index_name):
                        logger.info(f"Deleting old index '{self.index_name}' with mismatched dimensions...")
                        client.indices.delete(index=self.index_name)
                        logger.info(f"✅ Old index deleted successfully")
                    
                    # Recreate the vectorstore (which will create a new index with correct dimensions)
                    logger.info(f"Recreating index '{self.index_name}' with {current_dimension} dimensions...")
                    self._initialize_langchain_store()
                    
                    # Retry adding documents
                    logger.info(f"Retrying to add {len(cleaned_documents)} documents to recreated index...")
                    self.vectorstore.add_documents(cleaned_documents)
                    logger.info(f"✅ Successfully added {len(cleaned_documents)} documents to recreated index")
                    return
                    
                except Exception as recreate_error:
                    logger.error(
                        f"❌ Failed to auto-recreate index on dimension mismatch: {str(recreate_error)}\n"
                        f"   Original error: {error_str}\n"
                        f"   Please manually delete the index '{self.index_name}' and try again."
                    )
                    raise ValueError(
                        f"Dimension mismatch error and auto-recreation failed: {str(recreate_error)}. "
                        f"Original error: {error_str}. "
                        f"Please manually delete the index '{self.index_name}' and try again."
                    )
            else:
                logger.error(f"Failed to add documents to OpenSearch vectorstore: {error_str}")
                raise ValueError(f"Failed to add documents to OpenSearch vectorstore: {error_str}")
    
    def as_retriever(self, search_type: str = "similarity", search_kwargs: Optional[Dict] = None):
        """Get retriever for querying."""
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Process documents first.")
        
        return self.vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs or {}
        )
    
    def save_local(self, path: str):
        """OpenSearch doesn't support local saving - data is stored in cloud."""
        logger.warning("OpenSearch stores data in the cloud. No local save needed.")
    
    def load_local(self, path: str):
        """OpenSearch loads from the index automatically - no local load needed."""
        logger.info("OpenSearch loads data from the cloud index automatically.")
        # The index is already connected, so we just verify it exists
        try:
            # Try to get a sample document to verify connection
            # This is a lightweight check
            pass
        except Exception as e:
            logger.warning(f"Could not verify OpenSearch index connection: {str(e)}")
    
    @staticmethod
    def sanitize_index_name(document_name: str) -> str:
        """
        Sanitize a document name to create a valid OpenSearch index name.
        
        OpenSearch index naming rules:
        - Lowercase only
        - No spaces (replace with hyphens)
        - No special characters except hyphens and underscores
        - Must start with a letter or underscore
        - Max length: 255 characters
        
        Args:
            document_name: Original document name (e.g., "My Document.pdf")
            
        Returns:
            Sanitized index name (e.g., "my-document-pdf")
        """
        # Remove file extension if present
        name_without_ext = os.path.splitext(document_name)[0]
        
        # Convert to lowercase
        sanitized = name_without_ext.lower()
        
        # Replace spaces and special characters with hyphens
        sanitized = re.sub(r'[^a-z0-9_-]', '-', sanitized)
        
        # Replace multiple consecutive hyphens with single hyphen
        sanitized = re.sub(r'-+', '-', sanitized)
        
        # Remove leading/trailing hyphens and underscores
        sanitized = sanitized.strip('-').strip('_')
        
        # Ensure it starts with a letter or underscore (OpenSearch requirement)
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = 'doc-' + sanitized
        
        # Truncate to 255 characters (OpenSearch limit)
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
            # Remove trailing hyphen if truncated
            sanitized = sanitized.rstrip('-')
        
        # If empty after sanitization, use default
        if not sanitized:
            sanitized = 'document'
        
        return sanitized
    
    def hybrid_search(
        self,
        query: str,
        query_vector: List[float],
        k: int = 10,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filter: Optional[Dict] = None,
        alternate_query: Optional[str] = None,
        min_score: Optional[float] = None
    ) -> List[Document]:
        """
        Perform optimized hybrid search combining semantic (vector) and keyword (text) search.
        
        Performance optimizations:
        - Query result caching (configurable TTL)
        - ef_search parameter for HNSW speed/accuracy tradeoff
        - min_score threshold to skip irrelevant results
        - Reduced over-fetching with smart k multiplier
        - Parallel msearch execution
        
        Args:
            query: Text query for keyword search (usually English)
            query_vector: Embedding vector for semantic search
            k: Number of results to return
            semantic_weight: Weight for semantic search results
            keyword_weight: Weight for keyword search results
            filter: Optional OpenSearch filter
            alternate_query: Optional query in original language (for dual-language search)
            min_score: Minimum similarity score threshold (default from config)
        """
        if self.vectorstore is None:
            raise ValueError("Vector store not initialized. Process documents first.")
        
        search_start_time = time.time()
        
        # Get performance config
        from shared.config.settings import ARISConfig
        knn_config = ARISConfig.get_knn_performance_config()
        ef_search = knn_config['ef_search']
        if min_score is None:
            min_score = knn_config['min_score']
        cache_ttl = knn_config['cache_ttl_seconds']
        max_fetch_multiplier = knn_config['max_fetch_multiplier']
        
        # Build cache key (use first 100 chars of query + filter hash)
        filter_hash = hashlib.md5(str(filter).encode()).hexdigest()[:8] if filter else "none"
        cache_key = hashlib.md5(
            f"{query[:100]}:{k}:{semantic_weight}:{filter_hash}:{self.index_name}".encode()
        ).hexdigest()
        
        # Check cache
        if cache_ttl > 0 and cache_key in _hybrid_cache:
            cache_time = _hybrid_cache_timestamps.get(cache_key, 0)
            if time.time() - cache_time < cache_ttl:
                logger.info(f"🚀 Cache hit for hybrid search (saved ~1-2 min)")
                return _hybrid_cache[cache_key]
        
        try:
            client = self.vectorstore.client
            
            # Normalize weights
            total_weight = semantic_weight + keyword_weight
            if total_weight > 0:
                semantic_weight = semantic_weight / total_weight
                keyword_weight = keyword_weight / total_weight
            else:
                semantic_weight = 0.5
                keyword_weight = 0.5
            
            # Calculate optimized fetch sizes (reduced over-fetching)
            fetch_k = int(k * max_fetch_multiplier)
            
            # Prepare Multi-Search for parallel semantic and keyword retrieval
            semantic_results = []
            keyword_results = []
            msearch_body = []
            
            # 1. Prepare Semantic Search (if weight > 0) with ef_search optimization
            if semantic_weight > 0:
                knn_size = max(fetch_k, int(k * (1 + semantic_weight * 0.5)))  # Reduced multiplier
                knn_query = {
                    "size": knn_size,
                    "_source": ["text", "metadata", "source", "page", "content_type"],  # Only needed fields
                    "query": {
                        "knn": {
                            "vector_field": {
                                "vector": query_vector,
                                "k": knn_size,
                                "method_parameters": {
                                    "ef_search": ef_search
                                }
                            }
                        }
                    }
                }
                if filter:
                    knn_query["query"]["knn"]["vector_field"]["filter"] = filter
                
                # Add min_score if specified
                if min_score and min_score > 0:
                    knn_query["min_score"] = min_score
                
                msearch_body.extend([{"index": self.index_name}, knn_query])
            
            # 2. Prepare Keyword Search (if weight > 0)
            # ENHANCED: Add phrase matching with very high boost to prioritize exact phrase matches
            if keyword_weight > 0:
                should_clauses = [
                    # Exact phrase match - HIGHEST priority (boost 10x)
                    {
                        "match_phrase": {
                            "text": {
                                "query": query,
                                "boost": 10.0,
                                "slop": 1  # Strict: only 1 word between phrase terms
                            }
                        }
                    },
                    # Phrase match with more flexibility (boost 5x)
                    {
                        "match_phrase": {
                            "text": {
                                "query": query,
                                "boost": 5.0,
                                "slop": 3  # Allow 3 words between phrase terms
                            }
                        }
                    },
                    # Standard multi-match for individual terms (lower boost)
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["text^1.5", "metadata.text_english^1.0", "metadata.source^0.5"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    }
                ]
                
                if alternate_query and alternate_query != query:
                    # Also add phrase match for alternate query
                    should_clauses.append({
                        "match_phrase": {
                            "text": {
                                "query": alternate_query,
                                "boost": 4.0,
                                "slop": 2
                            }
                        }
                    })
                    should_clauses.append({
                        "multi_match": {
                            "query": alternate_query,
                            "fields": ["metadata.text_original^2", "text^0.5"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    })
                
                text_query = {
                    "size": int(k * (1 + keyword_weight)),
                    "_source": ["text", "metadata", "source", "page", "content_type"],
                    "query": {
                        "bool": {
                            "should": should_clauses,
                            "minimum_should_match": 1
                        }
                    }
                }
                if filter:
                    text_query["query"]["bool"]["filter"] = filter
                
                msearch_body.extend([{"index": self.index_name}, text_query])
            
            # 3. Execute Multi-Search
            if msearch_body:
                try:
                    msearch_response = client.msearch(body=msearch_body)
                    responses = msearch_response.get("responses", [])
                    
                    resp_idx = 0
                    if semantic_weight > 0 and resp_idx < len(responses):
                        semantic_results = responses[resp_idx].get("hits", {}).get("hits", [])
                        resp_idx += 1
                    
                    if keyword_weight > 0 and resp_idx < len(responses):
                        keyword_results = responses[resp_idx].get("hits", {}).get("hits", [])
                except Exception as e:
                    logger.warning(f"Multi-search failed: {str(e)}. Falling back to sequential search.")
                    # Fallback to sequential if msearch fails (unlikely)
                    if not semantic_results and semantic_weight > 0:
                        try:
                            semantic_response = client.search(index=self.index_name, body=knn_query)
                            semantic_results = semantic_response.get("hits", {}).get("hits", [])
                        except Exception as e:
                            logger.debug(f"hybrid_search: semantic fallback failed: {type(e).__name__}: {e}")
                    if not keyword_results and keyword_weight > 0:
                        try:
                            keyword_response = client.search(index=self.index_name, body=text_query)
                            keyword_results = keyword_response.get("hits", {}).get("hits", [])
                        except Exception as e:
                            logger.debug(f"hybrid_search: keyword fallback failed: {type(e).__name__}: {e}")
            
            # Combine results using RRF
            all_hits = semantic_results + keyword_results
            
            # Process results and combine using RRF
            results = self._combine_hybrid_results(
                all_hits,
                k,
                semantic_weight,
                keyword_weight,
                semantic_results,
                keyword_results
            )
            
            # Convert to Document objects and preserve similarity scores
            documents = []
            for hit in results:
                source = hit.get("_source", {})
                text = source.get("text", "")
                
                # CRITICAL FIX: LangChain stores metadata fields at TOP LEVEL of _source,
                # not nested under 'metadata'. Check both locations for compatibility.
                metadata = source.get("metadata", {})
                
                # Also check top-level _source for essential metadata fields
                # (LangChain OpenSearchVectorSearch stores metadata at top level)
                essential_metadata_fields = [
                    'source', 'page', 'source_page', 'chunk_index', 'total_chunks',
                    'parser_used', 'pages', 'images_detected', 'extraction_percentage',
                    'start_char', 'end_char', 'token_count',
                    'page_extraction_method', 'page_confidence',
                    'has_image', 'image_ref', 'image_index', 'image_bbox', 'image_info', 'image_page',
                    'content_type', 'document_id',
                    'language', 'language_detected', 'primary_language'
                ]
                for field in essential_metadata_fields:
                    if field not in metadata and field in source:
                        metadata[field] = source[field]
                
                # Extract similarity score from hit if available
                # Priority: hybrid_score (from RRF) > _score (from OpenSearch) > None
                hit_score = None
                if "_hybrid_score" in hit:
                    hit_score = hit.get("_hybrid_score")
                elif "_score" in hit:
                    hit_score = hit.get("_score")
                
                if hit_score is not None:
                    # Store score in metadata for later use
                    metadata["_opensearch_score"] = float(hit_score)
                
                doc = Document(
                    page_content=text,
                    metadata=metadata
                )
                documents.append(doc)
            
            final_docs = documents[:k]
            
            # Cache results for future queries
            if cache_ttl > 0:
                _hybrid_cache[cache_key] = final_docs
                _hybrid_cache_timestamps[cache_key] = time.time()
                # Clean old cache entries (keep max 100)
                if len(_hybrid_cache) > 100:
                    oldest_keys = sorted(_hybrid_cache_timestamps.keys(), key=lambda x: _hybrid_cache_timestamps[x])[:50]
                    for old_key in oldest_keys:
                        _hybrid_cache.pop(old_key, None)
                        _hybrid_cache_timestamps.pop(old_key, None)
            
            total_time = time.time() - search_start_time
            logger.info(f"✅ Hybrid search completed in {total_time:.2f}s with {len(final_docs)} results (semantic={semantic_weight:.2f}, keyword={keyword_weight:.2f}, ef_search={ef_search})")
            return final_docs
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            # Fallback to semantic-only search
            logger.warning("Falling back to semantic-only search")
            try:
                # Use standard similarity search as fallback
                return self.vectorstore.similarity_search(query, k=k)
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {str(fallback_error)}")
                return []
    
    def _combine_hybrid_results(
        self,
        all_hits: List[Dict],
        k: int,
        semantic_weight: float,
        keyword_weight: float,
        semantic_results: List[Dict],
        keyword_results: List[Dict]
    ) -> List[Dict]:
        """
        Combine semantic and keyword search results using Reciprocal Rank Fusion (RRF).
        
        Args:
            all_hits: Combined list of all search hits
            k: Number of final results
            semantic_weight: Weight for semantic results
            keyword_weight: Weight for keyword results
            semantic_results: List of semantic search hits
            keyword_results: List of keyword search hits
            
        Returns:
            Combined and re-ranked results
        """
        # Create sets to identify which results came from which search
        semantic_ids = {hit.get("_id") for hit in semantic_results}
        keyword_ids = {hit.get("_id") for hit in keyword_results}
        
        # Group results by document ID
        doc_scores = {}
        doc_hits = {}
        
        # Process semantic results
        for rank, hit in enumerate(semantic_results, 1):
            doc_id = hit.get("_id")
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "semantic_score": 0.0,
                    "keyword_score": 0.0,
                    "semantic_rank": float('inf'),
                    "keyword_rank": float('inf')
                }
                doc_hits[doc_id] = hit
            
            # Calculate RRF score: 1 / (k + rank)
            rrf_score = 1.0 / (60 + rank)  # k=60 is standard RRF parameter
            doc_scores[doc_id]["semantic_score"] = rrf_score * semantic_weight
            doc_scores[doc_id]["semantic_rank"] = rank
        
        # Process keyword results
        for rank, hit in enumerate(keyword_results, 1):
            doc_id = hit.get("_id")
            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    "semantic_score": 0.0,
                    "keyword_score": 0.0,
                    "semantic_rank": float('inf'),
                    "keyword_rank": float('inf')
                }
                doc_hits[doc_id] = hit
            
            # Calculate RRF score: 1 / (k + rank)
            rrf_score = 1.0 / (60 + rank)  # k=60 is standard RRF parameter
            doc_scores[doc_id]["keyword_score"] = rrf_score * keyword_weight
            doc_scores[doc_id]["keyword_rank"] = rank
        
        # Combine scores and sort
        combined_results = []
        for doc_id, scores in doc_scores.items():
            total_score = scores["semantic_score"] + scores["keyword_score"]
            # Store the combined score in the hit for later extraction
            if doc_id in doc_hits:
                doc_hits[doc_id]["_hybrid_score"] = total_score
            combined_results.append({
                "hit": doc_hits[doc_id],
                "combined_score": total_score,
                "semantic_score": scores["semantic_score"],
                "keyword_score": scores["keyword_score"]
            })
        
        # Sort by combined score (descending)
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Return top k
        return [result["hit"] for result in combined_results[:k]]
    
    def index_exists(self, index_name: Optional[str] = None) -> bool:
        """
        Check if an OpenSearch index exists.
        
        Args:
            index_name: Index name to check (defaults to self.index_name)
            
        Returns:
            True if index exists, False otherwise
        """
        if self.vectorstore is None:
            return False
        
        check_index = index_name or self.index_name
        
        try:
            client = self.vectorstore.client
            exists = client.indices.exists(index=check_index)
            return exists
        except Exception as e:
            logger.warning(f"Could not check if index '{check_index}' exists: {str(e)}")
            return False

    def count_documents(self, query: Optional[Dict[str, Any]] = None, index_name: Optional[str] = None) -> int:
        if self.vectorstore is None:
            return 0

        target_index = index_name or self.index_name
        try:
            client = self.vectorstore.client
            body = {"query": query or {"match_all": {}}}
            resp = client.count(index=target_index, body=body)
            return int(resp.get("count", 0) or 0)
        except Exception as e:
            logger.warning(f"Could not count documents in index '{target_index}': {str(e)}")
            return 0
    
    def find_next_available_index_name(self, base_index_name: str) -> str:
        """
        Find the next available index name by auto-incrementing.
        
        If base_index_name exists, tries base_index_name-1, base_index_name-2, etc.
        
        Args:
            base_index_name: Base index name to check
            
        Returns:
            Available index name (either base_index_name or base_index_name-N)
        """
        # First check if base name is available
        if not self.index_exists(base_index_name):
            return base_index_name
        
        # Try incrementing numbers
        counter = 1
        while counter < 1000:  # Safety limit
            candidate_name = f"{base_index_name}-{counter}"
            if not self.index_exists(candidate_name):
                return candidate_name
            counter += 1
        
        # If we've tried 1000 times, something is wrong
        raise ValueError(f"Could not find available index name after 1000 attempts for base: {base_index_name}")
    
    def get_index_name_for_document(self, document_name: str, auto_increment: bool = True) -> str:
        """
        Generate an OpenSearch index name from a document name.
        
        Args:
            document_name: Name of the document (e.g., "My Document.pdf")
            auto_increment: If True, auto-increment if index exists. If False, return base name.
            
        Returns:
            Index name to use (sanitized and possibly incremented)
        """
        # Sanitize document name
        base_index_name = self.sanitize_index_name(document_name)
        
        if auto_increment:
            return self.find_next_available_index_name(base_index_name)
        else:
            return base_index_name


class OpenSearchMultiIndexManager:
    """Manages multiple OpenSearch indexes for per-document storage."""
    
    def __init__(self, embeddings, domain, region=None, endpoint=None):
        self.embeddings = embeddings
        self.domain = domain
        self.region = region
        self.endpoint = endpoint
        self.index_stores: Dict[str, OpenSearchVectorStore] = {}  # index_name -> store
    
    def get_or_create_index_store(self, index_name: str) -> OpenSearchVectorStore:
        """Get or create vectorstore for a specific index."""
        if index_name not in self.index_stores:
            self.index_stores[index_name] = OpenSearchVectorStore(
                embeddings=self.embeddings,
                domain=self.domain,
                index_name=index_name,
                region=self.region,
                endpoint=self.endpoint
            )
        return self.index_stores[index_name]
    
    def search_across_indexes(
        self, 
        query: str, 
        index_names: List[str], 
        k: int = 10,
        use_mmr: bool = False,
        fetch_k: int = 50,
        lambda_mult: float = 0.3,
        use_hybrid_search: bool = False,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filter: Optional[Dict] = None,
        alternate_query: Optional[str] = None,
        **kwargs
    ) -> List[Document]:
        """
        Search across multiple indexes and combine results with GLOBAL RE-RANKING.
        
        FIX: Previous implementation divided results per index (k/n per index) and 
        concatenated without re-ranking. This caused irrelevant results when searching
        all documents because early indexes got priority regardless of relevance.
        
        NEW: Get k results from EACH index, then globally re-rank by relevance score.
        """
        all_results = []
        
        # FIX: Get k results from EACH index (not k/n), then re-rank globally
        # This ensures we get the best results from each document
        results_per_index = max(k, 10)  # At least k or 10 results per index
        
        # Pre-compute query embedding ONCE for efficiency (avoid embedding per index)
        query_vector = None
        if use_hybrid_search and index_names:
            try:
                first_store = self.get_or_create_index_store(index_names[0])
                query_vector = first_store.embeddings.embed_query(query)
            except Exception as e:
                logger.warning(f"Could not pre-compute query embedding: {e}")
        
        import concurrent.futures
        
        def search_single_index(index_name):
            try:
                store = self.get_or_create_index_store(index_name)
                
                if use_hybrid_search:
                    # Use pre-computed embedding for efficiency
                    return store.hybrid_search(
                        query=query,
                        query_vector=query_vector,
                        k=results_per_index,
                        semantic_weight=semantic_weight,
                        keyword_weight=keyword_weight,
                        filter=filter,
                        alternate_query=alternate_query
                    )
                elif use_mmr:
                    # MMR: Use retriever
                    retriever = store.vectorstore.as_retriever(
                        search_type="mmr",
                        search_kwargs={
                            "k": results_per_index,
                            "fetch_k": fetch_k,
                            "lambda_mult": lambda_mult,
                            "filter": filter
                        }
                    )
                    mmr_results = retriever.invoke(query)
                    # Add score based on MMR ranking (higher rank = higher score)
                    for rank, doc in enumerate(mmr_results):
                        doc.metadata = doc.metadata or {}
                        doc.metadata["_opensearch_score"] = 1.0 / (1 + rank)
                    return mmr_results
                else:
                    # Basic similarity search: Use similarity_search_with_score for scores
                    try:
                        search_kwargs_inner = {"k": results_per_index}
                        if filter:
                            search_kwargs_inner["filter"] = filter
                        
                        results_with_scores = store.vectorstore.similarity_search_with_score(
                            query, **search_kwargs_inner
                        )
                        results = []
                        for doc, score in results_with_scores:
                            doc.metadata = doc.metadata or {}
                            doc.metadata["_opensearch_score"] = float(score)
                            results.append(doc)
                        return results
                    except Exception as score_err:
                        # Fallback to retriever
                        logger.debug(f"similarity_search_with_score failed, using retriever: {score_err}")
                        search_kwargs={"k": results_per_index}
                        if filter:
                            search_kwargs["filter"] = filter
                        retriever = store.vectorstore.as_retriever(
                            search_kwargs=search_kwargs
                        )
                        return retriever.invoke(query)
            except Exception as e:
                logger.warning(f"Error searching index '{index_name}': {e}")
                return []

        # Execute searches in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(index_names), 10)) as executor:
            future_to_index = {executor.submit(search_single_index, name): name for name in index_names}
            for future in concurrent.futures.as_completed(future_to_index):
                index_name = future_to_index[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.debug(f"Found {len(results)} results in index '{index_name}'")
                except Exception as e:
                    logger.warning(f"Thread error searching index '{index_name}': {e}")
        
        # ======== GLOBAL RE-RANKING ========
        # FIX: Sort ALL results by relevance score before returning top k
        # This ensures the most relevant results from ANY document are returned
        
        # Deduplicate by content hash while preserving scores
        seen = set()
        unique_results = []
        for doc in all_results:
            content_hash = hash(doc.page_content[:100])  # Hash first 100 chars
            if content_hash not in seen:
                seen.add(content_hash)
                unique_results.append(doc)
        
        # GLOBAL RE-RANKING: Sort by PHRASE MATCH + relevance score
        # CRITICAL FIX: When RRF scores are similar, prioritize exact phrase matches
        import re
        
        def get_phrase_match_score(doc: Document, query_text: str) -> float:
            """
            Calculate phrase match score for re-ranking.
            Exact phrase matches get highest score, partial matches get lower.
            """
            content = (doc.page_content or '').lower()
            query_lower = query_text.lower()
            
            # Extract meaningful phrases (2+ words) from query
            words = re.findall(r'\b\w+\b', query_lower)
            stop_words = {'what', 'is', 'the', 'a', 'an', 'of', 'in', 'for', 'to', 'and', 'or', 'how', 'why', 'when', 'where', 'which'}
            content_words = [w for w in words if w not in stop_words and len(w) > 2]
            
            score = 0.0
            
            # Check for exact full query phrase match (highest priority)
            clean_query = ' '.join(content_words)
            if clean_query and clean_query in content:
                score += 10.0
                logger.debug(f"Exact phrase match found: '{clean_query}'")
            
            # Check for 2-word phrase matches
            for i in range(len(content_words) - 1):
                phrase = f"{content_words[i]} {content_words[i+1]}"
                if phrase in content:
                    score += 3.0
                # Check with 1-word gap (e.g., "leave policy" matches "leave the policy")
                pattern = rf'\b{re.escape(content_words[i])}\b\s+\w*\s*\b{re.escape(content_words[i+1])}\b'
                if re.search(pattern, content):
                    score += 1.5
            
            # Check individual keyword matches (lower priority)
            for word in content_words:
                if re.search(rf'\b{re.escape(word)}\b', content):
                    score += 0.5
            
            return score
        
        def get_relevance_score(doc: Document) -> float:
            """Extract relevance score from document metadata."""
            metadata = doc.metadata or {}
            # Priority: _opensearch_score (hybrid) > _score > 0
            if "_opensearch_score" in metadata:
                return float(metadata["_opensearch_score"])
            if "_score" in metadata:
                return float(metadata["_score"])
            return 0.0
        
        # Calculate phrase match scores for all results
        for doc in unique_results:
            phrase_score = get_phrase_match_score(doc, query)
            doc.metadata['_phrase_match_score'] = phrase_score
        
        # Sort by: (1) phrase match score (primary), (2) relevance score (secondary)
        # This ensures documents with exact phrase matches rank higher
        unique_results.sort(
            key=lambda doc: (
                doc.metadata.get('_phrase_match_score', 0),
                get_relevance_score(doc)
            ),
            reverse=True
        )
        
        logger.info(f"🔄 Global re-ranking: {len(unique_results)} unique results from {len(index_names)} indexes, returning top {k}")
        
        # Log top results for debugging
        if unique_results:
            top_info = [(f"phrase={doc.metadata.get('_phrase_match_score', 0):.1f}", 
                        f"score={get_relevance_score(doc):.4f}",
                        doc.metadata.get('source', 'Unknown')[:20]) 
                       for doc in unique_results[:min(5, len(unique_results))]]
            logger.info(f"🔄 Top {len(top_info)} after phrase-aware re-ranking: {top_info}")
        
        return unique_results[:k]
    
    def get_all_indexes(self) -> List[str]:
        """Get list of all managed index names."""
        return list(self.index_stores.keys())


class OpenSearchCRUDManager:
    """
    CRUD operations manager for OpenSearch vector indexes.
    Provides comprehensive management capabilities for documents and vectors.
    """
    
    def __init__(self, embeddings, domain: str, region: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize CRUD manager.
        
        Args:
            embeddings: Embeddings model to use
            domain: OpenSearch domain name
            region: AWS region
            endpoint: Direct endpoint URL (optional)
        """
        self.embeddings = embeddings
        self.domain = domain
        self.region = region or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        self.endpoint = endpoint
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenSearch client."""
        try:
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from requests_aws4auth import AWS4Auth
            
            access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
            
            if not access_key or not secret_key:
                raise ValueError("OpenSearch credentials not configured")
            
            # Get endpoint if not provided
            if not self.endpoint:
                opensearch_client = boto3.client(
                    'opensearch',
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name=self.region
                )
                domain_info = opensearch_client.describe_domain(DomainName=self.domain)
                domain_status = domain_info.get('DomainStatus', {})
                
                if 'Endpoint' in domain_status:
                    self.endpoint = domain_status['Endpoint']
                elif 'Endpoints' in domain_status:
                    endpoints = domain_status['Endpoints']
                    self.endpoint = list(endpoints.values())[0] if endpoints else None
                
                if not self.endpoint:
                    raise ValueError(f"Could not find endpoint for OpenSearch domain: {self.domain}")
            
            if not self.endpoint.startswith('http'):
                self.endpoint = f"https://{self.endpoint}"
            
            # Create auth
            awsauth = AWS4Auth(access_key, secret_key, self.region, 'es')
            
            # Parse host from endpoint
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            host = parsed.netloc or parsed.path
            
            self._client = OpenSearch(
                hosts=[{'host': host, 'port': 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
            
            logger.info(f"OpenSearch CRUD Manager initialized: {self.endpoint}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenSearch CRUD client: {e}")
            raise
    
    # ==================== INDEX OPERATIONS ====================
    
    def list_all_indexes(self, prefix: str = "aris-") -> List[Dict[str, Any]]:
        """
        List all OpenSearch indexes matching prefix.
        
        Args:
            prefix: Index name prefix to filter (default: "aris-")
            
        Returns:
            List of index information dicts
        """
        try:
            # Get all indexes
            indices = self._client.cat.indices(format='json')
            
            result = []
            for idx in indices:
                index_name = idx.get('index', '')
                if index_name.startswith(prefix):
                    # Get detailed mapping info
                    try:
                        mapping = self._client.indices.get_mapping(index=index_name)
                        index_mapping = mapping.get(index_name, {}).get('mappings', {})
                        properties = index_mapping.get('properties', {})
                        
                        # Find vector dimension
                        dimension = None
                        for field_name, field_config in properties.items():
                            if field_config.get('type') == 'knn_vector':
                                dimension = field_config.get('dimension')
                                break
                    except Exception as e:
                        logger.debug(f"operation: {type(e).__name__}: {e}")
                        dimension = None
                    
                    result.append({
                        'index_name': index_name,
                        'chunk_count': int(idx.get('docs.count', 0) or 0),
                        'size': idx.get('store.size', '0b'),
                        'status': idx.get('health', 'unknown'),
                        'dimension': dimension,
                        'created_at': None  # OpenSearch doesn't store creation time directly
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            return []
    
    def get_index_info(self, index_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific index.
        
        Args:
            index_name: Name of the index
            
        Returns:
            Index information dict or None
        """
        try:
            if not self._client.indices.exists(index=index_name):
                return None
            
            # Get index stats
            stats = self._client.indices.stats(index=index_name)
            index_stats = stats.get('indices', {}).get(index_name, {})
            
            # Get mapping
            mapping = self._client.indices.get_mapping(index=index_name)
            index_mapping = mapping.get(index_name, {}).get('mappings', {})
            properties = index_mapping.get('properties', {})
            
            # Find vector dimension
            dimension = None
            for field_name, field_config in properties.items():
                if field_config.get('type') == 'knn_vector':
                    dimension = field_config.get('dimension')
                    break
            
            primaries = index_stats.get('primaries', {})
            docs = primaries.get('docs', {})
            store = primaries.get('store', {})
            
            return {
                'index_name': index_name,
                'exists': True,
                'chunk_count': docs.get('count', 0),
                'deleted_docs': docs.get('deleted', 0),
                'size_bytes': store.get('size_in_bytes', 0),
                'dimension': dimension,
                'properties': list(properties.keys()),
                'status': 'active'
            }
            
        except Exception as e:
            logger.error(f"Failed to get index info for '{index_name}': {e}")
            return None
    
    def delete_index(self, index_name: str) -> Dict[str, Any]:
        """
        Delete an OpenSearch index.
        
        Args:
            index_name: Name of the index to delete
            
        Returns:
            Result dict with success status
        """
        try:
            if not self._client.indices.exists(index=index_name):
                return {
                    'success': False,
                    'index_name': index_name,
                    'message': f"Index '{index_name}' does not exist",
                    'chunks_deleted': 0
                }
            
            # Get doc count before deletion
            count_resp = self._client.count(index=index_name)
            chunks_count = count_resp.get('count', 0)
            
            # Delete the index
            self._client.indices.delete(index=index_name)
            
            logger.info(f"Deleted index '{index_name}' with {chunks_count} chunks")
            
            return {
                'success': True,
                'index_name': index_name,
                'message': f"Successfully deleted index '{index_name}'",
                'chunks_deleted': chunks_count
            }
            
        except Exception as e:
            logger.error(f"Failed to delete index '{index_name}': {e}")
            return {
                'success': False,
                'index_name': index_name,
                'message': f"Failed to delete index: {str(e)}",
                'chunks_deleted': 0
            }
    
    def delete_indexes_bulk(self, index_names: List[str]) -> Dict[str, Any]:
        """
        Delete multiple OpenSearch indexes.
        
        Args:
            index_names: List of index names to delete
            
        Returns:
            Result dict with bulk deletion status
        """
        results = {
            'success': True,
            'total_requested': len(index_names),
            'total_deleted': 0,
            'total_chunks_deleted': 0,
            'failed': [],
            'message': ''
        }
        
        for index_name in index_names:
            result = self.delete_index(index_name)
            if result['success']:
                results['total_deleted'] += 1
                results['total_chunks_deleted'] += result['chunks_deleted']
            else:
                results['failed'].append({
                    'index_name': index_name,
                    'error': result['message']
                })
        
        if results['failed']:
            results['success'] = len(results['failed']) < len(index_names)
            results['message'] = f"Deleted {results['total_deleted']}/{len(index_names)} indexes, {len(results['failed'])} failed"
        else:
            results['message'] = f"Successfully deleted all {results['total_deleted']} indexes"
        
        return results
    
    # ==================== CHUNK OPERATIONS ====================
    
    def list_chunks(
        self, 
        index_name: str, 
        offset: int = 0, 
        limit: int = 100,
        source_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List chunks in an index with pagination.
        
        Args:
            index_name: Index name to query
            offset: Starting offset
            limit: Maximum results
            source_filter: Optional source document filter
            
        Returns:
            Dict with chunks and pagination info
        """
        try:
            if not self._client.indices.exists(index=index_name):
                return {
                    'index_name': index_name,
                    'chunks': [],
                    'total': 0,
                    'offset': offset,
                    'limit': limit,
                    'error': f"Index '{index_name}' does not exist"
                }
            
            # Build query
            query = {"match_all": {}}
            if source_filter:
                query = {
                    "bool": {
                        "must": [{"match": {"source": source_filter}}]
                    }
                }
            
            # Execute search
            response = self._client.search(
                index=index_name,
                body={
                    "query": query,
                    "from": offset,
                    "size": limit,
                    "sort": [{"_id": "asc"}]
                }
            )
            
            hits = response.get('hits', {})
            total = hits.get('total', {})
            total_count = total.get('value', 0) if isinstance(total, dict) else total
            
            chunks = []
            for hit in hits.get('hits', []):
                source = hit.get('_source', {})
                chunks.append({
                    'chunk_id': hit.get('_id'),
                    'text': source.get('text', ''),
                    'page': source.get('page') or source.get('metadata', {}).get('page'),
                    'chunk_index': source.get('chunk_index') or source.get('metadata', {}).get('chunk_index'),
                    'source': source.get('source') or source.get('metadata', {}).get('source'),
                    'language': source.get('language') or source.get('metadata', {}).get('language'),
                    'metadata': source.get('metadata', {}),
                    'score': hit.get('_score')
                })
            
            return {
                'index_name': index_name,
                'chunks': chunks,
                'total': total_count,
                'offset': offset,
                'limit': limit
            }
            
        except Exception as e:
            logger.error(f"Failed to list chunks in '{index_name}': {e}")
            return {
                'index_name': index_name,
                'chunks': [],
                'total': 0,
                'offset': offset,
                'limit': limit,
                'error': str(e)
            }
    
    def get_chunk(self, index_name: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific chunk by ID.
        
        Args:
            index_name: Index name
            chunk_id: Document/chunk ID
            
        Returns:
            Chunk data or None
        """
        try:
            response = self._client.get(index=index_name, id=chunk_id)
            source = response.get('_source', {})
            
            return {
                'chunk_id': response.get('_id'),
                'text': source.get('text', ''),
                'page': source.get('page') or source.get('metadata', {}).get('page'),
                'chunk_index': source.get('chunk_index') or source.get('metadata', {}).get('chunk_index'),
                'source': source.get('source') or source.get('metadata', {}).get('source'),
                'language': source.get('language') or source.get('metadata', {}).get('language'),
                'metadata': source.get('metadata', {})
            }
            
        except Exception as e:
            logger.warning(f"Chunk '{chunk_id}' not found in '{index_name}': {e}")
            return None
    
    def create_chunk(
        self,
        index_name: str,
        text: str,
        page: int = 1,
        source: Optional[str] = None,
        language: str = "eng",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new chunk with embedding.
        
        Args:
            index_name: Target index
            text: Text content
            page: Page number
            source: Source document name
            language: Language code
            metadata: Additional metadata
            
        Returns:
            Result dict with chunk ID
        """
        try:
            # Generate embedding
            embedding = self.embeddings.embed_query(text)
            
            # Prepare document
            doc = {
                'text': text,
                'vector_field': embedding,
                'page': page,
                'source': source,
                'language': language,
                'content_type': 'text',
                'metadata': metadata or {}
            }
            
            # Index document
            response = self._client.index(index=index_name, body=doc)
            
            chunk_id = response.get('_id')
            logger.info(f"Created chunk '{chunk_id}' in index '{index_name}'")
            
            return {
                'success': True,
                'chunk_id': chunk_id,
                'index_name': index_name,
                'message': f"Successfully created chunk"
            }
            
        except Exception as e:
            logger.error(f"Failed to create chunk in '{index_name}': {e}")
            return {
                'success': False,
                'chunk_id': None,
                'index_name': index_name,
                'message': f"Failed to create chunk: {str(e)}"
            }
    
    def update_chunk(
        self,
        index_name: str,
        chunk_id: str,
        text: Optional[str] = None,
        page: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update an existing chunk.
        
        Args:
            index_name: Index name
            chunk_id: Chunk ID to update
            text: New text content (regenerates embedding if provided)
            page: New page number
            metadata: Metadata to merge
            
        Returns:
            Result dict
        """
        try:
            # Build update doc
            update_doc = {}
            
            if text is not None:
                update_doc['text'] = text
                # Regenerate embedding
                embedding = self.embeddings.embed_query(text)
                update_doc['vector_field'] = embedding
            
            if page is not None:
                update_doc['page'] = page
            
            if metadata:
                # Get existing doc to merge metadata
                existing = self._client.get(index=index_name, id=chunk_id)
                existing_metadata = existing.get('_source', {}).get('metadata', {})
                existing_metadata.update(metadata)
                update_doc['metadata'] = existing_metadata
            
            if not update_doc:
                return {
                    'success': False,
                    'chunk_id': chunk_id,
                    'message': 'No fields to update'
                }
            
            # Execute update
            self._client.update(
                index=index_name,
                id=chunk_id,
                body={'doc': update_doc}
            )
            
            logger.info(f"Updated chunk '{chunk_id}' in index '{index_name}'")
            
            return {
                'success': True,
                'chunk_id': chunk_id,
                'index_name': index_name,
                'message': 'Successfully updated chunk'
            }
            
        except Exception as e:
            logger.error(f"Failed to update chunk '{chunk_id}' in '{index_name}': {e}")
            return {
                'success': False,
                'chunk_id': chunk_id,
                'index_name': index_name,
                'message': f"Failed to update chunk: {str(e)}"
            }
    
    def delete_chunk(self, index_name: str, chunk_id: str) -> Dict[str, Any]:
        """
        Delete a specific chunk.
        
        Args:
            index_name: Index name
            chunk_id: Chunk ID to delete
            
        Returns:
            Result dict
        """
        try:
            self._client.delete(index=index_name, id=chunk_id)
            
            logger.info(f"Deleted chunk '{chunk_id}' from index '{index_name}'")
            
            return {
                'success': True,
                'chunk_id': chunk_id,
                'index_name': index_name,
                'message': 'Successfully deleted chunk'
            }
            
        except Exception as e:
            logger.error(f"Failed to delete chunk '{chunk_id}' from '{index_name}': {e}")
            return {
                'success': False,
                'chunk_id': chunk_id,
                'index_name': index_name,
                'message': f"Failed to delete chunk: {str(e)}"
            }
    
    def delete_chunks_by_source(self, index_name: str, source: str) -> Dict[str, Any]:
        """
        Delete all chunks from a specific source document.
        
        Args:
            index_name: Index name
            source: Source document name
            
        Returns:
            Result dict with deletion count
        """
        try:
            # Delete by query
            response = self._client.delete_by_query(
                index=index_name,
                body={
                    "query": {
                        "bool": {
                            "should": [
                                {"match": {"source": source}},
                                {"match": {"metadata.source": source}}
                            ]
                        }
                    }
                }
            )
            
            deleted = response.get('deleted', 0)
            logger.info(f"Deleted {deleted} chunks from source '{source}' in index '{index_name}'")
            
            return {
                'success': True,
                'index_name': index_name,
                'source': source,
                'chunks_deleted': deleted,
                'message': f"Successfully deleted {deleted} chunks"
            }
            
        except Exception as e:
            logger.error(f"Failed to delete chunks from source '{source}' in '{index_name}': {e}")
            return {
                'success': False,
                'index_name': index_name,
                'source': source,
                'chunks_deleted': 0,
                'message': f"Failed to delete chunks: {str(e)}"
            }
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search_vectors(
        self,
        query: str,
        index_names: Optional[List[str]] = None,
        k: int = 10,
        use_hybrid: bool = True,
        semantic_weight: float = 0.7
    ) -> Dict[str, Any]:
        """
        Search vectors across indexes.
        
        Args:
            query: Search query
            index_names: Specific indexes to search (None = all aris- indexes)
            k: Number of results
            use_hybrid: Use hybrid search
            semantic_weight: Weight for semantic search
            
        Returns:
            Search results dict
        """
        import time
        start_time = time.time()
        
        try:
            # Get indexes to search
            if not index_names:
                all_indexes = self.list_all_indexes()
                index_names = [idx['index_name'] for idx in all_indexes]
            
            if not index_names:
                return {
                    'query': query,
                    'results': [],
                    'total': 0,
                    'indexes_searched': [],
                    'search_time_ms': 0
                }
            
            # Generate query embedding
            query_vector = self.embeddings.embed_query(query)
            
            all_results = []
            
            for index_name in index_names:
                try:
                    if use_hybrid:
                        # Hybrid search with semantic and keyword
                        # OpenSearch KNN query format - vector_field is the field name, not "field" parameter
                        knn_results = self._client.search(
                            index=index_name,
                            body={
                                "size": k,
                                "query": {
                                    "knn": {
                                        "vector_field": {
                                            "vector": query_vector,
                                            "k": k
                                        }
                                    }
                                }
                            }
                        )
                        
                        text_results = self._client.search(
                            index=index_name,
                            body={
                                "size": k,
                                "query": {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["text", "metadata.source"],
                                        "fuzziness": "AUTO"
                                    }
                                }
                            }
                        )
                        
                        # Combine with RRF-like scoring
                        seen_ids = {}
                        for rank, hit in enumerate(knn_results.get('hits', {}).get('hits', []), 1):
                            doc_id = hit['_id']
                            rrf_score = semantic_weight / (60 + rank)
                            seen_ids[doc_id] = {'hit': hit, 'score': rrf_score}
                        
                        keyword_weight = 1 - semantic_weight
                        for rank, hit in enumerate(text_results.get('hits', {}).get('hits', []), 1):
                            doc_id = hit['_id']
                            rrf_score = keyword_weight / (60 + rank)
                            if doc_id in seen_ids:
                                seen_ids[doc_id]['score'] += rrf_score
                            else:
                                seen_ids[doc_id] = {'hit': hit, 'score': rrf_score}
                        
                        # Sort by combined score
                        sorted_results = sorted(seen_ids.values(), key=lambda x: x['score'], reverse=True)
                        
                        for item in sorted_results[:k]:
                            hit = item['hit']
                            source = hit.get('_source', {})
                            all_results.append({
                                'chunk_id': hit['_id'],
                                'text': source.get('text', ''),
                                'page': source.get('page') or source.get('metadata', {}).get('page'),
                                'chunk_index': source.get('chunk_index') or source.get('metadata', {}).get('chunk_index'),
                                'source': source.get('source') or source.get('metadata', {}).get('source'),
                                'language': source.get('language') or source.get('metadata', {}).get('language'),
                                'metadata': source.get('metadata', {}),
                                'score': item['score'],
                                'index': index_name
                            })
                    else:
                        # Semantic-only search
                        # OpenSearch KNN query format - vector_field is the field name
                        response = self._client.search(
                            index=index_name,
                            body={
                                "size": k,
                                "query": {
                                    "knn": {
                                        "vector_field": {
                                            "vector": query_vector,
                                            "k": k
                                        }
                                    }
                                }
                            }
                        )
                        
                        for hit in response.get('hits', {}).get('hits', []):
                            source = hit.get('_source', {})
                            all_results.append({
                                'chunk_id': hit['_id'],
                                'text': source.get('text', ''),
                                'page': source.get('page') or source.get('metadata', {}).get('page'),
                                'chunk_index': source.get('chunk_index') or source.get('metadata', {}).get('chunk_index'),
                                'source': source.get('source') or source.get('metadata', {}).get('source'),
                                'language': source.get('language') or source.get('metadata', {}).get('language'),
                                'metadata': source.get('metadata', {}),
                                'score': hit.get('_score'),
                                'index': index_name
                            })
                
                except Exception as e:
                    logger.warning(f"Error searching index '{index_name}': {e}")
                    continue
            
            # Sort all results by score and limit
            all_results.sort(key=lambda x: x.get('score', 0) or 0, reverse=True)
            final_results = all_results[:k]
            
            search_time_ms = (time.time() - start_time) * 1000
            
            return {
                'query': query,
                'results': final_results,
                'total': len(final_results),
                'indexes_searched': index_names,
                'search_time_ms': search_time_ms
            }
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {
                'query': query,
                'results': [],
                'total': 0,
                'indexes_searched': index_names or [],
                'search_time_ms': (time.time() - start_time) * 1000,
                'error': str(e)
            }

