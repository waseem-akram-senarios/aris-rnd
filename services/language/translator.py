"""
Translation Service for ARIS RAG System.
Provides translation capabilities using OpenAI or AWS Translate.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Translation service supporting multiple providers.
    Primary: OpenAI GPT-4o (highest quality)
    Fallback: AWS Translate (cost-effective for high volume)
    """
    
    def __init__(self, provider: str = "openai"):
        """
        Initialize the translation service.
        
        Args:
            provider: Translation provider ('openai', 'aws', or 'auto')
        """
        self.provider = provider.lower()
        self._openai_client = None
        self._aws_translate = None
        
        if self.provider in ("openai", "auto"):
            self._init_openai()
        
        if self.provider in ("aws", "auto"):
            self._init_aws()
        
        logger.info(f"✅ Translation service initialized (provider: {self.provider})")
    
    def _init_openai(self):
        """Initialize OpenAI client for translation."""
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._openai_client = OpenAI(api_key=api_key)
                logger.info("OpenAI translation client ready")
        except ImportError:
            logger.warning("OpenAI package not available for translation")
    
    def _init_aws(self):
        """Initialize AWS Translate client."""
        try:
            import boto3
            self._aws_translate = boto3.client('translate')
            logger.info("AWS Translate client ready")
        except Exception as e:
            logger.warning(f"AWS Translate not available: {e}")
    
    def translate(
        self, 
        text: str, 
        target_lang: str, 
        source_lang: Optional[str] = None
    ) -> str:
        """
        Translate text to the target language.
        
        Args:
            text: Text to translate
            target_lang: Target language code (e.g., 'en', 'es', 'Spanish')
            source_lang: Source language code (auto-detected if not provided)
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        # Normalize language codes
        target_lang = self._normalize_lang_code(target_lang)
        if source_lang:
            source_lang = self._normalize_lang_code(source_lang)
        
        # Skip translation if source and target are the same
        if source_lang and source_lang == target_lang:
            return text
        
        # Try OpenAI first (best quality)
        if self._openai_client and self.provider in ("openai", "auto"):
            try:
                return self._translate_openai(text, target_lang, source_lang)
            except Exception as e:
                logger.warning(f"OpenAI translation failed: {e}")
                if self.provider == "auto" and self._aws_translate:
                    pass  # Fall through to AWS
                else:
                    return text  # Return original if no fallback
        
        # Try AWS Translate
        if self._aws_translate and self.provider in ("aws", "auto"):
            try:
                return self._translate_aws(text, target_lang, source_lang)
            except Exception as e:
                logger.warning(f"AWS translation failed: {e}")
                return text
        
        logger.warning("No translation provider available, returning original text")
        return text
    
    def _translate_openai(
        self, 
        text: str, 
        target_lang: str, 
        source_lang: Optional[str]
    ) -> str:
        """Translate using OpenAI GPT-4o."""
        target_name = self._get_language_name(target_lang)
        
        messages = [
            {
                "role": "system",
                "content": f"You are a professional translator. Translate the following text to {target_name}. "
                          f"Maintain the original meaning, tone, and formatting. "
                          f"Only output the translation, nothing else."
            },
            {
                "role": "user",
                "content": text
            }
        ]
        
        response = self._openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3,  # Lower temperature for consistent translations
            max_tokens=len(text) * 2  # Allow for expansion in translation
        )
        
        translated = response.choices[0].message.content.strip()
        logger.debug(f"Translated {len(text)} chars to {target_lang}")
        return translated
    
    def _translate_aws(
        self, 
        text: str, 
        target_lang: str, 
        source_lang: Optional[str]
    ) -> str:
        """Translate using AWS Translate."""
        # AWS uses different language codes
        aws_target = self._to_aws_lang_code(target_lang)
        aws_source = self._to_aws_lang_code(source_lang) if source_lang else "auto"
        
        response = self._aws_translate.translate_text(
            Text=text,
            SourceLanguageCode=aws_source,
            TargetLanguageCode=aws_target
        )
        
        return response['TranslatedText']
    
    def _normalize_lang_code(self, code: str) -> str:
        """Normalize language code to ISO 639-1."""
        if not code:
            return "en"
        
        code = code.lower().strip()
        
        # Handle full language names
        name_to_code = {
            "english": "en",
            "spanish": "es",
            "french": "fr",
            "german": "de",
            "portuguese": "pt",
            "italian": "it",
            "dutch": "nl",
            "russian": "ru",
            "japanese": "ja",
            "korean": "ko",
            "chinese": "zh",
            "arabic": "ar",
        }
        
        if code in name_to_code:
            return name_to_code[code]
        
        # Handle ISO 639-3 codes
        iso_639_3_to_1 = {
            "eng": "en",
            "spa": "es",
            "fra": "fr",
            "deu": "de",
            "por": "pt",
            "ita": "it",
            "nld": "nl",
            "rus": "ru",
            "jpn": "ja",
            "kor": "ko",
            "zho": "zh",
            "ara": "ar",
        }
        
        if code in iso_639_3_to_1:
            return iso_639_3_to_1[code]
        
        # Already ISO 639-1
        return code[:2] if len(code) > 2 else code
    
    def _to_aws_lang_code(self, code: str) -> str:
        """Convert to AWS Translate language codes."""
        code = self._normalize_lang_code(code)
        
        # AWS uses specific codes for some languages
        aws_codes = {
            "zh": "zh",
            "zh-cn": "zh",
            "zh-tw": "zh-TW",
        }
        
        return aws_codes.get(code, code)
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code."""
        names = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "pt": "Portuguese",
            "it": "Italian",
            "nl": "Dutch",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
            "ar": "Arabic",
        }
        return names.get(code, code)


# Singleton instance
_translator_instance: Optional[TranslationService] = None


def get_translator(provider: str = "openai") -> TranslationService:
    """Get the singleton translation service instance."""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = TranslationService(provider=provider)
    return _translator_instance
