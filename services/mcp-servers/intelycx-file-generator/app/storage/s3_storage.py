"""S3 storage implementation."""

import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import BaseStorage, StorageResult

logger = logging.getLogger(__name__)


class S3Storage(BaseStorage):
    """S3 implementation of storage interface."""
    
    def __init__(self, bucket_name: str, region: str = "us-east-2"):
        """
        Initialize S3 storage.
        
        Args:
            bucket_name: S3 bucket name for file storage
            region: AWS region for S3 operations
        """
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            self.s3_client = boto3.client('s3', region_name=region)
            logger.info(f"🪣 S3Storage initialized: bucket={bucket_name}, region={region}")
        except NoCredentialsError:
            logger.error("❌ AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {str(e)}")
            raise
    
    async def upload_file(
        self, 
        file_content: bytes, 
        chat_id: str, 
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> StorageResult:
        """Upload file to S3."""
        file_path = self._construct_file_path(chat_id, filename)
        
        try:
            logger.info(f"📤 Uploading file to S3: s3://{self.bucket_name}/{file_path}")
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
                ServerSideEncryption='AES256'  # Enable encryption
            )
            
            # Construct file URL
            file_url = f"s3://{self.bucket_name}/{file_path}"
            file_size = len(file_content)
            
            logger.info(f"✅ File uploaded successfully: {file_url} ({file_size} bytes)")
            
            return StorageResult(
                success=True,
                file_url=file_url,
                file_path=file_path,
                file_size=file_size
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = f"S3 upload failed ({error_code}): {str(e)}"
            logger.error(f"❌ {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message
            )
        except Exception as e:
            error_message = f"Unexpected error during S3 upload: {str(e)}"
            logger.error(f"❌ {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message
            )
    
    async def delete_file(self, chat_id: str, filename: str) -> StorageResult:
        """Delete file from S3."""
        file_path = self._construct_file_path(chat_id, filename)
        
        try:
            logger.info(f"🗑️ Deleting file from S3: s3://{self.bucket_name}/{file_path}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            
            logger.info(f"✅ File deleted successfully: {file_path}")
            
            return StorageResult(
                success=True,
                file_path=file_path
            )
            
        except ClientError as e:
            error_message = f"S3 delete failed: {str(e)}"
            logger.error(f"❌ {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message
            )
    
    async def get_file_url(
        self, 
        chat_id: str, 
        filename: str, 
        expiry_seconds: int = 3600
    ) -> StorageResult:
        """Generate signed URL for S3 file access."""
        file_path = self._construct_file_path(chat_id, filename)
        
        try:
            logger.info(f"🔗 Generating signed URL for: s3://{self.bucket_name}/{file_path}")
            
            # Generate presigned URL
            signed_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_path},
                ExpiresIn=expiry_seconds
            )
            
            logger.info(f"✅ Signed URL generated (expires in {expiry_seconds}s)")
            
            return StorageResult(
                success=True,
                file_url=signed_url,
                file_path=file_path
            )
            
        except ClientError as e:
            error_message = f"Failed to generate signed URL: {str(e)}"
            logger.error(f"❌ {error_message}")
            
            return StorageResult(
                success=False,
                error_message=error_message
            )
