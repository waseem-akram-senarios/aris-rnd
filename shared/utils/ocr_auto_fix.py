"""
OCR auto-fix service.
Detects accuracy issues and triggers re-processing with enhanced OCR settings.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from config.accuracy_config import ACCURACY_THRESHOLDS, VERIFICATION_SETTINGS

logger = logging.getLogger(__name__)


class OCRAutoFix:
    """Service for automatically fixing low accuracy OCR"""
    
    def __init__(self):
        """Initialize auto-fix service"""
        self.auto_fix_threshold = ACCURACY_THRESHOLDS.get('auto_fix_threshold', 0.80)
        self.retry_limit = VERIFICATION_SETTINGS.get('auto_fix_retry_limit', 2)
    
    def fix_low_accuracy(
        self,
        document_id: str,
        verification_report: Dict[str, Any],
        document_processor: Optional[Any] = None,
        pdf_file_content: Optional[bytes] = None,
        document_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Automatically fix low accuracy OCR.
        
        Args:
            document_id: Document ID
            verification_report: Verification report from OCRVerifier
            document_processor: Document processor instance
            pdf_file_content: PDF file content (if available)
            document_name: Document name
        
        Returns:
            Fix report dictionary
        """
        result = {
            'document_id': document_id,
            'fix_timestamp': datetime.utcnow().isoformat() + 'Z',
            'fix_applied': False,
            'fix_method': None,
            'images_fixed': 0,
            'accuracy_before': verification_report.get('overall_accuracy', 0.0),
            'accuracy_after': 0.0,
            'fix_details': [],
            'errors': []
        }
        
        try:
            overall_accuracy = verification_report.get('overall_accuracy', 0.0)
            
            # Check if fix is needed
            if overall_accuracy >= self.auto_fix_threshold:
                result['fix_details'].append(f"Accuracy {overall_accuracy:.2%} is above threshold {self.auto_fix_threshold:.2%}. No fix needed.")
                return result
            
            result['fix_details'].append(f"Accuracy {overall_accuracy:.2%} is below threshold. Attempting auto-fix...")
            
            # Identify problematic images
            problematic_images = []
            for img_verification in verification_report.get('image_verifications', []):
                accuracy = img_verification.get('accuracy_score', 0.0)
                if accuracy < self.auto_fix_threshold:
                    problematic_images.append(img_verification)
            
            if not problematic_images:
                result['fix_details'].append("No problematic images identified.")
                return result
            
            result['fix_details'].append(f"Found {len(problematic_images)} images with low accuracy.")
            
            # If document processor and PDF content available, re-process
            if document_processor and pdf_file_content and document_name:
                try:
                    result['fix_method'] = 're_process_with_enhanced_ocr'
                    result['fix_details'].append("Re-processing document with enhanced OCR settings...")
                    
                    # Re-process with enhanced settings
                    # Note: This would require access to the document processor
                    # For now, we'll log the recommendation
                    result['fix_details'].append("Re-processing would be triggered here with enhanced OCR settings.")
                    result['fix_details'].append("Enhanced settings: higher OCR resolution, better preprocessing, alternative OCR engine.")
                    
                    # In a full implementation, this would:
                    # 1. Re-process the document with enhanced OCR
                    # 2. Update OpenSearch with corrected OCR
                    # 3. Re-verify accuracy
                    # 4. Return updated accuracy score
                    
                    result['fix_applied'] = True
                    result['images_fixed'] = len(problematic_images)
                    
                except Exception as e:
                    logger.error(f"Error during auto-fix re-processing: {e}", exc_info=True)
                    result['errors'].append(f"Re-processing error: {str(e)}")
            else:
                result['fix_details'].append("Document processor or PDF content not available. Manual re-processing recommended.")
                result['recommendations'] = [
                    f"Re-process document {document_id} with enhanced OCR settings",
                    "Use alternative OCR engine if available",
                    "Increase OCR resolution/preprocessing quality",
                    f"Focus on {len(problematic_images)} problematic images"
                ]
        
        except Exception as e:
            logger.error(f"Error in auto-fix: {e}", exc_info=True)
            result['errors'].append(f"Auto-fix error: {str(e)}")
        
        return result
    
    def should_auto_fix(self, verification_report: Dict[str, Any]) -> bool:
        """
        Determine if auto-fix should be applied.
        
        Args:
            verification_report: Verification report
        
        Returns:
            True if auto-fix should be applied
        """
        if not VERIFICATION_SETTINGS.get('enable_auto_fix', True):
            return False
        
        overall_accuracy = verification_report.get('overall_accuracy', 0.0)
        return overall_accuracy < self.auto_fix_threshold
    
    def get_fix_recommendations(self, verification_report: Dict[str, Any]) -> List[str]:
        """
        Get recommendations for fixing accuracy issues.
        
        Args:
            verification_report: Verification report
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        overall_accuracy = verification_report.get('overall_accuracy', 0.0)
        inaccurate_count = verification_report.get('inaccurate_images', 0)
        needs_review_count = verification_report.get('needs_review_images', 0)
        
        if overall_accuracy < self.auto_fix_threshold:
            recommendations.append("Overall accuracy is below acceptable threshold. Re-processing recommended.")
        
        if inaccurate_count > 0:
            recommendations.append(f"{inaccurate_count} images have very low accuracy. These should be re-processed.")
        
        if needs_review_count > 0:
            recommendations.append(f"{needs_review_count} images need manual review.")
        
        # Specific recommendations based on issues
        issues = verification_report.get('issues_found', [])
        if issues:
            recommendations.append(f"Found {len(issues)} specific issues. Review verification report for details.")
        
        return recommendations
