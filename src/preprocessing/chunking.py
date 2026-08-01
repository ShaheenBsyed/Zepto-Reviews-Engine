"""
Chunking Module

Splits long text into overlapping chunks for embedding and retrieval.
- Short reviews (< 300 tokens): kept as single chunk
- Long posts: split into 300-500 token segments with 50-token overlap

Each chunk inherits all metadata from the parent record.

Phase 2 of the preprocessing pipeline.
"""

from typing import List, Dict, Any, Optional
import uuid
import logging
import tiktoken

logger = logging.getLogger(__name__)


class Chunker:
    """Splits text into overlapping chunks for embedding and retrieval."""
    
    def __init__(
        self,
        min_chunk_tokens: int = 300,
        max_chunk_tokens: int = 500,
        overlap_tokens: int = 50
    ):
        """
        Initialize the chunker.
        
        Args:
            min_chunk_tokens: Minimum tokens for a chunk (below this, don't split).
            max_chunk_tokens: Maximum tokens per chunk.
            overlap_tokens: Number of tokens to overlap between chunks.
        """
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens
        
        # Initialize tokenizer (using cl100k_base - same as text-embedding-3-small)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken tokenizer: {e}")
            self.tokenizer = None
    
    def _count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in text.
        
        Args:
            text: The text to count tokens for.
            
        Returns:
            Number of tokens.
        """
        if self.tokenizer is None:
            # Fallback: approximate tokens as words * 1.3
            return len(text.split()) * 13 // 10
        
        return len(self.tokenizer.encode(text))
    
    def _split_into_chunks(
        self,
        text: str,
        record_id: str
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: The text to chunk.
            record_id: The parent record ID for provenance.
            
        Returns:
            List of chunk dictionaries.
        """
        token_count = self._count_tokens(text)
        
        # If text is short enough, keep as single chunk
        if token_count <= self.max_chunk_tokens:
            return [{
                'chunk_id': str(uuid.uuid4()),
                'text': text,
                'parent_record_id': record_id,
                'chunk_index': 0,
                'total_chunks': 1
            }]
        
        # Split long text into chunks
        chunks = []
        chunk_index = 0
        
        # Use sentence-based splitting for better semantic boundaries
        sentences = self._split_into_sentences(text)
        
        current_chunk_text = ""
        current_chunk_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            
            # If adding this sentence would exceed max chunk size,
            # save current chunk and start new one
            if current_chunk_tokens + sentence_tokens > self.max_chunk_tokens and current_chunk_text:
                # Save current chunk
                chunks.append({
                    'chunk_id': str(uuid.uuid4()),
                    'text': current_chunk_text.strip(),
                    'parent_record_id': record_id,
                    'chunk_index': chunk_index,
                    'total_chunks': 0  # Will update at end
                })
                chunk_index += 1
                
                # Start new chunk with overlap
                # For overlap, we keep the last N tokens from previous chunk
                overlap_text = self._get_overlap_text(current_chunk_text)
                current_chunk_text = overlap_text + " " + sentence
                current_chunk_tokens = self._count_tokens(current_chunk_text)
            else:
                # Add sentence to current chunk
                if current_chunk_text:
                    current_chunk_text += " " + sentence
                else:
                    current_chunk_text = sentence
                current_chunk_tokens += sentence_tokens
        
        # Don't forget the last chunk
        if current_chunk_text.strip():
            chunks.append({
                'chunk_id': str(uuid.uuid4()),
                'text': current_chunk_text.strip(),
                'parent_record_id': record_id,
                'chunk_index': chunk_index,
                'total_chunks': 0  # Will update at end
            })
        
        # Update total_chunks for all chunks
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk['total_chunks'] = total_chunks
        
        logger.debug(f"Split text into {total_chunks} chunks (original: {token_count} tokens)")
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: The text to split.
            
        Returns:
            List of sentences.
        """
        # Simple sentence splitting on common punctuation
        # This is a heuristic - for production, consider using NLTK sentence tokenizer
        import re
        
        # Split on . ! ? followed by space or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _get_overlap_text(self, text: str) -> str:
        """
        Get the last N tokens of text for overlap.
        
        Args:
            text: The text to extract overlap from.
            
        Returns:
            Overlap text.
        """
        if self.overlap_tokens == 0:
            return ""
        
        token_count = self._count_tokens(text)
        
        if token_count <= self.overlap_tokens:
            return text
        
        # Get the last overlap_tokens tokens
        if self.tokenizer:
            tokens = self.tokenizer.encode(text)
            overlap_tokens = tokens[-self.overlap_tokens:]
            overlap_text = self.tokenizer.decode(overlap_tokens)
        else:
            # Fallback: approximate by word count
            words = text.split()
            overlap_words = words[-(self.overlap_tokens * 10 // 13):]  # Approximate
            overlap_text = " ".join(overlap_words)
        
        return overlap_text
    
    def chunk_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a single record.
        
        Args:
            record: A record with at least 'text' and 'id' fields.
            
        Returns:
            List of chunk dictionaries with inherited metadata.
        """
        text = record.get('text', '').strip()
        record_id = record.get('id', '')
        
        if not text:
            logger.warning(f"Record {record_id} has empty text, skipping")
            return []
        
        # Split into chunks
        chunks = self._split_into_chunks(text, record_id)
        
        # Inherit metadata from parent record
        metadata_fields = ['source', 'app', 'rating', 'created_at', 'language', 'metadata']
        for chunk in chunks:
            for field in metadata_fields:
                if field in record:
                    chunk[field] = record[field]
        
        return chunks
    
    def chunk_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple records.
        
        Args:
            records: List of records to chunk.
            
        Returns:
            List of all chunks from all records.
        """
        all_chunks = []
        
        for record in records:
            chunks = self.chunk_record(record)
            all_chunks.extend(chunks)
        
        logger.info(
            f"Chunking: {len(all_chunks)} chunks created from {len(records)} records "
            f"(average {len(all_chunks) / len(records):.1f} chunks per record)"
        )
        
        return all_chunks
