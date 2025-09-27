"""Configuration management for intelycx-rag MCP server."""

import os
from typing import Optional


# Simple configuration using environment variables (matching other MCP servers)
class Settings:
    """Application settings with environment variable support."""
    
    def __init__(self):
        # Server configuration
        self.host = os.environ.get("HOST", "0.0.0.0")
        self.port = int(os.environ.get("PORT", "8082"))
        self.debug = os.environ.get("DEBUG", "false").lower() == "true"
        
        # AWS Configuration
        self.aws_region = os.environ.get("AWS_REGION", "us-east-2")
        self.aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        
        # Bedrock Configuration
        self.bedrock_region = os.environ.get("BEDROCK_REGION", "us-east-2")
        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
        self.embedding_dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", "1536"))
        
        # OpenSearch Configuration
        self.opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "https://localhost:9200")
        self.opensearch_username = os.environ.get("OPENSEARCH_USERNAME")
        self.opensearch_password = os.environ.get("OPENSEARCH_PASSWORD")
        self.opensearch_use_ssl = os.environ.get("OPENSEARCH_USE_SSL", "true").lower() == "true"
        self.opensearch_verify_certs = os.environ.get("OPENSEARCH_VERIFY_CERTS", "true").lower() == "true"
        
        # S3 Configuration
        self.s3_document_bucket = os.environ.get("S3_DOCUMENT_BUCKET", "iris-batch-001-data-975049910508")
        self.s3_document_prefix = os.environ.get("S3_DOCUMENT_PREFIX", "knowledge-base/")
        
        # Database Configuration
        self.database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://aris:aris_dev_password_2024@aris-postgres:5432/aris_agent")
        
        # Knowledge Base Configuration
        self.knowledge_index_name = os.environ.get("KNOWLEDGE_INDEX_NAME", "manufacturing-knowledge")
        self.default_domain = os.environ.get("DEFAULT_DOMAIN", "manufacturing")
        
        # Chunking Configuration
        self.chunk_target_size = int(os.environ.get("CHUNK_TARGET_SIZE", "1000"))
        self.chunk_max_size = int(os.environ.get("CHUNK_MAX_SIZE", "1500"))
        self.chunk_overlap = int(os.environ.get("CHUNK_OVERLAP", "200"))
        
        # Search Configuration
        self.default_search_limit = int(os.environ.get("DEFAULT_SEARCH_LIMIT", "5"))
        self.similarity_threshold = float(os.environ.get("SIMILARITY_THRESHOLD", "0.7"))
        
        # MCP Configuration
        self.mcp_api_key = os.environ.get("MCP_API_KEY", "mcp-dev-key-12345")


# Global settings instance
settings = Settings()
