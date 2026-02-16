"""Log email driver for testing and development."""

import os
import logging
import json
from typing import Dict, Any
from datetime import datetime

from .base import BaseEmailDriver, EmailMessage, EmailResult


logger = logging.getLogger(__name__)


class LogDriver(BaseEmailDriver):
    """Log email driver that logs emails instead of sending them."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize log driver with configuration."""
        super().__init__(config)
        
        # Log configuration
        self.log_level = config.get("log_level", "INFO").upper()
        self.log_file = config.get("log_file", os.getenv("EMAIL_LOG_FILE"))
        self.include_body = config.get("include_body", True)
        self.include_attachments = config.get("include_attachments", True)
        self.pretty_print = config.get("pretty_print", True)
        
        # Set up file logging if specified
        if self.log_file:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
                
                # Create file handler
                file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                file_handler.setLevel(getattr(logging, self.log_level))
                
                # Create formatter
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(formatter)
                
                # Create separate logger for email logs
                self.email_logger = logging.getLogger(f"{__name__}.emails")
                self.email_logger.addHandler(file_handler)
                self.email_logger.setLevel(getattr(logging, self.log_level))
                
                logger.info(f"Email log driver configured to write to: {self.log_file}")
                
            except Exception as e:
                logger.error(f"Failed to configure email log file: {e}")
                self.email_logger = logger
        else:
            self.email_logger = logger
    
    async def send(self, message: EmailMessage) -> EmailResult:
        """Log email instead of sending it."""
        try:
            # Create comprehensive log entry
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "email_data": {
                    "from": f"{message.from_name} <{message.from_email}>" if message.from_name else message.from_email,
                    "to": [str(recipient) for recipient in message.to],
                    "cc": [str(recipient) for recipient in message.cc] if message.cc else [],
                    "bcc": [str(recipient) for recipient in message.bcc] if message.bcc else [],
                    "reply_to": message.reply_to,
                    "subject": message.subject,
                    "priority": message.priority.value,
                    "is_html": message.is_html,
                    "headers": message.headers,
                    "recipient_count": message.recipient_count,
                    "attachments_count": len(message.attachments)
                }
            }
            
            # Include body if configured
            if self.include_body:
                log_data["email_data"]["body"] = message.body
                log_data["email_data"]["body_length"] = len(message.body)
            
            # Include attachment details if configured
            if self.include_attachments and message.attachments:
                log_data["email_data"]["attachments"] = [
                    {
                        "filename": att.filename,
                        "content_type": att.content_type,
                        "size_bytes": len(att.content)
                    }
                    for att in message.attachments
                ]
            
            # Calculate email size
            email_size_kb = self._calculate_size(message)
            log_data["email_data"]["size_kb"] = email_size_kb
            
            # Generate message ID
            message_id = self._create_message_id()
            log_data["email_data"]["message_id"] = message_id
            
            # Format log message
            if self.pretty_print:
                log_message = f"""
📧 EMAIL LOGGED (not sent):
═══════════════════════════════════════════════════════════════
Message ID: {message_id}
From: {log_data['email_data']['from']}
To: {', '.join(log_data['email_data']['to'])}
{f"CC: {', '.join(log_data['email_data']['cc'])}" if log_data['email_data']['cc'] else ""}
{f"BCC: {', '.join(log_data['email_data']['bcc'])}" if log_data['email_data']['bcc'] else ""}
Subject: {message.subject}
Priority: {message.priority.value.upper()}
Format: {'HTML' if message.is_html else 'Plain Text'}
Size: {email_size_kb} KB
Attachments: {len(message.attachments)}
═══════════════════════════════════════════════════════════════
{f"Body ({len(message.body)} chars):" if self.include_body else "Body: [hidden]"}
{message.body if self.include_body else ""}
═══════════════════════════════════════════════════════════════
"""
            else:
                log_message = f"EMAIL LOGGED: {json.dumps(log_data, indent=2)}"
            
            # Log the email
            self.email_logger.info(log_message)
            
            # Also log a summary to the main logger
            logger.info(
                f"Email logged: {message.subject} -> "
                f"{len(message.to)} recipients, "
                f"{len(message.attachments)} attachments, "
                f"{email_size_kb} KB"
            )
            
            return EmailResult(
                success=True,
                message_id=message_id,
                recipients_count=len(message.to),
                cc_count=len(message.cc),
                bcc_count=len(message.bcc),
                status="logged_to_file" if self.log_file else "logged_to_console",
                sent_at=datetime.now(),
                size_kb=email_size_kb,
                driver_used="log",
                metadata={
                    "log_file": self.log_file,
                    "log_level": self.log_level,
                    "attachments_count": len(message.attachments),
                    "priority": message.priority.value,
                    "body_included": self.include_body,
                    "attachments_logged": self.include_attachments
                }
            )
            
        except Exception as e:
            logger.error(f"Error logging email: {e}")
            return EmailResult(
                success=False,
                error=f"Log driver error: {str(e)}",
                driver_used="log",
                metadata={"exception_type": type(e).__name__}
            )
    
    async def test_connection(self) -> bool:
        """Test log driver (always returns True)."""
        try:
            # Test logging capability
            test_message = f"Email log driver test at {datetime.now().isoformat()}"
            self.email_logger.info(test_message)
            logger.info("Log driver test successful")
            return True
        except Exception as e:
            logger.error(f"Log driver test failed: {e}")
            return False
