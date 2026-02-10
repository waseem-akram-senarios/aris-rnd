#!/usr/bin/env python3
"""
Migration script to move Document Registry from JSON file to OpenSearch.
Reads existing 'storage/document_registry.json' and indexes documents into 'aris-registry-metadata'.
"""
import os
import sys
import json
import logging
import time
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config.settings import ARISConfig
from boto3 import Session
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_opensearch_client():
    """Initialize OpenSearch client using settings."""
    host = ARISConfig.AWS_OPENSEARCH_DOMAIN
    region = ARISConfig.AWS_OPENSEARCH_REGION
    
    if not host:
        logger.error("AWS_OPENSEARCH_DOMAIN not set in configuration")
        sys.exit(1)
        
    # Remove protocol if present for host setting (boto3 needs it clean, but opensearch-py needs clean host)
    if host.startswith('https://'):
        host = host.replace('https://', '')
    elif host.startswith('http://'):
        host = host.replace('http://', '')
    
    credentials = Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, 'es')
    
    # If credentials not found in session (e.g. from env vars), try manual config
    if not credentials:
        from requests_aws4auth import AWS4Auth
        auth = AWS4Auth(
            ARISConfig.AWS_OPENSEARCH_ACCESS_KEY_ID,
            ARISConfig.AWS_OPENSEARCH_SECRET_ACCESS_KEY,
            region,
            'es'
        )

    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client

def create_registry_index(client, index_name):
    """Create the registry index with appropriate mappings."""
    if client.indices.exists(index=index_name):
        logger.info(f"Index '{index_name}' already exists.")
        return

    # Define mapping optimize for metadata search
    mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1
            }
        },
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
    
    try:
        client.indices.create(index=index_name, body=mapping)
        logger.info(f"Created index '{index_name}'")
    except Exception as e:
        logger.error(f"Failed to create index: {e}")
        sys.exit(1)

def migrate_data():
    """Read JSON registry and push to OpenSearch."""
    json_path = "storage/document_registry.json"
    
    if not os.path.exists(json_path):
        logger.warning(f"Registry file not found at {json_path}. Nothing to migrate.")
        return

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read registry file: {e}")
        sys.exit(1)

    if not data:
        logger.info("Registry is empty. Nothing to migrate.")
        return

    logger.info(f"Found {len(data)} documents in registry file.")
    
    client = get_opensearch_client()
    index_name = ARISConfig.DOCUMENT_REGISTRY_INDEX
    
    # Ensure index exists
    create_registry_index(client, index_name)
    
    success_count = 0
    error_count = 0
    
    for doc_id, doc_data in data.items():
        try:
            # Ensure document_id is in the body
            if 'document_id' not in doc_data:
                doc_data['document_id'] = doc_id
            
            # Use document_id as the OpenSearch _id
            client.index(
                index=index_name,
                id=doc_id,
                body=doc_data,
                refresh=True
            )
            success_count += 1
            if success_count % 10 == 0:
                logger.info(f"Migrated {success_count} documents...")
                
        except Exception as e:
            logger.error(f"Failed to migrate document {doc_id}: {e}")
            error_count += 1
            
    logger.info(f"Migration complete. Success: {success_count}, Failed: {error_count}")

if __name__ == "__main__":
    logger.info("Starting registry migration to OpenSearch...")
    migrate_data()
