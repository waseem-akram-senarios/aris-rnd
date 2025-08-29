"""Email client for sending emails - simplified for FastMCP."""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

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


class EmailClient:
    """Email client for sending emails."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def send_email(
        self,
        to: Union[str, List[str], List[Dict[str, str]]],
        subject: str,
        body: str,
        cc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
        bcc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
        is_html: bool = False,
        attachments: Optional[List[EmailAttachment]] = None
    ) -> Dict[str, Any]:
        """
        Send an email with flexible recipient formats.
        
        Args:
            to: Recipients - can be string, list of strings, or list of dicts with email/name
            subject: Email subject
            body: Email body content
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            is_html: Whether body is HTML format
            attachments: Email attachments (optional)
            
        Returns:
            Dict with send status and message ID
        """
        # Normalize recipients
        to_recipients = self._normalize_recipients(to)
        cc_recipients = self._normalize_recipients(cc) if cc else None
        bcc_recipients = self._normalize_recipients(bcc) if bcc else None
        
        # Log the email details instead of actually sending
        logger.info("📧 EMAIL SEND REQUEST:")
        logger.info(f"  📬 To: {[self._format_recipient(r) for r in to_recipients]}")
        
        if cc_recipients:
            logger.info(f"  📋 CC: {[self._format_recipient(r) for r in cc_recipients]}")
            
        if bcc_recipients:
            logger.info(f"  🔒 BCC: {[self._format_recipient(r) for r in bcc_recipients]}")
            
        logger.info(f"  📝 Subject: {subject}")
        logger.info(f"  📄 Body Type: {'HTML' if is_html else 'Plain Text'}")
        logger.info(f"  📎 Attachments: {len(attachments) if attachments else 0}")
        
        # Log body content (truncated for readability)
        body_preview = body[:200] + "..." if len(body) > 200 else body
        logger.info(f"  💬 Body Preview: {body_preview}")
        
        if attachments:
            for i, attachment in enumerate(attachments):
                logger.info(f"  📎 Attachment {i+1}: {attachment.filename} ({attachment.content_type}, {len(attachment.content)} bytes)")
        
        # Return success response (simulated)
        message_id = str(uuid.uuid4())
        
        logger.info(f"  ✅ Email logged successfully with ID: {message_id}")
        
        return {
            "success": True,
            "message_id": message_id,
            "status": "logged",
            "recipients_count": len(to_recipients),
            "cc_count": len(cc_recipients) if cc_recipients else 0,
            "bcc_count": len(bcc_recipients) if bcc_recipients else 0,
            "timestamp": "2024-08-26T00:00:00Z"  # Would be actual timestamp in real implementation
        }
    
    def _normalize_recipients(self, recipients: Union[str, List[str], List[Dict[str, str]]]) -> List[EmailRecipient]:
        """Normalize various recipient formats to EmailRecipient objects."""
        if not recipients:
            return []
        
        if isinstance(recipients, str):
            return [EmailRecipient(email=recipients)]
        
        result = []
        for recipient in recipients:
            if isinstance(recipient, str):
                result.append(EmailRecipient(email=recipient))
            elif isinstance(recipient, dict):
                result.append(EmailRecipient(
                    email=recipient.get("email", ""),
                    name=recipient.get("name")
                ))
        
        return result
    
    def _format_recipient(self, recipient: EmailRecipient) -> str:
        """Format recipient for logging."""
        if recipient.name:
            return f"{recipient.name} <{recipient.email}>"
        return recipient.email
