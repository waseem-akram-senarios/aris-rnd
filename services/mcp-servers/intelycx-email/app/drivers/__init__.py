"""Email drivers package for Intelycx Email MCP Server."""

from .base import BaseEmailDriver, EmailMessage, EmailAttachment, EmailRecipient, EmailResult, EmailPriority
from .ses_driver import SESDriver
from .smtp_driver import SMTPDriver
from .log_driver import LogDriver
from .factory import EmailDriverFactory

__all__ = [
    "BaseEmailDriver",
    "EmailMessage", 
    "EmailAttachment",
    "EmailRecipient",
    "EmailResult",
    "EmailPriority",
    "SESDriver",
    "SMTPDriver", 
    "LogDriver",
    "EmailDriverFactory"
]
