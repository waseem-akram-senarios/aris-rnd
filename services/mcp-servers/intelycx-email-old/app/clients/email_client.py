from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmailRecipient:
    """Email recipient information."""
    email: str
    name: Optional[str] = None


@dataclass
class EmailAttachment:
    """Email attachment information."""
    filename: str
    content_type: str
    content: bytes


@dataclass
class EmailMessage:
    """Email message structure."""
    to: List[EmailRecipient]
    subject: str
    body: str
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None
    attachments: Optional[List[EmailAttachment]] = None
    is_html: bool = False


@dataclass
class EmailClient:
    """Email client for sending emails."""
    smtp_host: str
    smtp_port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True

    async def send_email(self, message: EmailMessage) -> Dict[str, Any]:
        """
        Send an email message (dummy implementation - just logs).
        
        Args:
            message: EmailMessage object containing email details
            
        Returns:
            Dict with send status and message ID
        """
        # Log the email details instead of actually sending
        logger.info("📧 EMAIL SEND REQUEST:")
        logger.info(f"  📬 To: {[f'{r.name} <{r.email}>' if r.name else r.email for r in message.to]}")
        
        if message.cc:
            logger.info(f"  📋 CC: {[f'{r.name} <{r.email}>' if r.name else r.email for r in message.cc]}")
            
        if message.bcc:
            logger.info(f"  🔒 BCC: {[f'{r.name} <{r.email}>' if r.name else r.email for r in message.bcc]}")
            
        logger.info(f"  📝 Subject: {message.subject}")
        logger.info(f"  📄 Body Type: {'HTML' if message.is_html else 'Plain Text'}")
        logger.info(f"  📎 Attachments: {len(message.attachments) if message.attachments else 0}")
        
        # Log body content (truncated for readability)
        body_preview = message.body[:200] + "..." if len(message.body) > 200 else message.body
        logger.info(f"  💬 Body Preview: {body_preview}")
        
        if message.attachments:
            for i, attachment in enumerate(message.attachments):
                logger.info(f"  📎 Attachment {i+1}: {attachment.filename} ({attachment.content_type}, {len(attachment.content)} bytes)")
        
        # Return success response (simulated)
        import uuid
        message_id = str(uuid.uuid4())
        
        logger.info(f"  ✅ Email logged successfully with ID: {message_id}")
        
        return {
            "success": True,
            "message_id": message_id,
            "status": "logged",
            "recipients_count": len(message.to),
            "timestamp": "2024-08-26T00:00:00Z"  # Would be actual timestamp in real implementation
        }
    
    async def send_simple_email(
        self, 
        to_email: str, 
        subject: str, 
        body: str,
        to_name: Optional[str] = None,
        is_html: bool = False
    ) -> Dict[str, Any]:
        """
        Send a simple email with minimal parameters.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            to_name: Optional recipient name
            is_html: Whether body is HTML format
            
        Returns:
            Dict with send status and message ID
        """
        recipient = EmailRecipient(email=to_email, name=to_name)
        message = EmailMessage(
            to=[recipient],
            subject=subject,
            body=body,
            is_html=is_html
        )
        
        return await self.send_email(message)
