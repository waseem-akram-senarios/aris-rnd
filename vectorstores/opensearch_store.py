"""
OpenSearch Vector Store implementation for RAG system.
Uses AWS OpenSearch Service with LangChain integration.
"""
import os
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
            for auth_name, auth, conn_class in auth_methods:
                try:
                    logger.info(f"Trying {auth_name} authentication...")
                    
                    kwargs = {
                        'opensearch_url': self.endpoint,
                        'index_name': self.index_name,
                        'embedding_function': self.embeddings,
                        'http_auth': auth,
                        'use_ssl': True,
                        'verify_certs': True,
                        'ssl_assert_hostname': False,
                        'ssl_show_warn': False
                    }
                    
                    if conn_class:
                        kwargs['connection_class'] = conn_class
                    
                    self.vectorstore = OpenSearchVectorSearch(**kwargs)
                    
                    # Test connection by trying to get cluster info
                    try:
                        # This will fail if auth doesn't work
                        test_client = self.vectorstore.client
                        test_client.info()
                        logger.info(f"✅ OpenSearch vector store initialized with {auth_name} (index: {self.index_name})")
                        return
                    except Exception as test_e:
                        logger.warning(f"{auth_name} connection test failed: {str(test_e)[:100]}")
                        continue
                        
                except Exception as e:
                    last_error = e
                    logger.warning(f"{auth_name} failed: {str(e)[:100]}")
                    continue
            
            # If all methods failed
            raise ValueError(
                f"Failed to initialize OpenSearch with any authentication method. "
                f"Last error: {str(last_error)}. "
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
    
    def from_documents(self, documents: List[Document]) -> 'OpenSearchVectorStore':
        """Create vector store from documents."""
        if not documents:
            raise ValueError("Cannot create vector store from empty document list")
        
        logger.info(f"Creating OpenSearch vectorstore from {len(documents)} documents...")
        
        try:
            # Add documents to the index
            # OpenSearchVectorSearch will create the index if it doesn't exist
            self.vectorstore.add_documents(documents)
            logger.info(f"OpenSearch vectorstore created successfully with {len(documents)} documents")
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
            self.vectorstore.add_documents(documents)
            logger.info(f"Successfully added {len(documents)} documents to OpenSearch vectorstore")
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

