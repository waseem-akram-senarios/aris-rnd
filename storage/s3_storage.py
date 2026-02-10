"""
S3 Document Storage Service for ARIS RAG System.
Handles document upload, download, and management in AWS S3.
"""
import os
import boto3
import logging
from botocore.exceptions import ClientError
from typing import Optional, Dict, List, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class S3DocumentStorage:
    """
    S3-based document storage for ARIS RAG system.
    
    Uses existing AWS credentials from environment:
    - AWS_OPENSEARCH_ACCESS_KEY_ID
    - AWS_OPENSEARCH_SECRET_ACCESS_KEY
    - AWS_OPENSEARCH_REGION
    """
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        prefix: str = "aris-documents/"
    ):
        """
        Initialize S3 storage service.
        
        Args:
            bucket_name: S3 bucket name (default from env S3_BUCKET_NAME)
            region: AWS region (default from env AWS_OPENSEARCH_REGION)
            prefix: S3 key prefix for documents
        """
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME', 'intelycx-waseem-s3-bucket')
        self.region = region or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        self.prefix = prefix
        
        # Initialize S3 client with credentials
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'),
            region_name=self.region
        )
        
        logger.info(f"S3DocumentStorage initialized: bucket={self.bucket_name}, region={self.region}")
    
    def _get_document_key(self, document_id: str, filename: str) -> str:
        """Generate S3 key for a document."""
        return f"{self.prefix}{document_id}/{filename}"
    
    def _get_metadata_key(self, document_id: str) -> str:
        """Generate S3 key for document metadata."""
        return f"{self.prefix}{document_id}/metadata.json"
    
    def upload_document(
        self,
        file_content: bytes,
        document_id: str,
        filename: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a document to S3.
        
        Args:
            file_content: Binary file content
            document_id: Unique document identifier
            filename: Original filename
            content_type: MIME type
            metadata: Additional metadata to store
            
        Returns:
            Dict with s3_key, s3_url, bucket info
        """
        s3_key = self._get_document_key(document_id, filename)
        
        # Prepare S3 metadata (must be string values)
        s3_metadata = {
            'document-id': document_id,
            'original-filename': filename,
            'upload-timestamp': datetime.utcnow().isoformat(),
            'source': 'ARIS-RAG-System'
        }
        if metadata:
            for k, v in metadata.items():
                s3_metadata[k.replace('_', '-')] = str(v)
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type,
                Metadata=s3_metadata
            )
            
            s3_url = f"s3://{self.bucket_name}/{s3_key}"
            https_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            
            logger.info(f"Document uploaded to S3: {s3_key}")
            
            return {
                'success': True,
                'document_id': document_id,
                's3_key': s3_key,
                's3_url': s3_url,
                'https_url': https_url,
                'bucket': self.bucket_name,
                'region': self.region,
                'size_bytes': len(file_content)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            logger.error(f"S3 upload failed: {error_code} - {error_msg}")
            return {
                'success': False,
                'error': f"{error_code}: {error_msg}",
                'document_id': document_id
            }
        except Exception as e:
            logger.error(f"S3 upload error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'document_id': document_id
            }
    
    def download_document(self, document_id: str, filename: str) -> Optional[bytes]:
        """
        Download a document from S3.
        
        Args:
            document_id: Document identifier
            filename: Filename to download
            
        Returns:
            File content as bytes, or None if not found
        """
        s3_key = self._get_document_key(document_id, filename)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            content = response['Body'].read()
            logger.info(f"Document downloaded from S3: {s3_key}")
            return content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning(f"Document not found in S3: {s3_key}")
            else:
                logger.error(f"S3 download failed: {error_code}")
            return None
        except Exception as e:
            logger.error(f"S3 download error: {str(e)}")
            return None
    
    def get_document_url(self, document_id: str, filename: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for document download.
        
        Args:
            document_id: Document identifier
            filename: Filename
            expires_in: URL expiration in seconds (default 1 hour)
            
        Returns:
            Presigned URL or None if error
        """
        s3_key = self._get_document_key(document_id, filename)
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
    
    def delete_document(self, document_id: str, filename: Optional[str] = None) -> bool:
        """
        Delete a document from S3.
        
        Args:
            document_id: Document identifier
            filename: Specific file to delete, or None to delete all files for document
            
        Returns:
            True if successful
        """
        try:
            if filename:
                # Delete specific file
                s3_key = self._get_document_key(document_id, filename)
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                logger.info(f"Deleted from S3: {s3_key}")
            else:
                # Delete all files for this document
                prefix = f"{self.prefix}{document_id}/"
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix
                )
                
                if 'Contents' in response:
                    for obj in response['Contents']:
                        self.s3_client.delete_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        logger.info(f"Deleted from S3: {obj['Key']}")
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"S3 delete permission denied. IAM user needs s3:DeleteObject and s3:ListObjectsV2 permissions on bucket '{self.bucket_name}'")
            else:
                logger.error(f"S3 delete failed: {error_code} - {e}")
            return False
        except Exception as e:
            logger.error(f"S3 delete error: {str(e)}")
            return False
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents in S3 storage.
        
        Returns:
            List of document info dicts (empty list if permission denied or error)
        """
        documents = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    key = obj['Key']
                    # Skip metadata files
                    if key.endswith('metadata.json'):
                        continue
                    
                    # Extract document_id from key
                    parts = key.replace(self.prefix, '').split('/')
                    if len(parts) >= 2:
                        doc_id = parts[0]
                        filename = parts[1]
                        
                        documents.append({
                            'document_id': doc_id,
                            'filename': filename,
                            's3_key': key,
                            'size_bytes': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat()
                        })
            
            logger.info(f"Listed {len(documents)} documents from S3")
            return documents
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"S3 list permission denied. IAM user needs s3:ListObjectsV2 permission on bucket '{self.bucket_name}'. Using local registry instead.")
            else:
                logger.error(f"S3 list failed: {error_code} - {e}")
            return []
        except Exception as e:
            logger.error(f"S3 list error: {str(e)}")
            return []
    
    def document_exists(self, document_id: str, filename: str) -> bool:
        """Check if a document exists in S3."""
        s3_key = self._get_document_key(document_id, filename)
        
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.debug(f"document_exists: {type(e).__name__}: {e}")
            return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get S3 storage configuration info."""
        return {
            'bucket': self.bucket_name,
            'region': self.region,
            'prefix': self.prefix,
            'enabled': True,
            's3_url_base': f"s3://{self.bucket_name}/{self.prefix}"
        }


# Singleton instance
_s3_storage: Optional[S3DocumentStorage] = None


def get_s3_storage() -> S3DocumentStorage:
    """Get or create S3 storage singleton."""
    global _s3_storage
    if _s3_storage is None:
        _s3_storage = S3DocumentStorage()
    return _s3_storage
