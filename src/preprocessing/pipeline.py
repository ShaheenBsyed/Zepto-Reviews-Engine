"""
Preprocessing Pipeline Orchestrator

Coordinates all preprocessing steps in sequence:
1. Language filter
2. Deduplication (MinHash)
3. Noise removal
4. Chunking

This is the main entry point for Phase 2 preprocessing.
"""

from typing import List, Dict, Any, Optional
import json
import logging
from pathlib import Path
from datetime import datetime
from collections import Counter

from .language_filter import LanguageFilter
from .deduplication import Deduplicator
from .noise_removal import NoiseRemover
from .chunking import Chunker

logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """
    Orchestrates the complete preprocessing pipeline.

    The pipeline runs sequentially:
    Raw records → Language filter → Deduplication → Noise removal → Chunking → Clean chunks (JSONL)
    """

    def __init__(
        self,
        allow_hinglish: bool = False,
        min_word_count: int = 6,
        dedup_threshold: float = 0.97,
        min_chunk_tokens: int = 300,
        max_chunk_tokens: int = 500,
        overlap_tokens: int = 50,
    ):
        """
        Initialize the preprocessing pipeline.

        Args:
            allow_hinglish: Allow Hinglish (mixed Hindi-English) records.
            min_word_count: Minimum word count for noise removal.
            dedup_threshold: Jaccard similarity threshold for deduplication.
            min_chunk_tokens: Minimum tokens per chunk.
            max_chunk_tokens: Maximum tokens per chunk.
            overlap_tokens: Token overlap between chunks.
        """
        self.allow_hinglish = allow_hinglish
        self.min_word_count = min_word_count
        self.dedup_threshold = dedup_threshold
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens

        # Initialize pipeline components
        self.language_filter = LanguageFilter(allow_hinglish=allow_hinglish)
        self.deduplicator = Deduplicator(threshold=dedup_threshold)
        self.noise_remover = NoiseRemover(min_word_count=min_word_count)
        self.chunker = Chunker(
            min_chunk_tokens=min_chunk_tokens,
            max_chunk_tokens=max_chunk_tokens,
            overlap_tokens=overlap_tokens,
        )

        # Statistics tracking
        self.stats = {
            "raw_count": 0,
            "after_language_filter": 0,
            "after_deduplication": 0,
            "after_noise_removal": 0,
            "final_chunk_count": 0,
        }

        self._records_after_noise_removal: List[Dict[str, Any]] = []

    def run(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run the complete preprocessing pipeline.

        Args:
            records: List of raw records from the ingestion layer.

        Returns:
            List of clean, chunked records ready for embedding.
        """
        logger.info("=" * 60)
        logger.info("Starting Preprocessing Pipeline")
        logger.info(f"Input: {len(records)} raw records")
        logger.info("=" * 60)

        self.stats["raw_count"] = len(records)

        # Step 1: Language filter
        logger.info("\n[Step 1/4] Language Filter")
        records = self.language_filter.filter_records(records)
        self.stats["after_language_filter"] = len(records)

        if len(records) == 0:
            logger.error("No records passed language filter. Aborting pipeline.")
            return []

        # Step 2: Deduplication
        logger.info("\n[Step 2/4] Deduplication (MinHash)")
        dedup_before = len(records)
        records = self.deduplicator.deduplicate_records(records)
        self.stats["after_deduplication"] = len(records)
        duplicates_removed = dedup_before - len(records)

        if len(records) == 0:
            logger.error("No records passed deduplication. Aborting pipeline.")
            return []

        # Step 3: Noise removal
        logger.info("\n[Step 3/4] Noise Removal")
        noise_before = len(records)
        records = self.noise_remover.filter_records(records)
        self.stats["after_noise_removal"] = len(records)
        noise_removed = noise_before - len(records)

        if len(records) == 0:
            logger.error("No records passed noise removal. Aborting pipeline.")
            return []

        # Store records after noise removal for reporting
        self._records_after_noise_removal = records

        # Step 4: Chunking
        logger.info("\n[Step 4/4] Chunking")
        chunks = self.chunker.chunk_records(records)
        self.stats["final_chunk_count"] = len(chunks)

        # Validate corpus quality
        self._validate_corpus(chunks, records)

        # Generate detailed report
        self._generate_report(
            duplicates_removed,
            noise_removed,
            records,
            chunks,
        )

        # Log final statistics
        self._log_stats()

        return chunks

    def _validate_corpus(
        self,
        chunks: List[Dict[str, Any]],
        records: List[Dict[str, Any]],
    ) -> None:
        """Validate corpus quality before saving."""
        logger.info("\nvalidating corpus quality...")

        required_fields = ["chunk_id", "text", "parent_record_id", "source", "app"]
        errors: List[str] = []

        # Check 1: No empty chunks
        empty_chunks = [c for c in chunks if not c.get("text", "").strip()]
        if empty_chunks:
            errors.append(f"Found {len(empty_chunks)} chunks with empty text")

        # Check 2: All chunks have required fields
        for i, chunk in enumerate(chunks):
            for field in required_fields:
                if field not in chunk or not chunk[field]:
                    errors.append(f"Chunk {i} missing required field '{field}'")

        # Check 3: No duplicate chunk IDs
        chunk_ids = [c["chunk_id"] for c in chunks if "chunk_id" in c]
        dup_ids = set([x for x in chunk_ids if chunk_ids.count(x) > 1])
        if dup_ids:
            errors.append(f"Found {len(dup_ids)} duplicate chunk IDs")

        # Check 4: Metadata preserved for every chunk
        for i, chunk in enumerate(chunks):
            for field in ["source", "app"]:
                if field not in chunk or not chunk[field]:
                    errors.append(f"Chunk {i} missing metadata field '{field}'")

        # Check 5: Randomly inspect 50 processed records
        import random

        sample_size = min(50, len(records))
        sample = random.sample(records, sample_size) if len(records) >= 50 else records
        for i, record in enumerate(sample):
            text = record.get("text", "").strip()
            if not text:
                errors.append(f"Sampled record {i} has empty text")
            if not record.get("source"):
                errors.append(f"Sampled record {i} missing source")
            if not record.get("app"):
                errors.append(f"Sampled record {i} missing app")

        if errors:
            error_msg = "Corpus validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Corpus validation passed: {len(chunks)} chunks, {len(records)} records")

    def _generate_report(
        self,
        duplicates_removed: int,
        noise_removed_count: int,
        records: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Generate a detailed preprocessing report."""
        # Compute distributions
        languages = Counter(r.get("language", "unknown") for r in records)
        ratings = Counter(r.get("rating") for r in records)
        sources = Counter(r.get("source", "unknown") for r in records)
        apps = Counter(r.get("app", "unknown") for r in records)

        # Compute average chunk length
        if chunks:
            total_chars = sum(len(c.get("text", "")) for c in chunks)
            avg_chunk_len = total_chars / len(chunks)
        else:
            avg_chunk_len = 0

        report_lines = [
            "==========================",
            "PREPROCESSING REPORT",
            "==========================",
            "",
            "Raw Reviews:              " + str(self.stats["raw_count"]),
            "After Language Filter:    " + str(self.stats["after_language_filter"]),
            f"Duplicates Removed:       {duplicates_removed}",
            f"Noise Removed:            {noise_removed_count}",
            "Final Reviews:            " + str(len(records)),
            "Chunks Generated:         " + str(self.stats["final_chunk_count"]),
            f"Average Chunk Length:     {avg_chunk_len:.0f} chars",
            "",
            "Language Distribution:",
        ]
        for lang, count in sorted(languages.items(), key=lambda x: -x[1]):
            report_lines.append(f"  {lang}: {count}")

        report_lines.append("")
        report_lines.append("Rating Distribution:")
        for rating in sorted(ratings.keys(), key=lambda r: r if r is not None else -1):
            if rating is None:
                continue
            report_lines.append(f"  {rating} star: {ratings[rating]}")

        report_lines.append("")
        report_lines.append("Source Distribution:")
        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            report_lines.append(f"  {source}: {count}")

        report_lines.append("")
        report_lines.append("App Distribution:")
        for app, count in sorted(apps.items(), key=lambda x: -x[1]):
            report_lines.append(f"  {app}: {count}")

        report_lines.append("")
        report_lines.append("==========================")

        report_text = "\n".join(report_lines)
        logger.info("\n" + report_text)

        # Save report alongside processed outputs
        output_dir = Path("data/processed")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "preprocessing_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info(f"Preprocessing report saved to {report_path}")

    def _log_stats(self):
        """Log pipeline statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("Preprocessing Pipeline Statistics")
        logger.info("=" * 60)
        logger.info(f"Raw records:                    {self.stats['raw_count']}")
        logger.info(
            f"After language filter:         {self.stats['after_language_filter']} "
            f"({self._pct(self.stats['after_language_filter'], self.stats['raw_count'])})"
        )
        logger.info(
            f"After deduplication:            {self.stats['after_deduplication']} "
            f"({self._pct(self.stats['after_deduplication'], self.stats['raw_count'])})"
        )
        logger.info(
            f"After noise removal:            {self.stats['after_noise_removal']} "
            f"({self._pct(self.stats['after_noise_removal'], self.stats['raw_count'])})"
        )
        logger.info(f"Final chunk count:              {self.stats['final_chunk_count']}")
        logger.info("=" * 60)

    def _pct(self, numerator: int, denominator: int) -> str:
        """Calculate percentage."""
        if denominator == 0:
            return "0.0%"
        return f"{100 * numerator / denominator:.1f}%"

    def save_chunks(
        self,
        chunks: List[Dict[str, Any]],
        output_path: str,
        include_stats: bool = True,
    ):
        """
        Save chunks to a JSONL file.

        Args:
            chunks: List of chunk dictionaries.
            output_path: Path to output JSONL file.
            include_stats: If True, prepends statistics as a JSON comment.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving chunks to {output_path}")

        with open(output_path, "w", encoding="utf-8") as f:
            # Write statistics as a comment line
            if include_stats:
                stats_line = f"# Preprocessing stats: {json.dumps(self.stats)}\n"
                f.write(stats_line)

            # Write each chunk as a JSON line
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(chunks)} chunks to {output_path}")

    def get_stats(self) -> Dict[str, int]:
        """Get pipeline statistics."""
        return self.stats.copy()


