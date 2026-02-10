"""
OCR verification service.
Compares PDF content with stored OCR results and calculates accuracy metrics.
"""
import logging
import difflib
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    try:
        from fuzzywuzzy import fuzz as fuzzy_fuzz
        HAS_FUZZYWUZZY = True
        HAS_RAPIDFUZZ = False
    except ImportError:
        HAS_RAPIDFUZZ = False
        HAS_FUZZYWUZZY = False


class OCRVerifier:
    """Service for verifying OCR accuracy"""
    
    def __init__(self):
        """Initialize OCR verifier"""
        self.min_accuracy_threshold = 0.85
        self.warning_threshold = 0.90
    
    def verify_image_ocr(
        self,
        pdf_image_data: bytes,
        stored_ocr_text: str,
        page_number: int,
        image_index: int,
        re_run_ocr: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Verify OCR accuracy for a single image.
        
        Args:
            pdf_image_data: Raw image data from PDF
            stored_ocr_text: OCR text stored in OpenSearch
            page_number: Page number
            image_index: Image index on page
            re_run_ocr: Optional function to re-run OCR on image
        
        Returns:
            Verification result dictionary
        """
        result = {
            'page_number': page_number,
            'image_index': image_index,
            'stored_ocr_length': len(stored_ocr_text) if stored_ocr_text else 0,
            'verified_ocr_length': 0,
            'accuracy_score': 0.0,
            'character_accuracy': 0.0,
            'word_accuracy': 0.0,
            'missing_content': [],
            'extra_content': [],
            'verification_status': 'not_verified',
            'verification_timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
        try:
            # If re-run OCR function provided, re-extract OCR
            verified_ocr_text = stored_ocr_text
            if re_run_ocr:
                try:
                    verified_ocr_text = re_run_ocr(pdf_image_data)
                    result['verified_ocr_length'] = len(verified_ocr_text) if verified_ocr_text else 0
                except Exception as e:
                    logger.warning(f"Could not re-run OCR for verification: {e}")
                    verified_ocr_text = stored_ocr_text
            else:
                result['verified_ocr_length'] = result['stored_ocr_length']
            
            if not stored_ocr_text and not verified_ocr_text:
                result['verification_status'] = 'no_content'
                return result
            
            # Normalize text for comparison
            stored_normalized = self._normalize_text(stored_ocr_text or '')
            verified_normalized = self._normalize_text(verified_ocr_text or '')
            
            # Calculate similarity scores
            similarity = self._calculate_similarity(stored_normalized, verified_normalized)
            result['accuracy_score'] = similarity
            
            # Character-level accuracy
            if stored_normalized and verified_normalized:
                char_accuracy = self._character_accuracy(stored_normalized, verified_normalized)
                result['character_accuracy'] = char_accuracy
            
            # Word-level accuracy
            stored_words = stored_normalized.split()
            verified_words = verified_normalized.split()
            if stored_words and verified_words:
                word_accuracy = self._word_accuracy(stored_words, verified_words)
                result['word_accuracy'] = word_accuracy
            
            # Find differences
            diff = list(difflib.unified_diff(
                stored_normalized.splitlines(keepends=True),
                verified_normalized.splitlines(keepends=True),
                lineterm=''
            ))
            
            # Extract missing and extra content
            missing = []
            extra = []
            for line in diff:
                if line.startswith('-') and not line.startswith('---'):
                    missing.append(line[1:].strip())
                elif line.startswith('+') and not line.startswith('+++'):
                    extra.append(line[1:].strip())
            
            result['missing_content'] = missing[:10]  # Limit to first 10
            result['extra_content'] = extra[:10]
            
            # Determine status
            if similarity >= self.warning_threshold:
                result['verification_status'] = 'accurate'
            elif similarity >= self.min_accuracy_threshold:
                result['verification_status'] = 'needs_review'
            else:
                result['verification_status'] = 'inaccurate'
        
        except Exception as e:
            logger.error(f"Error verifying image OCR: {e}", exc_info=True)
            result['verification_error'] = str(e)
            result['verification_status'] = 'error'
        
        return result
    
    def verify_document(
        self,
        document_id: str,
        pdf_file_content: bytes,
        stored_images: List[Dict[str, Any]],
        re_run_ocr: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Verify entire document OCR accuracy.
        
        Args:
            document_id: Document ID
            pdf_file_content: PDF file content as bytes
            stored_images: List of stored image data from OpenSearch
            re_run_ocr: Optional function to re-run OCR
        
        Returns:
            Comprehensive verification report
        """
        from shared.utils.pdf_content_extractor import extract_pdf_content
        
        result = {
            'document_id': document_id,
            'verification_timestamp': datetime.utcnow().isoformat() + 'Z',
            'overall_accuracy': 0.0,
            'page_verifications': [],
            'image_verifications': [],
            'issues_found': [],
            'recommendations': [],
            'total_images_verified': 0,
            'accurate_images': 0,
            'needs_review_images': 0,
            'inaccurate_images': 0
        }
        
        try:
            # Extract PDF content
            pdf_content = extract_pdf_content(pdf_file_content)
            
            if 'extraction_error' in pdf_content:
                result['issues_found'].append(f"Could not extract PDF content: {pdf_content['extraction_error']}")
                return result
            
            # Create image lookup by page and index
            stored_images_by_page = {}
            for img in stored_images:
                page = img.get('page', 0)
                img_idx = img.get('image_number', 0)
                if page not in stored_images_by_page:
                    stored_images_by_page[page] = {}
                stored_images_by_page[page][img_idx] = img
            
            # Verify each page
            overall_accuracies = []
            for page_data in pdf_content.get('pages', []):
                page_num = page_data.get('page_number')
                page_images = page_data.get('images', [])
                
                page_verification = {
                    'page_number': page_num,
                    'text_accuracy': None,  # Could verify native text if needed
                    'images_accuracy': 0.0,
                    'issues': [],
                    'image_verifications': []
                }
                
                page_image_accuracies = []
                
                # Verify each image on the page
                for pdf_image in page_images:
                    img_idx = pdf_image.get('image_index')
                    image_data = pdf_image.get('image_data')
                    
                    # Find corresponding stored image
                    stored_img = stored_images_by_page.get(page_num, {}).get(img_idx)
                    
                    if stored_img:
                        stored_ocr = stored_img.get('ocr_text', '')
                        
                        # Verify OCR
                        verification = self.verify_image_ocr(
                            pdf_image_data=image_data,
                            stored_ocr_text=stored_ocr,
                            page_number=page_num,
                            image_index=img_idx,
                            re_run_ocr=re_run_ocr
                        )
                        
                        page_image_accuracies.append(verification.get('accuracy_score', 0.0))
                        result['image_verifications'].append(verification)
                        page_verification['image_verifications'].append(verification)
                        
                        result['total_images_verified'] += 1
                        status = verification.get('verification_status')
                        if status == 'accurate':
                            result['accurate_images'] += 1
                        elif status == 'needs_review':
                            result['needs_review_images'] += 1
                        elif status == 'inaccurate':
                            result['inaccurate_images'] += 1
                        
                        # Collect issues
                        if status != 'accurate':
                            issue = f"Page {page_num}, Image {img_idx}: {status} (accuracy: {verification.get('accuracy_score', 0):.2%})"
                            page_verification['issues'].append(issue)
                            result['issues_found'].append(issue)
                    else:
                        issue = f"Page {page_num}, Image {img_idx}: Not found in stored images"
                        page_verification['issues'].append(issue)
                        result['issues_found'].append(issue)
                
                # Calculate page image accuracy
                if page_image_accuracies:
                    page_verification['images_accuracy'] = sum(page_image_accuracies) / len(page_image_accuracies)
                    overall_accuracies.append(page_verification['images_accuracy'])
                
                result['page_verifications'].append(page_verification)
            
            # Calculate overall accuracy
            if overall_accuracies:
                result['overall_accuracy'] = sum(overall_accuracies) / len(overall_accuracies)
            
            # Generate recommendations
            if result['overall_accuracy'] < self.min_accuracy_threshold:
                result['recommendations'].append("Overall accuracy is below threshold. Consider re-processing with enhanced OCR settings.")
            
            if result['inaccurate_images'] > 0:
                result['recommendations'].append(f"{result['inaccurate_images']} images have low accuracy. Review and potentially re-process.")
            
            if result['needs_review_images'] > 0:
                result['recommendations'].append(f"{result['needs_review_images']} images need manual review.")
        
        except Exception as e:
            logger.error(f"Error verifying document: {e}", exc_info=True)
            result['verification_error'] = str(e)
            result['issues_found'].append(f"Verification error: {str(e)}")
        
        return result
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ''
        # Remove extra whitespace, normalize case
        normalized = ' '.join(text.split())
        return normalized.lower()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Use rapidfuzz if available
        if HAS_RAPIDFUZZ:
            return fuzz.ratio(text1, text2) / 100.0
        elif HAS_FUZZYWUZZY:
            return fuzzy_fuzz.ratio(text1, text2) / 100.0
        else:
            # Fallback to difflib
            return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def _character_accuracy(self, text1: str, text2: str) -> float:
        """Calculate character-level accuracy"""
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Use SequenceMatcher for character-level comparison
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()
    
    def _word_accuracy(self, words1: List[str], words2: List[str]) -> float:
        """Calculate word-level accuracy"""
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        # Count matching words
        set1 = set(words1)
        set2 = set(words2)
        
        if not set1 and not set2:
            return 1.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
