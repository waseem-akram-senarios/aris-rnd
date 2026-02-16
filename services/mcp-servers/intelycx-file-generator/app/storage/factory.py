"""Storage factory for creating storage instances based on configuration."""

import os
import logging
from typing import Optional

from .base import BaseStorage
from .s3_storage import S3Storage

logger = logging.getLogger(__name__)


class StorageFactory:
    """Factory for creating storage implementations."""
    
    @staticmethod
    def create_storage(
        storage_type: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None
    ) -> BaseStorage:
        """
        Create storage instance based on configuration.
        
        Args:
            storage_type: Storage driver type (default from STORAGE_DRIVER env var)
            bucket_name: S3 bucket name (default from S3_BUCKET_NAME env var)
            region: AWS region (default from AWS_REGION env var)
            
        Returns:
            BaseStorage implementation
            
        Raises:
            ValueError: If unsupported storage type or missing configuration
        """
        # Get configuration from environment or parameters
        storage_type = storage_type or os.getenv("STORAGE_DRIVER", "s3").lower()
        bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        region = region or os.getenv("AWS_REGION", "us-east-2")
        
        logger.info(f"🏗️ Creating storage instance: type={storage_type}")
        
        if storage_type == "s3":
            if not bucket_name:
                raise ValueError(
                    "S3 bucket name is required. Set S3_BUCKET_NAME environment variable "
                    "or pass bucket_name parameter."
                )
            
            return S3Storage(bucket_name=bucket_name, region=region)
        
        # Future storage implementations can be added here
        # elif storage_type == "ftp":
        #     return FTPStorage(...)
        # elif storage_type == "local":
        #     return LocalStorage(...)
        
        else:
            supported_types = ["s3"]  # Add more as implemented
            raise ValueError(
                f"Unsupported storage type: {storage_type}. "
                f"Supported types: {', '.join(supported_types)}"
            )
