"""
Relevance Filter Module

Filters records based on relevance to the research questions.
Uses a two-pass approach:
1. Keyword-based fast pass (required)
2. Optional semantic similarity pass using embeddings

The keyword list is derived from the 8 canonical research questions in config/research_questions.json.

Phase 2 of the preprocessing pipeline.
"""

from typing import List, Dict, Any, Set, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RelevanceFilter:
    """Filters records based on relevance to category exploration research questions."""
    
    def __init__(
        self,
        keywords: Optional[List[str]] = None,
        research_questions_path: Optional[str] = None,
        use_semantic_filter: bool = False,
        semantic_threshold: float = 0.7
    ):
        """
        Initialize the relevance filter.
        
        Args:
            keywords: Custom keyword list. If None, loads from research_questions.json.
            research_questions_path: Path to research_questions.json config file.
            use_semantic_filter: If True, uses semantic similarity as secondary check.
            semantic_threshold: Cosine similarity threshold for semantic pass.
        """
        self.use_semantic_filter = use_semantic_filter
        self.semantic_threshold = semantic_threshold
        
        # Load keywords
        if keywords is not None:
            self.keywords = set(k.lower() for k in keywords)
        else:
            self.keywords = self._load_keywords_from_config(research_questions_path)
        
        logger.info(f"Relevance filter initialized with {len(self.keywords)} keywords")
        logger.debug(f"Keywords: {sorted(self.keywords)}")
        
        # Semantic filter components (initialized later if needed)
        self.embedding_model = None
        self.anchor_embedding = None
    
    def _load_keywords_from_config(self, config_path: Optional[str]) -> Set[str]:
        """
        Load relevance keywords from research_questions.json.
        
        Args:
            config_path: Path to config file. If None, uses default path.
            
        Returns:
            Set of relevance keywords.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "research_questions.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Collect all relevance_keywords from all questions
            all_keywords = []
            for question in config.get('questions', []):
                all_keywords.extend(question.get('relevance_keywords', []))
            
            logger.info(f"Loaded {len(all_keywords)} keywords from {config_path}")
            return set(k.lower() for k in all_keywords)
            
        except Exception as e:
            logger.error(f"Failed to load keywords from {config_path}: {e}")
            # Fallback to default keywords
            return {
                'explore', 'category', 'try', 'discover', 'new product', 'habit',
                'recommend', 'suggest', 'first time', 'used to', 'switched', 'browsing',
                'same', 'always', 'routine', 'repeat', 'stick to', 'familiar',
                'didn\'t try', 'never tried', 'afraid', 'not sure', 'risky',
                'don\'t trust', 'expensive', 'unfamiliar', 'hesitant',
                'discovered', 'found out', 'didn\'t know', 'saw an ad',
                'fixed list', 'reorder', 'auto-order', 'don\'t browse',
                'reviews', 'ratings', 'brand', 'trust', 'guarantee',
                'frustrating', 'annoying', 'can\'t find', 'search doesn\'t work',
                'new baby', 'new pet', 'just moved', 'health goal',
                'wish they had', 'should add', 'why no', 'missing', 'no option'
            }
    
    def _initialize_semantic_filter(self):
        """
        Initialize the semantic filter components.
        This is lazy-loaded only if use_semantic_filter is True.
        """
        if self.embedding_model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info("Loading sentence transformer model for semantic filtering...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Create anchor embedding for "category exploration"
            anchor_text = (
                "I want to explore new categories and try different products "
                "in the grocery delivery app. I want to discover new items."
            )
            self.anchor_embedding = self.embedding_model.encode(anchor_text)
            
            logger.info("Semantic filter initialized")
            
        except ImportError:
            logger.warning("sentence-transformers not available, semantic filter disabled")
            self.use_semantic_filter = False
        except Exception as e:
            logger.error(f"Failed to initialize semantic filter: {e}")
            self.use_semantic_filter = False
    
    def _keyword_match(self, text: str) -> bool:
        """
        Check if text contains any relevance keywords.
        
        Args:
            text: The text to check.
            
        Returns:
            True if any keyword is found, False otherwise.
        """
        text_lower = text.lower()
        
        # Check for exact keyword matches
        for keyword in self.keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def _semantic_match(self, text: str) -> bool:
        """
        Check if text is semantically similar to category exploration.
        
        Args:
            text: The text to check.
            
        Returns:
            True if semantic similarity exceeds threshold, False otherwise.
        """
        if not self.use_semantic_filter or self.embedding_model is None:
            # If semantic filter is not enabled, return True (pass)
            return True
        
        try:
            text_embedding = self.embedding_model.encode(text)
            
            # Compute cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity(
                [text_embedding],
                [self.anchor_embedding]
            )[0][0]
            
            return similarity >= self.semantic_threshold
            
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}, defaulting to pass")
            return True
    
    def filter_record(self, record: Dict[str, Any]) -> bool:
        """
        Determine if a record should be retained based on relevance.
        
        Args:
            record: A record with at least a 'text' field.
            
        Returns:
            True if the record should be retained, False otherwise.
        """
        text = record.get('text', '').strip()
        
        if not text:
            logger.warning("Record has empty text field")
            return False
        
        # Keyword pass (required)
        if not self._keyword_match(text):
            logger.debug(f"Filtered out record (no keyword match): {text[:50]}...")
            return False
        
        # Semantic pass (optional)
        if self.use_semantic_filter:
            self._initialize_semantic_filter()
            if not self._semantic_match(text):
                logger.debug(f"Filtered out record (semantic threshold not met): {text[:50]}...")
                return False
        
        return True
    
    def filter_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter a list of records based on relevance.
        
        Args:
            records: List of records to filter.
            
        Returns:
            List of records that passed the relevance filter.
        """
        filtered = [record for record in records if self.filter_record(record)]
        
        retention_rate = len(filtered) / len(records) if records else 0
        
        logger.info(
            f"Relevance filter: {len(filtered)}/{len(records)} records retained "
            f"({len(records) - len(filtered)} filtered out, {retention_rate:.1%} retention)"
        )
        
        # Warn if retention is too low
        if retention_rate < 0.3:
            logger.warning(
                f"Relevance filter retention rate is very low ({retention_rate:.1%}). "
                "Consider expanding the keyword list."
            )
        
        return filtered