def load_records_from_sqlite(db_path: str) -> List[Dict[str, Any]]:
    """
    Load raw records from SQLite database.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        List of records.
    """
    import sqlite3

    logger.info(f"Loading records from SQLite database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews")

    records = [dict(row) for row in cursor.fetchall()]

    conn.close()

    logger.info(f"Loaded {len(records)} records from database")

    return records


def main():
    """
    Main entry point for running the preprocessing pipeline.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Preprocessing Pipeline for Zepto AI Review Engine"
    )
    parser.add_argument(
        "--input-db",
        type=str,
        default="data/raw/reviews.db",
        help="Path to SQLite database with raw reviews",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/clean_chunks.jsonl",
        help="Path to output JSONL file with clean chunks",
    )
    parser.add_argument(
        "--allow-hinglish",
        action="store_true",
        help="Allow Hinglish (mixed Hindi-English) records",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load records
    records = load_records_from_sqlite(args.input_db)

    if not records:
        logger.error("No records loaded from database. Exiting.")
        return

    # Initialize pipeline
    pipeline = PreprocessingPipeline(
        allow_hinglish=args.allow_hinglish,
    )

    # Run pipeline
    chunks = pipeline.run(records)

    # Save chunks
    pipeline.save_chunks(chunks, args.output)

    logger.info("Preprocessing pipeline completed successfully")


if __name__ == "__main__":
    main()
