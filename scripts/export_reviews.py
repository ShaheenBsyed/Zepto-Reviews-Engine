"""Export reviews from SQLite to JSON files for the Next.js API routes."""

import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "raw" / "reviews.db"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def export_reviews() -> None:
    if not DB_PATH.is_file():
        print("Database not found, skipping export.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT source, app, text, rating, created_at, language FROM reviews"
    )
    rows = cursor.fetchall()

    reviews = []
    for row in rows:
        reviews.append(
            {
                "source": row["source"] or "",
                "app": row["app"] or "",
                "text": row["text"] or "",
                "rating": row["rating"],
                "date": row["created_at"] or "",
                "language": row["language"] or "",
            }
        )

    conn.close()

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    reviews_path = OUTPUTS_DIR / "reviews_export.json"
    with open(reviews_path, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False)
    print(f"Exported {len(reviews)} reviews to {reviews_path}")

    source_counts: dict[str, int] = {}
    app_counts: dict[str, int] = {}
    rating_counts: dict[str, int] = {}

    for r in reviews:
        source_counts[r["source"]] = source_counts.get(r["source"], 0) + 1
        app_counts[r["app"]] = app_counts.get(r["app"], 0) + 1
        if r["rating"] is not None:
            key = str(r["rating"])
            rating_counts[key] = rating_counts.get(key, 0) + 1

    distribution = {
        "by_source": source_counts,
        "by_app": app_counts,
        "by_rating": rating_counts,
    }
    dist_path = OUTPUTS_DIR / "review_distribution.json"
    with open(dist_path, "w", encoding="utf-8") as f:
        json.dump(distribution, f, ensure_ascii=False)
    print(f"Exported review distribution to {dist_path}")

    sources = sorted(set(r["source"] for r in reviews if r["source"]))
    apps = sorted(set(r["app"] for r in reviews if r["app"]))
    ratings = sorted(set(r["rating"] for r in reviews if r["rating"] is not None))

    filters = {
        "sources": sources,
        "apps": apps,
        "ratings": ratings,
    }
    filters_path = OUTPUTS_DIR / "review_filters.json"
    with open(filters_path, "w", encoding="utf-8") as f:
        json.dump(filters, f, ensure_ascii=False)
    print(f"Exported review filters to {filters_path}")


if __name__ == "__main__":
    export_reviews()