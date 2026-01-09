"""
Language Detection Service for ARIS RAG System.
Uses langdetect library for fast, accurate language identification.
Includes OCR language mapping for Tesseract and multilingual support.
"""

import logging
from typing import List, Tuple, Optional, Dict

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
    "uk": "Ukrainian",
    "cs": "Czech",
    "sk": "Slovak",
    "bg": "Bulgarian",
    "sr": "Serbian",
    "hr": "Croatian",
    "el": "Greek",
    "he": "Hebrew",
    "fa": "Persian",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
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
    "uk": "ukr",
    "cs": "ces",
    "sk": "slk",
    "bg": "bul",
    "sr": "srp",
    "hr": "hrv",
    "el": "ell",
    "he": "heb",
    "fa": "fas",
    "bn": "ben",
    "ta": "tam",
    "te": "tel",
    "mr": "mar",
    "gu": "guj",
}

# Tesseract OCR language codes (ISO 639-3 based)
# Maps ISO 639-1/639-3 to Tesseract language data file names
OCR_LANGUAGE_MAP = {
    # Latin script languages
    "en": "eng", "eng": "eng",
    "es": "spa", "spa": "spa",
    "fr": "fra", "fra": "fra",
    "de": "deu", "deu": "deu",
    "pt": "por", "por": "por",
    "it": "ita", "ita": "ita",
    "nl": "nld", "nld": "nld",
    "pl": "pol", "pol": "pol",
    "tr": "tur", "tur": "tur",
    "vi": "vie", "vie": "vie",
    "id": "ind", "ind": "ind",
    "ms": "msa", "msa": "msa",
    # Cyrillic script languages
    "ru": "rus", "rus": "rus",
    "uk": "ukr", "ukr": "ukr",
    "bg": "bul", "bul": "bul",
    "sr": "srp", "srp": "srp",
    # CJK languages
    "ja": "jpn", "jpn": "jpn",
    "ko": "kor", "kor": "kor",
    "zh-cn": "chi_sim", "zho": "chi_sim",
    "zh-tw": "chi_tra",
    # RTL and complex scripts
    "ar": "ara", "ara": "ara",
    "he": "heb", "heb": "heb",
    "fa": "fas", "fas": "fas",
    # South Asian scripts
    "hi": "hin", "hin": "hin",
    "bn": "ben", "ben": "ben",
    "ta": "tam", "tam": "tam",
    "te": "tel", "tel": "tel",
    "mr": "mar", "mar": "mar",
    "gu": "guj", "guj": "guj",
    # Southeast Asian scripts
    "th": "tha", "tha": "tha",
    # Greek
    "el": "ell", "ell": "ell",
}

# Script type classifications for OCR optimization
SCRIPT_TYPES = {
    "latin": ["en", "es", "fr", "de", "pt", "it", "nl", "pl", "tr", "vi", "id", "ms"],
    "cyrillic": ["ru", "uk", "bg", "sr"],
    "cjk": ["ja", "ko", "zh-cn", "zh-tw"],
    "arabic": ["ar", "fa"],
    "hebrew": ["he"],
    "devanagari": ["hi", "mr"],
    "bengali": ["bn"],
    "tamil": ["ta"],
    "telugu": ["te"],
    "gujarati": ["gu"],
    "thai": ["th"],
    "greek": ["el"],
}

# OCR parameters optimized for different script types
OCR_PARAMS_BY_SCRIPT = {
    "latin": {
        "dpi": 300,
        "tesseract_config": "--oem 3 --psm 3",
        "preprocessing": "standard",
    },
    "cyrillic": {
        "dpi": 300,
        "tesseract_config": "--oem 3 --psm 3",
        "preprocessing": "standard",
    },
    "cjk": {
        "dpi": 400,  # Higher DPI for complex characters
        "tesseract_config": "--oem 3 --psm 6",  # PSM 6 for uniform text blocks
        "preprocessing": "enhanced",  # Better contrast for stroke detection
    },
    "arabic": {
        "dpi": 300,
        "tesseract_config": "--oem 3 --psm 4",  # PSM 4 for single column RTL
        "preprocessing": "rtl",
    },
    "hebrew": {
        "dpi": 300,
        "tesseract_config": "--oem 3 --psm 4",
        "preprocessing": "rtl",
    },
    "devanagari": {
        "dpi": 350,
        "tesseract_config": "--oem 3 --psm 6",
        "preprocessing": "enhanced",
    },
    "default": {
        "dpi": 300,
        "tesseract_config": "--oem 3 --psm 3",
        "preprocessing": "standard",
    },
}


