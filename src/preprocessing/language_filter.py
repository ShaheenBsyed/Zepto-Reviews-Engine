"""
Language Filter Module

Filters records based on language detection. Keeps English and optionally Hinglish reviews.
Uses langdetect for language identification.

Phase 2 of the preprocessing pipeline.
"""

from typing import List, Dict, Any, Optional
from langdetect import detect, LangDetectException
import logging

logger = logging.getLogger(__name__)


class LanguageFilter:
    """Filters records based on language detection."""
    
    def __init__(self, allow_hinglish: bool = False):
        """
        Initialize the language filter.
        
        Args:
            allow_hinglish: If True, allows Hinglish (mixed Hindi-English) records.
                          If False, only English records are retained.
        """
        self.allow_hinglish = allow_hinglish
        
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of a text string.
        
        Args:
            text: The text to analyze.
            
        Returns:
            Language code (e.g., 'en', 'hi') or None if detection fails.
        """
        try:
            return detect(text)
        except LangDetectException:
            logger.warning(f"Language detection failed for text: {text[:50]}...")
            return None
    
    def is_hinglish(self, text: str) -> bool:
        """
        Heuristic detection of Hinglish (mixed Hindi-English).
        
        This is a simple heuristic - true Hinglish detection would require
        more sophisticated NLP. For now, we use a basic check for common
        Hindi transliteration patterns mixed with English.
        
        Args:
            text: The text to analyze.
            
        Returns:
            True if the text appears to be Hinglish, False otherwise.
        """
        # Common Hindi words in Roman script
        hinglish_indicators = [
            'hai', 'hain', 'kya', 'kaise', 'bahut', 'accha', 'acha',
            'bhai', 'did', 'please', 'sahi', 'galat', 'kuch', 'isko',
            'usko', 'mera', 'tera', 'hamara', 'tumhara', 'ye', 'woh'
        ]
        
        text_lower = text.lower()
        indicator_count = sum(1 for word in hinglish_indicators if word in text_lower)
        
        # If we have multiple Hindi indicators and English words, it's likely Hinglish
        english_words = [w for w in text_lower.split() if w.isalpha() and len(w) > 2]
        has_english = len(english_words) > 3
        
        return indicator_count >= 2 and has_english
    
    def filter_record(self, record: Dict[str, Any]) -> bool:
        """
        Determine if a record should be retained based on language.
        
        Args:
            record: A record with at least a 'text' field.
            
        Returns:
            True if the record should be retained, False otherwise.
        """
        text = record.get('text', '').strip()
        
        if not text:
            logger.warning("Record has empty text field")
            return False
        
        # Detect language
        lang = self.detect_language(text)
        
        # If detection failed, be conservative and keep it
        if lang is None:
            logger.info(f"Language detection failed, keeping record: {text[:50]}...")
            return True
        
        # Always keep English
        if lang == 'en':
            return True
        
        # If Hinglish is allowed, check for Hinglish patterns
        if self.allow_hinglish and self.is_hinglish(text):
            logger.debug(f"Retained Hinglish record: {text[:50]}...")
            return True
        
        # Log why we're filtering
        logger.debug(f"Filtered out non-English record (lang={lang}): {text[:50]}...")
        return False
    
    def filter_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter a list of records based on language.
        
        Args:
            records: List of records to filter.
            
        Returns:
            List of records that passed the language filter.
        """
        filtered = [record for record in records if self.filter_record(record)]
        
        logger.info(
            f"Language filter: {len(filtered)}/{len(records)} records retained "
            f"({len(records) - len(filtered)} filtered out)"
        )
        
        return filtered
