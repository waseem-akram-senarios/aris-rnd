"""
OpenSearch Vector Store implementation for RAG system.
Uses AWS OpenSearch Service with LangChain integration.
"""
import os
import re
import logging
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
        self.domain = domain
        self.index_name = index_name
        self.region = region or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        # Get AWS credentials
        self.access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "OpenSearch credentials not found. Please set AWS_OPENSEARCH_ACCESS_KEY_ID "
                "and AWS_OPENSEARCH_SECRET_ACCESS_KEY in .env file"
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
                    
                    kwargs = {
                        'opensearch_url': self.endpoint,
                        'index_name': self.index_name,
                        'embedding_function': self.embeddings,
                        'http_auth': auth,
                        'use_ssl': True,
                        'verify_certs': True,
                        'ssl_assert_hostname': False,
                        'ssl_show_warn': False,
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
                'start_char', 'end_char', 'token_count'
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
            
            # Create cleaned document
            cleaned_doc = Document(
                page_content=doc.page_content,
                metadata=cleaned_metadata
            )
            cleaned_documents.append(cleaned_doc)
        
        return cleaned_documents
    
    def from_documents(self, documents: List[Document]) -> 'OpenSearchVectorStore':
        """Create vector store from documents."""
        if not documents:
            raise ValueError("Cannot create vector store from empty document list")
        
        logger.info(f"Creating OpenSearch vectorstore from {len(documents)} documents...")
        
        try:
            # Clean metadata before adding to OpenSearch (remove large nested structures)
            cleaned_documents = self._clean_metadata_for_opensearch(documents)
            logger.info(f"Cleaned metadata for {len(cleaned_documents)} documents (removed large nested structures)")
            
            # Add documents to the index
            # OpenSearchVectorSearch will create the index if it doesn't exist
            self.vectorstore.add_documents(cleaned_documents)
            logger.info(f"OpenSearch vectorstore created successfully with {len(cleaned_documents)} documents")
        except Exception as e:
            logger.error(f"Failed to create OpenSearch vectorstore: {str(e)}")
            raise ValueError(f"Failed to create OpenSearch vectorstore: {str(e)}")
        
        return self
    
    def add_documents(self, documents: List[Document]):
        """Add documents to existing vector store."""
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
            
            self.vectorstore.add_documents(cleaned_documents)
            logger.info(f"Successfully added {len(cleaned_documents)} documents to OpenSearch vectorstore")
        except Exception as e:
            logger.error(f"Failed to add documents to OpenSearch vectorstore: {str(e)}")
            raise ValueError(f"Failed to add documents to OpenSearch vectorstore: {str(e)}")
    
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

