"""Amazon SES email driver implementation."""

import os
import logging
from typing import Dict, Any
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import boto3
from botocore.exceptions import ClientError

from .base import BaseEmailDriver, EmailMessage, EmailResult, EmailPriority


logger = logging.getLogger(__name__)


class SESDriver(BaseEmailDriver):
    """Amazon SES email driver."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize SES driver with configuration."""
        super().__init__(config)
        
        # SES configuration
        self.region = config.get("region", os.getenv("EMAIL_REGION", "us-east-1"))
        self.from_email = config.get("from_email", os.getenv("EMAIL_SENDER"))
        self.from_name = config.get("from_name", os.getenv("EMAIL_SENDER_NAME", "Intelycx ARIS"))
        
        # AWS configuration
        self.aws_access_key_id = config.get("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
        self.aws_secret_access_key = config.get("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY"))
        self.aws_session_token = config.get("aws_session_token", os.getenv("AWS_SESSION_TOKEN"))
        
        # Validate required configuration
        if not self.from_email:
            raise ValueError("SES driver requires 'from_email' or EMAIL_SENDER environment variable")
        
        # Initialize SES client
        try:
            kwargs = {"region_name": self.region}
            if self.aws_access_key_id and self.aws_secret_access_key:
                kwargs.update({
                    "aws_access_key_id": self.aws_access_key_id,
                    "aws_secret_access_key": self.aws_secret_access_key
                })
                if self.aws_session_token:
                    kwargs["aws_session_token"] = self.aws_session_token
            
            self.ses_client = boto3.client('ses', **kwargs)
            logger.info(f"SES driver initialized for region: {self.region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize SES client: {e}")
            raise
    
    async def send(self, message: EmailMessage) -> EmailResult:
        """Send email using Amazon SES."""
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
            
            # What a recipient sees if they don't use an email reader
            msg.preamble = 'Multipart message.\n'
            
            # Add message body
            if message.is_html:
                body_part = MIMEText(message.body, 'html', 'utf-8')
            else:
                body_part = MIMEText(message.body, 'plain', 'utf-8')
            msg.attach(body_part)
            
            # Add attachments
            for attachment in message.attachments:
                try:
                    part = MIMEApplication(attachment.content)
                    part.add_header(
                        'Content-Disposition', 
                        'attachment', 
                        filename=attachment.filename
                    )
                    if attachment.content_type:
                        part.set_type(attachment.content_type)
                    msg.attach(part)
                    logger.debug(f"Added attachment: {attachment.filename} ({len(attachment.content)} bytes)")
                except Exception as e:
                    logger.error(f"Failed to attach file {attachment.filename}: {e}")
                    # Continue with other attachments
            
            # Collect all destination emails
            destinations = []
            for recipient in message.to:
                destinations.append(recipient.email)
            for recipient in message.cc:
                destinations.append(recipient.email)
            for recipient in message.bcc:
                destinations.append(recipient.email)
            
            # Send via SES
            logger.info(f"Sending email via SES to {len(destinations)} recipients")
            response = self.ses_client.send_raw_email(
                Source=message.from_email,
                Destinations=destinations,
                RawMessage={'Data': msg.as_string()}
            )
            
            # Extract message ID from response
            message_id = response.get('MessageId', self._create_message_id())
            
            # Calculate email size
            email_size_kb = self._calculate_size(message)
            
            logger.info(f"Email sent successfully via SES. Message ID: {message_id}")
            
            return EmailResult(
                success=True,
                message_id=message_id,
                recipients_count=len(message.to),
                cc_count=len(message.cc),
                bcc_count=len(message.bcc),
                status="sent_via_ses",
                sent_at=datetime.now(),
                size_kb=email_size_kb,
                driver_used="ses",
                metadata={
                    "ses_message_id": message_id,
                    "ses_region": self.region,
                    "attachments_count": len(message.attachments),
                    "priority": message.priority.value
                }
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"SES ClientError: {error_code} - {error_message}")
            
            # Provide user-friendly error messages
            user_friendly_errors = {
                'MessageRejected': 'Email was rejected by SES. Please check recipient addresses.',
                'MailFromDomainNotVerified': 'Sender domain is not verified in SES.',
                'ConfigurationSetDoesNotExist': 'SES configuration set not found.',
                'AccountSendingPaused': 'SES account sending is currently paused.',
                'SendingQuotaExceeded': 'SES sending quota exceeded for today.',
                'DailyQuotaExceeded': 'Daily SES quota exceeded.',
                'RateLimitExceeded': 'SES rate limit exceeded. Please try again later.',
            }
            
            friendly_message = user_friendly_errors.get(error_code, f"SES error: {error_message}")
            
            return EmailResult(
                success=False,
                error=f"SES Error ({error_code}): {friendly_message}",
                driver_used="ses",
                metadata={
                    "ses_error_code": error_code,
                    "ses_error_message": error_message,
                    "recipients_attempted": len(message.all_recipients)
                }
            )
            
        except Exception as e:
            logger.error(f"Unexpected error sending email via SES: {e}")
            return EmailResult(
                success=False,
                error=f"SES driver error: {str(e)}",
                driver_used="ses",
                metadata={"exception_type": type(e).__name__}
            )
    
    async def test_connection(self) -> bool:
        """Test SES connection and sending quota."""
        try:
            # Check SES sending quota
            quota_response = self.ses_client.get_send_quota()
            logger.info(f"SES quota check: {quota_response}")
            
            # Check verified email addresses
            verified_response = self.ses_client.list_verified_email_addresses()
            verified_emails = verified_response.get('VerifiedEmailAddresses', [])
            
            if self.from_email not in verified_emails:
                logger.warning(f"From email {self.from_email} is not verified in SES")
                # Check if domain is verified instead
                domain = self.from_email.split('@')[1] if '@' in self.from_email else ''
                if domain:
                    domain_response = self.ses_client.list_verified_email_addresses()
                    # Note: This is a simplified check. In production, you'd want to check domain verification separately
            
            logger.info(f"SES connection test successful. Verified emails: {len(verified_emails)}")
            return True
            
        except ClientError as e:
            logger.error(f"SES connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"SES connection test error: {e}")
            return False
    
    def get_sending_statistics(self) -> Dict[str, Any]:
        """Get SES sending statistics."""
        try:
            quota = self.ses_client.get_send_quota()
            stats = self.ses_client.get_send_statistics()
            
            return {
                "quota": quota,
                "statistics": stats,
                "region": self.region
            }
        except Exception as e:
            logger.error(f"Failed to get SES statistics: {e}")
            return {"error": str(e)}
