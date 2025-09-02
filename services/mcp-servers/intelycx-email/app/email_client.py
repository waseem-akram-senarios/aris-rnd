"""Enhanced email client with driver support - Laravel-style architecture."""

import os
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from .drivers import (
    BaseEmailDriver, 
    EmailMessage, 
    EmailAttachment, 
    EmailRecipient, 
    EmailResult,
    EmailPriority,
    EmailDriverFactory
)

logger = logging.getLogger(__name__)


class EmailClient:
    """Enhanced email client with pluggable driver support."""
    
    def __init__(
        self,
        driver_name: Optional[str] = None,
        driver_config: Optional[Dict[str, Any]] = None,
        # Legacy parameters for backward compatibility
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        """Initialize email client with driver support.
        
        Args:
            driver_name: Email driver to use ('ses', 'smtp', 'log'). Defaults to EMAIL_DRIVER env var.
            driver_config: Driver-specific configuration. If None, uses environment variables.
            
            # Legacy parameters (for backward compatibility):
            smtp_host, smtp_port, username, password, use_tls: SMTP configuration
        """
        # Handle legacy initialization (backward compatibility)
        if smtp_host and not driver_name:
            logger.info("Legacy SMTP configuration detected, using SMTP driver")
            driver_name = "smtp"
            if not driver_config:
                driver_config = {
                    "host": smtp_host,
                    "port": smtp_port,
                    "username": username,
                    "password": password,
                    "use_tls": use_tls,
                }
        
        # Create email driver
        self.driver: BaseEmailDriver = EmailDriverFactory.create_driver(driver_name, driver_config)
        
        logger.info(f"Email client initialized with {self.driver.driver_name} driver")

    async def send_email(
        self,
        to: Union[str, List[str], List[Dict[str, str]]],
        subject: str,
        body: str,
        cc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
        bcc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
        is_html: bool = False,
        priority: EmailPriority = EmailPriority.NORMAL,
        attachments: Optional[List[EmailAttachment]] = None,
        reply_to: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email using the configured driver.
        
        Args:
            to: Recipients - can be string, list of strings, or list of dicts with email/name
            subject: Email subject
            body: Email body content
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            is_html: Whether body is HTML format
            priority: Email priority level
            attachments: Email attachments (optional)
            reply_to: Reply-to address (optional)
            headers: Custom email headers (optional)
            
        Returns:
            Dict with send status and message details
        """
        try:
            # Create email message
            email_message = EmailMessage(
                to=self.driver._normalize_recipients(to),
                subject=subject,
                body=body,
                cc=self.driver._normalize_recipients(cc) if cc else [],
                bcc=self.driver._normalize_recipients(bcc) if bcc else [],
                is_html=is_html,
                priority=priority,
                attachments=attachments or [],
                reply_to=reply_to,
                headers=headers or {}
            )
            
            # Send via driver
            result: EmailResult = await self.driver.send(email_message)
            
            # Convert result to dict for backward compatibility
            return {
                "success": result.success,
                "message_id": result.message_id,
                "status": result.status,
                "recipients_count": result.recipients_count,
                "cc_count": result.cc_count,
                "bcc_count": result.bcc_count,
                "error": result.error,
                "sent_at": result.sent_at.isoformat() if result.sent_at else None,
                "size_kb": result.size_kb,
                "driver_used": result.driver_used,
                "metadata": result.metadata
            }
            
        except Exception as e:
            logger.error(f"Email client error: {e}")
            return {
                "success": False,
                "error": f"Email client error: {str(e)}",
                "driver_used": self.driver.driver_name,
                "timestamp": datetime.now().isoformat()
            }
    
    async def test_connection(self) -> bool:
        """Test the email driver connection."""
        return await self.driver.test_connection()
    
    def get_driver_info(self) -> Dict[str, Any]:
        """Get information about the current email driver."""
        return {
            "driver_name": self.driver.driver_name,
            "driver_class": self.driver.__class__.__name__,
            "config_keys": list(self.driver.config.keys())
        }
    
    # Utility methods for creating attachments
    @staticmethod
    def create_attachment_from_file(
        file_path: str, 
        filename: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> EmailAttachment:
        """Create an email attachment from a file."""
        return EmailAttachment.from_file(file_path, filename, content_type)
    
    @staticmethod
    def create_attachment_from_content(
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream"
    ) -> EmailAttachment:
        """Create an email attachment from content."""
        return EmailAttachment(
            filename=filename,
            content=content,
            content_type=content_type
        )
