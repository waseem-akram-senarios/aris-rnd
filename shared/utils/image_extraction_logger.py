"""
Specialized logging utilities for image extraction operations.
Provides structured logging for OCR, marker detection, and storage operations.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from scripts.setup_logging import setup_logging

# Create dedicated logger for image extraction
IMAGE_EXTRACTION_LOGGER = setup_logging(
    name="aris_rag.image_extraction",
    level=logging.INFO,
    log_file="logs/image_extraction.log"
)


class ImageExtractionLogger:
    """
    Specialized logger for image extraction events.
    Provides structured logging with event types and metadata.
    """
    
    # Event types
    IMAGE_DETECTION_START = "IMAGE_DETECTION_START"
    IMAGE_DETECTED = "IMAGE_DETECTED"
    OCR_START = "OCR_START"
    OCR_PROGRESS = "OCR_PROGRESS"
    OCR_COMPLETE = "OCR_COMPLETE"
    MARKER_INSERTION = "MARKER_INSERTION"
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    STORAGE_START = "STORAGE_START"
    STORAGE_SUCCESS = "STORAGE_SUCCESS"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    QUERY_EXTRACTION = "QUERY_EXTRACTION"
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize image extraction logger.
        
        Args:
            logger: Optional logger instance (defaults to IMAGE_EXTRACTION_LOGGER)
        """
        self.logger = logger or IMAGE_EXTRACTION_LOGGER
        self.start_times: Dict[str, float] = {}  # Track operation start times
    
    def _create_log_entry(
        self,
        event: str,
        level: str = "INFO",
        source: Optional[str] = None,
        image_number: Optional[int] = None,
        page: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create structured log entry.
        
        Args:
            event: Event type
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            source: Document source name
            image_number: Image number
            page: Page number
            **kwargs: Additional metadata
            
        Returns:
            Dictionary with log entry data
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "event": event,
        }
        
        if source:
            entry["source"] = source
        if image_number is not None:
            entry["image_number"] = image_number
        if page is not None:
            entry["page"] = page
        
        # Add any additional metadata
        entry.update(kwargs)
        
        return entry
    
    def _log_structured(self, entry: Dict[str, Any], log_level: str = "INFO"):
        """
        Log structured entry as JSON.
        
        Args:
            entry: Log entry dictionary
            log_level: Log level string
        """
        log_message = json.dumps(entry)
        
        if log_level == "DEBUG":
            self.logger.debug(log_message)
        elif log_level == "INFO":
            self.logger.info(log_message)
        elif log_level == "WARNING":
            self.logger.warning(log_message)
        elif log_level == "ERROR":
            self.logger.error(log_message)
        else:
            self.logger.info(log_message)
    
    def log_image_detection_start(self, source: str, method: str = "auto"):
        """
        Log start of image detection.
        
        Args:
            source: Document source name
            method: Detection method (auto, docling, pymupdf, textract)
        """
        operation_id = f"{source}_detection"
        self.start_times[operation_id] = time.time()
        
        entry = self._create_log_entry(
            self.IMAGE_DETECTION_START,
            source=source,
            detection_method=method
        )
        self._log_structured(entry)
    
    def log_image_detected(
        self,
        source: str,
        image_count: int,
        detection_methods: list = None,
        page: Optional[int] = None
    ):
        """
        Log image detection completion.
        
        Args:
            source: Document source name
            image_count: Number of images detected
            detection_methods: List of methods that detected images
            page: Page number if single page
        """
        operation_id = f"{source}_detection"
        duration_ms = None
        if operation_id in self.start_times:
            duration_ms = int((time.time() - self.start_times[operation_id]) * 1000)
            del self.start_times[operation_id]
        
        entry = self._create_log_entry(
            self.IMAGE_DETECTED,
            source=source,
            image_count=image_count,
            detection_methods=detection_methods or [],
            page=page,
            duration_ms=duration_ms
        )
        self._log_structured(entry)
    
    def log_ocr_start(
        self,
        source: str,
        image_number: Optional[int] = None,
        page: Optional[int] = None,
        extraction_method: str = "docling"
    ):
        """
        Log start of OCR processing.
        
        Args:
            source: Document source name
            image_number: Image number (if specific image)
            page: Page number
            extraction_method: OCR method (docling, textract, pymupdf)
        """
        operation_id = f"{source}_image_{image_number}_ocr" if image_number else f"{source}_ocr"
        self.start_times[operation_id] = time.time()
        
        entry = self._create_log_entry(
            self.OCR_START,
            source=source,
            image_number=image_number,
            page=page,
            extraction_method=extraction_method
        )
        self._log_structured(entry)
    
    def log_ocr_progress(
        self,
        source: str,
        progress: float,
        image_number: Optional[int] = None,
        message: Optional[str] = None
    ):
        """
        Log OCR progress update.
        
        Args:
            source: Document source name
            progress: Progress percentage (0.0-1.0)
            image_number: Image number (if specific image)
            message: Optional progress message
        """
        entry = self._create_log_entry(
            self.OCR_PROGRESS,
            level="DEBUG",
            source=source,
            image_number=image_number,
            progress=progress,
            message=message
        )
        self._log_structured(entry, "DEBUG")
    
    def log_ocr_complete(
        self,
        source: str,
        ocr_text_length: int,
        image_number: Optional[int] = None,
        page: Optional[int] = None,
        extraction_method: str = "docling",
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        Log OCR completion.
        
        Args:
            source: Document source name
            ocr_text_length: Length of extracted OCR text
            image_number: Image number (if specific image)
            page: Page number
            extraction_method: OCR method used
            success: Whether OCR was successful
            error: Error message if failed
        """
        operation_id = f"{source}_image_{image_number}_ocr" if image_number else f"{source}_ocr"
        duration_ms = None
        if operation_id in self.start_times:
            duration_ms = int((time.time() - self.start_times[operation_id]) * 1000)
            del self.start_times[operation_id]
        
        entry = self._create_log_entry(
            self.OCR_COMPLETE,
            level="INFO" if success else "ERROR",
            source=source,
            image_number=image_number,
            page=page,
            ocr_text_length=ocr_text_length,
            extraction_method=extraction_method,
            success=success,
            error=error,
            duration_ms=duration_ms
        )
        self._log_structured(entry, "INFO" if success else "ERROR")
    
    def log_marker_insertion(
        self,
        source: str,
        markers_inserted: int,
        total_images: int,
        coverage_percentage: float,
        method: str = "pattern_detection"
    ):
        """
        Log image marker insertion.
        
        Args:
            source: Document source name
            markers_inserted: Number of markers inserted
            total_images: Total number of images detected
            coverage_percentage: Percentage of images with markers
            method: Method used (pattern_detection, position_based, etc.)
        """
        entry = self._create_log_entry(
            self.MARKER_INSERTION,
            source=source,
            markers_inserted=markers_inserted,
            total_images=total_images,
            coverage_percentage=coverage_percentage,
            method=method
        )
        self._log_structured(entry)
    
    def log_text_extraction(
        self,
        source: str,
        image_number: int,
        ocr_text_length: int,
        page: Optional[int] = None,
        has_marker: bool = True
    ):
        """
        Log text extraction from image.
        
        Args:
            source: Document source name
            image_number: Image number
            ocr_text_length: Length of extracted text
            page: Page number
            has_marker: Whether image marker was present
        """
        entry = self._create_log_entry(
            self.TEXT_EXTRACTION,
            source=source,
            image_number=image_number,
            page=page,
            ocr_text_length=ocr_text_length,
            has_marker=has_marker
        )
        self._log_structured(entry)
    
    def log_storage_start(
        self,
        source: str,
        image_count: int,
        storage_method: str = "opensearch"
    ):
        """
        Log start of image storage operation.
        
        Args:
            source: Document source name
            image_count: Number of images to store
            storage_method: Storage method (opensearch, etc.)
        """
        operation_id = f"{source}_storage"
        self.start_times[operation_id] = time.time()
        
        entry = self._create_log_entry(
            self.STORAGE_START,
            source=source,
            image_count=image_count,
            storage_method=storage_method
        )
        self._log_structured(entry)
    
    def log_storage_success(
        self,
        source: str,
        images_stored: int,
        image_ids: list = None
    ):
        """
        Log successful image storage.
        
        Args:
            source: Document source name
            images_stored: Number of images stored
            image_ids: List of stored image IDs
        """
        operation_id = f"{source}_storage"
        duration_ms = None
        if operation_id in self.start_times:
            duration_ms = int((time.time() - self.start_times[operation_id]) * 1000)
            del self.start_times[operation_id]
        
        entry = self._create_log_entry(
            self.STORAGE_SUCCESS,
            source=source,
            images_stored=images_stored,
            image_ids=image_ids or [],
            duration_ms=duration_ms
        )
        self._log_structured(entry)
    
    def log_storage_failure(
        self,
        source: str,
        error: str,
        images_attempted: int = 0
    ):
        """
        Log failed image storage.
        
        Args:
            source: Document source name
            error: Error message
            images_attempted: Number of images attempted
        """
        operation_id = f"{source}_storage"
        duration_ms = None
        if operation_id in self.start_times:
            duration_ms = int((time.time() - self.start_times[operation_id]) * 1000)
            del self.start_times[operation_id]
        
        entry = self._create_log_entry(
            self.STORAGE_FAILURE,
            level="ERROR",
            source=source,
            error=error,
            images_attempted=images_attempted,
            duration_ms=duration_ms
        )
        self._log_structured(entry, "ERROR")
    
    def log_query_extraction(
        self,
        source: str,
        image_number: int,
        ocr_text_length: int,
        extraction_method: str = "query_time",
        page: Optional[int] = None
    ):
        """
        Log image content extraction at query time.
        
        Args:
            source: Document source name
            image_number: Image number
            ocr_text_length: Length of extracted OCR text
            extraction_method: Extraction method (query_time)
            page: Page number
        """
        entry = self._create_log_entry(
            self.QUERY_EXTRACTION,
            source=source,
            image_number=image_number,
            page=page,
            ocr_text_length=ocr_text_length,
            extraction_method=extraction_method
        )
        self._log_structured(entry)


# Global instance for easy import
image_logger = ImageExtractionLogger()

