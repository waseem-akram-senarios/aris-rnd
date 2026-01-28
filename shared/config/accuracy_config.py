"""
Accuracy thresholds and configuration for ARIS RAG System.

🎯 OPTIMIZED FOR MAXIMUM ACCURACY (R&D Settings)
These settings are used across all services for consistency.
"""

# =========================================================================
# OCR ACCURACY THRESHOLDS
# =========================================================================
ACCURACY_THRESHOLDS = {
    'min_ocr_accuracy': 0.85,      # 85% minimum acceptable OCR accuracy
    'min_text_accuracy': 0.90,     # 90% minimum for text extraction
    'auto_fix_threshold': 0.80,    # Auto-fix if accuracy below 80%
    'warning_threshold': 0.90,     # Warn if accuracy below 90%
    'excellent_threshold': 0.95    # Excellent if accuracy above 95%
}

# =========================================================================
# OCR VERIFICATION SETTINGS
# =========================================================================
VERIFICATION_SETTINGS = {
    're_run_ocr_on_verify': False,     # Re-run OCR during verification
    'max_missing_content_items': 10,   # Max items to report in missing_content
    'max_extra_content_items': 10,     # Max items to report in extra_content
    'enable_auto_fix': True,           # Enable automatic OCR fixing
    'auto_fix_retry_limit': 3          # Max retries for auto-fix
}

# =========================================================================
# 🎯 RETRIEVAL ACCURACY THRESHOLDS
# =========================================================================
RETRIEVAL_THRESHOLDS = {
    # Minimum similarity score for a chunk to be considered relevant
    'min_similarity_score': 0.3,
    
    # Minimum rerank score to include in final results
    'min_rerank_score': 0.2,
    
    # Confidence score thresholds for citation display
    'high_confidence': 0.7,        # 70%+ = High confidence (green)
    'medium_confidence': 0.4,      # 40-70% = Medium confidence (yellow)
    'low_confidence': 0.0,         # Below 40% = Low confidence (red)
}

# =========================================================================
# 🎯 ANSWER GENERATION THRESHOLDS
# =========================================================================
GENERATION_THRESHOLDS = {
    # Minimum chunks required to generate an answer
    'min_chunks_for_answer': 1,
    
    # Maximum chunks to include in context (prevent token overflow)
    'max_chunks_in_context': 15,
    
    # Minimum total relevance score to attempt answer generation
    'min_total_relevance': 0.5,
}

# =========================================================================
# 🎯 FUZZY MATCHING SETTINGS (For typo tolerance)
# =========================================================================
FUZZY_MATCHING = {
    # Minimum ratio for fuzzy string matching (0.0 - 1.0)
    'min_match_ratio': 0.75,
    
    # Quick check: minimum character overlap percentage
    'min_char_overlap': 0.4,
    
    # Enable fuzzy matching for keyword search
    'enabled': True,
}

# =========================================================================
# 🎯 DEDUPLICATION SETTINGS
# =========================================================================
DEDUPLICATION = {
    # Similarity threshold for considering chunks as duplicates
    'similarity_threshold': 0.92,
    
    # Method: 'semantic' (embedding-based) or 'text' (string-based)
    'method': 'semantic',
    
    # Enable cross-document deduplication
    'cross_document': True,
}

# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def get_confidence_level(score: float) -> str:
    """Get confidence level label based on score."""
    if score >= RETRIEVAL_THRESHOLDS['high_confidence']:
        return 'high'
    elif score >= RETRIEVAL_THRESHOLDS['medium_confidence']:
        return 'medium'
    return 'low'


def should_include_citation(similarity_score: float, rerank_score: float = None) -> bool:
    """Determine if a citation should be included based on scores."""
    if rerank_score is not None:
        return rerank_score >= RETRIEVAL_THRESHOLDS['min_rerank_score']
    return similarity_score >= RETRIEVAL_THRESHOLDS['min_similarity_score']


def get_all_accuracy_settings() -> dict:
    """Get all accuracy settings as a dictionary."""
    return {
        'ocr_thresholds': ACCURACY_THRESHOLDS,
        'verification': VERIFICATION_SETTINGS,
        'retrieval': RETRIEVAL_THRESHOLDS,
        'generation': GENERATION_THRESHOLDS,
        'fuzzy_matching': FUZZY_MATCHING,
        'deduplication': DEDUPLICATION,
    }
