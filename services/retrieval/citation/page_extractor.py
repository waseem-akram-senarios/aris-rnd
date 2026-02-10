"""
Page number extraction, source attribution, and validation for citations.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import re
import logging
from typing import List, Dict, Optional, Any

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class PageExtractionMixin:
    """Mixin providing page number extraction, source attribution, and validation for citations capabilities."""
    
    def _extract_source_from_chunk(self, doc, chunk_text: str, fallback_sources: List[str] = None, ui_config: Optional[Dict] = None) -> tuple:
        """
        Extract source document name from chunk metadata or text with confidence scoring.
        Ensures accurate citation by preserving source through the entire pipeline.
        
        Args:
            doc: Document object with metadata
            chunk_text: Chunk text content
            fallback_sources: List of source names as fallback
            ui_config: Optional UI configuration (temperature, max_tokens, active_sources)
        
        Returns:
            Tuple of (source_name, confidence_score)
            confidence: 1.0 (metadata) > 0.7 (alt_metadata) > 0.5 (text_marker) > 0.3 (document_index) > 0.1 (fallback)
        """
        import re
        # os is already imported at module level, no need to import again
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Use UI config if provided, otherwise use instance config
        if ui_config is None:
            ui_config = getattr(self, 'ui_config', {})
        
        # Log UI configuration for debugging
        if ui_config:
            logger.debug(f"Citation extraction using UI config: temperature={ui_config.get('temperature')}, max_tokens={ui_config.get('max_tokens')}")
        
        def normalize_source(source_str: str) -> str:
            """Normalize source path to filename and validate."""
            if not source_str:
                return source_str
            source_str = str(source_str).strip()
            # Extract filename from path if it's a path
            if os.sep in source_str or '/' in source_str or '\\' in source_str:
                source_str = os.path.basename(source_str)
            return source_str
        
        def validate_against_document_index(source_str: str) -> bool:
            """Check if source exists in document_index for validation."""
            if not hasattr(self, 'document_index') or not self.document_index:
                return False
            # Check if source (or normalized version) exists in document_index
            normalized = normalize_source(source_str)
            for doc_id in self.document_index.keys():
                if normalize_source(doc_id) == normalized or doc_id == source_str:
                    return True
            return False
        
        # First try metadata - this is the most reliable source (confidence: 1.0)
        source = doc.metadata.get('source', None)
        if source:
            source = normalize_source(source)
            if source and source != 'Unknown' and source != '':
                # Validate against document_index if available
                if validate_against_document_index(source):
                    logger.debug(f"Source extracted from metadata (validated): {source}")
                return source, 1.0
        
        # Try alternative metadata keys (for compatibility) (confidence: 0.7)
        alt_keys = ['document_name', 'file_name', 'filename', 'doc_name']
        for key in alt_keys:
            source = doc.metadata.get(key, None)
            if source:
                source = normalize_source(source)
                if source and source != 'Unknown' and source != '':
                    if validate_against_document_index(source):
                        logger.debug(f"Found source in alternate metadata key '{key}' (validated): {source}")
                    else:
                        logger.debug(f"Found source in alternate metadata key '{key}': {source}")
                    return source, 0.7
        
        # Try to extract from chunk text markers (less reliable but useful fallback) (confidence: 0.5)
        source_match = re.search(r'\[Source\s+\d+:\s*([^\]]+?)(?:\s*\(Page\s+\d+\))?\]', chunk_text)
        if source_match:
            source = source_match.group(1).strip()
            source = re.sub(r'\s*\(Page\s+\d+\)', '', source)
            source = normalize_source(source)
            if source and source != 'Unknown':
                if validate_against_document_index(source):
                    logger.debug(f"Extracted source from chunk text marker (validated): {source}")
                else:
                    logger.debug(f"Extracted source from chunk text marker: {source}")
                return source, 0.5
        
        # Try document_index lookup using chunk_index (confidence: 0.3)
        if hasattr(self, 'document_index') and self.document_index and doc.metadata.get('chunk_index') is not None:
            chunk_index = doc.metadata.get('chunk_index')
            for doc_id, chunk_indices in self.document_index.items():
                if chunk_index in chunk_indices:
                    source = normalize_source(doc_id)
                    if source and source != 'Unknown':
                        logger.info(f"Recovered source from document_index: {source}")
                        return source, 0.3
        
        # Fallback to provided sources list (last resort) (confidence: 0.1)
        if fallback_sources:
            for fallback_source in fallback_sources:
                if fallback_source and str(fallback_source).strip() and str(fallback_source).strip() != 'Unknown':
                    source = normalize_source(str(fallback_source).strip())
                    if source and source != 'Unknown':
                        logger.debug(f"Using fallback source: {source}")
                        return source, 0.1
        
        # Log warning if we couldn't find a source
        logger.warning(f"Could not extract source from chunk. Metadata keys: {list(doc.metadata.keys()) if hasattr(doc, 'metadata') else 'N/A'}")
        return 'Unknown', 0.0
    
    def _get_page_from_char_position(self, start_char: Optional[int], end_char: Optional[int], 
                                     page_blocks: List[Dict]) -> Optional[int]:
        """
        Find page number using precise character position matching.
        This is the most accurate method when character positions are available.
        
        Args:
            start_char: Starting character position of chunk in document
            end_char: Ending character position of chunk in document
            page_blocks: List of page block dictionaries with start_char, end_char, page
        
        Returns:
            Page number with maximum overlap, or None if no match found
        """
        if start_char is None or not page_blocks:
            return None
        
        # Use end_char if available, otherwise estimate from start_char
        chunk_end = end_char if end_char is not None else start_char + 500  # Estimate 500 chars
        
        # Calculate overlap with each page
        page_overlaps = {}
        
        for block in page_blocks:
            if not isinstance(block, dict):
                continue
            
            block_start = block.get('start_char')
            block_end = block.get('end_char')
            block_page = block.get('page')
            
            # Skip if missing required fields
            if block_start is None or block_page is None:
                continue
            
            # Use block_end if available, otherwise estimate
            if block_end is None:
                block_text = block.get('text', '')
                block_end = block_start + len(block_text) if block_text else block_start + 1000
            
            # Calculate overlap
            overlap_start = max(start_char, block_start)
            overlap_end = min(chunk_end, block_end)
            
            if overlap_start < overlap_end:
                overlap_chars = overlap_end - overlap_start
                chunk_size = chunk_end - start_char
                
                # Calculate overlap percentage
                if chunk_size > 0:
                    overlap_ratio = overlap_chars / chunk_size
                    
                    # Track page with maximum overlap
                    if block_page not in page_overlaps:
                        page_overlaps[block_page] = {
                            'overlap_chars': 0,
                            'overlap_ratio': 0.0,
                            'start_char': block_start,
                            'end_char': block_end
                        }
                    
                    # Accumulate overlap for this page
                    page_overlaps[block_page]['overlap_chars'] += overlap_chars
                    if overlap_ratio > page_overlaps[block_page]['overlap_ratio']:
                        page_overlaps[block_page]['overlap_ratio'] = overlap_ratio
        
        if not page_overlaps:
            return None
        
        # Find page with maximum overlap
        # Prefer page with most character overlap, then highest ratio
        best_page = max(page_overlaps.keys(), 
                       key=lambda p: (page_overlaps[p]['overlap_chars'], 
                                     page_overlaps[p]['overlap_ratio']))
        
        # Only return if there's significant overlap (>10% of chunk)
        if page_overlaps[best_page]['overlap_ratio'] > 0.1:
            return int(best_page)
        
        return None

    def _validate_page_assignment(self, page: int, doc, chunk_text: str, page_blocks: List[Dict]) -> tuple:
        """
        Cross-validate a proposed page number against multiple signals to improve accuracy.

        Returns:
            (validated_page, confidence_score)
        """
        import re
        from scripts.setup_logging import get_logger

        logger = get_logger("aris_rag.rag_system")

        validation_sources = []

        # 1) source_page metadata
        source_page = doc.metadata.get("source_page", None)
        if source_page is not None:
            try:
                if int(source_page) == int(page):
                    validation_sources.append(("source_page", 1.0))
            except Exception as e:
                logger.debug(f"_validate_page_assignment: {type(e).__name__}: {e}")
                pass

        # 2) page metadata
        page_meta = doc.metadata.get("page", None)
        if page_meta is not None:
            try:
                if int(page_meta) == int(page):
                    validation_sources.append(("page_metadata", 0.8))
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                pass

        # 3) character-position match (highest quality when available)
        start_char = doc.metadata.get("start_char", None)
        end_char = doc.metadata.get("end_char", None)
        if start_char is not None and page_blocks:
            try:
                page_from_pos = self._get_page_from_char_position(start_char, end_char, page_blocks)
                if page_from_pos is not None and int(page_from_pos) == int(page):
                    validation_sources.append(("char_position", 1.0))
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                pass

        # 4) explicit text marker in chunk
        page_match = re.search(r"---\s*Page\s+(\d+)\s*---", chunk_text or "")
        if page_match:
            try:
                if int(page_match.group(1)) == int(page):
                    validation_sources.append(("text_marker", 0.6))
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                pass

        if len(validation_sources) >= 2:
            max_conf = max(s[1] for s in validation_sources)
            confidence = min(1.0, max_conf + 0.1)  # small boost when signals agree
            logger.debug(f"Page {page} validated by multiple sources: {validation_sources} (confidence={confidence:.2f})")
            return int(page), confidence

        if len(validation_sources) == 1:
            src, conf = validation_sources[0]
            logger.debug(f"Page {page} validated by {src} (confidence={conf:.2f})")
            return int(page), conf

        # No corroboration; still return the candidate but with reduced confidence
        logger.debug(f"Page {page} could not be corroborated; returning lower confidence")
        return int(page), 0.5
    
    def _extract_page_number(self, doc, chunk_text: str) -> tuple:
        """
        Extract and validate page number from multiple sources with enhanced accuracy.
        PRIORITY: Image metadata > Character position matching > source_page > page_blocks > page > text markers
        
        ENHANCED: Now prioritizes image metadata (page from image_ref or image_page) for OCR content.
        This fixes QA issue where page numbers were incorrect for image-transcribed content.
        
        Args:
            doc: Document object with metadata
            chunk_text: Chunk text content
        
        Returns:
            Tuple of (page_number, confidence_score)
            confidence: 1.0 (image metadata) > 1.0 (char position) > 1.0 (source_page) > 0.9 (page_blocks) > 0.8 (page) > 0.6 (text marker) > 0.4 (fallback)
        """
        import re
        from typing import Optional
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Get document's actual page count from metadata
        doc_pages = doc.metadata.get('pages', None)
        
        # Validate page number is within reasonable range
        def validate_page(page_num) -> bool:
            """Validate page number is within reasonable range (1-10000)."""
            try:
                page_int = int(page_num)
                return 1 <= page_int <= 10000
            except (ValueError, TypeError):
                logger.debug("validate_page: exception suppressed")
                return False
        
        # Validate extracted page against document page count
        def validate_against_doc(page_num) -> bool:
            """Validate page number is within document's actual page range."""
            if page_num is None:
                return False
            if not validate_page(page_num):  # Existing range check (1-10000)
                return False
            # Only reject if doc_pages is known AND positive (>0).
            # doc_pages == 0 or None means unknown total pages - don't reject.
            if doc_pages is not None and doc_pages > 0 and page_num > doc_pages:
                source = doc.metadata.get('source', 'Unknown')
                logger.warning(
                    f"Page {page_num} exceeds document page count {doc_pages}. "
                    f"Source: {source}"
                )
                return False
            return True
        
        # PRIORITY 1: TEXT MARKERS (Most accurate - explicit page delimiters in content)
        # Find ALL page markers and use the FIRST one (indicates starting page of content)
        # These markers are inserted during PDF parsing and are the most reliable source
        page_markers = re.findall(r'---\s*Page\s+(\d+)\s*---', chunk_text)
        if page_markers:
            first_page = int(page_markers[0])
            if validate_against_doc(first_page):
                logger.debug(f"📄 [TEXT MARKER] Page {first_page} from '--- Page X ---' marker (highest priority)")
                return first_page, 0.98
        
        # PRIORITY 2: METADATA (Only if no text markers found)
        # Check for explicitly stored page number in metadata
        # Note: Metadata page can be inaccurate for chunked content spanning multiple pages
        meta_page = doc.metadata.get('page')
        if meta_page is not None:
            try:
                page_val = int(meta_page)
                if validate_against_doc(page_val):
                    return page_val, 0.85
            except (ValueError, TypeError):
                logger.debug("operation: exception suppressed")
                pass


        # Check for "Source: Page X" patterns (common in some document formats)
        source_page_match = re.search(r'Source:.*?Page\s+(\d+)', chunk_text, re.IGNORECASE)
        if source_page_match:
            source_page_num = int(source_page_match.group(1))
            if validate_against_doc(source_page_num):
                logger.info(f"📄 [TEXT MARKER] Page {source_page_num} from 'Source: ... Page X' pattern")
                return source_page_num, 0.95
        
        # PRIORITY 1: Image metadata (only if no text markers found)
        # Check if this chunk is from an image (OCR content)
        image_ref = doc.metadata.get('image_ref', None)
        image_page = doc.metadata.get('image_page', None)
        has_image = doc.metadata.get('has_image', False)
        image_index = doc.metadata.get('image_index', None)
        
        # For image content, also check for page patterns in the text
        if has_image or image_index is not None or image_ref or '<!-- image -->' in chunk_text:
            # Check for "Image X on Page Y" pattern (various formats)
            image_page_patterns = [
                r'Image\s+\d+\s+on\s+[Pp]age\s+(\d+)',           # "Image 5 on Page 3"
                r'Imagen\s+\d+\s+(?:en\s+)?[Pp][áa]gina\s+(\d+)',  # Spanish: "Imagen 5 en Página 3"
                r'Fig(?:ure)?\s*\d+.*?[Pp]age\s+(\d+)',           # "Figure 5 - Page 3"
                r'[Pp]age\s+(\d+).*?Image\s+\d+',                  # "Page 3 - Image 5"
            ]
            for pattern in image_page_patterns:
                image_page_match = re.search(pattern, chunk_text[:500], re.IGNORECASE)
                if image_page_match:
                    img_page_num = int(image_page_match.group(1))
                    if validate_against_doc(img_page_num):
                        logger.info(f"📸 [IMAGE PAGE] Page {img_page_num} extracted from image-page pattern in text")
                        return img_page_num, 0.95
            
            # Check for "Page X" pattern at start of text
            page_ref_match = re.search(r'^[Pp]age\s+(\d+)', chunk_text[:100])
            if page_ref_match:
                img_page_num = int(page_ref_match.group(1))
                if validate_against_doc(img_page_num):
                    logger.info(f"📸 [IMAGE PAGE] Page {img_page_num} from page reference at start of image content")
                    return img_page_num, 0.9
            
            # Check for footer-style page numbers (common in OCR)
            footer_page_patterns = [
                r'[-–—]\s*(\d+)\s*[-–—]',                        # "- 5 -" or "— 5 —"
                r'\bp(?:g|age)?\.?\s*(\d+)\b',                    # "pg. 5" or "p. 5" or "page 5"
                r'\bpágina\s+(\d+)\b',                            # Spanish "página 5"
            ]
            for pattern in footer_page_patterns:
                footer_match = re.search(pattern, chunk_text[-200:], re.IGNORECASE)
                if footer_match:
                    footer_page = int(footer_match.group(1))
                    if validate_against_doc(footer_page):
                        logger.info(f"📸 [IMAGE PAGE] Page {footer_page} from footer pattern in OCR content")
                        return footer_page, 0.85
        
        # If no text markers, use image metadata
        # IMPROVED: Accept page 1 if there's corroborating evidence (start_char is small)
        if image_ref and isinstance(image_ref, dict):
            img_page = image_ref.get('page') or image_ref.get('image_page') or image_ref.get('source_page')
            if img_page and validate_against_doc(img_page):
                img_page_int = int(img_page)
                start_char_val = doc.metadata.get('start_char', None)
                
                # Accept page 1 if start_char is at beginning of document (< 2000 chars)
                # or if image_index is 0 or 1 (first images are usually on page 1)
                img_idx = doc.metadata.get('image_index', 0) or image_ref.get('image_index', 0)
                is_early_content = (start_char_val is not None and start_char_val < 2000) or (img_idx in [0, 1])
                
                if img_page_int > 1:
                    logger.info(f"📸 [IMAGE METADATA] Page {img_page} from image_ref")
                    return img_page_int, 0.8
                elif is_early_content:
                    # Page 1 is likely correct for early content
                    logger.info(f"📸 [IMAGE METADATA] Page 1 from image_ref (corroborated by early position)")
                    return 1, 0.75
                else:
                    logger.debug(f"📸 [IMAGE METADATA] Page {img_page} from image_ref (uncertain - checking other sources)")
        
        if image_page and validate_against_doc(image_page):
            img_page_int = int(image_page)
            if img_page_int > 1:
                logger.info(f"📸 [IMAGE METADATA] Page {image_page} from image_page metadata")
                return img_page_int, 0.8
            else:
                # Check if it's early content
                start_char_val = doc.metadata.get('start_char', None)
                if start_char_val is not None and start_char_val < 2000:
                    logger.info(f"📸 [IMAGE METADATA] Page 1 from image_page (corroborated by early position)")
                    return 1, 0.75
        
        # PRIORITY 1: Character position-based matching (HIGHEST ACCURACY for text content)
        start_char = doc.metadata.get('start_char', None)
        end_char = doc.metadata.get('end_char', None)
        page_blocks = doc.metadata.get('page_blocks', [])
        
        if start_char is not None and page_blocks:
            page_from_position = self._get_page_from_char_position(start_char, end_char, page_blocks)
            if page_from_position and validate_against_doc(page_from_position):
                logger.debug(f"Page extracted from character position: {page_from_position} (start_char={start_char}, end_char={end_char})")
                return int(page_from_position), 1.0  # Highest confidence for position-based matching
        
        # Cross-validate with page_blocks metadata if available (enhanced accuracy)
        def get_page_from_page_blocks(chunk_text: str, page_blocks: list) -> Optional[int]:
            """Extract page number from page_blocks metadata using character positions or text matching."""
            if not page_blocks:
                return None
            
            # PRIORITY: Character position matching (most accurate)
            if start_char is not None:
                page_from_pos = self._get_page_from_char_position(start_char, end_char, page_blocks)
                if page_from_pos:
                    logger.debug(f"Page from character position matching: {page_from_pos}")
                    return page_from_pos
            
            # Fallback: Text-based matching (for chunks without character positions)
            if not chunk_text:
                return None
            
            chunk_preview = chunk_text[:200].strip()
            if not chunk_preview:
                return None
            
            # Enhanced text matching: try to match with page-level blocks
            # Some page_blocks have nested structure with 'blocks' array
            best_match = None
            best_match_score = 0.0
            
            for block in page_blocks:
                if not isinstance(block, dict):
                    continue
                
                block_page = block.get('page')
                if not block_page:
                    continue
                
                # Check page-level text
                block_text = block.get('text', '')
                if block_text:
                    # Calculate text similarity
                    chunk_words = set(chunk_preview[:100].lower().split())
                    block_words = set(block_text[:200].lower().split())
                    if chunk_words and block_words:
                        overlap = len(chunk_words.intersection(block_words))
                        total = len(chunk_words.union(block_words))
                        similarity = overlap / total if total > 0 else 0.0
                        
                        if similarity > best_match_score and similarity > 0.3:  # 30% threshold
                            best_match_score = similarity
                            best_match = int(block_page)
                
                # Also check nested blocks if available
                nested_blocks = block.get('blocks', [])
                if isinstance(nested_blocks, list):
                    for nested_block in nested_blocks:
                        if isinstance(nested_block, dict):
                            nested_text = nested_block.get('text', '')
                            if nested_text:
                                chunk_words = set(chunk_preview[:100].lower().split())
                                nested_words = set(nested_text[:150].lower().split())
                                if chunk_words and nested_words:
                                    overlap = len(chunk_words.intersection(nested_words))
                                    total = len(chunk_words.union(nested_words))
                                    similarity = overlap / total if total > 0 else 0.0
                                    
                                    if similarity > best_match_score and similarity > 0.3:
                                        best_match_score = similarity
                                        best_match = int(block_page)
            
            if best_match:
                logger.debug(f"Page from text matching: {best_match} (similarity: {best_match_score:.2f})")
                return best_match
            
            return None
        
        # PRIORITY 2: Try source_page metadata (high confidence: 1.0)
        page = doc.metadata.get('source_page', None)
        if page is not None:
            if validate_against_doc(page):
                # Cross-validate with character position if available
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page), doc, chunk_text, page_blocks
                )
                if validated_confidence >= 0.8:
                    logger.debug(f"Page {validated_page} validated from source_page with cross-validation (confidence: {validated_confidence:.2f})")
                    return validated_page, validated_confidence
                else:
                    logger.debug(f"Page extracted from source_page metadata: {page}")
                    return int(page), 1.0
            else:
                logger.warning(f"Invalid page number in source_page metadata: {page} (doc has {doc_pages} pages)")
        
        # PRIORITY 3: Try page_blocks (confidence: 0.9 baseline; boosted if corroborated)
        page_blocks = doc.metadata.get('page_blocks', [])
        if page_blocks:
            page_from_blocks = get_page_from_page_blocks(chunk_text, page_blocks)
            if page_from_blocks and validate_against_doc(page_from_blocks):
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page_from_blocks), doc, chunk_text, page_blocks
                )
                logger.debug(
                    f"Page extracted from page_blocks: {validated_page} "
                    f"(confidence: {validated_confidence:.2f})"
                )
                return validated_page, max(0.9, validated_confidence)
        
        # PRIORITY 4: Try page metadata (confidence: 0.8)
        page = doc.metadata.get('page', None)
        if page is not None:
            if validate_against_doc(page):
                # Cross-validate
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page), doc, chunk_text, page_blocks
                )
                logger.debug(f"Page extracted from page metadata: {validated_page} (confidence: {validated_confidence:.2f})")
                return validated_page, validated_confidence
            else:
                logger.warning(f"Invalid page number in page metadata: {page} (doc has {doc_pages} pages)")
        
        # Extract from text markers: "--- Page X ---" (confidence: 0.6)
        # Enhanced pattern matching with better validation
        page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (--- Page X ---): {page_num}")
                return page_num, 0.6
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Extract from text markers: "Page X" or "Document Page X" or "VUORMAR Page X" (confidence: 0.4)
        # Enhanced: Look for "Page X" patterns including document name prefixes
        # Pattern 1: "VUORMAR Page 10" or "Document Page 5" (document name + Page + number)
        # Handle both with and without newlines/whitespace
        page_match = re.search(r'(\w+)\s+Page\s+(\d+)', chunk_text, re.IGNORECASE | re.MULTILINE)
        if page_match:
            page_num = int(page_match.group(2))
            # More lenient validation - if doc_pages is None, still accept reasonable page numbers
            if doc_pages is None or page_num <= doc_pages:
                if validate_page(page_num):  # Basic range check (1-10000)
                    logger.info(f"Page extracted from text marker ({page_match.group(1)} Page {page_num}): {page_num}")
                    return page_num, 0.5  # Slightly higher confidence for document name + page pattern
        
        # Pattern 2: Standalone "Page X" at line start or after newline
        page_match = re.search(r'(?:^|\n)\s*Page\s+(\d+)(?:\s|$|\.|,|;|:)', chunk_text, re.IGNORECASE | re.MULTILINE)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (Page X): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Pattern 3: "Page X of Y" or "Page X/Y" (take first number)
        page_match = re.search(r'Page\s+(\d+)(?:\s+of\s+\d+|\s*/\s*\d+)', chunk_text, re.IGNORECASE)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (Page X of Y): {page_num}")
                return page_num, 0.4
        
        # Try page range patterns: "Page 5-7" or "Pages 10-12" (take first page, confidence: 0.4)
        page_range_match = re.search(r'Pages?\s+(\d+)[-\s]+(\d+)', chunk_text, re.IGNORECASE)
        if page_range_match:
            page_num = int(page_range_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from page range (first page): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from page range {page_num} exceeds document pages {doc_pages}")
        
        # Try to extract from chunk_index if available (confidence: 0.3) - NEW
        chunk_index = doc.metadata.get('chunk_index', None)
        if chunk_index is not None and page_blocks:
            # Estimate page from chunk position (rough heuristic)
            try:
                # If we have page_blocks, try to infer page from chunk position
                total_chunks = len([b for b in page_blocks if isinstance(b, dict) and b.get('text')])
                if total_chunks > 0:
                    # Rough estimate: assume chunks are distributed evenly across pages
                    estimated_page = min(int((chunk_index / max(total_chunks, 1)) * (doc_pages or 1)) + 1, doc_pages or 1)
                    if validate_against_doc(estimated_page):
                        logger.debug(f"Page estimated from chunk_index: {estimated_page}")
                        return estimated_page, 0.3
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                pass
        
        # No valid page found - use fallback: page 1 with low confidence
        # ENHANCED: Try to look for any page number in metadata as absolute last resort
        page_fallback = doc.metadata.get('page') or doc.metadata.get('source_page') or doc.metadata.get('image_page')
        if page_fallback and validate_against_doc(page_fallback):
            logger.info(f"📄 [FALLBACK METADATA] Using page {page_fallback} from ANY metadata field")
            return int(page_fallback), 0.2
            
        source = doc.metadata.get('source', 'Unknown')
        
        # MONITORING: Alert if we're falling back to page 1 on a multi-page document
        # This often indicates character offset drift or parser misalignment
        if doc_pages and doc_pages > 1:
            logger.warning(f"⚠️ [OFFSET MONITOR] No page number found in chunk, using fallback page 1 for multi-page doc. "
                           f"Source: {source} ({doc_pages} pages). This may indicate character offset drift.")
        else:
            logger.warning(f"No page number found in chunk, using fallback page 1. Source: {source}")
            
        return 1, 0.1  # Fallback to page 1 with very low confidence
    
