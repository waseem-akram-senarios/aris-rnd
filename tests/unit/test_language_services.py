"""
Unit tests for Language Detection and Translation services.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from unittest.mock import patch, MagicMock


class TestLanguageDetector(unittest.TestCase):
    """Tests for the LanguageDetector class."""
    
    def test_detect_english(self):
        """Test detection of English text."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        # Use longer text for reliable detection
        result = detector.detect("Hello, how are you doing today? I hope you are having a wonderful day and everything is going well for you.")
        self.assertEqual(result, "en")
    
    def test_detect_spanish(self):
        """Test detection of Spanish text."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        result = detector.detect("Hola, ¿cómo estás? Espero que estés bien.")
        self.assertEqual(result, "es")
    
    def test_detect_short_text_fallback(self):
        """Test that short text returns fallback language."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        # Text under 10 chars should return fallback
        result = detector.detect("Hi", fallback="en")
        self.assertEqual(result, "en")
    
    def test_detect_to_iso639_3(self):
        """Test conversion to ISO 639-3 codes."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        result = detector.detect_to_iso639_3("Hola, ¿cómo estás hoy?")
        self.assertEqual(result, "spa")
    
    def test_get_language_name(self):
        """Test language name retrieval."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        self.assertEqual(detector.get_language_name("en"), "English")
        self.assertEqual(detector.get_language_name("es"), "Spanish")
        self.assertEqual(detector.get_language_name("spa"), "Spanish")


class TestTranslationService(unittest.TestCase):
    """Tests for the TranslationService class."""
    
    @patch('openai.OpenAI')
    def test_translate_spanish_to_english(self, mock_openai):
        """Test translation from Spanish to English."""
        from services.language.translator import TranslationService
        
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "How are you?"
        mock_client.chat.completions.create.return_value = mock_response
        
        translator = TranslationService(provider="openai")
        translator._openai_client = mock_client
        
        result = translator.translate("¿Cómo estás?", target_lang="en", source_lang="es")
        self.assertEqual(result, "How are you?")
    
    def test_normalize_language_codes(self):
        """Test language code normalization."""
        from services.language.translator import TranslationService
        
        translator = TranslationService.__new__(TranslationService)
        translator._openai_client = None
        translator._aws_translate = None
        translator.provider = "openai"
        
        # Test full names
        self.assertEqual(translator._normalize_lang_code("Spanish"), "es")
        self.assertEqual(translator._normalize_lang_code("English"), "en")
        
        # Test ISO 639-3
        self.assertEqual(translator._normalize_lang_code("spa"), "es")
        self.assertEqual(translator._normalize_lang_code("eng"), "en")
    
    def test_skip_same_language_translation(self):
        """Test that translation is skipped for same source/target."""
        from services.language.translator import TranslationService
        
        translator = TranslationService.__new__(TranslationService)
        translator._openai_client = MagicMock()
        translator._aws_translate = None
        translator.provider = "openai"
        
        result = translator.translate("Hello", target_lang="en", source_lang="en")
        self.assertEqual(result, "Hello")


class TestLanguageIntegration(unittest.TestCase):
    """Integration tests for language services."""
    
    def test_detector_singleton(self):
        """Test that get_detector returns singleton instance."""
        from services.language.detector import get_detector
        
        detector1 = get_detector()
        detector2 = get_detector()
        self.assertIs(detector1, detector2)
    
    def test_fallback_detection_spanish_chars(self):
        """Test fallback detection using Spanish special characters."""
        from services.language.detector import LanguageDetector
        
        detector = LanguageDetector()
        detector._available = False  # Force fallback mode
        
        result = detector._fallback_detect("Hola señor, ¿cómo está usted?", "en")
        self.assertEqual(result, "es")


if __name__ == "__main__":
    unittest.main()
