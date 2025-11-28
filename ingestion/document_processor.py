"""
Document processor for real-time ingestion with progress tracking.
"""
import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from parsers.parser_factory import ParserFactory
from rag_system import RAGSystem

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of document processing."""
    status: str  # 'success', 'failed', 'processing'
    document_name: str
    chunks_created: int = 0
    tokens_extracted: int = 0
    parser_used: Optional[str] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    extraction_percentage: float = 0.0
    images_detected: bool = False


class DocumentProcessor:
    """Processes documents with real-time progress tracking."""
    
    def __init__(self, rag_system: RAGSystem):
        """
        Initialize document processor.
        
        Args:
            rag_system: RAGSystem instance to use for processing
        """
        self.rag_system = rag_system
        self.processing_state: Dict[str, Dict] = {}  # {doc_id: {status, progress, ...}}
    
    def process_document(
        self,
        file_path: str,
        file_content: Optional[bytes] = None,
        file_name: Optional[str] = None,
        parser_preference: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> ProcessingResult:
        """
        Process a single document.
        
        Args:
            file_path: Path to the file (or identifier)
            file_content: Optional file content as bytes
            file_name: Optional file name for display
            parser_preference: Preferred parser ('auto', 'pymupdf', 'docling', 'textract')
            progress_callback: Optional callback function(status, progress) for updates
        
        Returns:
            ProcessingResult with processing statistics
        """
        start_time = time.time()
        doc_name = file_name or os.path.basename(file_path)
        doc_id = file_path
        
        # Initialize state
        self.processing_state[doc_id] = {
            'status': 'processing',
            'progress': 0.0,
            'document_name': doc_name
        }
        
        if progress_callback:
            progress_callback('processing', 0.0)
        
        try:
            # Get file size
            file_size = len(file_content) if file_content else 0
            if not file_size and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            
            # Get file type
            file_ext = os.path.splitext(doc_name)[1].lower().lstrip('.')
            file_type = file_ext if file_ext else 'unknown'
            
            # Step 1: Parse document (25% progress)
            if progress_callback:
                progress_callback('parsing', 0.25)
            
            parse_start = time.time()
            try:
                # Log parser selection
                parser_name = parser_preference or "auto"
                logger.info(f"DocumentProcessor: Processing {doc_name} with parser: {parser_name}")
                if parser_preference:
                    logger.info(f"DocumentProcessor: Explicit parser selected: {parser_preference} (will NOT fall back)")
                
                # Special handling for Docling - show progress updates
                if parser_preference and parser_preference.lower() == 'docling':
                    if progress_callback:
                        progress_callback('parsing', 0.3)
                        # Update status to show Docling is processing
                        logger.info(f"Docling: Processing {doc_name} (this may take 5-15 minutes)...")
                
                # Parse document (this will block for Docling, but that's expected)
                logger.info(f"DocumentProcessor: Calling parser with preference: {parser_preference}")
                parsed_doc = ParserFactory.parse_with_fallback(
                    file_path,
                    file_content,
                    preferred_parser=parser_preference
                )
                
                # Log successful parsing
                if parsed_doc:
                    logger.info(
                        f"DocumentProcessor: Parser '{parsed_doc.parser_used}' completed successfully: "
                        f"{parsed_doc.pages} pages, {len(parsed_doc.text):,} chars, "
                        f"{parsed_doc.extraction_percentage*100:.1f}% extraction"
                    )
                    logger.info(f"DocumentProcessor: Text preview (first 200 chars): {parsed_doc.text[:200] if parsed_doc.text else 'EMPTY'}...")
                else:
                    logger.error("DocumentProcessor: Parser returned None!")
                    raise ValueError("Parser returned None - document could not be parsed")
            except IndexError as e:
                logger.error(f"Parser error (list index out of range): {str(e)}")
                raise ValueError(f"Parser error (list index out of range): {str(e)}. The PDF may be corrupted or in an unsupported format.")
            except Exception as e:
                logger.error(f"Parser error: {str(e)}")
                raise ValueError(f"Parser error: {str(e)}")
            parsing_time = time.time() - parse_start
            logger.info(f"Parsing completed in {parsing_time:.2f} seconds")
            
            # Validate parsed document
            if parsed_doc is None:
                raise ValueError("Parser returned None - document could not be parsed")
            if not hasattr(parsed_doc, 'text'):
                raise ValueError("Parsed document missing 'text' attribute")
            if not hasattr(parsed_doc, 'parser_used'):
                raise ValueError("Parsed document missing 'parser_used' attribute")
            
            # Check if text is empty (common for scanned/image PDFs)
            doc_text = parsed_doc.text if parsed_doc.text else ""
            if not doc_text or not doc_text.strip():
                # Check if this is an image-based PDF
                if parsed_doc.images_detected or parsed_doc.extraction_percentage < 0.1:
                    # Check if a specific parser was requested
                    requested_parser = parser_preference.lower() if parser_preference else None
                    actual_parser = parsed_doc.parser_used.lower() if hasattr(parsed_doc, 'parser_used') else 'unknown'
                    
                    # If a specific parser was requested but a different one was used, that's an error
                    if requested_parser and requested_parser != 'auto' and actual_parser != requested_parser:
                        logger.error(f"DocumentProcessor: ERROR - Requested {requested_parser} but got {actual_parser}")
                        raise ValueError(
                            f"Parser selection error: You selected '{parser_preference}' but '{parsed_doc.parser_used}' was used instead. "
                            f"This should not happen. Please report this issue."
                        )
                    
                    # Suggest Docling first (has OCR capabilities), then Textract
                    suggestions = []
                    if actual_parser != 'docling':
                        suggestions.append("1. Use Docling parser (has OCR capabilities for scanned PDFs) - Select 'Docling' in parser settings")
                    if actual_parser != 'textract':
                        suggestions.append("2. Use Textract parser (requires AWS credentials) - Select 'Textract' in parser settings")
                    suggestions.append("3. Use OCR software to convert the PDF to text first")
                    
                    error_msg = (
                        f"Document appears to be image-based (scanned PDF). "
                        f"No text could be extracted.\n"
                        f"Parser used: {parsed_doc.parser_used}\n"
                    )
                    
                    if requested_parser and requested_parser != 'auto':
                        error_msg += f"Parser requested: {parser_preference}\n"
                    
                    error_msg += (
                        f"Extraction: {parsed_doc.extraction_percentage * 100:.1f}%\n"
                        f"Pages: {parsed_doc.pages}\n"
                        f"Images detected: {parsed_doc.images_detected}\n\n"
                        f"Solutions:\n"
                        + "\n".join(suggestions)
                    )
                    
                    if actual_parser != 'textract':
                        error_msg += "\n4. Ensure AWS credentials are configured if using Textract"
                    
                    raise ValueError(error_msg)
                else:
                    raise ValueError(
                        f"No text could be extracted from the document. "
                        f"The document may be corrupted or in an unsupported format."
                    )
            
            # Step 2: Process with RAG system (50% progress)
            if progress_callback:
                progress_callback('chunking', 0.5)
            
            chunk_start = time.time()
            # Add to RAG system incrementally
            try:
                # Ensure text is valid string
                if not isinstance(doc_text, str):
                    doc_text = str(doc_text)
                
                # Create a wrapper callback that maps internal progress to our progress range
                def chunking_progress_callback(status, progress):
                    if progress_callback:
                        # Map internal progress (0.0-1.0) to our range (0.5-0.95)
                        # chunking: 0.5-0.7, embedding: 0.7-0.95
                        if status == 'chunking':
                            mapped_progress = 0.5 + (progress * 0.2)  # 0.5 to 0.7
                        elif status == 'embedding':
                            mapped_progress = 0.7 + (progress * 0.25)  # 0.7 to 0.95
                        else:
                            mapped_progress = 0.5 + (progress * 0.45)  # 0.5 to 0.95
                        progress_callback(status, mapped_progress)
                
                logger.info(f"Starting chunking and embedding for {doc_name} ({len(doc_text):,} characters)...")
                stats = self.rag_system.add_documents_incremental(
                    texts=[doc_text],
                    metadatas=[{
                        'source': doc_name,
                        'parser_used': getattr(parsed_doc, 'parser_used', 'unknown'),
                        'pages': getattr(parsed_doc, 'pages', 0),
                        'images_detected': getattr(parsed_doc, 'images_detected', False),
                        'extraction_percentage': getattr(parsed_doc, 'extraction_percentage', 0.0)
                    }],
                    progress_callback=chunking_progress_callback
                )
                logger.info(f"Chunking and embedding completed: {stats['chunks_created']} chunks, {stats['tokens_added']:,} tokens")
            except IndexError as e:
                import traceback
                error_details = traceback.format_exc()
                raise ValueError(
                    f"Chunking error (list index out of range): {str(e)}\n"
                    f"The document may be too large or have formatting issues.\n"
                    f"Error details: {error_details[:500]}"
                )
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                raise ValueError(f"Chunking error: {str(e)}\nError details: {error_details[:500]}")
            chunking_time = time.time() - chunk_start
            
            # Estimate embedding time (usually fast, but track it)
            embedding_time = 0.0  # Embedding happens in add_documents_incremental
            
            # Step 3: Complete (100% progress)
            if progress_callback:
                progress_callback('complete', 1.0)
            
            processing_time = time.time() - start_time
            
            result = ProcessingResult(
                status='success',
                document_name=doc_name,
                chunks_created=stats['chunks_created'],
                tokens_extracted=stats['tokens_added'],
                parser_used=parsed_doc.parser_used,
                processing_time=processing_time,
                extraction_percentage=parsed_doc.extraction_percentage,
                images_detected=parsed_doc.images_detected
            )
            
            # Record metrics if collector is available
            if hasattr(self.rag_system, 'metrics_collector') and self.rag_system.metrics_collector:
                self.rag_system.metrics_collector.record_processing(
                    document_name=doc_name,
                    file_size=file_size,
                    file_type=file_type,
                    parser_used=parsed_doc.parser_used,
                    pages=parsed_doc.pages,
                    chunks_created=stats['chunks_created'],
                    tokens_extracted=stats['tokens_added'],
                    extraction_percentage=parsed_doc.extraction_percentage,
                    confidence=parsed_doc.confidence if hasattr(parsed_doc, 'confidence') else 1.0,
                    processing_time=processing_time,
                    parsing_time=parsing_time,
                    chunking_time=chunking_time,
                    embedding_time=embedding_time,
                    success=True,
                    images_detected=parsed_doc.images_detected
                )
            
            self.processing_state[doc_id] = {
                'status': 'success',
                'progress': 1.0,
                'document_name': doc_name,
                'result': result
            }
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            # Get file size for metrics
            file_size = len(file_content) if file_content else 0
            if not file_size and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(doc_name)[1].lower().lstrip('.')
            file_type = file_ext if file_ext else 'unknown'
            
            result = ProcessingResult(
                status='failed',
                document_name=doc_name,
                error=error_msg,
                processing_time=processing_time
            )
            
            # Record failed metrics
            if hasattr(self.rag_system, 'metrics_collector') and self.rag_system.metrics_collector:
                self.rag_system.metrics_collector.record_processing(
                    document_name=doc_name,
                    file_size=file_size,
                    file_type=file_type,
                    parser_used=parser_preference or 'unknown',
                    pages=0,
                    chunks_created=0,
                    tokens_extracted=0,
                    extraction_percentage=0.0,
                    confidence=0.0,
                    processing_time=processing_time,
                    success=False,
                    error=error_msg
                )
            
            self.processing_state[doc_id] = {
                'status': 'failed',
                'progress': 1.0,
                'document_name': doc_name,
                'error': error_msg,
                'result': result
            }
            
            if progress_callback:
                progress_callback('failed', 1.0)
            
            return result
    
    def process_documents_batch(
        self,
        files: List[Dict],  # List of {path, content, name}
        parser_preference: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[ProcessingResult]:
        """
        Process multiple documents sequentially.
        
        Args:
            files: List of file dictionaries with 'path', 'content' (optional), 'name'
            parser_preference: Preferred parser
            progress_callback: Optional callback(doc_index, total_docs, status, progress)
        
        Returns:
            List of ProcessingResult objects
        """
        results = []
        total_files = len(files)
        
        for idx, file_info in enumerate(files):
            file_path = file_info.get('path', '')
            file_content = file_info.get('content')
            file_name = file_info.get('name', os.path.basename(file_path))
            
            # Create callback wrapper
            def doc_progress_callback(status, progress):
                if progress_callback:
                    overall_progress = (idx + progress) / total_files
                    progress_callback(idx, total_files, file_name, status, overall_progress)
            
            # Process document
            result = self.process_document(
                file_path=file_path,
                file_content=file_content,
                file_name=file_name,
                parser_preference=parser_preference,
                progress_callback=doc_progress_callback
            )
            
            results.append(result)
        
        return results
    
    def get_processing_state(self, doc_id: str) -> Optional[Dict]:
        """Get processing state for a document."""
        return self.processing_state.get(doc_id)
    
    def get_all_states(self) -> Dict[str, Dict]:
        """Get all processing states."""
        return self.processing_state.copy()
    
    def clear_state(self, doc_id: Optional[str] = None):
        """Clear processing state for a document or all documents."""
        if doc_id:
            self.processing_state.pop(doc_id, None)
        else:
            self.processing_state.clear()

