"""Clients package for Intelycx Email MCP Server."""

from .email_client import EmailClient, EmailMessage, EmailRecipient, EmailAttachment

__all__ = ["EmailClient", "EmailMessage", "EmailRecipient", "EmailAttachment"]
