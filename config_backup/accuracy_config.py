"""
Accuracy thresholds and configuration for OCR verification.
"""
# Accuracy thresholds
ACCURACY_THRESHOLDS = {
    'min_ocr_accuracy': 0.85,  # 85% minimum acceptable
    'min_text_accuracy': 0.90,  # 90% minimum for text
    'auto_fix_threshold': 0.80,  # Auto-fix if below 80%
    'warning_threshold': 0.90,   # Warn if below 90%
    'excellent_threshold': 0.95   # Excellent if above 95%
}

# Verification settings
VERIFICATION_SETTINGS = {
    're_run_ocr_on_verify': False,  # Whether to re-run OCR during verification
    'max_missing_content_items': 10,  # Max items to report in missing_content
    'max_extra_content_items': 10,   # Max items to report in extra_content
    'enable_auto_fix': True,          # Enable automatic fixing
    'auto_fix_retry_limit': 2         # Max retries for auto-fix
}
