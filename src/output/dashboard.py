"""
src/output/dashboard.py
===================================
Production-ready responsive web dashboard for Zepto AI Review Engine.

Serves as the primary output of the pipeline, visualizing insights, themes,
reviews, segment profiles, evaluation results, and UMAP clusters through an
interactive web interface. Designed for local development and deployable to
Vercel for public access.

Run with:
    python -m src.output.dashboard

The dashboard serves at http://localhost:5000
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from urllib.parse import quote

from flask import Flask, jsonify, render_template, request

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard() -> str:
    """Render the main dashboard page."""
    return render_template("dashboard.html")


# ── API: Insights ─────────────────────────────────────────────────────────────

@app.route("/api/insights")
def api_insights() -> str:
    """Return insights data as JSON, enriched with faithfulness scores if available."""
    insights_path = OUTPUTS_DIR / "insights.json"
    if not insights_path.is_file():
        return jsonify({"insights": [], "count": 0})

    with open(insights_path, encoding="utf-8") as f:
        data = json.load(f)

    eval_path = OUTPUTS_DIR / "eval_report.json"
    if eval_path.is_file():
        try:
            with open(eval_path, encoding="utf-8") as f:
                eval_data = json.load(f)
            per_insight = eval_data.get("faithfulness", {}).get("per_insight", {})
            for insight in data.get("insights", []):
                qid = insight.get("research_question_id", "")
                score_info = per_insight.get(qid, {})
                insight["faithfulness_score"] = score_info.get("faithfulness_score")
                insight["faithfulness_passed"] = score_info.get("faithfulness_passed")
                insight["faithfulness_judge"] = score_info.get("judge")
        except (json.JSONDecodeError, OSError):
            pass

    return jsonify(data)


# ── API: Themes ───────────────────────────────────────────────────────────────

@app.route("/api/themes")
def api_themes() -> str:
    """Return themes data as JSON."""
    themes_path = OUTPUTS_DIR / "themes.json"
    if themes_path.is_file():
        with open(themes_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"themes": data, "count": len(data)})
    return jsonify({"themes": [], "count": 0})


# ── API: Evaluation Report ────────────────────────────────────────────────────

@app.route("/api/eval")
def api_eval() -> str:
    """Return Phase 6 evaluation report as JSON."""
    eval_path = OUTPUTS_DIR / "eval_report.json"
    if eval_path.is_file():
        with open(eval_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"phase": "Phase 6", "passed": False, "error": "No evaluation report found."})


# ── API: UMAP Visualization ───────────────────────────────────────────────────

@app.route("/api/umap")
def api_umap() -> str:
    """Return UMAP cluster visualization as JSON coordinates or redirect to image."""
    fmt = request.args.get("format", "json")
    coords_path = OUTPUTS_DIR / "umap_coords.json"

    if fmt == "image":
        image_path = OUTPUTS_DIR / "umap_clusters.png"
        if image_path.is_file():
            return jsonify({
                "image_url": "/static/umap_clusters.png",
                "exists": True,
            })
        return jsonify({"exists": False})

    if coords_path.is_file():
        with open(coords_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({"points": [], "count": 0})


# ── API: Segment Profiles ─────────────────────────────────────────────────────

@app.route("/api/segments")
def api_segments() -> str:
    """Derive segment profiles from insights and retrieval results."""
    insights_path = OUTPUTS_DIR / "insights.json"
    if not insights_path.is_file():
        return jsonify({"segments": [], "count": 0})

    with open(insights_path, encoding="utf-8") as f:
        data = json.load(f)

    segments: dict[str, dict[str, Any]] = {}
    for insight in data.get("insights", []):
        segment = insight.get("segment", "Unknown")
        if not segment or segment == "Unknown":
            continue

        if segment not in segments:
            segments[segment] = {
                "segment": segment,
                "insights": [],
                "research_questions": [],
                "average_confidence": 0.0,
                "evidence_count": 0,
            }

        segments[segment]["insights"].append({
            "research_question_id": insight.get("research_question_id"),
            "research_question_label": insight.get("research_question_label"),
            "finding": insight.get("finding"),
            "implication": insight.get("implication"),
            "confidence": insight.get("confidence", 0.0),
        })
        segments[segment]["research_questions"].append(insight.get("research_question_label"))
        segments[segment]["evidence_count"] += len(insight.get("evidence", []))

    segment_list = []
    for seg in segments.values():
        confidences = [i["confidence"] for i in seg["insights"] if i["confidence"] is not None]
        seg["average_confidence"] = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        seg["insight_count"] = len(seg["insights"])
        segment_list.append(seg)

    return jsonify({"segments": segment_list, "count": len(segment_list)})


# ── API: Stats ────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats() -> str:
    """Return pipeline statistics."""
    stats = {
        "phase": "Phase 7 - Dashboard & Deployment",
        "raw_records": 0,
        "clean_chunks": 0,
        "sources": [],
        "apps": [],
        "date_range": {"earliest": None, "latest": None},
        "total_insights": 0,
        "total_themes": 0,
        "eval_passed": False,
    }

    # Load ingestion report
    report_path = OUTPUTS_DIR / "ingestion_report.json"
    if report_path.is_file():
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        stats["raw_records"] = report.get("total_records_in_store", 0)
        stats["sources"] = list(report.get("records_by_source", {}).keys())
        stats["apps"] = list(report.get("records_by_app", {}).keys())
        stats["date_range"] = report.get("date_range", {})

    # Load preprocessing stats
    chunks_path = DATA_DIR / "processed" / "clean_chunks.jsonl"
    if chunks_path.is_file():
        chunk_count = 0
        with open(chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    chunk_count += 1
        stats["clean_chunks"] = chunk_count

    # Load insights count
    insights_path = OUTPUTS_DIR / "insights.json"
    if insights_path.is_file():
        with open(insights_path, encoding="utf-8") as f:
            data = json.load(f)
        stats["total_insights"] = len(data.get("insights", []))

    # Load themes count
    themes_path = OUTPUTS_DIR / "themes.json"
    if themes_path.is_file():
        with open(themes_path, encoding="utf-8") as f:
            data = json.load(f)
        stats["total_themes"] = len(data) if isinstance(data, list) else len(data.get("themes", []))

    # Load eval status
    eval_path = OUTPUTS_DIR / "eval_report.json"
    if eval_path.is_file():
        with open(eval_path, encoding="utf-8") as f:
            data = json.load(f)
        stats["eval_passed"] = data.get("passed", False)

    return jsonify(stats)


# ── API: Reviews ──────────────────────────────────────────────────────────────

@app.route("/api/reviews")
def api_reviews() -> str:
    """Return raw review data for the dashboard with optional filtering."""
    db_path = DATA_DIR / "raw" / "reviews.db"
    reviews = []
    total_count = 0

    source = request.args.get("source", "")
    app = request.args.get("app", "")
    rating = request.args.get("rating", "")
    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 50)), 200)

    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT source, app, text, rating, created_at, language FROM reviews WHERE 1=1"
        params = []

        if source:
            query += " AND source = ?"
            params.append(source)
        if app:
            query += " AND app = ?"
            params.append(app)
        if rating:
            query += " AND rating = ?"
            params.append(int(rating))
        if search:
            query += " AND text LIKE ?"
            params.append(f"%{search}%")

        count_query = f"SELECT COUNT(*) FROM reviews WHERE 1=1"
        for p in params:
            count_query += " AND " + count_query.split("WHERE 1=1")[1].split("AND")[0].strip() + " ?"
        count_query = "SELECT COUNT(*) FROM reviews"
        if source:
            count_query += " WHERE source = ?"
            cp = [source]
        else:
            cp = []
        if app:
            count_query += " AND app = ?" if source else " WHERE app = ?"
            cp.append(app)
        if rating:
            count_query += " AND rating = ?"
            cp.append(int(rating))
        if search:
            count_query += " AND text LIKE ?"
            cp.append(f"%{search}%")

        cursor.execute(count_query, cp)
        total_count = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        query += f" ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        reviews = [dict(row) for row in rows]
        conn.close()

    return jsonify({
        "reviews": reviews,
        "count": len(reviews),
        "total": total_count,
        "page": page,
        "page_size": page_size,
    })


@app.route("/api/review-filters")
def api_review_filters() -> str:
    """Return available filter options for the review browser."""
    db_path = DATA_DIR / "raw" / "reviews.db"
    filters = {"sources": [], "apps": [], "ratings": []}

    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT source FROM reviews WHERE source IS NOT NULL ORDER BY source")
        filters["sources"] = [row["source"] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT app FROM reviews WHERE app IS NOT NULL ORDER BY app")
        filters["apps"] = [row["app"] for row in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT rating FROM reviews WHERE rating IS NOT NULL ORDER BY rating")
        filters["ratings"] = [row["rating"] for row in cursor.fetchall()]

        conn.close()

    return jsonify(filters)


@app.route("/api/review-distribution")
def api_review_distribution() -> str:
    """Return review distribution by source and app."""
    db_path = DATA_DIR / "raw" / "reviews.db"
    distribution = {"by_source": {}, "by_app": {}, "by_rating": {}}

    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT source, COUNT(*) as cnt FROM reviews GROUP BY source")
        for row in cursor.fetchall():
            distribution["by_source"][row["source"]] = row["cnt"]

        cursor.execute("SELECT app, COUNT(*) as cnt FROM reviews GROUP BY app")
        for row in cursor.fetchall():
            distribution["by_app"][row["app"]] = row["cnt"]

        cursor.execute(
            "SELECT rating, COUNT(*) as cnt FROM reviews WHERE rating IS NOT NULL GROUP BY rating ORDER BY rating"
        )
        for row in cursor.fetchall():
            distribution["by_rating"][str(row["rating"])] = row["cnt"]

        conn.close()

    return jsonify(distribution)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the dashboard."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting Zepto AI Review Engine Dashboard")
    logger.info("Dashboard available at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    main()
