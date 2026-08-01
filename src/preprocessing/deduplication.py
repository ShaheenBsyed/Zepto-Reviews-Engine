"""
Deduplication Module

Removes near-duplicate records using MinHash LSH (Locality Sensitive Hashing).
This catches paraphrased duplicates that exact-match filtering would miss.

Phase 2 of the preprocessing pipeline.
"""

from typing import List, Dict, Any, Set
from datasketch import MinHash, MinHashLSH
import logging
import re

logger = logging.getLogger(__name__)


class Deduplicator:
    """Removes near-duplicate records using MinHash LSH."""
    
    def __init__(self, num_perm: int = 128, threshold: float = 0.97, ngram_size: int = 3):
        """
        Initialize the deduplicator.
        
        Args:
            num_perm: Number of permutations for MinHash (higher = more accurate but slower).
            threshold: Jaccard similarity threshold for considering records as duplicates.
                      0.97 is conservative to avoid flagging distinct but similar reviews.
            ngram_size: Size of n-grams for MinHash (default 3 for word trigrams).
        """
        self.num_perm = num_perm
        self.threshold = threshold
        self.ngram_size = ngram_size
        
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for MinHash: lowercase, remove punctuation, normalize whitespace.
        
        Args:
            text: Raw text.
            
        Returns:
            Preprocessed text.
        """
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation but keep alphanumeric and spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _get_ngrams(self, text: str) -> List[str]:
        """
        Generate n-grams from text.
        
        Args:
            text: Preprocessed text.
            
        Returns:
            List of n-grams.
        """
        tokens = text.split()
        if len(tokens) < self.ngram_size:
            return tokens
        
        ngrams = []
        for i in range(len(tokens) - self.ngram_size + 1):
            ngram = ' '.join(tokens[i:i + self.ngram_size])
            ngrams.append(ngram)
        
        return ngrams
    
    def _create_minhash(self, text: str) -> MinHash:
        """
        Create a MinHash signature for text.
        
        Args:
            text: Raw text.
            
        Returns:
            MinHash object.
        """
        preprocessed = self._preprocess_text(text)
        ngrams = self._get_ngrams(preprocessed)
        
        minhash = MinHash(num_perm=self.num_perm)
        for ngram in ngrams:
            minhash.update(ngram.encode('utf-8'))
        
        return minhash
    
    def deduplicate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove near-duplicate records from the list.
        
        Args:
            records: List of records to deduplicate. Each record must have a 'text' field.
            
        Returns:
            List of deduplicated records.
        """
        if not records:
            logger.warning("Empty records list provided to deduplicator")
            return []
        
        logger.info(f"Starting deduplication on {len(records)} records")
        
        # Create LSH index
        lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        
        # Store MinHash signatures and record indices
        minhashes = {}
        duplicate_indices: Set[int] = set()
        
        # Build index
        for idx, record in enumerate(records):
            text = record.get('text', '')
            if not text:
                logger.warning(f"Record at index {idx} has empty text, skipping")
                continue
            
            minhash = self._create_minhash(text)
            minhashes[idx] = minhash
            
            # Insert into LSH
            lsh.insert(idx, minhash)
        
        # Find duplicates
        for idx, record in enumerate(records):
            if idx in duplicate_indices:
                continue
            
            text = record.get('text', '')
            if not text:
                continue
            
            minhash = minhashes[idx]
            
            # Query for similar records
            similar_indices = set(lsh.query(minhash))
            
            # Remove the current index from results (self-match)
            similar_indices.discard(idx)
            
            # Mark similar records as duplicates
            for similar_idx in similar_indices:
                if similar_idx not in duplicate_indices:
                    logger.debug(
                        f"Found duplicate: record {similar_idx} is similar to record {idx} "
                        f"(similarity >= {self.threshold})"
                    )
                    duplicate_indices.add(similar_idx)
        
        # Filter out duplicates
        deduplicated = [
            record for idx, record in enumerate(records)
            if idx not in duplicate_indices
        ]
        
        logger.info(
            f"Deduplication: {len(deduplicated)}/{len(records)} records retained "
            f"({len(records) - len(deduplicated)} duplicates removed)"
        )
        
        return deduplicated
