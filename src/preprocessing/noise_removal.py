"""
Noise Removal Module

Removes low-quality, uninformative content from the corpus.
Filters out:
- Reviews under minimum word count (default 15 words)
- Emoji-only or punctuation-only content
- Generic boilerplate phrases ("good app", "nice app", "5 stars", etc.)

Phase 2 of the preprocessing pipeline.
"""

from typing import List, Dict, Any, Set
import re
import logging

logger = logging.getLogger(__name__)


class NoiseRemover:
    """Removes low-quality, uninformative content from records."""
    
    def __init__(self, min_word_count: int = 6):
        """
        Initialize the noise remover.
        
        Args:
            min_word_count: Minimum number of words a record must have to be retained.
                          Reviews shorter than this are almost always uninformative.
        """
        self.min_word_count = min_word_count
        
        # Generic boilerplate phrases that provide no signal
        self.boilerplate_phrases = {
            'good app', 'nice app', 'great app', 'awesome app',
            'bad app', 'terrible app', 'worst app',
            '5 stars', '5 star', '4 stars', '4 star',
            '1 star', '1 stars', '2 stars', '2 star',
            'love it', 'hate it', 'excellent', 'amazing',
            'very good', 'very bad', 'perfect', 'useless',
            'pathetic', 'superb', 'fantastic', 'horrible',
            'best app', 'worst app', 'good service', 'bad service'
        }
    
    def _count_words(self, text: str) -> int:
        """
        Count the number of words in text.
        
        Args:
            text: The text to analyze.
            
        Returns:
            Number of words.
        """
        # Split on whitespace and filter empty strings
        words = [w for w in text.split() if w.strip()]
        return len(words)
    
    def _is_emoji_only(self, text: str) -> bool:
        """
        Check if text consists only of emojis or special characters.
        
        Args:
            text: The text to analyze.
            
        Returns:
            True if text is emoji/punctuation only, False otherwise.
        """
        # Remove all emojis and special characters
        # If nothing remains, it was emoji-only
        cleaned = re.sub(r'[^\w\s]', '', text)
        cleaned = re.sub(r'\s+', '', cleaned)
        return len(cleaned) == 0
    
    def _is_boilerplate(self, text: str) -> bool:
        """
        Check if text is a generic boilerplate phrase.
        
        Args:
            text: The text to analyze.
            
        Returns:
            True if text matches boilerplate patterns, False otherwise.
        """
        text_lower = text.lower().strip()
        
        # Direct match with boilerplate phrases
        if text_lower in self.boilerplate_phrases:
            return True
        
        # Check if text is just a boilerplate phrase with minimal variation
        for phrase in self.boilerplate_phrases:
            # If the text is very short and contains the boilerplate phrase
            if len(text_lower) <= len(phrase) + 5 and phrase in text_lower:
                return True
        
        return False
    
    def _has_meaningful_content(self, text: str) -> bool:
        """
        Check if text has any meaningful alphanumeric content.
        
        Args:
            text: The text to analyze.
            
        Returns:
            True if text has meaningful content, False otherwise.
        """
        # Check for at least some alphanumeric characters
        alphanumeric_chars = re.findall(r'[a-zA-Z0-9]', text)
        return len(alphanumeric_chars) >= 3
    
    def filter_record(self, record: Dict[str, Any]) -> bool:
        """
        Determine if a record should be retained based on noise criteria.
        
        Args:
            record: A record with at least a 'text' field.
            
        Returns:
            True if the record should be retained, False otherwise.
        """
        text = record.get('text', '').strip()
        
        if not text:
            logger.warning("Record has empty text field")
            return False
        
        # Check for emoji-only content
        if self._is_emoji_only(text):
            logger.debug(f"Filtered emoji-only record: {text[:50]}...")
            return False
        
        # Check for meaningful content
        if not self._has_meaningful_content(text):
            logger.debug(f"Filtered record with no meaningful content: {text[:50]}...")
            return False
        
        # Check minimum word count
        word_count = self._count_words(text)
        if word_count < self.min_word_count:
            logger.debug(
                f"Filtered record with {word_count} words (minimum {self.min_word_count}): "
                f"{text[:50]}..."
            )
            return False
        
        # Check for boilerplate
        if self._is_boilerplate(text):
            logger.debug(f"Filtered boilerplate record: {text[:50]}...")
            return False
        
        return True
    
    def filter_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter a list of records based on noise criteria.
        
        Args:
            records: List of records to filter.
            
        Returns:
            List of records that passed the noise filter.
        """
        filtered = [record for record in records if self.filter_record(record)]
        
        logger.info(
            f"Noise removal: {len(filtered)}/{len(records)} records retained "
            f"({len(records) - len(filtered)} filtered out)"
        )
        
        return filtered
