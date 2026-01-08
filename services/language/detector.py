"""
Language Detection Service for ARIS RAG System.
Uses langdetect library for fast, accurate language identification.
"""

import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Language code mapping (ISO 639-1 to full names)
LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
}

# ISO 639-3 mapping (for document metadata compatibility)
ISO_639_1_TO_639_3 = {
    "en": "eng",
    "es": "spa",
    "fr": "fra",
    "de": "deu",
    "pt": "por",
    "it": "ita",
    "nl": "nld",
    "pl": "pol",
    "ru": "rus",
    "ja": "jpn",
    "ko": "kor",
    "zh-cn": "zho",
    "zh-tw": "zho",
    "ar": "ara",
    "hi": "hin",
    "tr": "tur",
    "vi": "vie",
    "th": "tha",
    "id": "ind",
    "ms": "msa",
}


class LanguageDetector:
    """
    Language detection service using langdetect library.
    Provides fast, accurate detection for 50+ languages.
    """
    
    def __init__(self):
        """Initialize the language detector."""
        try:
            from langdetect import DetectorFactory
            # Set seed for reproducibility
            DetectorFactory.seed = 0
            self._available = True
            logger.info("✅ Language detector initialized successfully")
        except ImportError:
            self._available = False
            logger.warning("⚠️ langdetect not installed. Language detection will use fallback.")
    
    def detect(self, text: str, fallback: str = "en") -> str:
        """
        Detect the language of the given text.
        
        Args:
            text: Text to analyze
            fallback: Language code to return if detection fails
            
        Returns:
            ISO 639-1 language code (e.g., 'en', 'es', 'fr')
        """
        if not text or len(text.strip()) < 10:
            logger.debug(f"Text too short for reliable detection, using fallback: {fallback}")
            return fallback
        
        if not self._available:
            return self._fallback_detect(text, fallback)
        
        try:
            from langdetect import detect
            detected = detect(text)
            logger.debug(f"Detected language: {detected}")
            return detected
        except Exception as e:
            logger.warning(f"Language detection failed: {e}. Using fallback: {fallback}")
            return fallback
    
    def detect_with_confidence(self, text: str) -> List[Tuple[str, float]]:
        """
        Detect language with confidence scores.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of (language_code, probability) tuples, sorted by probability
        """
        if not text or len(text.strip()) < 10:
            return [("en", 1.0)]
        
        if not self._available:
            return [(self._fallback_detect(text, "en"), 0.8)]
        
        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            return [(str(r.lang), r.prob) for r in results]
        except Exception as e:
            logger.warning(f"Language detection with confidence failed: {e}")
            return [("en", 0.5)]
    
    def detect_to_iso639_3(self, text: str, fallback: str = "eng") -> str:
        """
        Detect language and return ISO 639-3 code (for document metadata).
        
        Args:
            text: Text to analyze
            fallback: ISO 639-3 code to return if detection fails
            
        Returns:
            ISO 639-3 language code (e.g., 'eng', 'spa', 'fra')
        """
        detected_639_1 = self.detect(text)
        return ISO_639_1_TO_639_3.get(detected_639_1, fallback)
    
    def get_language_name(self, code: str) -> str:
        """
        Get the full language name from a code.
        
        Args:
            code: ISO 639-1 or 639-3 language code
            
        Returns:
            Full language name (e.g., 'Spanish', 'English')
        """
        # Check ISO 639-1 first
        if code in LANGUAGE_NAMES:
            return LANGUAGE_NAMES[code]
        
        # Check ISO 639-3
        for code_1, code_3 in ISO_639_1_TO_639_3.items():
            if code == code_3:
                return LANGUAGE_NAMES.get(code_1, code)
        
        return code  # Return code itself if no mapping found
    
    def _fallback_detect(self, text: str, fallback: str) -> str:
        """
        Simple fallback detection based on character analysis.
        Not as accurate as langdetect but works without dependencies.
        """
        # Check for Spanish-specific characters
        spanish_chars = set("ñáéíóúü¿¡")
        if any(c in text.lower() for c in spanish_chars):
            return "es"
        
        # Check for French-specific patterns
        french_patterns = ["ç", "œ", "ê", "ë", "î", "ï", "ô", "û", "ù"]
        if any(p in text.lower() for p in french_patterns):
            return "fr"
        
        # Check for German-specific characters
        german_chars = set("äöüß")
        if any(c in text.lower() for c in german_chars):
            return "de"
        
        # Check for Cyrillic (Russian, etc.)
        if any('\u0400' <= c <= '\u04FF' for c in text):
            return "ru"
        
        # Check for CJK characters
        if any('\u4e00' <= c <= '\u9fff' for c in text):
            return "zh-cn"
        
        # Check for Japanese Hiragana/Katakana
        if any('\u3040' <= c <= '\u30ff' for c in text):
            return "ja"
        
        # Check for Korean Hangul
        if any('\uac00' <= c <= '\ud7a3' for c in text):
            return "ko"
        
        # Check for Arabic
        if any('\u0600' <= c <= '\u06FF' for c in text):
            return "ar"
        
        return fallback


# Singleton instance for easy access
_detector_instance: Optional[LanguageDetector] = None


def get_detector() -> LanguageDetector:
    """Get the singleton language detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector()
    return _detector_instance
