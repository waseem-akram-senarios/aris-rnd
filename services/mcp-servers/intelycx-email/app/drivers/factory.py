"""Email driver factory for creating and managing email drivers."""

import os
import logging
from typing import Dict, Any, Type, Optional, List

from .base import BaseEmailDriver
from .ses_driver import SESDriver
from .smtp_driver import SMTPDriver
from .log_driver import LogDriver


logger = logging.getLogger(__name__)


class EmailDriverFactory:
    """Factory for creating email drivers based on configuration."""
    
    # Registry of available drivers
    DRIVERS: Dict[str, Type[BaseEmailDriver]] = {
        "ses": SESDriver,
        "smtp": SMTPDriver,
        "log": LogDriver,
    }
    
    @classmethod
    def create_driver(cls, driver_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> BaseEmailDriver:
        """Create an email driver instance.
        
        Args:
            driver_name: Name of the driver to create. If None, uses EMAIL_DRIVER env var.
            config: Driver configuration. If None, uses environment variables.
            
        Returns:
            Configured email driver instance.
            
        Raises:
            ValueError: If driver name is invalid or configuration is missing.
        """
        # Determine driver name
        if driver_name is None:
            driver_name = os.getenv("EMAIL_DRIVER", "log").lower()
        else:
            driver_name = driver_name.lower()
        
        # Validate driver name
        if driver_name not in cls.DRIVERS:
            available_drivers = ", ".join(cls.DRIVERS.keys())
            raise ValueError(f"Unknown email driver '{driver_name}'. Available drivers: {available_drivers}")
        
        # Create default configuration if none provided
        if config is None:
            config = cls._get_default_config(driver_name)
        
        # Get driver class and create instance
        driver_class = cls.DRIVERS[driver_name]
        
        try:
            logger.info(f"Creating email driver: {driver_name}")
            driver = driver_class(config)
            logger.info(f"Email driver '{driver_name}' created successfully")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to create email driver '{driver_name}': {e}")
            raise ValueError(f"Failed to initialize {driver_name} driver: {str(e)}")
    
    @classmethod
    def _get_default_config(cls, driver_name: str) -> Dict[str, Any]:
        """Get default configuration for a driver from environment variables."""
        if driver_name == "ses":
            return {
                "region": os.getenv("EMAIL_REGION", "us-east-1"),
                "from_email": os.getenv("EMAIL_SENDER"),
                "from_name": os.getenv("EMAIL_SENDER_NAME", "Intelycx ARIS"),
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "aws_session_token": os.getenv("AWS_SESSION_TOKEN"),
            }
        
        elif driver_name == "smtp":
            return {
                "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
                "port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("SMTP_USER"),
                "password": os.getenv("SMTP_PASSWORD"),
                "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                "use_ssl": os.getenv("SMTP_USE_SSL", "false").lower() == "true",
                "from_email": os.getenv("EMAIL_SENDER"),
                "from_name": os.getenv("EMAIL_SENDER_NAME", "Intelycx ARIS"),
                "timeout": int(os.getenv("SMTP_TIMEOUT", "30")),
            }
        
        elif driver_name == "log":
            return {
                "log_level": os.getenv("EMAIL_LOG_LEVEL", "INFO"),
                "log_file": os.getenv("EMAIL_LOG_FILE"),
                "include_body": os.getenv("EMAIL_LOG_INCLUDE_BODY", "true").lower() == "true",
                "include_attachments": os.getenv("EMAIL_LOG_INCLUDE_ATTACHMENTS", "true").lower() == "true",
                "pretty_print": os.getenv("EMAIL_LOG_PRETTY_PRINT", "true").lower() == "true",
            }
        
        else:
            return {}
    
    @classmethod
    def get_available_drivers(cls) -> List[str]:
        """Get list of available driver names."""
        return list(cls.DRIVERS.keys())
    
    @classmethod
    def register_driver(cls, name: str, driver_class: Type[BaseEmailDriver]):
        """Register a custom email driver."""
        if not issubclass(driver_class, BaseEmailDriver):
            raise ValueError("Driver class must inherit from BaseEmailDriver")
        
        cls.DRIVERS[name.lower()] = driver_class
        logger.info(f"Registered custom email driver: {name}")
    
    @classmethod
    async def test_all_drivers(cls) -> Dict[str, bool]:
        """Test all available drivers with their default configurations."""
        results = {}
        
        for driver_name in cls.DRIVERS.keys():
            try:
                logger.info(f"Testing driver: {driver_name}")
                driver = cls.create_driver(driver_name)
                results[driver_name] = await driver.test_connection()
                logger.info(f"Driver {driver_name} test: {'PASSED' if results[driver_name] else 'FAILED'}")
                
            except Exception as e:
                logger.error(f"Driver {driver_name} test failed with exception: {e}")
                results[driver_name] = False
        
        return results
