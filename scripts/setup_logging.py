"""
Enhanced logging configuration for ARIS RAG System
Provides structured, formatted logs for both FastAPI and Streamlit
"""
import logging
import sys
from datetime import datetime
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Create a copy of the record to avoid modifying the original
        # (which would affect file handlers)
        record_copy = logging.makeLogRecord(record.__dict__)
        # Add color to levelname only for console output
        if record_copy.levelname in self.COLORS:
            record_copy.levelname = f"{self.COLORS[record_copy.levelname]}{record_copy.levelname}{self.RESET}"
        
        return super().format(record_copy)


def setup_logging(
    name: str = "aris_rag",
    level: int = logging.INFO,
    log_file: str = None,
    format_string: str = None
) -> logging.Logger:
    """
    Set up enhanced logging configuration.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        format_string: Custom format string
    
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Default format
    if format_string is None:
        format_string = (
            '%(asctime)s | %(levelname)-8s | %(name)s | '
            '%(filename)s:%(lineno)d | %(message)s'
        )
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = ColoredFormatter(format_string, datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if log file specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        # Remove ANSI color codes from format string for file output
        # Use plain formatter without colors
        file_formatter = logging.Formatter(
            format_string,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """Get or create a logger with default configuration"""
    if name is None:
        name = "aris_rag"
    
    logger = logging.getLogger(name)
    
    # If logger doesn't have handlers, set it up
    if not logger.handlers:
        setup_logging(name)
    
    return logger


def setup_image_extraction_logging(
    level: int = logging.INFO,
    log_file: str = "logs/image_extraction.log"
) -> logging.Logger:
    """
    Set up specialized logging for image extraction operations.
    
    Args:
        level: Logging level
        log_file: Log file path
    
    Returns:
        Configured logger for image extraction
    """
    logger = setup_logging(
        name="aris_rag.image_extraction",
        level=level,
        log_file=log_file
    )
    
    return logger

