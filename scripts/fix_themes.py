#!/usr/bin/env python
"""Post-process themes.json to merge similar barriers and add theme_name."""
import json
from collections import defaultdict
from pathlib import Path

THEMES_PATH = Path("outputs/themes.json")

BARRIER_MERGE = {
    "Delivery Delays": "Delivery & Availability",
    "Limited Availability": "Delivery & Availability",
    "Out of Stock": "Delivery & Availability",
    "Poor Customer Support": "Support & Refund Issues",
    "Refund Concerns": "Support & Refund Issues",
    "Quality Concerns": "Quality & Freshness",
    "Freshness Concerns": "Quality & Freshness",
    "App Usability Issues": "App & Experience",
    "Limited Assortment": "App & Experience",
    "Trust Issues": "Trust & Pricing",
    "High Prices": "Trust & Pricing",
}


def merge_themes(themes):
    grouped = defaultdict(list)
    for t in themes:
        category = t.get("category", "General / Multiple Categories")
        barrier = t.get("barrier", "Trust Issues")
        merged_barrier = BARRIER_MERGE.get(barrier, barrier)
        key = (category, merged_barrier)
        grouped[key].append(t)

    merged = []
    for (category, barrier), group in grouped.items():
        combined_quotes = []
        seen_quotes = set()
        all_keywords = []
        seen_keywords = set()
        total_samples = 0
        all_chunks = []
        descriptions = []

        for t in group:
            total_samples += t.get("num_samples", 0)
            all_chunks.extend(t.get("representative_chunks", []))
            desc = t.get("description", "").strip()
            if desc:
                descriptions.append(desc)
            for q in t.get("quotes", []):
                q_clean = q.strip()[:200]
                if q_clean and q_clean not in seen_quotes and len(q_clean) > 20:
                    seen_quotes.add(q_clean)
                    combined_quotes.append(q_clean)
            for kw in t.get("keywords", []):
                kw_clean = kw.strip().lower()
                if kw_clean and kw_clean not in seen_keywords:
                    seen_keywords.add(kw_clean)
                    all_keywords.append(kw)

        description = " ".join(descriptions[:2]) if descriptions else f"Customers discussing {category.lower()} mention concerns about {barrier.lower()}."
        theme_name = f"{barrier} — {category}"

        merged.append({
            "cluster_id": group[0]["cluster_id"],
            "theme_name": theme_name,
            "category": category,
            "barrier": barrier,
            "description": description[:500],
            "keywords": all_keywords[:8],
            "quotes": combined_quotes[:5],
            "representative_chunks": list(dict.fromkeys(all_chunks))[:20],
            "num_samples": total_samples,
        })

    merged.sort(key=lambda t: t["num_samples"], reverse=True)
    for i, t in enumerate(merged):
        t["cluster_id"] = i

    return merged


def main():
    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        themes = json.load(f)

    print(f"Original themes: {len(themes)}")
    merged = merge_themes(themes)
    print(f"Merged themes: {len(merged)}")

    with open(THEMES_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"Saved to {THEMES_PATH}")


if __name__ == "__main__":
    main()
