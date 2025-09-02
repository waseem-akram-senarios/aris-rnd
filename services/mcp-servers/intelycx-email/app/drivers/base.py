"""Base email driver interface and models."""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class EmailAttachment:
    """Email attachment model."""
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    
    @classmethod
    def from_file(cls, file_path: str, filename: Optional[str] = None, content_type: Optional[str] = None) -> "EmailAttachment":
        """Create attachment from file path."""
        if filename is None:
            filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        if content_type is None:
            # Simple content type detection
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.pdf': 'application/pdf',
                '.txt': 'text/plain',
                '.html': 'text/html',
                '.json': 'application/json',
                '.csv': 'text/csv',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.zip': 'application/zip',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            }
            content_type = content_type_map.get(ext, "application/octet-stream")
        
        return cls(filename=filename, content=content, content_type=content_type)


@dataclass
class EmailRecipient:
    """Email recipient model."""
    email: str
    name: Optional[str] = None
    
    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass
class EmailMessage:
    """Complete email message model."""
    to: List[EmailRecipient]
    subject: str
    body: str
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None
    reply_to: Optional[str] = None
    is_html: bool = False
    priority: EmailPriority = EmailPriority.NORMAL
    attachments: Optional[List[EmailAttachment]] = None
    headers: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """Initialize optional fields."""
        if self.cc is None:
            self.cc = []
        if self.bcc is None:
            self.bcc = []
        if self.attachments is None:
            self.attachments = []
        if self.headers is None:
            self.headers = {}
    
    @property
    def all_recipients(self) -> List[EmailRecipient]:
        """Get all recipients (to + cc + bcc)."""
        return self.to + self.cc + self.bcc
    
    @property
    def recipient_count(self) -> int:
        """Total number of recipients."""
        return len(self.to) + len(self.cc) + len(self.bcc)


@dataclass
class EmailResult:
    """Email sending result."""
    success: bool
    message_id: Optional[str] = None
    recipients_count: int = 0
    cc_count: int = 0
    bcc_count: int = 0
    status: str = ""
    error: Optional[str] = None
    sent_at: Optional[datetime] = None
    size_kb: Optional[float] = None
    driver_used: str = ""
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set default values."""
        if self.sent_at is None:
            self.sent_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class BaseEmailDriver(ABC):
    """Abstract base class for email drivers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize driver with configuration."""
        self.config = config
        self.driver_name = self.__class__.__name__.replace("Driver", "").lower()
    
    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailResult:
        """Send an email message."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the driver can connect and send emails."""
        pass
    
    def _normalize_recipients(self, recipients: Union[str, List[str], List[Dict[str, str]]]) -> List[EmailRecipient]:
        """Normalize recipients to EmailRecipient objects."""
        if isinstance(recipients, str):
            return [EmailRecipient(email=recipients)]
        
        result = []
        for recipient in recipients:
            if isinstance(recipient, str):
                result.append(EmailRecipient(email=recipient))
            elif isinstance(recipient, dict):
                result.append(EmailRecipient(
                    email=recipient["email"],
                    name=recipient.get("name")
                ))
            else:
                result.append(EmailRecipient(email=str(recipient)))
        
        return result
    
    def _calculate_size(self, message: EmailMessage) -> float:
        """Calculate approximate email size in KB."""
        size = len(message.subject) + len(message.body)
        
        # Add recipient sizes
        for recipient in message.all_recipients:
            size += len(str(recipient))
        
        # Add attachment sizes
        for attachment in message.attachments:
            size += len(attachment.content)
        
        return round(size / 1024, 2)
    
    def _create_message_id(self) -> str:
        """Generate a unique message ID."""
        import uuid
        return f"{uuid.uuid4()}@{self.driver_name}"
