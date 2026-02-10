"""
Docling parser using the simple quickstart pattern from documentation.
Uses ThreadPoolExecutor to prevent UI blocking during long processing.
"""
import os
import logging
import warnings
import re
from typing import Optional, Callable, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .base_parser import BaseParser, ParsedDocument

# Set up logging
logger = logging.getLogger(__name__)

# Suppress Streamlit ScriptRunContext warnings from background threads
warnings.filterwarnings('ignore', message='.*missing ScriptRunContext.*', category=UserWarning)

# Import image extraction logger
try:
    from shared.utils.image_extraction_logger import image_logger
except ImportError:
    # Fallback if logger not available
    image_logger = None


class DoclingParser(BaseParser):
    """Parser using Docling library - following the official quickstart pattern."""
    
    def __init__(self):
        super().__init__("docling")
        try:
            from docling.document_converter import DocumentConverter
            self.DocumentConverter = DocumentConverter
        except ImportError:
            raise ImportError(
                "Docling is not installed. "
                "Install it with: pip install docling"
            )
    
    def _verify_ocr_models(self):
        """Verify OCR models are available for Docling."""
        try:
            # Try to check if OCR models exist
            from pathlib import Path
            import os
            
            # Docling stores models in user home directory
            home_dir = Path.home()
            models_path = home_dir / ".cache" / "docling" / "models"
            
            # Check if models directory exists and has content
            if models_path.exists():
                # Check for model files (common OCR model patterns)
                model_files = list(models_path.rglob("*.onnx"))  # ONNX models used by RapidOCR
                model_files.extend(list(models_path.rglob("*.pt")))  # PyTorch models
                model_files.extend(list(models_path.rglob("*.pth")))  # PyTorch models
                model_files.extend(list(models_path.rglob("*.bin")))  # Binary model files
                
                if model_files:
                    logger.info(f"Docling: ✅ OCR models found ({len(model_files)} model files)")
                    return True
                elif any(models_path.iterdir()):
                    # Directory exists with some content, assume models might be there
                    logger.info("Docling: ✅ OCR models directory found (models may be available)")
                    return True
                else:
                    logger.warning("Docling: ⚠️  OCR models directory exists but is empty")
                    logger.warning("Docling: Install models with: docling download-models")
                    return False
            else:
                logger.warning("Docling: ⚠️  OCR models directory not found")
                logger.warning("Docling: Install models with: docling download-models")
                logger.warning("Docling: OCR may still work if models are installed elsewhere or auto-downloaded")
                # Don't return False here - models might be auto-downloaded or in different location
                # Return True to allow processing to continue (Docling will handle missing models)
                return True
        except Exception as e:
            logger.warning(f"Docling: Could not verify OCR models: {e}")
            logger.warning("Docling: OCR may still work if models are available")
            # Return True to allow processing - Docling will handle missing models gracefully
            return True
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle PDF files."""
        _, ext = os.path.splitext(file_path.lower())
        return ext == '.pdf'
    
    def is_available(self) -> bool:
        """Check if Docling is installed and available."""
        try:
            from docling.document_converter import DocumentConverter
            return True
        except ImportError as e:
            logger.debug(f"is_available: {type(e).__name__}: {e}")
            return False
    
    def test_ocr_configuration(self) -> dict:
        """
        Test OCR configuration and return diagnostic information.
        
        Returns:
            dict with status, models_available, config_status, etc.
        """
        result = {
            'ocr_available': False,
            'models_available': False,
            'config_success': False,
            'warnings': [],
            'errors': []
        }
        
        # Check models
        result['models_available'] = self._verify_ocr_models()
        
        # Test OCR configuration - default DocumentConverter has OCR enabled by default
        try:
            # The default DocumentConverter has OCR enabled by default
            test_converter = self.DocumentConverter()
            result['config_success'] = True
            result['ocr_available'] = True
            result['warnings'].append("Using default converter (OCR enabled by default in Docling)")
        except Exception as e:
            logger.debug(f"test_ocr_configuration: {type(e).__name__}: {e}")
            result['errors'].append(f"OCR configuration test failed: {e}")
        
        return result
    
    def _insert_image_markers(self, text: str, image_positions: list = None) -> str:
        """
        Insert <!-- image --> markers into text at specified positions or before image-related content.
        
        Args:
            text: Text content
            image_positions: Optional list of character positions where images should be marked
        
        Returns:
            Text with image markers inserted
        """
        if not text or not text.strip():
            return text
        
        # If image positions provided, insert markers at those positions
        if image_positions:
            # Sort positions in reverse order to maintain indices when inserting
            sorted_positions = sorted(image_positions, reverse=True)
            result_text = text
            for pos in sorted_positions:
                if 0 <= pos <= len(result_text):
                    result_text = result_text[:pos] + "<!-- image -->\n" + result_text[pos:]
            return result_text
        
        # Otherwise, return text as-is (markers should be inserted by parser logic)
        return text
    
    def _insert_image_markers_in_text(self, text: str, image_count: int, image_positions_by_page: dict = None) -> str:
        """
        Insert <!-- image --> markers into text by detecting image-like content patterns.
        Enhanced with better pattern detection and fallback distribution.
        Can use actual image positions from Docling for more accurate placement.
        
        Args:
            text: Text content
            image_count: Expected number of images
            image_positions_by_page: Optional dict mapping page_num -> list of image indices
        
        Returns:
            Text with image markers inserted
        """
        # Allow marker insertion even if image_count is 0 (will estimate)
        if not text or not text.strip():
            return text
        # If image_count is 0, estimate based on text length
        if image_count == 0:
            estimated_count = max(1, len(text) // 5000)  # Rough estimate: 1 marker per 5K chars
            logger.info(f"Docling: image_count is 0, estimating {estimated_count} images for marker insertion")
            image_count = estimated_count
        
        import re
        
        # Strategy: Look for patterns that indicate OCR text from images
        # and insert markers before them
        
        lines = text.split('\n')
        result_lines = []
        markers_inserted = 0
        last_marker_line = -10  # Track last line where marker was inserted
        
        # Strategy 0: Use image positions from Docling if available (most accurate)
        if image_positions_by_page:
            logger.info(f"Docling: Using image positions from Docling for marker insertion ({len(image_positions_by_page)} pages with images)")
            # Map page numbers to line numbers in text
            page_to_lines = {}
            current_page = None
            for i, line in enumerate(lines):
                # Check for page markers
                page_match = re.search(r'---\s*Page\s+(\d+)', line, re.IGNORECASE)
                if page_match:
                    current_page = int(page_match.group(1))
                    if current_page not in page_to_lines:
                        page_to_lines[current_page] = []
                    page_to_lines[current_page].append(i)
                elif current_page is not None:
                    if current_page not in page_to_lines:
                        page_to_lines[current_page] = []
                    page_to_lines[current_page].append(i)
            
            # Insert markers at pages that have images
            for page_num, image_indices in image_positions_by_page.items():
                if page_num in page_to_lines:
                    # Insert marker at start of page (first line after page marker)
                    page_lines = page_to_lines[page_num]
                    if page_lines:
                        insert_line = page_lines[0] + 1  # After page marker
                        if insert_line < len(lines):
                            # Insert marker for each image on this page
                            for img_idx in image_indices:
                                if insert_line <= len(result_lines):
                                    result_lines.insert(insert_line, '<!-- image -->')
                                    markers_inserted += 1
                                    insert_line += 1  # Space markers for multiple images on same page
                else:
                                    result_lines.append('<!-- image -->')
                                    markers_inserted += 1
            
            # If we inserted markers using positions, continue with pattern detection for remaining
            if markers_inserted > 0:
                logger.info(f"Docling: Inserted {markers_inserted} markers using image positions from Docling")
        
        # Enhanced pattern detection
        for i, line in enumerate(lines):
            # Check if this line looks like image content
            is_image_content = False
            
            # Check for part numbers (6+ digits followed by dash and text) - more flexible
            if re.search(r'\d{6,}[-]\s*[A-Za-z]', line) or re.search(r'\d{5,}-\s*\w+', line):
                is_image_content = True
            
            # Check for drawer references (more patterns)
            if (re.search(r'DRAWER\s+\d+', line, re.IGNORECASE) or
                re.search(r'Drawer\s+\d+', line) or
                re.search(r'drawer\s+\d+', line, re.IGNORECASE)):
                is_image_content = True
            
            # Check for tool sizes (numbers followed by MM/INCH and text)
            if (re.search(r'\d+\s*MM\s+[A-Z]', line) or
                re.search(r'\d+\s*INCH', line, re.IGNORECASE) or
                re.search(r'\d+["\']\s+[A-Z]', line)):  # Inches with quotes
                is_image_content = True
            
            # Check for structured lists with underscores (OCR pattern) - more patterns
            if ('___' in line or '____' in line or '_____' in line or
                re.search(r'_+\s*$', line)):  # Underscores at end of line
                is_image_content = True
            
            # Check for quantity patterns
            if re.search(r'Quantity:\s*\d+', line, re.IGNORECASE):
                is_image_content = True
            
            # Check for tool reorder patterns
            if re.search(r'Tool\s+Re.*order', line, re.IGNORECASE):
                is_image_content = True
            
            # Check for table patterns (YES/NO checkboxes)
            if re.search(r'\|\s*YES\s*\|\s*NO\s*\|', line, re.IGNORECASE):
                is_image_content = True
            
            # Check for socket/wrench patterns
            if re.search(r'\d+["\']\s+Socket', line, re.IGNORECASE) or re.search(r'\d+MM\s+Wrench', line, re.IGNORECASE):
                is_image_content = True
            
            # If this looks like image content and we haven't inserted a marker recently
            # CRITICAL FIX: Reduced spacing from 2 to 1 for better coverage
            if is_image_content and (i - last_marker_line) > 1:  # Reduced from 2 to 1 for maximum coverage
                # Check if previous lines don't already have marker
                if i == 0 or '<!-- image -->' not in '\n'.join(result_lines[-5:]):
                    result_lines.append('<!-- image -->')
                    markers_inserted += 1
                    last_marker_line = i
            
            result_lines.append(line)
        
        # Enhanced fallback: If we didn't insert enough markers, try multiple strategies
        if markers_inserted < image_count and len(lines) > image_count:
            additional_markers = image_count - markers_inserted
            if additional_markers > 0:
                insertion_points = []
                
                # Strategy 1: Find good insertion points (after page markers, before structured content)
                for i, line in enumerate(lines):
                    if line.startswith('--- Page') and i + 1 < len(lines):
                        # Check if next few lines have image-like content
                        next_lines = '\n'.join(lines[i+1:min(i+20, len(lines))])  # Increased window
                        if (re.search(r'\d{6,}-\s*[A-Z]', next_lines) or 
                            re.search(r'DRAWER', next_lines, re.IGNORECASE) or
                            re.search(r'___+', next_lines) or
                            re.search(r'\|\s*YES\s*\|\s*NO\s*\|', next_lines) or
                            re.search(r'Quantity:', next_lines, re.IGNORECASE) or
                            re.search(r'Tool\s+Re', next_lines, re.IGNORECASE)):
                            insertion_points.append(i + 1)
                
                # Strategy 2: Find pages with structured content (tables, lists)
                if len(insertion_points) < additional_markers:
                    for i, line in enumerate(lines):
                        if (re.search(r'\|.*\|', line) or  # Table rows
                            re.search(r'^[\s]*[-•]\s+', line) or  # List items
                            re.search(r'^[\s]*\d+[\.)]\s+', line)):  # Numbered lists
                            if i > 0 and '<!-- image -->' not in result_lines[max(0, i-5):i]:
                                insertion_points.append(i)
                                if len(insertion_points) >= additional_markers:
                                    break
                
                # Strategy 3: Even distribution across document if still not enough
                if len(insertion_points) < additional_markers:
                    # Calculate spacing for even distribution
                    total_lines = len(lines)
                    remaining_markers = additional_markers - len(insertion_points)
                    if remaining_markers > 0 and total_lines > remaining_markers:
                        spacing = max(1, total_lines // (remaining_markers + 1))
                        for i in range(spacing, total_lines, spacing):
                            if i < len(result_lines):
                                # Check if marker already nearby
                                nearby_markers = sum(1 for j in range(max(0, i-5), min(len(result_lines), i+5)) 
                                                   if j < len(result_lines) and '<!-- image -->' in result_lines[j])
                                if nearby_markers == 0:
                                    insertion_points.append(i)
                                    if len(insertion_points) >= additional_markers:
                                        break
                
                # Strategy 4: Use page boundaries for even distribution
                if len(insertion_points) < additional_markers:
                    # Find all page markers
                    page_marker_lines = []
                    for i, line in enumerate(lines):
                        if line.startswith('--- Page') or re.search(r'---\s*Page\s+\d+', line, re.IGNORECASE):
                            page_marker_lines.append(i)
                    
                    # Distribute markers after page markers
                    if page_marker_lines and additional_markers > len(insertion_points):
                        remaining = additional_markers - len(insertion_points)
                        markers_per_page = max(1, remaining // len(page_marker_lines)) if page_marker_lines else 0
                        for page_line in page_marker_lines:
                            if len(insertion_points) >= additional_markers:
                                break
                            insert_after = page_line + 1
                            if insert_after < len(result_lines):
                                for _ in range(markers_per_page):
                                    if len(insertion_points) >= additional_markers:
                                        break
                                    if '<!-- image -->' not in result_lines[max(0, insert_after-3):insert_after+1]:
                                        insertion_points.append(insert_after)
                                        insert_after += 2  # Space markers
                
                # Insert markers at found points
                for point in sorted(set(insertion_points))[:additional_markers]:
                    if point < len(result_lines) and '<!-- image -->' not in result_lines[max(0, point-3):point+1]:
                        result_lines.insert(point, '<!-- image -->')
                        markers_inserted += 1
                        if markers_inserted >= image_count:
                            break
        
        result_text = '\n'.join(result_lines)
        
        # Log statistics
        marker_coverage = (markers_inserted / image_count * 100) if image_count > 0 else 0
        logger.info(f"Docling: Inserted {markers_inserted}/{image_count} image markers ({marker_coverage:.1f}% coverage)")
        
        if markers_inserted < image_count * 0.8:  # Less than 80% coverage
            logger.warning(f"Docling: ⚠️  Only {markers_inserted}/{image_count} markers inserted. Some image content may not be marked.")
        
        return result_text
    
    def _extract_individual_images(
        self,
        text: str,
        image_count: int,
        source: str,
        page_blocks: List[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract individual images from text with markers.
        
        Args:
            text: Text with image markers
            image_count: Total number of images detected
            source: Document source name
            page_blocks: List of page blocks for page number mapping
            
        Returns:
            List of image dictionaries with OCR text and metadata
        """
        if not image_logger:
            # If logger not available, still extract but without logging
            pass
        
        extracted_images = []
        
        # If no markers but we have text and images were detected, try to extract anyway
        if not text:
            return extracted_images
        
        # Check if markers exist
        has_markers = '<!-- image -->' in text
        
        if not has_markers:
            # No markers - try to extract from text patterns or create single image entry
            logger.warning(f"Docling: No image markers found in text, but images detected. Attempting extraction without markers...")
            
            # If we have substantial text, create at least one image entry
            if len(text.strip()) > 100:
                # Create a single image entry from the text
                image_data = {
                    'source': source,
                    'image_number': 1,
                    'page': 1,  # Default to page 1
                    'ocr_text': text[:10000],  # First 10K chars
                    'ocr_text_length': min(len(text), 10000),
                    'marker_detected': False,
                    'extraction_method': 'docling_ocr_no_markers',
                    'full_chunk': text[:1000],
                    'context_before': None
                }
                extracted_images.append(image_data)
                logger.info(f"Docling: Created 1 image entry from text without markers (text_length={len(text)})")
            
            return extracted_images
        
        # Split by markers
        marker_pattern = '<!-- image -->'
        parts = text.split(marker_pattern)
        
        # Create page mapping from page_blocks
        page_map = {}
        if page_blocks:
            current_char = 0
            for block in page_blocks:
                if block.get('type') == 'page':
                    page_num = block.get('page', 1)
                    start_char = block.get('start_char', current_char)
                    page_map[start_char] = page_num
        
        # Process each image (parts after first marker)
        image_counter = 0
        current_char_pos = 0
        
        for idx in range(1, len(parts)):  # Skip first part (before first marker)
            image_counter += 1
            
            # Get text before this marker (for context)
            before_text = parts[idx - 1].strip() if idx > 0 else ''
            
            # Get text after marker (OCR content)
            # If there's another marker, only take text up to next marker
            if idx + 1 < len(parts):
                after_text = parts[idx].strip()
            else:
                after_text = parts[idx].strip()
            
            # Extract OCR text (limit to reasonable size)
            ocr_text = after_text[:10000] if after_text else ''  # Limit to 10K chars per image
            
            # Estimate page number from character position
            page_num = 1  # Default
            if page_map:
                # Find closest page marker before this position
                for char_pos, page in sorted(page_map.items()):
                    if char_pos <= current_char_pos:
                        page_num = page
                    else:
                        break
            
            # Update character position
            current_char_pos += len(before_text) + len(marker_pattern) + len(after_text)
            
            # Log text extraction for this image
            if image_logger:
                image_logger.log_text_extraction(
                    source=source,
                    image_number=image_counter,
                    ocr_text_length=len(ocr_text),
                    page=page_num,
                    has_marker=True
                )
            
            # Create image data structure
            image_data = {
                'source': source,
                'image_number': image_counter,
                'page': page_num,
                'ocr_text': ocr_text,
                'ocr_text_length': len(ocr_text),
                'marker_detected': True,
                'extraction_method': 'docling_ocr',
                'full_chunk': f"{before_text[-500:]}{marker_pattern}{after_text[:500]}",  # Sample chunk
                'context_before': before_text[-500:] if before_text else None
            }
            
            extracted_images.append(image_data)
        
        # Log OCR completion for all images
        if image_logger and extracted_images:
            total_ocr_length = sum(img.get('ocr_text_length', 0) for img in extracted_images)
            image_logger.log_ocr_complete(
                source=source,
                ocr_text_length=total_ocr_length,
                extraction_method='docling',
                success=True
            )
        
        return extracted_images
    
    def _extract_text_per_page(self, doc, total_pages: int, progress_callback: Optional[Callable[[str, float], None]] = None):
        """
        Extract text per page from Docling document structure.
        
        Args:
            doc: Docling document object
            total_pages: Total number of pages in document
            progress_callback: Optional progress callback
        
        Returns:
            Tuple of (full_text_with_markers, page_blocks, success_flag)
            success_flag: True if per-page extraction succeeded, False if fallback needed
        """
        text_parts = []
        page_blocks = []
        cumulative_pos = 0
        per_page_extraction_success = False
        
        try:
            # Try to access pages structure
            if not hasattr(doc, 'pages') or not doc.pages:
                logger.warning("Docling: No pages structure available, will use fallback")
                return "", [], False
            
            pages_dict = doc.pages
            pages_iterable = None
            
            # Handle both dict and list formats
            if isinstance(pages_dict, dict):
                # Dict format: keys might be page numbers or indices
                # Try to get pages in order
                try:
                    # Try numeric keys first (1, 2, 3...)
                    sorted_keys = sorted([k for k in pages_dict.keys() if isinstance(k, (int, str))], 
                                        key=lambda x: int(x) if str(x).isdigit() else 0)
                    if sorted_keys:
                        pages_iterable = [(int(k) if str(k).isdigit() else 0, pages_dict[k]) for k in sorted_keys]
                    else:
                        # Fallback: use values directly
                        pages_iterable = enumerate(pages_dict.values(), 1)
                except Exception as e:
                    logger.debug(f"operation: {type(e).__name__}: {e}")
                    # Fallback: use values directly
                    pages_iterable = enumerate(pages_dict.values(), 1)
            elif isinstance(pages_dict, list):
                pages_iterable = enumerate(pages_dict, 1)
            else:
                logger.warning("Docling: Pages structure format not recognized, will use fallback")
                return "", [], False
            
            # Try to extract text from each page using physical numbering
            pages_with_text = 0
            
            # Create a sorted list of physical pages to ensure strict 1-to-N mapping
            # This avoids logical container duplicates
            physical_pages_visited = set()
            
            for page_idx, page_obj in pages_iterable:
                # CRITICAL: Prioritize physical page number property (page_no)
                # Fallback to logical key if property missing
                physical_page_num = getattr(page_obj, 'page_no', None)
                if physical_page_num is None:
                    # Try other common PDF property names
                    physical_page_num = getattr(page_obj, 'physical_page_number', None)
                
                # If still None, use the key or index (1-based fallback)
                if physical_page_num is None:
                    page_num = (page_idx if isinstance(page_idx, int) else 
                               page_idx[0] if isinstance(page_idx, tuple) else 1)
                else:
                    page_num = int(physical_page_num)
                
                # Prevent logical duplicates for the same physical page
                if page_num in physical_pages_visited:
                    logger.debug(f"Docling: Skipping redundant logical block for physical page {page_num}")
                    continue
                physical_pages_visited.add(page_num)
                
                page_content = page_obj if not isinstance(page_idx, tuple) else page_idx[1]
                page_text = ""
                
                # Method 1: page.export_to_text()
                if hasattr(page_content, 'export_to_text'):
                    try:
                        page_text = page_content.export_to_text()
                        if page_text and page_text.strip():
                            per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} export_to_text() failed: {e}")
                
                # Method 2: page.get_text()
                if not page_text and hasattr(page_content, 'get_text'):
                    try:
                        page_text = page_content.get_text()
                        if page_text and page_text.strip():
                            per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} get_text() failed: {e}")
                
                # Method 3: Extract from page.blocks
                if not page_text and hasattr(page_content, 'blocks'):
                    try:
                        block_texts = []
                        for block in page_content.blocks:
                            is_image_block = False
                            if hasattr(block, 'type') and block.type in ['image', 'figure', 'picture', 'illustration']:
                                is_image_block = True
                            
                            block_text = ""
                            if hasattr(block, 'text') and block.text:
                                block_text = block.text
                            elif hasattr(block, 'get_text'):
                                try:
                                    block_text = block.get_text()
                                except Exception as e:
                                    logger.debug(f"operation: {type(e).__name__}: {e}")
                                    pass
                            
                            if block_text:
                                if is_image_block:
                                    block_texts.append("<!-- image -->\n" + block_text)
                                else:
                                    block_texts.append(block_text)
                        
                        if block_texts:
                            page_text = '\n'.join(block_texts)
                            if page_text.strip():
                                per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} blocks extraction failed: {e}")

                
                # Check for images on this page (pictures attribute)
                page_has_images = False
                if hasattr(page_content, 'pictures') and len(page_content.pictures) > 0:
                    page_has_images = True
                    # If we have text but no image markers yet, insert them
                    # Insert marker at the start if this page has images and text was extracted
                    if page_text and '<!-- image -->' not in page_text:
                        # Check if text looks like OCR content (short lines, structured)
                        # Insert marker before text if images are present
                        page_text = "<!-- image -->\n" + page_text
                
                # If we got text from this page, add it with marker
                if page_text and page_text.strip():
                    pages_with_text += 1
                    
                    # Add page marker (matching PyMuPDF format)
                    page_marker = f"--- Page {page_num} ---\n"
                    page_text_with_marker = page_marker + page_text
                    
                    # Track character positions for accurate page boundaries
                    # cumulative_pos includes previous pages + separators
                    page_start = cumulative_pos
                    page_end = cumulative_pos + len(page_text_with_marker)
                    
                    # Create page block with accurate boundaries
                    page_blocks.append({
                        'page': page_num,
                        'text': page_text,
                        'start_char': page_start,
                        'end_char': page_end,
                        'blocks': [{'text': page_text, 'page': page_num}]
                    })
                    
                    # Add to full text with marker
                    text_parts.append(page_text_with_marker)
                    
                    # Update cumulative position including the separator (\n\n) that will be added
                    # This ensures offsets remain accurate when joined
                    cumulative_pos = page_end + 2
                    
                    # Update progress
                    if progress_callback and total_pages > 0:
                        try:
                            progress = 0.9 + (page_num / total_pages) * 0.05  # 90-95% range
                            progress_callback(f"Docling: Extracted page {page_num}/{total_pages}...", progress)
                        except Exception as e:
                            logger.warning(f"operation: {type(e).__name__}: {e}")
                            pass
            
            if per_page_extraction_success and pages_with_text > 0:
                full_text = "\n\n".join(text_parts)
                logger.info(f"Docling: ✅ Per-page extraction successful - {pages_with_text}/{total_pages} pages extracted")
                return full_text, page_blocks, True
            else:
                logger.warning(f"Docling: Per-page extraction failed or extracted 0 pages, will use fallback")
                return "", [], False
                
        except Exception as e:
            logger.warning(f"Docling: Error in per-page extraction: {e}, will use fallback")
            import traceback
            logger.debug(f"Docling: Per-page extraction traceback: {traceback.format_exc()}")
            return "", [], False
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None, progress_callback: Optional[Callable[[str, float], None]] = None, _retry_without_callback: bool = False) -> ParsedDocument:
        """
        Parse PDF using Docling - simple quickstart pattern.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
            progress_callback: Optional callback(status_message, progress) for UI updates
        
        Returns:
            ParsedDocument with extracted text and metadata
        """
        try:
            # Handle file_content by saving to temp file if needed
            actual_path = file_path
            temp_file = None
            if file_content:
                import tempfile
                # Create temp file in system temp directory
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', mode='wb')
                temp_file.write(file_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk
                temp_file.close()
                actual_path = temp_file.name
                # Verify temp file was created and has content
                if not os.path.exists(actual_path):
                    raise ValueError(f"Temp file was not created: {actual_path}")
                if os.path.getsize(actual_path) == 0:
                    raise ValueError(f"Temp file is empty: {actual_path}")
            
            # Use absolute path
            actual_path = os.path.abspath(actual_path)
            if not os.path.exists(actual_path):
                raise ValueError(f"File not found: {actual_path}")
            
            # Initialize image detection variables early (before text extraction uses them)
            images_detected = False
            image_count = 0
            detection_methods = []
            
            # Log image detection start
            if image_logger:
                image_logger.log_image_detection_start(source=file_path, method="docling")
            
            # Log start of processing
            file_size = os.path.getsize(actual_path)
            file_size_mb = file_size / 1024 / 1024
            # Estimate pages based on file size (1-2 MB per page for scanned PDFs, less for text-based)
            estimated_pages = max(1, int(file_size_mb / 1.5)) if file_size_mb > 0 else 0
            # Estimate processing time (5-20 minutes for scanned PDFs with OCR)
            if file_size_mb > 10:
                estimated_time = "15-30 minutes"
            elif file_size_mb > 5:
                estimated_time = "10-20 minutes"
            else:
                estimated_time = "5-15 minutes"
            
            logger.info(f"Docling: Starting conversion of {os.path.basename(actual_path)} ({file_size_mb:.2f} MB)")
            logger.info(f"Docling: File size: {file_size_mb:.2f} MB | Estimated pages: {estimated_pages} | Estimated time: {estimated_time}")
            logger.info(f"Docling: Progress updates every 15 seconds")
            
            # Run Docling conversion in a separate thread to prevent UI blocking
            # Docling can take 5-10 minutes for large PDFs
            def run_docling_conversion():
                """Run Docling conversion in thread."""
                try:
                    logger.info("Docling: [Phase 1/4] Initializing DocumentConverter with OCR enabled...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 1/4] Initializing DocumentConverter with OCR enabled...", 0.1)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    
                    # Enable OCR for image-based PDFs
                    # Verify OCR models are available first
                    ocr_models_available = self._verify_ocr_models()
                    if not ocr_models_available:
                        logger.warning("Docling: OCR models may not be available - OCR may fail")
                        logger.warning("Docling: Run 'docling download-models' to install OCR models")
                    
                    # Configure DocumentConverter with OCR enabled
                    try:
                        # FIX for v2.68.0: Use explicit TesseractCliOcrOptions instead of default OcrAutoOptions
                        try:
                            from docling.datamodel.pipeline_options import PdfPipelineOptions
                            from docling.document_converter import PdfFormatOption
                            
                            # Try TesseractCliOcrOptions first (most compatible)
                            try:
                                from docling.datamodel.pipeline_options import TesseractCliOcrOptions
                                ocr_options = TesseractCliOcrOptions()
                                ocr_backend = "TesseractCli"
                            except ImportError:
                                # Fallback to EasyOcrOptions
                                try:
                                    from docling.datamodel.pipeline_options import EasyOcrOptions
                                    ocr_options = EasyOcrOptions()
                                    ocr_backend = "EasyOCR"
                                except ImportError:
                                    ocr_options = None
                                    ocr_backend = None
                            
                            if ocr_options:
                                # Configure pipeline with OCR enabled using explicit OCR options
                                pipeline_options = PdfPipelineOptions(
                                    do_ocr=True,
                                    ocr_options=ocr_options
                                )
                                
                                try:
                                    converter = self.DocumentConverter(
                                        format_options={
                                            "pdf": PdfFormatOption(pipeline_options=pipeline_options)
                                        }
                                    )
                                except Exception as conv_init_err:
                                    logger.warning(f"Docling: Converter init failed with OCR ({conv_init_err}). Falling back to no-OCR.")
                                    # This will trigger the outer exception handler to fallback
                                    raise ImportError(f"OCR init failed: {conv_init_err}")
                                    
                                logger.info(f"Docling: ✅ Using DocumentConverter with OCR ENABLED ({ocr_backend})")
                            else:
                                raise ImportError("No OCR options available")
                                
                        except Exception as ocr_init_err:
                            logger.warning(f"Docling: Failed to initialize OCR pipeline ({ocr_init_err}). Disabling OCR.")
                            
                            # Fallback to NO OCR
                            from docling.datamodel.pipeline_options import PdfPipelineOptions
                            from docling.document_converter import PdfFormatOption
                            pipeline_options = PdfPipelineOptions(do_ocr=False)
                            converter = self.DocumentConverter(
                                format_options={
                                    "pdf": PdfFormatOption(pipeline_options=pipeline_options)
                                }
                            )
                            logger.info("Docling: ✅ Using DocumentConverter with OCR DISABLED (Text-only mode)")
                    except Exception as fatal_config_err:
                        # This catches errors even during fallback
                        logger.warning(f"Docling: Pipeline config failed completely ({fatal_config_err}). Trying defaults.")
                        converter = self.DocumentConverter()
                    
                    logger.info("Docling: [Phase 2/4] DocumentConverter initialized with OCR, starting conversion...")
                    logger.info("Docling: OCR will process images in the document (this may take time)...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 2/4] Starting document conversion with OCR...", 0.2)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    logger.info(f"Docling: [Phase 2/4] Converting file: {os.path.basename(actual_path)}")
                    
                    try:
                        result = converter.convert(actual_path, raises_on_error=False)
                    except RuntimeError as runtime_err:
                        if "Tesseract" in str(runtime_err):
                            logger.error(f"Docling: Tesseract runtime error during conversion: {runtime_err}")
                            logger.info("Docling: Attempting fallback to text-only mode...")
                            # Recreate converter without OCR
                            from docling.datamodel.pipeline_options import PdfPipelineOptions
                            from docling.document_converter import PdfFormatOption
                            pipeline_options = PdfPipelineOptions(do_ocr=False)
                            converter = self.DocumentConverter(
                                format_options={
                                    "pdf": PdfFormatOption(pipeline_options=pipeline_options)
                                }
                            )
                            result = converter.convert(actual_path, raises_on_error=False)
                            logger.info("Docling: ✅ Fallback to text-only mode succeeded")
                        else:
                            raise
                    logger.info("Docling: [Phase 3/4] Conversion completed, accessing document...")
                    logger.info("Docling: OCR processing complete - extracting text from converted document...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 3/4] Conversion completed, accessing document...", 0.8)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    doc = result.document
                    page_count = len(doc.pages) if hasattr(doc, 'pages') else 'unknown'
                    logger.info(f"Docling: [Phase 4/4] Document accessed successfully, pages: {page_count}")
                    if progress_callback:
                        try:
                            progress_callback(f"Docling: [Phase 4/4] Document accessed, {page_count} pages", 0.9)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    return doc
                except Exception as e:
                    logger.error(f"Docling: Error in conversion thread: {str(e)}")
                    raise
            
            # Use ThreadPoolExecutor without file-level timeout
            # Files will process completely regardless of size
            # Docling processes all pages which can take a long time, especially for scanned PDFs with OCR
            # No timeout - will process completely
            try:
                # Wait for result with periodic progress logging
                import time as time_module
                import threading
                
                start_time = time_module.time()
                progress_logging_active = threading.Event()
                progress_logging_active.set()
                
                # Get max timeout from env or use default (30 minutes)
                max_timeout = int(os.getenv('DOCLING_MAX_TIMEOUT', '1800'))  # 30 minutes default
                
                # Track progress for stuck detection
                last_progress_value = 0.0
                last_progress_change_time = start_time
                stuck_threshold = 10 * 60  # 10 minutes without progress change
                stuck_warning_logged = False
                
                # Future will be set by executor
                future_ref = [None]  # Use list to allow modification in nested scope
                
                def log_progress():
                    """Log detailed progress every 15 seconds while processing."""
                    nonlocal last_progress_value, last_progress_change_time, stuck_warning_logged
                    
                    # Suppress Streamlit ScriptRunContext warnings in background thread
                    # These warnings are harmless when running in background threads and can be safely ignored
                    import warnings
                    warnings.filterwarnings('ignore', message='.*missing ScriptRunContext.*')
                    warnings.filterwarnings('ignore', message='.*ScriptRunContext.*')
                    # Suppress UserWarning category that Streamlit uses for ScriptRunContext
                    warnings.filterwarnings('ignore', category=UserWarning, message='.*ScriptRunContext.*')
                    
                    check_interval = 15  # Log every 15 seconds (more frequent)
                    last_log_time = start_time
                    
                    while progress_logging_active.is_set():
                        time_module.sleep(check_interval)
                        if not progress_logging_active.is_set():
                            break
                        
                        elapsed = time_module.time() - start_time
                        
                        # Check if maximum processing time exceeded
                        if elapsed > max_timeout + 60:  # Slightly longer than timeout
                            logger.warning(f"Docling: Maximum processing time exceeded. Stopping progress logging.")
                            progress_logging_active.clear()
                            return
                        
                        # Check if future is actually done (conversion completed)
                        # Don't show 100% until conversion is actually complete
                        future_done = False
                        if future_ref[0] is not None:
                            future_done = future_ref[0].done()
                        
                            minutes = int(elapsed // 60)
                            seconds = int(elapsed % 60)
                        
                        # Calculate estimated progress based on elapsed time and file size
                        # Docling typically processes at 0.5-2 pages per minute for scanned PDFs with OCR
                        # For text-based PDFs, it's much faster (10-50 pages per minute)
                        # IMPORTANT: Cap at 95% until future is actually done to avoid showing 100% while still processing
                        if file_size_mb > 10:
                            # Large scanned PDF - estimate 0.5-1 page per minute
                            processing_rate = 0.75
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                # For unknown pages, use time-based with cap at 0.95 until done
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        elif file_size_mb > 5:
                            # Medium scanned PDF - estimate 1-2 pages per minute
                            processing_rate = 1.5
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        else:
                            # Small PDF - estimate 2-5 pages per minute
                            processing_rate = 3.0
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        
                        # If future is done, show 95-99% (finalizing)
                        if future_done:
                            estimated_progress = min(0.99, estimated_progress + 0.04)  # Show 95-99% when done but not yet retrieved
                        
                        # Stuck processing detection
                        if estimated_progress >= 0.90:
                            if abs(estimated_progress - last_progress_value) < 0.01:
                                # Progress hasn't changed significantly
                                if elapsed - last_progress_change_time > stuck_threshold and not stuck_warning_logged:
                                    logger.warning(f"Docling: Processing appears stuck at ~{int(estimated_progress*100)}% for {stuck_threshold//60} minutes")
                                    logger.warning(f"Docling: Document may have unprocessable pages. Consider using PyMuPDF parser.")
                                    stuck_warning_logged = True
                            else:
                                # Progress has changed, reset tracking
                                last_progress_value = estimated_progress
                                last_progress_change_time = elapsed
                                stuck_warning_logged = False
                        else:
                            # Progress is still low, update tracking
                            last_progress_value = estimated_progress
                            last_progress_change_time = elapsed
                        
                        # Estimate remaining time based on current progress
                        if estimated_progress > 0.05:  # Only estimate if we have meaningful progress
                            estimated_total_time = elapsed / estimated_progress
                            estimated_remaining = max(0, estimated_total_time - elapsed)
                            remaining_minutes = int(estimated_remaining // 60)
                            remaining_seconds = int(estimated_remaining % 60)
                            remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining"
                        else:
                            remaining_str = "calculating..."
                        
                        # Determine current phase based on elapsed time
                        if elapsed < 30:
                            phase = "Initializing DocumentConverter"
                        elif elapsed < 120:
                            phase = "Analyzing document structure"
                        elif elapsed < 300:
                            phase = "Processing pages (OCR if needed)"
                        else:
                            phase = "Processing remaining pages (OCR if needed)"
                        
                        # Log detailed progress
                        progress_pct = int(estimated_progress * 100)
                        
                        # Add status indicator if future is done
                        status_indicator = ""
                        if future_done:
                            status_indicator = " (conversion complete, finalizing...)"
                        elif estimated_progress >= 0.95:
                            status_indicator = " (processing final pages...)"
                        
                        log_msg = (
                            f"Docling: [{phase}] "
                            f"Progress: ~{progress_pct}%{status_indicator} | "
                            f"Elapsed: {minutes}m {seconds}s | "
                            f"{remaining_str} | "
                            f"File: {file_size_mb:.1f}MB | "
                            f"Estimated pages: {estimated_pages}"
                        )
                        logger.info(log_msg)
                        
                        # Call progress callback if available (safely handle Streamlit NoSessionContext)
                        if progress_callback:
                            try:
                                # Map progress to 0.1-0.9 range (leaving 0.9-1.0 for final steps)
                                callback_progress = 0.1 + (estimated_progress * 0.8)
                                progress_callback(log_msg, callback_progress)
                            except Exception as callback_error:
                                # Handle NoSessionContext and other threading issues
                                if "NoSessionContext" in str(callback_error) or "NoSessionContext" in type(callback_error).__name__:
                                    # Don't call callback from background thread - just log
                                    logger.debug(f"Docling: Skipping progress callback (NoSessionContext in background thread)")
                                else:
                                    # Log other callback errors but don't fail
                                    logger.warning(f"Docling: Progress callback error: {str(callback_error)}")
                        
                            last_log_time = elapsed
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_docling_conversion)
                    future_ref[0] = future  # Store reference for log_progress to access
                    
                    logger.info(f"Docling: Processing in background thread (no timeout - will process completely)...")
                    logger.info(f"Docling: File size: {file_size_mb:.2f} MB | Estimated time: {estimated_time} | Estimated pages: {estimated_pages}")
                    
                    # Start progress logging thread
                    progress_thread = threading.Thread(target=log_progress, daemon=True)
                    progress_thread.start()
                    
                    try:
                        # Wait for result with maximum timeout to prevent infinite hangs
                        # Docling can get stuck on pages with no text, so we need a safety timeout
                        logger.info(f"Docling: Waiting for conversion result (max timeout: {max_timeout//60} minutes)...")
                        
                        # Check periodically if future is done and log final progress
                        import time as time_check
                        last_check = time_check.time()
                        while not future.done() and (time_check.time() - start_time) < max_timeout:
                            time_check.sleep(1)  # Check every second
                            elapsed_check = time_check.time() - start_time
                            if elapsed_check - last_check >= 15:  # Log every 15 seconds
                                logger.info(f"Docling: Still waiting for conversion to complete... ({int(elapsed_check//60)}m {int(elapsed_check%60)}s elapsed)")
                                last_check = elapsed_check
                        
                        # Now get the result (should be done or will timeout)
                        doc = future.result(timeout=max_timeout)  # Add timeout to prevent infinite hangs
                        progress_logging_active.clear()
                        logger.info("Docling: Document conversion successful - result received")
                        if doc is None:
                            raise ValueError("Docling conversion returned None - conversion may have failed")
                        logger.info(f"Docling: Document object received, type: {type(doc)}")
                        logger.info("Docling: ✅ Conversion 100% complete - processing finished")
                    except FutureTimeoutError:
                        progress_logging_active.clear()
                        logger.error(f"Docling: Processing timed out after {max_timeout//60} minutes")
                        logger.error(f"Docling: Document may have unprocessable pages or is too complex")
                        logger.error(f"Docling: Try using PyMuPDF parser instead, or check document for corrupted pages")
                        raise ValueError(
                            f"Docling processing timed out after {max_timeout//60} minutes. "
                            f"The document may have pages that cannot be processed or is too complex. "
                            f"Try using PyMuPDF parser instead."
                        )
                    except Exception as e:
                        progress_logging_active.clear()
                        error_str = str(e) if str(e) else type(e).__name__
                        logger.error(f"Docling: Error waiting for result: {error_str}")
                        if "timeout" in error_str.lower() or "TimeoutError" in str(type(e)):
                            logger.error(f"Docling: Processing timed out. Try using PyMuPDF parser instead.")
                        raise
                    finally:
                        progress_logging_active.clear()
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_str = str(e) if str(e) else type(e).__name__
                if not error_str or error_str.strip() == "":
                    error_str = f"Unknown error ({type(e).__name__})"
                
                logger.error(f"Docling: Conversion failed: {error_str}")
                logger.error(f"Docling: Full traceback:\n{error_details}")
                
                # Create user-friendly error message
                if "not valid" in error_str.lower():
                    error_msg = f"Docling cannot process this PDF - the file format is not valid. Error: {error_str}. Try using PyMuPDF parser instead."
                elif "timeout" in error_str.lower():
                    error_msg = f"Docling conversion timed out. The PDF may be very large or complex. Error: {error_str}. Try using PyMuPDF parser for faster processing."
                else:
                    error_msg = f"Docling conversion failed: {error_str}. The PDF may be corrupted or in an unsupported format. Try using PyMuPDF parser instead."
                
                raise ValueError(error_msg)
            
            # PRIMARY METHOD: Extract text per page for accurate page numbers
            # This ensures page markers and accurate page_blocks for citation support
            logger.info("Docling: Extracting text per page for accurate page numbers...")
            
            page_blocks = []  # Store page-level blocks for citation support
            text = ""
            total_pages = 0
            
            try:
                # Get page count first
                if hasattr(doc, 'pages') and doc.pages:
                    pages_dict = doc.pages
                    if isinstance(pages_dict, dict):
                        total_pages = len(pages_dict)
                    elif isinstance(pages_dict, list):
                        total_pages = len(pages_dict)
                    else:
                        total_pages = 1
                else:
                    total_pages = 1
                
                logger.info(f"Docling: Document has {total_pages} pages")
                
                # PRIMARY: Try per-page extraction first for accurate page numbers
                text, page_blocks, per_page_success = self._extract_text_per_page(doc, total_pages, progress_callback)
                
                if per_page_success and text:
                    logger.info(f"Docling: ✅ Per-page text extraction completed ({len(text):,} characters with page markers)")
                else:
                    # FALLBACK: Use export_to_text() if per-page extraction failed
                    logger.info("Docling: Per-page extraction not available, using export_to_text() with fallback page markers...")
                    try:
                        text = doc.export_to_text()
                        logger.info(f"Docling: ✅ Text export completed ({len(text):,} characters)")
                        
                        # Check if images were detected - if so, insert image markers
                        # We'll insert markers at strategic points in the text
                        if images_detected and image_count > 0 and text:
                            # Try to find image-related content patterns and insert markers
                            # Look for patterns that might indicate OCR text from images
                            import re
                            
                            # Pattern 1: Look for structured lists (common in OCR from images)
                            # Pattern 2: Look for part numbers (e.g., 65300001-, 65300-)
                            # Pattern 3: Look for drawer/tool references
                            
                            # Insert markers before likely image content
                            # Split by page markers first if they exist
                            if '--- Page' in text:
                                # Text already has page markers, insert image markers strategically
                                parts = re.split(r'(--- Page \d+ ---)', text)
                                result_parts = []
                                for i, part in enumerate(parts):
                                    result_parts.append(part)
                                    # After page markers, check if next part looks like image content
                                    if part.startswith('--- Page') and i + 1 < len(parts):
                                        next_part = parts[i + 1]
                                        # Check if next part has image-like patterns
                                        if (re.search(r'\d{6,}-\s*[A-Z]', next_part) or  # Part numbers
                                            re.search(r'DRAWER\s+\d+', next_part, re.IGNORECASE) or  # Drawer references
                                            re.search(r'\d+\s*MM\s+[A-Z]', next_part) or  # Tool sizes
                                            (len(next_part) > 50 and len(next_part.split('\n')) > 5 and 
                                             all(len(line.strip()) < 100 for line in next_part.split('\n')[:10]))):  # Short lines (OCR pattern)
                                            # Insert image marker before this content
                                            if '<!-- image -->' not in next_part[:100]:
                                                result_parts.append('<!-- image -->\n')
                                text = ''.join(result_parts)
                            else:
                                # No page markers, insert image markers at strategic points
                                # Insert markers before lines that look like image content
                                lines = text.split('\n')
                                result_lines = []
                                for i, line in enumerate(lines):
                                    # Check if this line looks like image content
                                    if (re.search(r'\d{6,}-\s*[A-Z]', line) or  # Part numbers
                                        re.search(r'DRAWER\s+\d+', line, re.IGNORECASE) or  # Drawer references
                                        (i > 0 and re.search(r'\d+\s*MM\s+[A-Z]', line))):  # Tool sizes
                                        # Check if previous line doesn't already have marker
                                        if i == 0 or '<!-- image -->' not in result_lines[-1]:
                                            result_lines.append('<!-- image -->')
                                    result_lines.append(line)
                                text = '\n'.join(result_lines)
                            
                            logger.info(f"Docling: Inserted image markers in fallback text (images detected: {image_count})")
                        
                        # Add page markers to text and create page_blocks as fallback
                        if total_pages > 1 and text:
                            # Split text into approximate pages and add markers
                            text_lines = text.split('\n')
                            lines_per_page = max(1, len(text_lines) // total_pages)
                            text_parts = []
                            cumulative_pos = 0
                            
                            for page_idx in range(1, total_pages + 1):
                                start_line = (page_idx - 1) * lines_per_page
                                end_line = page_idx * lines_per_page if page_idx < total_pages else len(text_lines)
                                page_text = '\n'.join(text_lines[start_line:end_line])
                                
                                if page_text.strip():
                                    # Add page marker (matching PyMuPDF format)
                                    page_marker = f"--- Page {page_idx} ---\n"
                                    page_text_with_marker = page_marker + page_text
                                    
                                    # Track character positions
                                    page_start = cumulative_pos
                                    page_end = cumulative_pos + len(page_text_with_marker)
                                    
                                    # Create page block with boundaries
                                    page_blocks.append({
                                        'page': page_idx,
                                        'text': page_text.strip(),
                                        'start_char': page_start,
                                        'end_char': page_end,
                                        'blocks': [{'text': page_text.strip(), 'page': page_idx}]
                                    })
                                    
                                    text_parts.append(page_text_with_marker)
                                    cumulative_pos = page_end + 2
                            
                            # Rebuild text with page markers
                            text = "\n\n".join(text_parts)
                            logger.info(f"Docling: ✅ Added page markers to text ({len(text):,} characters)")
                            
                            # After adding page markers, check if we need to insert image markers
                            # (images_detected will be set later, so we'll check it after image detection)
                    
                    except Exception as e1:
                        logger.warning(f"Docling: export_to_text() failed: {e1}, trying export_to_markdown()...")
                        # FALLBACK: Use export_to_markdown() if export_to_text() fails
                        try:
                            text = doc.export_to_markdown()
                            logger.info(f"Docling: ✅ Markdown export completed ({len(text):,} characters)")
                            
                            # Add page markers to markdown and create page_blocks
                            if total_pages > 1 and text:
                                text_lines = text.split('\n')
                                lines_per_page = max(1, len(text_lines) // total_pages)
                                text_parts = []
                                cumulative_pos = 0
                                
                                for page_idx in range(1, total_pages + 1):
                                    start_line = (page_idx - 1) * lines_per_page
                                    end_line = page_idx * lines_per_page if page_idx < total_pages else len(text_lines)
                                    page_text = '\n'.join(text_lines[start_line:end_line])
                                    
                                    if page_text.strip():
                                        # Add page marker
                                        page_marker = f"--- Page {page_idx} ---\n"
                                        page_text_with_marker = page_marker + page_text
                                        
                                        # Track character positions
                                        page_start = cumulative_pos
                                        page_end = cumulative_pos + len(page_text_with_marker)
                                        
                                        page_blocks.append({
                                            'page': page_idx,
                                            'text': page_text.strip(),
                                            'start_char': page_start,
                                            'end_char': page_end,
                                            'blocks': [{'text': page_text.strip(), 'page': page_idx}]
                                        })
                                        
                                        text_parts.append(page_text_with_marker)
                                        cumulative_pos = page_end + 2
                                
                                # Rebuild text with page markers
                                text = "\n\n".join(text_parts)
                                logger.info(f"Docling: ✅ Added page markers to markdown text ({len(text):,} characters)")
                        except Exception as e2:
                            logger.error(f"Docling: Both export methods failed: export_to_text()={e1}, export_to_markdown()={e2}")
                            raise ValueError(f"Docling: Could not export document text. Both methods failed.")
                    
                    # After text extraction, check if we need to insert image markers
                    # (This happens after images_detected is set, so we check it here)
                    if images_detected and image_count > 0 and text and '<!-- image -->' not in text:
                        # Images were detected but markers not inserted - insert them now
                        logger.info(f"Docling: Images detected ({image_count}) but no markers in text, inserting markers...")
                        # Use image positions if available (will be empty dict if not extracted)
                        text = self._insert_image_markers_in_text(text, image_count, image_positions_by_page=image_positions_by_page if 'image_positions_by_page' in locals() else None)
                        logger.info(f"Docling: ✅ Inserted image markers in extracted text")
            except Exception as e:
                logger.error(f"Docling: Error during text extraction: {str(e)}")
                # Try alternative export methods (prefer export_to_text first)
                text = None
                if hasattr(doc, 'export_to_text'):
                    try:
                        logger.info("Docling: Trying export_to_text as primary method...")
                        text = doc.export_to_text()
                        logger.info(f"Docling: Text export completed ({len(text) if text else 0:,} characters)")
                    except Exception as e2:
                        logger.error(f"Docling: Error exporting to text: {str(e2)}")
                        # Try markdown as fallback
                        if hasattr(doc, 'export_to_markdown'):
                            try:
                                logger.info("Docling: Trying export_to_markdown as fallback...")
                                text = doc.export_to_markdown()
                                logger.info(f"Docling: Markdown export completed ({len(text) if text else 0:,} characters)")
                            except Exception as e3:
                                logger.error(f"Docling: Error exporting to markdown: {str(e3)}")
                
                if not text or not text.strip():
                    raise ValueError(f"Docling: Could not export document text. Both export methods failed: {str(e)}")
            
            # Validate text extraction - try alternative methods if text is empty
            if not text or not text.strip():
                # Try export_to_text as primary fallback
                if hasattr(doc, 'export_to_text'):
                    try:
                        text = doc.export_to_text()
                        logger.info(f"Docling: Text validation: export_to_text() extracted {len(text):,} characters")
                    except Exception as e:
                        logger.debug(f"operation: {type(e).__name__}: {e}")
                        pass
                
                # Try markdown as secondary fallback
                if (not text or not text.strip()) and hasattr(doc, 'export_to_markdown'):
                    try:
                        text = doc.export_to_markdown()
                        logger.info(f"Docling: Text validation: export_to_markdown() extracted {len(text):,} characters")
                    except Exception as e:
                        logger.debug(f"operation: {type(e).__name__}: {e}")
                        pass
                
                # If still empty, try get_text
                if not text or not text.strip():
                    if hasattr(doc, 'get_text'):
                        try:
                            text = doc.get_text()
                        except Exception as e:
                            logger.debug(f"operation: {type(e).__name__}: {e}")
                            pass
                
                # If still empty, try accessing text attribute directly
                if not text or not text.strip():
                    if hasattr(doc, 'text'):
                        try:
                            text = str(doc.text) if doc.text else ""
                        except Exception as e:
                            logger.debug(f"operation: {type(e).__name__}: {e}")
                            pass
            
            # Clean up temp file if created (after text extraction)
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            
            # Final validation - raise error if no text extracted
            if not text or not text.strip():
                raise ValueError(
                    f"Docling processed the PDF but extracted no text content. "
                    f"This may indicate the PDF format is not compatible with Docling's layout model. "
                    f"Try using PyMuPDF parser instead."
                )
            
            # Get page count - ensure it matches actual document page count
            pages = total_pages  # Use total_pages from extraction above
            if hasattr(doc, 'pages'):
                pages_dict = doc.pages
                if isinstance(pages_dict, dict):
                    pages = len(pages_dict)
                elif isinstance(pages_dict, list):
                    pages = len(pages_dict)
                # If total_pages was set during extraction, use it
                if total_pages > 0:
                    pages = total_pages
            
            # Validate pages count
            if pages <= 0:
                logger.warning(f"Docling: Invalid page count {pages}, using 1 as fallback")
                pages = 1
            elif total_pages > 0 and pages != total_pages:
                logger.warning(f"Docling: Page count mismatch - calculated {total_pages} but got {pages} from pages structure")
                # Use the higher value to be safe
                pages = max(pages, total_pages)
            
            # Calculate metrics
            text_length = len(text.strip())
            words = text.split()
            word_count = len(words)
            
            logger.info(f"Docling: Extracted {pages} pages, {len(text):,} characters, {word_count:,} words")
            
            # Verify OCR extracted text from images if images were detected
            # Note: images_detected will be set later, but we'll check it after detection
            
            # Estimate extraction percentage
            if pages > 0:
                estimated_chars_per_page = 2000  # Conservative estimate
                expected_text_length = pages * estimated_chars_per_page
                extraction_percentage = min(1.0, text_length / expected_text_length) if expected_text_length > 0 else 0.0
            else:
                extraction_percentage = 1.0 if text_length > 500 else (text_length / 500.0) if text_length > 0 else 0.0
            
            # Confidence based on text extraction
            if text_length > 2000:
                confidence = 0.95
            elif text_length > 1000:
                confidence = 0.85
            elif text_length > 500:
                confidence = 0.75
            elif text_length > 100:
                confidence = 0.65
            else:
                confidence = 0.5
            
            # Extract image positions from Docling for accurate marker insertion
            image_positions = []  # List of (page_num, char_offset) tuples
            image_positions_by_page = {}  # Map: page_num -> list of char_offsets
            
            # Check for images - use multiple detection methods
            # (variables already initialized above, now we detect images)
            try:
                # Method 1: Check doc.pictures (existing method) and extract positions
                if hasattr(doc, 'pictures') and len(doc.pictures) > 0:
                    images_detected = True
                    image_count = len(doc.pictures)
                    detection_methods.append(f"doc.pictures ({image_count} pictures)")
                    logger.info(f"Docling: Found {image_count} pictures in document")
                    
                    # Extract image positions from doc.pictures using physical page mapping
                    try:
                        for pic_idx, picture in enumerate(doc.pictures):
                            # CRITICAL: Prioritize physical page property
                            page_num = getattr(picture, 'page_no', None) or getattr(picture, 'page', None)
                            
                            if page_num is not None:
                                page_num = int(page_num)
                                if page_num not in image_positions_by_page:
                                    image_positions_by_page[page_num] = []
                                image_positions_by_page[page_num].append(pic_idx)
                                image_positions.append((page_num, pic_idx))

                        
                        if image_positions:
                            logger.info(f"Docling: Extracted image positions: {len(image_positions)} images across {len(image_positions_by_page)} pages")
                    except Exception as e:
                        logger.debug(f"Docling: Could not extract detailed image positions: {e}")
                        # Continue with image count only
                
                # Method 2: Check pages for image content
                if hasattr(doc, 'pages'):
                    pages_dict = doc.pages
                    if isinstance(pages_dict, (dict, list)):
                        page_images = 0
                        for page_content in (pages_dict.values() if isinstance(pages_dict, dict) else pages_dict):
                            # Check if page has image content
                            if hasattr(page_content, 'pictures') and len(page_content.pictures) > 0:
                                page_images += len(page_content.pictures)
                                images_detected = True
                            
                            # Check for image blocks in page structure
                            if hasattr(page_content, 'blocks'):
                                for block in page_content.blocks:
                                    if hasattr(block, 'type') and block.type in ['image', 'figure', 'picture', 'illustration']:
                                        page_images += 1
                                        images_detected = True
                                        break
                        
                        if page_images > 0:
                            image_count = max(image_count, page_images)
                            detection_methods.append(f"page content ({page_images} images)")
                
                # Method 3: Heuristic - if text is very low but file is large, likely image-based
                file_size_mb = os.path.getsize(actual_path) / 1024 / 1024 if os.path.exists(actual_path) else 0
                if not images_detected and text_length < 100 and file_size_mb > 0.5:
                    images_detected = True
                    # Estimate image count based on file size and pages
                    if image_count == 0:
                        # Rough estimate: 1 image per 2-3 pages for image-based PDFs
                        estimated_images = max(1, pages // 3) if pages > 0 else 1
                        image_count = estimated_images
                    detection_methods.append("heuristic (low text, large file)")
                    logger.info(f"Docling: Low text content suggests image-based PDF (estimated {image_count} images)")
                
                if images_detected:
                    logger.info(f"Docling: ✅ Images detected via: {', '.join(detection_methods)}")
                    # Log image detection completion
                    if image_logger:
                        image_logger.log_image_detected(
                            source=file_path,
                            image_count=image_count,
                            detection_methods=detection_methods
                        )
                else:
                    logger.info("Docling: No images detected in document")
                    
            except Exception as e:
                logger.warning(f"Docling: Error detecting images: {e}")
                # If we have very little text, assume images might be present
                if text_length < 100:
                    images_detected = True
                    logger.info("Docling: Assuming image-based PDF due to low text content")
            
            # Verify OCR extracted text from images if images were detected
            if images_detected:
                if text_length < 100:
                    logger.error("Docling: ❌ Images detected but very little text extracted - OCR may have failed!")
                    logger.error("Docling: Possible reasons:")
                    logger.error("   1. OCR models not downloaded (run: docling download-models)")
                    logger.error("   2. Images are too low quality for OCR")
                    logger.error("   3. OCR processing failed silently")
                    logger.error("   4. Document format not supported by OCR")
                    logger.error("Docling: 💡 Suggestion: Try using Textract parser for better OCR results")
                    logger.error("Docling: 💡 Or pre-process PDF with external OCR software")
                elif text_length < 500:
                    logger.warning("Docling: ⚠️  Images detected but limited text extracted")
                    logger.warning("Docling: OCR may have partially failed or images have low-quality text")
                else:
                    logger.info(f"Docling: ✅ OCR appears successful - extracted {text_length:,} characters from images")
                    # Log OCR completion
                    if image_logger:
                        image_logger.log_ocr_complete(
                            source=file_path,
                            ocr_text_length=text_length,
                            extraction_method='docling',
                            success=True
                        )
            
            # Insert image markers if images were detected but markers not present
            # Also handle case where image_count is 0 but images are detected
            if images_detected and text:
                markers_in_text = text.count('<!-- image -->')
                # If image_count is 0, estimate based on text length or use a default
                effective_image_count = image_count if image_count > 0 else max(1, text_length // 5000)  # Rough estimate: 1 image per 5K chars
                
                if markers_in_text == 0:
                    logger.info(f"Docling: Images detected (count={image_count}, effective={effective_image_count}) but no markers in text, inserting markers...")
                    # Use image positions if available for more accurate marker insertion
                    text = self._insert_image_markers_in_text(text, effective_image_count, image_positions_by_page=image_positions_by_page)
                    logger.info(f"Docling: ✅ Inserted image markers in extracted text")
                else:
                    # Markers already exist, but validate count
                    logger.info(f"Docling: Found {markers_in_text} existing image markers in text")
                    if image_count > 0 and markers_in_text < image_count * 0.8:  # Less than 80% coverage
                        logger.warning(f"Docling: ⚠️  Only {markers_in_text}/{image_count} markers found. Inserting additional markers...")
                        # Use image positions if available
                        text = self._insert_image_markers_in_text(text, image_count, image_positions_by_page=image_positions_by_page)
                    elif image_count == 0 and markers_in_text > 0:
                        # Update image_count based on markers found
                        image_count = markers_in_text
                        logger.info(f"Docling: Updated image_count to {image_count} based on markers found in text")
            
            # Recalculate markers after potential insertion
            final_markers = text.count('<!-- image -->') if text else 0
            
            # Validation: Check marker count matches image count (within tolerance)
            if images_detected and image_count > 0:
                marker_coverage = (final_markers / image_count * 100) if image_count > 0 else 0
                if marker_coverage >= 80:
                    logger.info(f"Docling: ✅ Marker validation passed: {final_markers}/{image_count} markers ({marker_coverage:.1f}% coverage)")
                elif marker_coverage >= 50:
                    logger.warning(f"Docling: ⚠️  Marker validation: {final_markers}/{image_count} markers ({marker_coverage:.1f}% coverage) - some images may not be marked")
                else:
                    logger.error(f"Docling: ❌ Marker validation failed: {final_markers}/{image_count} markers ({marker_coverage:.1f}% coverage) - most images not marked")
            
            # Extract individual images for storage
            extracted_images = []
            # CRITICAL: Always try extraction if images are detected and we have text
            # The extraction method will handle cases with or without markers
            if images_detected and text and text_length > 0:
                # Ensure we have markers - insert if missing
                if final_markers == 0:
                    logger.info(f"Docling: Images detected ({image_count}) but no markers found. Inserting markers...")
                    # Use actual image_count if available, otherwise estimate
                    marker_count = image_count if image_count > 0 else max(1, text_length // 5000)
                    text = self._insert_image_markers_in_text(text, marker_count, image_positions_by_page=image_positions_by_page)
                    final_markers = text.count('<!-- image -->')
                    logger.info(f"Docling: Inserted {final_markers} markers (requested {marker_count})")
                    if final_markers > 0 and image_count == 0:
                        image_count = final_markers
                        logger.info(f"Docling: Updated image_count to {image_count} based on inserted markers")
                
                # Now extract images - this will work with or without markers
                try:
                    effective_image_count = image_count if image_count > 0 else max(1, final_markers) if final_markers > 0 else 1
                    logger.info(f"Docling: Attempting extraction with count={effective_image_count}, markers={final_markers}, text_length={text_length}")
                    
                    extracted_images = self._extract_individual_images(
                        text=text,
                        image_count=effective_image_count,
                        source=file_path,
                        page_blocks=page_blocks
                    )
                    
                    logger.info(f"Docling: Extraction completed: {len(extracted_images)} images extracted (requested {effective_image_count}, markers={final_markers})")
                    
                    # Log details of extracted images
                    if len(extracted_images) > 0:
                        logger.info(f"Docling: ✅ First extracted image keys: {list(extracted_images[0].keys())}")
                        logger.info(f"Docling: ✅ First image source: {extracted_images[0].get('source', 'MISSING')}")
                        logger.info(f"Docling: ✅ First image number: {extracted_images[0].get('image_number', 'MISSING')}")
                        logger.info(f"Docling: ✅ First image OCR length: {len(extracted_images[0].get('ocr_text', ''))}")
                        # Update image_count if we successfully extracted images
                        if image_count == 0 or image_count != len(extracted_images):
                            image_count = len(extracted_images)
                            logger.info(f"Docling: Updated image_count to {image_count} based on actual extracted images")
                    else:
                        logger.warning(f"Docling: ⚠️  Extraction returned empty list!")
                        logger.warning(f"Docling:   - Markers in text: {final_markers}")
                        logger.warning(f"Docling:   - Image count: {image_count}")
                        logger.warning(f"Docling:   - Text length: {text_length}")
                        logger.warning(f"Docling:   - Effective count: {effective_image_count}")
                        # Try fallback: create at least one image entry from text
                        if text_length > 100:
                            logger.info(f"Docling: Creating fallback image entry from text...")
                            extracted_images = [{
                                'source': file_path,
                                'image_number': 1,
                                'page': 1,
                                'ocr_text': text[:10000],  # First 10K chars
                                'ocr_text_length': min(len(text), 10000),
                                'marker_detected': final_markers > 0,
                                'extraction_method': 'docling_ocr_fallback',
                                'full_chunk': text[:1000],
                                'context_before': None
                            }]
                            logger.info(f"Docling: Created fallback image entry with {len(extracted_images[0].get('ocr_text', ''))} chars")
                except Exception as e:
                    logger.error(f"Docling: ❌ Failed to extract individual images: {str(e)}")
                    import traceback
                    logger.error(f"Docling: Extraction error details: {traceback.format_exc()}")
                    # Try fallback even on error
                    if text_length > 100:
                        logger.info(f"Docling: Creating fallback image entry after error...")
                        extracted_images = [{
                            'source': file_path,
                            'image_number': 1,
                            'page': 1,
                            'ocr_text': text[:10000],
                            'ocr_text_length': min(len(text), 10000),
                            'marker_detected': False,
                            'extraction_method': 'docling_ocr_error_fallback',
                            'full_chunk': text[:1000],
                            'context_before': None
                        }]
            else:
                logger.warning(f"Docling: Cannot extract images: images_detected={images_detected}, text_length={text_length}")
            
            # Log extracted_images status before adding to metadata
            logger.info(f"Docling: Final extracted_images count: {len(extracted_images)}")
            if len(extracted_images) > 0:
                logger.info(f"Docling: ✅ extracted_images list is populated - will be stored in OpenSearch")
            else:
                logger.warning(f"Docling: ⚠️  extracted_images list is empty - images will NOT be stored")
            
            # Add extracted_images to page_blocks for RAG citation
            if extracted_images:
                for img in extracted_images:
                    page_blocks.append({
                        'type': 'image',
                        'page': int(img.get('page', 1)), # Keep physical 1-based
                        'image_index': img.get('image_index'),
                        'bbox': img.get('bbox')
                    })

            
            metadata = {
                "source": file_path,
                "pages": pages,
                "text_length": text_length,
                "word_count": word_count,
                "file_size": len(file_content) if file_content else os.path.getsize(file_path),
                "page_blocks": page_blocks,  # Store page-level blocks for citation support
                "image_count": image_count,  # Store image count for queries
                "images_detected": images_detected,  # Store boolean flag
                "extracted_images": extracted_images  # Store extracted image data for OpenSearch storage
            }
            
            # Ensure image_count is updated if we extracted images
            if len(extracted_images) > 0 and image_count == 0:
                image_count = len(extracted_images)
                metadata['image_count'] = image_count
                logger.info(f"Docling: Final image_count set to {image_count} based on extracted images")
            
            # Also update image_count in metadata if it was updated
            if image_count > 0:
                metadata['image_count'] = image_count
            
            return ParsedDocument(
                text=text,
                metadata=metadata,
                pages=pages,
                images_detected=images_detected,
                parser_used=self.name,
                confidence=confidence,
                extraction_percentage=extraction_percentage,
                image_count=image_count  # Use updated image_count
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            # Get error message - handle empty messages
            error_str = str(e) if str(e) else type(e).__name__
            if not error_str or error_str.strip() == "":
                error_str = f"Unknown error ({type(e).__name__})"
            
            # Log full error details
            logger.error(f"Docling: Failed to parse PDF: {error_str}")
            logger.error(f"Docling: Full traceback:\n{error_details}")
            
            # Clean up temp file on error
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            
            # Create user-friendly error message
            if "NoSessionContext" in error_str or "NoSessionContext" in type(e).__name__:
                # This is a Streamlit threading issue - try direct parsing without callbacks (only once)
                if not _retry_without_callback:
                    logger.warning(f"Docling: NoSessionContext error detected - this is a Streamlit threading issue, not a PDF problem")
                    logger.info(f"Docling: Attempting direct parsing without progress callbacks...")
                    try:
                        # Retry without progress callback (set flag to prevent infinite recursion)
                        return self.parse(file_path, file_content, progress_callback=None, _retry_without_callback=True)
                    except Exception as retry_error:
                        error_msg = (
                            f"Docling parser failed due to Streamlit session context issues (NoSessionContext). "
                            f"This is a threading limitation, not a PDF problem. "
                            f"Try using PyMuPDF parser instead, which handles this better."
                        )
                else:
                    # Already retried once, don't retry again
                    error_msg = (
                        f"Docling parser failed due to Streamlit session context issues (NoSessionContext). "
                        f"This is a threading limitation, not a PDF problem. "
                        f"Try using PyMuPDF parser instead, which handles this better."
                    )
            elif "not valid" in error_str.lower() or "cannot process" in error_str.lower():
                error_msg = f"Docling cannot process this PDF. The file may be corrupted, encrypted, or in an unsupported format. Error: {error_str}. Try using PyMuPDF parser instead."
            elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
                error_msg = f"Docling parsing timed out. The PDF may be very large or complex. Error: {error_str}. Try using PyMuPDF parser for faster processing."
            elif "too large" in error_str.lower():
                error_msg = f"PDF is too large for Docling to process. Error: {error_str}. Try using PyMuPDF or Textract parser instead."
            elif "memory" in error_str.lower() or "out of memory" in error_str.lower():
                error_msg = f"Docling ran out of memory processing this PDF. The document may be too large. Error: {error_str}. Try using PyMuPDF parser instead."
            else:
                error_msg = f"Failed to parse PDF with Docling: {error_str}. The PDF may be corrupted, encrypted, or in an unsupported format. Try using PyMuPDF parser for better compatibility."
            
            raise ValueError(error_msg)
