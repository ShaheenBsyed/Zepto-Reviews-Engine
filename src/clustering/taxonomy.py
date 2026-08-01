from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def consolidate_themes(
    themes: List[Dict[str, Any]],
    overlap_threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Consolidate themes that share too many representative chunks.

    Two themes are consolidated if they share more than `overlap_threshold`
    fraction of their top representative chunks (checked by chunk_id overlap).

    Args:
        themes: List of theme dicts, each with 'cluster_id', 'category',
            'barrier', 'description', 'quotes', 'keywords', and optionally
            'representative_chunks'.
        overlap_threshold: Fraction of shared chunks that triggers consolidation.

    Returns:
        Consolidated list of themes with merged labels and descriptions.
    """
    if len(themes) <= 1:
        return themes

    themes = [dict(t) for t in themes]

    for t in themes:
        if "representative_chunks" not in t:
            t["representative_chunks"] = [q for q in t.get("quotes", []) if isinstance(q, str) and len(q) > 20][:5]
        if "keywords" not in t:
            t["keywords"] = []
        if "category" not in t:
            t["category"] = "General / Multiple Categories"
        if "barrier" not in t:
            t["barrier"] = "Trust Issues"

    merged: List[Dict[str, Any]] = []
    merged_into: set[int] = set()

    for i, theme_a in enumerate(themes):
        if theme_a["cluster_id"] in merged_into:
            continue
        current = dict(theme_a)
        merged_into.add(theme_a["cluster_id"])

        for j, theme_b in enumerate(themes):
            if j <= i or theme_b["cluster_id"] in merged_into:
                continue

            a_chunks = set(current.get("representative_chunks", []))
            b_chunks = set(theme_b.get("representative_chunks", []))
            if not a_chunks or not b_chunks:
                continue
            overlap = len(a_chunks & b_chunks) / min(len(a_chunks), len(b_chunks))

            if overlap > overlap_threshold:
                current["description"] = (
                    (current.get("description", "") or "")
                    + " "
                    + (theme_b.get("description", "") or "")
                ).strip()
                current["representative_chunks"] = list(a_chunks | b_chunks)
                current["quotes"] = _merge_quotes(
                    current.get("quotes", []),
                    theme_b.get("quotes", []),
                )
                kw_a = set(current.get("keywords", []))
                kw_b = set(theme_b.get("keywords", []))
                current["keywords"] = list(kw_a | kw_b)
                current["num_samples"] = current.get("num_samples", 0) + theme_b.get("num_samples", 0)
                merged_into.add(theme_b["cluster_id"])
                logger.info(
                    "Consolidated cluster %d into cluster %d (overlap=%.2f)",
                    theme_b["cluster_id"],
                    current["cluster_id"],
                    overlap,
                )

        merged.append(current)

    logger.info(
        "Consolidated %d themes down to %d",
        len(themes),
        len(merged),
    )
    return merged


def _merge_quotes(quotes_a: List[str], quotes_b: List[str], max_quotes: int = 3) -> List[str]:
    """Merge two quote lists, deduplicating by content."""
    seen: set[str] = set()
    merged: List[str] = []
    for q in quotes_a + quotes_b:
        q_clean = q.strip()[:200]
        if q_clean and q_clean not in seen and len(q_clean) > 20:
            seen.add(q_clean)
            merged.append(q_clean)
            if len(merged) >= max_quotes:
                break
    return merged


def save_taxonomy(
    themes: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> Path:
    """Save the theme taxonomy JSON to disk."""
    output_path = Path(output_path or settings.outputs_dir / "themes.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    serializable_themes = []
    for t in themes:
        serializable_themes.append(
            {
                "cluster_id": t.get("cluster_id"),
                "theme_name": t.get("theme_name") or f"{t.get('barrier', 'Untitled')} — {t.get('category', 'General')}",
                "category": t.get("category", "General / Multiple Categories"),
                "barrier": t.get("barrier", "Trust Issues"),
                "description": t.get("description", ""),
                "keywords": t.get("keywords", []),
                "quotes": t.get("quotes", []),
                "representative_chunks": t.get("representative_chunks", []),
                "num_samples": t.get("num_samples", 0),
            }
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable_themes, f, indent=2, ensure_ascii=False)

    logger.info("Theme taxonomy saved with %d themes to %s", len(serializable_themes), output_path)
    return output_path


def load_taxonomy(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load a previously saved theme taxonomy JSON."""
    path = Path(path or settings.outputs_dir / "themes.json")
    if not path.exists():
        logger.warning("Taxonomy file not found at %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_taxonomy(themes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate that the taxonomy meets minimum quality requirements."""
    issues: List[str] = []

    if len(themes) < 2:
        issues.append(f"Only {len(themes)} themes found — expected at least 2")
    if len(themes) > 30:
        issues.append(f"{len(themes)} themes found — expected at most 30")

    categories = [t.get("category", "") for t in themes]
    duplicate_categories = [c for c in categories if categories.count(c) > 1]
    if duplicate_categories:
        issues.append(f"Duplicate categories found: {set(duplicate_categories)}")

    empty_categories = [t for t in themes if not t.get("category")]
    if empty_categories:
        issues.append(f"{len(empty_categories)} themes have no category")

    empty_barriers = [t for t in themes if not t.get("barrier")]
    if empty_barriers:
        issues.append(f"{len(empty_barriers)} themes have no barrier")

    themes_without_quotes = [t for t in themes if not t.get("quotes")]
    if themes_without_quotes:
        issues.append(f"{len(themes_without_quotes)} themes have no verbatim quotes")

    themes_without_keywords = [t for t in themes if not t.get("keywords")]
    if themes_without_keywords:
        issues.append(f"{len(themes_without_keywords)} themes have no keywords")

    themes_without_description = [t for t in themes if not t.get("description")]
    if themes_without_description:
        issues.append(f"{len(themes_without_description)} themes have no description")

    return {
        "valid": len(issues) == 0,
        "num_themes": len(themes),
        "issues": issues,
    }


def main() -> Dict[str, Any]:
    """Standalone entry point: load and validate existing taxonomy."""
    themes = load_taxonomy()
    validation = validate_taxonomy(themes)
    print(json.dumps(validation, indent=2))
    return validation


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))