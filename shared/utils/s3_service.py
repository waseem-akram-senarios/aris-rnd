"""
AWS S3 service for document storage and registry synchronization.
"""
import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class S3Service:
    """Service for interacting with AWS S3."""
    
    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize S3 service.
        
        Args:
            bucket_name: Name of the S3 bucket to use (defaults to ARISConfig.AWS_S3_BUCKET)
        """
        self.bucket_name = bucket_name or ARISConfig.AWS_S3_BUCKET
        self.enabled = ARISConfig.ENABLE_S3_STORAGE
        
        # Get credentials from environment (standard or OpenSearch-prefixed)
        self.access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = ARISConfig.AWS_OPENSEARCH_REGION or os.getenv('AWS_REGION', 'us-east-2')
        
        self.client = None
        if self.enabled:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize boto3 S3 client."""
        try:
            self.client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            logger.info(f"✅ S3 service initialized for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {str(e)}")
            self.enabled = False
    
    def upload_file(self, local_path: Union[str, Path], s3_key: str, content_type: Optional[str] = None) -> bool:
        """
        Upload a file to S3.
        
        Args:
            local_path: Path to local file
            s3_key: Key (path) in S3
            content_type: Optional MIME type
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            self.client.upload_file(str(local_path), self.bucket_name, s3_key, ExtraArgs=extra_args)
            logger.info(f"✅ Uploaded {local_path} to s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"❌ S3 upload failed: {str(e)}")
            return False

    def upload_bytes(self, content: bytes, s3_key: str, content_type: Optional[str] = None) -> bool:
        """
        Upload bytes directly to S3.
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
                
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                **extra_args
            )
            logger.info(f"✅ Uploaded bytes to s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"❌ S3 byte upload failed: {str(e)}")
            return False

    def download_file(self, s3_key: str, local_path: Union[str, Path]) -> bool:
        """
        Download a file from S3.
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.download_file(self.bucket_name, s3_key, str(local_path))
            logger.info(f"✅ Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"❌ S3 download failed: {str(e)}")
            return False

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"✅ Deleted s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"❌ S3 delete failed: {str(e)}")
            return False
    
    def delete_prefix(self, prefix: str) -> int:
        """
        Delete all objects with the given prefix from S3.
        Useful for deleting all files in a document folder.
        
        Args:
            prefix: S3 key prefix (e.g., 'documents/doc-123/')
            
        Returns:
            Number of objects deleted
        """
        if not self.enabled or not self.client:
            return 0
            
        try:
            # List all objects with the prefix
            paginator = self.client.get_paginator('list_objects_v2')
            deleted_count = 0
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                objects = page.get('Contents', [])
                if not objects:
                    continue
                
                # Delete objects in batches of 1000 (S3 limit)
                delete_keys = [{'Key': obj['Key']} for obj in objects]
                
                if delete_keys:
                    self.client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': delete_keys}
                    )
                    deleted_count += len(delete_keys)
                    logger.info(f"🗑️ Deleted {len(delete_keys)} objects with prefix: {prefix}")
            
            logger.info(f"✅ Total deleted: {deleted_count} objects with prefix s3://{self.bucket_name}/{prefix}")
            return deleted_count
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"⚠️ S3 permission denied for prefix '{prefix}'. IAM user needs s3:ListObjectsV2 and s3:DeleteObject permissions.")
            else:
                logger.error(f"❌ S3 delete_prefix failed for {prefix}: {error_code} - {str(e)}")
            return 0

    def get_public_url(self, s3_key: str) -> str:
        """Get the public URL for an S3 object (if bucket is public)."""
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

    def get_signed_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a pre-signed URL for an S3 object."""
        if not self.enabled or not self.client:
            return None
            
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.debug(f"get_signed_url: {type(e).__name__}: {e}")
            return None
