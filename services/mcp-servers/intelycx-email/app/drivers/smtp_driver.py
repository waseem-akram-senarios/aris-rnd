"""SMTP email driver implementation."""

import os
import logging
import smtplib
import ssl
from typing import Dict, Any
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from .base import BaseEmailDriver, EmailMessage, EmailResult, EmailPriority


logger = logging.getLogger(__name__)


class SMTPDriver(BaseEmailDriver):
    """SMTP email driver for standard email servers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SMTP driver with configuration."""
        super().__init__(config)
        
        # SMTP configuration
        self.host = config.get("host", os.getenv("SMTP_HOST", "smtp.gmail.com"))
        self.port = config.get("port", int(os.getenv("SMTP_PORT", "587")))
        self.username = config.get("username", os.getenv("SMTP_USER"))
        self.password = config.get("password", os.getenv("SMTP_PASSWORD"))
        self.use_tls = config.get("use_tls", os.getenv("SMTP_USE_TLS", "true").lower() == "true")
        self.use_ssl = config.get("use_ssl", os.getenv("SMTP_USE_SSL", "false").lower() == "true")
        
        # Email defaults
        self.from_email = config.get("from_email", os.getenv("EMAIL_SENDER", self.username))
        self.from_name = config.get("from_name", os.getenv("EMAIL_SENDER_NAME", "Intelycx ARIS"))
        
        # Connection timeout
        self.timeout = config.get("timeout", int(os.getenv("SMTP_TIMEOUT", "30")))
        
        # Validate required configuration
        if not self.host:
            raise ValueError("SMTP driver requires 'host' configuration")
        if not self.username or not self.password:
            raise ValueError("SMTP driver requires 'username' and 'password' configuration")
        
        logger.info(f"SMTP driver initialized: {self.host}:{self.port} (TLS: {self.use_tls}, SSL: {self.use_ssl})")
    
    async def send(self, message: EmailMessage) -> EmailResult:
        """Send email using SMTP."""
        try:
            # Set default from address if not specified
            if not message.from_email:
                message.from_email = self.from_email
            if not message.from_name:
                message.from_name = self.from_name
            
            # Create MIME message
            msg = MIMEMultipart()
            msg['Subject'] = message.subject
            msg['From'] = f"{message.from_name} <{message.from_email}>" if message.from_name else message.from_email
            msg['To'] = ", ".join([str(recipient) for recipient in message.to])
            
            if message.cc:
                msg['Cc'] = ", ".join([str(recipient) for recipient in message.cc])
            
            if message.reply_to:
                msg['Reply-To'] = message.reply_to
            
            # Add priority headers
            if message.priority != EmailPriority.NORMAL:
                priority_map = {
                    EmailPriority.LOW: ("5", "Low"),
                    EmailPriority.HIGH: ("2", "High"),
                    EmailPriority.URGENT: ("1", "Urgent")
                }
                if message.priority in priority_map:
                    x_priority, importance = priority_map[message.priority]
                    msg['X-Priority'] = x_priority
                    msg['Importance'] = importance
            
            # Add custom headers
            for header_name, header_value in message.headers.items():
                msg[header_name] = header_value
            
            # Add message body
            if message.is_html:
                body_part = MIMEText(message.body, 'html', 'utf-8')
            else:
                body_part = MIMEText(message.body, 'plain', 'utf-8')
            msg.attach(body_part)
            
            # Add attachments
            for attachment in message.attachments:
                try:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.content)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment.filename}'
                    )
                    if attachment.content_type:
                        part.set_type(attachment.content_type)
                    msg.attach(part)
                    logger.debug(f"Added attachment: {attachment.filename} ({len(attachment.content)} bytes)")
                except Exception as e:
                    logger.error(f"Failed to attach file {attachment.filename}: {e}")
                    # Continue with other attachments
            
            # Collect all destination emails
            all_recipients = []
            for recipient in message.all_recipients:
                all_recipients.append(recipient.email)
            
            # Connect to SMTP server and send
            logger.info(f"Connecting to SMTP server: {self.host}:{self.port}")
            
            if self.use_ssl:
                # Use SSL from the start
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
            else:
                # Use regular connection, potentially with STARTTLS
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            try:
                # Authenticate
                if self.username and self.password:
                    logger.debug("Authenticating with SMTP server")
                    server.login(self.username, self.password)
                
                # Send email
                logger.info(f"Sending email to {len(all_recipients)} recipients")
                refused = server.send_message(msg, to_addrs=all_recipients)
                
                if refused:
                    logger.warning(f"Some recipients were refused: {refused}")
                
                # Generate message ID
                message_id = self._create_message_id()
                
                # Calculate email size
                email_size_kb = self._calculate_size(message)
                
                logger.info(f"Email sent successfully via SMTP. Recipients: {len(all_recipients) - len(refused)}")
                
                return EmailResult(
                    success=True,
                    message_id=message_id,
                    recipients_count=len(message.to),
                    cc_count=len(message.cc),
                    bcc_count=len(message.bcc),
                    status="sent_via_smtp",
                    sent_at=datetime.now(),
                    size_kb=email_size_kb,
                    driver_used="smtp",
                    metadata={
                        "smtp_host": self.host,
                        "smtp_port": self.port,
                        "refused_recipients": refused,
                        "attachments_count": len(message.attachments),
                        "priority": message.priority.value,
                        "use_tls": self.use_tls,
                        "use_ssl": self.use_ssl
                    }
                )
                
            finally:
                server.quit()
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return EmailResult(
                success=False,
                error=f"SMTP authentication failed: Invalid username or password",
                driver_used="smtp",
                metadata={"smtp_error_code": e.smtp_code, "smtp_error_message": str(e)}
            )
            
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused: {e}")
            return EmailResult(
                success=False,
                error=f"SMTP recipients refused: {e.recipients}",
                driver_used="smtp",
                metadata={"refused_recipients": e.recipients}
            )
            
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"SMTP server disconnected: {e}")
            return EmailResult(
                success=False,
                error="SMTP server disconnected unexpectedly",
                driver_used="smtp",
                metadata={"smtp_error": str(e)}
            )
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return EmailResult(
                success=False,
                error=f"SMTP error: {str(e)}",
                driver_used="smtp",
                metadata={"smtp_error": str(e)}
            )
            
        except Exception as e:
            logger.error(f"Unexpected error sending email via SMTP: {e}")
            return EmailResult(
                success=False,
                error=f"SMTP driver error: {str(e)}",
                driver_used="smtp",
                metadata={"exception_type": type(e).__name__}
            )
    
    async def test_connection(self) -> bool:
        """Test SMTP connection and authentication."""
        try:
            logger.info(f"Testing SMTP connection to {self.host}:{self.port}")
            
            if self.use_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            try:
                if self.username and self.password:
                    server.login(self.username, self.password)
                    logger.info("SMTP authentication successful")
                
                # Send NOOP to test connection
                server.noop()
                logger.info("SMTP connection test successful")
                return True
                
            finally:
                server.quit()
                
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
