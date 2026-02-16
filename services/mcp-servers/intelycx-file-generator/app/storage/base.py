"""Base storage interface for file operations."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StorageResult:
    """Result of a storage operation."""
    success: bool
    file_url: Optional[str] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    file_size: Optional[int] = None


class BaseStorage(ABC):
    """Abstract base class for storage implementations."""
    
    @abstractmethod
    async def upload_file(
        self, 
        file_content: bytes, 
        chat_id: str, 
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> StorageResult:
        """
        Upload file content to storage.
        
        Args:
            file_content: The file content as bytes
            chat_id: Chat ID for organizing files
            filename: Name of the file
            content_type: MIME type of the file
            
        Returns:
            StorageResult with upload details
        """
        pass
    
    @abstractmethod
    async def delete_file(self, chat_id: str, filename: str) -> StorageResult:
        """
        Delete a file from storage.
        
        Args:
            chat_id: Chat ID where file is stored
            filename: Name of the file to delete
            
        Returns:
            StorageResult indicating success/failure
        """
        pass
    
    @abstractmethod
    async def get_file_url(
        self, 
        chat_id: str, 
        filename: str, 
        expiry_seconds: int = 3600
    ) -> StorageResult:
        """
        Get a signed URL for file access.
        
        Args:
            chat_id: Chat ID where file is stored
            filename: Name of the file
            expiry_seconds: URL expiry time in seconds
            
        Returns:
            StorageResult with signed URL
        """
        pass
    
    def _construct_file_path(self, chat_id: str, filename: str) -> str:
        """Construct the standard file path: /chats/{chat_id}/{filename}"""
        return f"chats/{chat_id}/{filename}"