class LanguageDetector:
    """
    Language detection service using langdetect library.
    Provides fast, accurate detection for 50+ languages.
    Includes OCR language mapping and script-specific optimization.
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
    
    def get_ocr_language(self, lang_code: str) -> str:
        """
        Get Tesseract OCR language code from ISO 639-1/639-3 code.
        
        Args:
            lang_code: ISO 639-1 or 639-3 language code
            
        Returns:
            Tesseract language code (e.g., 'eng', 'chi_sim', 'jpn')
        """
        code = lang_code.lower().strip()
        return OCR_LANGUAGE_MAP.get(code, "eng")
    
    def get_script_type(self, lang_code: str) -> str:
        """
        Get script type for a language.
        
        Args:
            lang_code: ISO 639-1 or 639-3 language code
            
        Returns:
            Script type (e.g., 'latin', 'cjk', 'cyrillic')
        """
        code = lang_code.lower().strip()
        
        # Convert 639-3 to 639-1 if needed
        for iso1, iso3 in ISO_639_1_TO_639_3.items():
            if code == iso3:
                code = iso1
                break
        
        for script_type, languages in SCRIPT_TYPES.items():
            if code in languages:
                return script_type
        
        return "latin"  # Default to Latin script
    
    def get_ocr_params(self, lang_code: str) -> Dict:
        """
        Get optimized OCR parameters for a language/script.
        
        Args:
            lang_code: ISO 639-1 or 639-3 language code
            
        Returns:
            Dict with OCR parameters (dpi, tesseract_config, preprocessing)
        """
        script_type = self.get_script_type(lang_code)
        return OCR_PARAMS_BY_SCRIPT.get(script_type, OCR_PARAMS_BY_SCRIPT["default"])
    
    def get_multi_ocr_languages(self, primary_lang: str, secondary_lang: Optional[str] = None) -> str:
        """
        Get combined OCR language string for multi-language documents.
        
        Args:
            primary_lang: Primary document language
            secondary_lang: Optional secondary language
            
        Returns:
            Combined Tesseract language string (e.g., 'eng+fra')
        """
        primary_ocr = self.get_ocr_language(primary_lang)
        
        if secondary_lang:
            secondary_ocr = self.get_ocr_language(secondary_lang)
            if secondary_ocr != primary_ocr:
                return f"{primary_ocr}+{secondary_ocr}"
        
        # Always include English as fallback for mixed documents
        if primary_ocr != "eng":
            return f"{primary_ocr}+eng"
        
        return primary_ocr
    
    def is_cjk_language(self, lang_code: str) -> bool:
        """Check if language uses CJK script."""
        return self.get_script_type(lang_code) == "cjk"
    
    def is_rtl_language(self, lang_code: str) -> bool:
        """Check if language is right-to-left."""
        script = self.get_script_type(lang_code)
        return script in ("arabic", "hebrew")
    
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
        
        # Check for Hebrew
        if any('\u0590' <= c <= '\u05FF' for c in text):
            return "he"
        
        # Check for Thai
        if any('\u0E00' <= c <= '\u0E7F' for c in text):
            return "th"
        
        # Check for Greek
        if any('\u0370' <= c <= '\u03FF' for c in text):
            return "el"
        
        # Check for Devanagari (Hindi, Marathi)
        if any('\u0900' <= c <= '\u097F' for c in text):
            return "hi"
        
        return fallback
    
    def detect_mixed_languages(self, text: str) -> Dict[str, float]:
        """
        Detect multiple languages in text and return their proportions.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict mapping language codes to their percentage (0-1) in text
        """
        if not text or len(text.strip()) < 20:
            return {"en": 1.0}
        
        if not self._available:
            # Fallback: use character-based detection
            primary = self._fallback_detect(text, "en")
            return {primary: 1.0}
        
        try:
            from langdetect import detect_langs
            results = detect_langs(text)
            return {str(r.lang): r.prob for r in results}
        except Exception as e:
            logger.warning(f"Mixed language detection failed: {e}")
            return {"en": 1.0}
    
    def detect_primary_and_secondary(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Detect primary and secondary languages in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (primary_language, secondary_language or None)
        """
        lang_probs = self.detect_mixed_languages(text)
        
        # Sort by probability
        sorted_langs = sorted(lang_probs.items(), key=lambda x: x[1], reverse=True)
        
        primary = sorted_langs[0][0] if sorted_langs else "en"
        
        # Only consider secondary if it has significant presence (>10%)
        secondary = None
        if len(sorted_langs) > 1 and sorted_langs[1][1] > 0.1:
            secondary = sorted_langs[1][0]
        
        return primary, secondary


# Singleton instance for easy access
_detector_instance: Optional[LanguageDetector] = None


def get_detector() -> LanguageDetector:
    """Get the singleton language detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = LanguageDetector()
    return _detector_instance


def get_ocr_language(lang_code: str) -> str:
    """Convenience function to get OCR language code."""
    return get_detector().get_ocr_language(lang_code)


def get_ocr_params(lang_code: str) -> Dict:
    """Convenience function to get OCR parameters for a language."""
    return get_detector().get_ocr_params(lang_code)
