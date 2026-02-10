"""
Shared document registry using OpenSearch as the backend database.
Replaces file-based JSON storage to eliminate race conditions and improve scalability.
"""
import os
import json
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import boto3
from boto3 import Session
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth, NotFoundError
from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class DocumentRegistry:
    """
    OpenSearch-backed Document Registry.
    Stores document metadata in a dedicated OpenSearch index.
    """
    
    def __init__(self, registry_path: str = None):
        """
        Initialize OpenSearch registry.
        
        Args:
            registry_path: Ignored, kept for backward compatibility.
        """
        self.index_name = ARISConfig.DOCUMENT_REGISTRY_INDEX
        self.client = self._initialize_client()
        self._ensure_index_exists()
        
    def _initialize_client(self) -> OpenSearch:
        """Initialize OpenSearch client."""
        host = ARISConfig.AWS_OPENSEARCH_DOMAIN
        region = ARISConfig.AWS_OPENSEARCH_REGION
        
        if not host:
            raise ValueError("AWS_OPENSEARCH_DOMAIN not configured")
            
        credentials = Session().get_credentials()

        # If host doesn't look like a URL (no dots), assume it's a domain name and resolve it
        if '.' not in host and 'localhost' not in host:
            try:
                opensearch_client = boto3.client(
                    'opensearch',
                    region_name=region,
                    aws_access_key_id=ARISConfig.AWS_OPENSEARCH_ACCESS_KEY_ID,
                    aws_secret_access_key=ARISConfig.AWS_OPENSEARCH_SECRET_ACCESS_KEY
                )
                response = opensearch_client.describe_domain(DomainName=host)
                host = response['DomainStatus']['Endpoint']
                logger.info(f"Resolved OpenSearch domain '{ARISConfig.AWS_OPENSEARCH_DOMAIN}' to endpoint: {host}")
            except Exception as e:
                logger.warning(f"Failed to resolve OpenSearch domain '{host}': {e}. Using as-is.")

        # Clean host URL
        if host.startswith('https://'):
            host = host.replace('https://', '')
        elif host.startswith('http://'):
            host = host.replace('http://', '')
        
        # Use boto3 credentials if available
        if credentials:
            auth = AWSV4SignerAuth(credentials, region, 'es')
        else:
            # Fallback to manual credentials from config
            try:
                from requests_aws4auth import AWS4Auth
                if ARISConfig.AWS_OPENSEARCH_ACCESS_KEY_ID and ARISConfig.AWS_OPENSEARCH_SECRET_ACCESS_KEY:
                    auth = AWS4Auth(
                        ARISConfig.AWS_OPENSEARCH_ACCESS_KEY_ID,
                        ARISConfig.AWS_OPENSEARCH_SECRET_ACCESS_KEY,
                        region,
                        'es'
                    )
                else:
                    logger.warning("No OpenSearch credentials found (env vars or ~/.aws/credentials)")
                    auth = None
            except ImportError:
                logger.warning("requests_aws4auth not installed, trying unauthenticated (likely to fail)")
                auth = None

        return OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )

    def _ensure_index_exists(self):
        """Create registry index if it doesn't exist."""
        try:
            if not self.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "document_id": {"type": "keyword"},
                            "document_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                            "status": {"type": "keyword"},
                            "created_at": {"type": "date"},
                            "updated_at": {"type": "date"},
                            "file_hash": {"type": "keyword"},
                            "parser_used": {"type": "keyword"},
                            "metadata": {"type": "object", "dynamic": True}
                        }
                    }
                }
                self.client.indices.create(index=self.index_name, body=mapping)
                logger.info(f"Created registry index: {self.index_name}")
        except Exception as e:
            logger.error(f"Error checking/creating registry index: {e}")

    def add_document(self, document_id: str, metadata: Dict):
        """Add or update document metadata."""
        try:
            # Ensure document_id is in the metadata
            metadata['document_id'] = document_id
            
            # Add timestamps
            if 'created_at' not in metadata:
                # Check if exists to preserve created_at
                existing = self.get_document(document_id)
                if existing and 'created_at' in existing:
                    metadata['created_at'] = existing['created_at']
                else:
                    metadata['created_at'] = datetime.now().isoformat()
            
            metadata['updated_at'] = datetime.now().isoformat()
            
            # Version tracking (simplified)
            if 'version_info' not in metadata:
                metadata['version_info'] = {'version': 1}
            else:
                current_ver = metadata['version_info'].get('version', 1)
                metadata['version_info']['version'] = current_ver + 1

            self.client.index(
                index=self.index_name,
                id=document_id,
                body=metadata,
                refresh=True  # Ensure immediate consistency
            )
            logger.info(f"Added/Updated document {document_id} in registry")
        except Exception as e:
            logger.error(f"Failed to add document {document_id}: {e}")
            raise

    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata by ID."""
        try:
            response = self.client.get(index=self.index_name, id=document_id)
            return response['_source']
        except NotFoundError as e:
            logger.debug(f"get_document: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None

    def list_documents(self) -> List[Dict]:
        """List all documents."""
        try:
            # Search all using scan/scroll or high limit
            # For registry, 10000 is a safe reasonable limit for now
            response = self.client.search(
                index=self.index_name,
                body={"query": {"match_all": {}}, "size": 1000}
            )
            return [hit['_source'] for hit in response['hits']['hits']]
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def remove_document(self, document_id: str) -> bool:
        """Remove document from registry."""
        try:
            self.client.delete(index=self.index_name, id=document_id, refresh=True)
            logger.info(f"Removed document {document_id} from registry")
            return True
        except NotFoundError as e:
            logger.warning(f"remove_document: {type(e).__name__}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error removing document {document_id}: {e}")
            return False

    def find_duplicate(self, document_name: str, file_hash: Optional[str] = None) -> Optional[Dict]:
        """Find existing document by name or hash."""
        try:
            should_clauses = [{"term": {"document_name.keyword": document_name}}]
            if file_hash:
                should_clauses.append({"term": {"file_hash": file_hash}})
            
            query = {
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1
                    }
                },
                "size": 1
            }
            response = self.client.search(index=self.index_name, body=query)
            hits = response['hits']['hits']
            if hits:
                return hits[0]['_source']
            return None
        except Exception as e:
            logger.error(f"Error finding duplicate: {e}")
            return None

    def find_documents_by_name(self, document_name: str) -> List[Dict]:
        """Find all documents with a given name."""
        try:
            query = {
                "query": {
                    "term": {"document_name.keyword": document_name}
                }
            }
            response = self.client.search(index=self.index_name, body=query)
            return [hit['_source'] for hit in response['hits']['hits']]
        except Exception as e:
            logger.error(f"Error finding documents by name: {e}")
            return []

    def find_document_by_name_and_parser(self, document_name: str, parser_used: str) -> Optional[Dict]:
        """Find document by name and parser."""
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"document_name.keyword": document_name}},
                            {"term": {"parser_used": parser_used}}
                        ]
                    }
                },
                "size": 1
            }
            response = self.client.search(index=self.index_name, body=query)
            hits = response['hits']['hits']
            if hits:
                return hits[0]['_source']
            return None
        except Exception as e:
            logger.error(f"Error finding document by name/parser: {e}")
            return None

    def mark_for_reindex(self, document_id: str) -> bool:
        """Mark document for re-indexing."""
        try:
            doc = self.get_document(document_id)
            if doc:
                doc['status'] = 'pending_reindex'
                self.add_document(document_id, doc)
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking for reindex: {e}")
            return False

    def clear_all(self):
        """Clear all documents from registry (Dangerous)."""
        try:
            self.client.delete_by_query(
                index=self.index_name,
                body={"query": {"match_all": {}}},
                refresh=True
            )
            logger.info("Cleared all documents from registry")
        except Exception as e:
            logger.error(f"Error clearing registry: {e}")

    # --- Backward Compatibility Methods (No-ops or simple wrappers) ---

    def _ensure_directory(self):
        pass

    def _sync_from_s3(self):
        pass  # Data is in OpenSearch, no file sync needed

    def _sync_to_s3(self):
        pass  # Data is persisted in OpenSearch

    def get_sync_status(self) -> Dict:
        """Get simplified sync status."""
        try:
            count = self.client.count(index=self.index_name)['count']
            return {
                'total_documents': count,
                'backend': 'opensearch',
                'index': self.index_name
            }
        except Exception as e:
            logger.debug(f"get_sync_status: {type(e).__name__}: {e}")
            return {'status': 'error', 'backend': 'opensearch'}

    def check_for_conflicts(self) -> Optional[Dict]:
        return None  # No file conflicts in DB

    def reload_from_disk(self) -> bool:
        return True  # Always fresh from DB

    def get_document_versions(self, document_id: str) -> List[Dict]:
        doc = self.get_document(document_id)
        return [doc] if doc else []

    def add_document_version(self, document_id: str, metadata: Dict):
        self.add_document(document_id, metadata)

