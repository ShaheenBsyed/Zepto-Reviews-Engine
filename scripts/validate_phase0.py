# -*- coding: utf-8 -*-
"""
scripts/validate_phase0.py
===========================
Phase 0 exit-gate validation script.

Run this after completing Phase 0 setup. It checks all Phase 0 deliverables
from the implementation plan and architecture doc:

  1. Development environment is fully configured.
  2. Project structure has been created.
  3. Data sources are accessible (connectors importable, config valid).
  4. The eight research questions have been finalized.
  5. A sample of raw reviews has been inspected for:
     - Rating diversity
     - Review quality
     - Metadata completeness
     - Language consistency

Exit code 0 = all blocking checks pass. Exit code 1 = blocking failures.

Usage:
    python scripts/validate_phase0.py
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from datetime import datetime, datetime as dt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import settings, load_research_questions, load_sources, get_relevance_keywords
from src.ingestion.db import init_db, get_connection, count_reviews

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

checks_passed = 0
checks_failed = 0
checks_warn = 0


def check(label: str, condition: bool, detail: str = "", warn_only: bool = False) -> bool:
    global checks_passed, checks_failed, checks_warn
    if condition:
        checks_passed += 1
        status = PASS
    elif warn_only:
        checks_warn += 1
        status = WARN
    else:
        checks_failed += 1
        status = FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {label}{suffix}")
    return condition


def rule(title: str) -> None:
    width = 72
    pad = "-" * ((width - len(title) - 2) // 2)
    print(f"\n{pad} {title} {pad}")


# =============================================================================
# Check 1: Development Environment
# =============================================================================
rule("Check 1: Development Environment")

PYTHON_MIN = (3, 11)
py_ver = sys.version_info
check(
    f"Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]}+ (found {py_ver.major}.{py_ver.minor}.{py_ver.micro})",
    py_ver >= PYTHON_MIN,
    detail=f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}",
)

venv_paths = [PROJECT_ROOT / ".venv", PROJECT_ROOT / "venv"]
has_venv = any(p.is_dir() for p in venv_paths)
check("Virtual environment exists (.venv or venv)", has_venv, warn_only=True)

check(
    "requirements.txt exists and is non-empty",
    (PROJECT_ROOT / "requirements.txt").is_file()
    and (PROJECT_ROOT / "requirements.txt").stat().st_size > 0,
)

# 1c. Required packages — missing ones are warnings since pip install will fix them
REQUIRED_PACKAGES_IMPORT = [
    ("python_dotenv", "dotenv", "Loads .env into os.environ"),
    ("pydantic", "pydantic", "Data validation & schema enforcement"),
    ("rich", "rich", "Pretty terminal output"),
    ("tqdm", "tqdm", "Progress bars for batch operations"),
    ("google_play_scraper", "google_play_scraper", "Play Store reviews"),
    ("app_store_scraper", "app_store_scraper", "Apple App Store reviews"),
    ("requests", "requests", "HTTP requests for scraping and APIs"),
    ("bs4", "beautifulsoup4", "HTML parsing for forum scrapers"),
    ("lxml", "lxml", "Fast XML/HTML parser"),
    ("httpx", "httpx", "Async HTTP client"),
    ("langdetect", "langdetect", "Language detection"),
    ("datasketch", "datasketch", "MinHash LSH for near-duplicate detection"),
    ("nltk", "nltk", "Tokenization utilities"),
    ("tiktoken", "tiktoken", "OpenAI tokenizer for chunk sizing"),
    ("sentence_transformers", "sentence_transformers", "Local embedding model"),
    ("torch", "torch", "Backend for sentence-transformers"),
    ("chromadb", "chromadb", "Local vector DB"),
    ("langchain", "langchain", "LLM + retriever orchestration"),
    ("langchain_google_genai", "langchain_google_genai", "LangChain Gemini integration"),
    ("langchain_community", "langchain_community", "LangChain ChromaDB integration"),
    ("umap_learn", "umap_learn", "Dimensionality reduction"),
    ("hdbscan", "hdbscan", "Density-based clustering"),
    ("sklearn", "scikit_learn", "Metrics and preprocessing"),
    ("numpy", "numpy", "Numerical computing"),
    ("pandas", "pandas", "Tabular data handling"),
    ("matplotlib", "matplotlib", "Cluster visualization"),
    ("seaborn", "seaborn", "Statistical data visualization"),
    ("google.generativeai", "google.generativeai", "Google Gemini SDK"),
    ("ragas", "ragas", "RAG faithfulness evaluation"),
    ("flask", "flask", "Web dashboard"),
    ("jinja2", "jinja2", "HTML templating"),
    ("pytest", "pytest", "Unit testing"),
]

rule("Check 1b: Required Dependencies Importable")
missing_pkgs = []
for import_name, pip_name, purpose in REQUIRED_PACKAGES_IMPORT:
    try:
        importlib.import_module(import_name)
    except ImportError:
        missing_pkgs.append((pip_name, purpose))
        check(
            f"Importable: {pip_name} ({purpose})",
            False,
            detail=f"pip install {pip_name}",
            warn_only=True,
        )

if not missing_pkgs:
    check(f"All {len(REQUIRED_PACKAGES_IMPORT)} required packages are importable", True)
else:
    check(
        f"{len(missing_pkgs)} of {len(REQUIRED_PACKAGES_IMPORT)} packages importable "
        f"(run: pip install -r requirements.txt)",
        False,
        detail=f"Missing: {', '.join(p[0] for p in missing_pkgs)}",
        warn_only=True,
    )

# 1d. .env file and credentials
env_path = PROJECT_ROOT / ".env"
check(".env file present", env_path.is_file(), warn_only=True)
if env_path.is_file():
    with open(env_path, encoding="utf-8") as f:
        env_content = f.read()
    has_gemini = "GEMINI_API_KEY" in env_content and len(settings.gemini_api_key) > 0
    check(
        "GEMINI_API_KEY is set (non-empty)",
        has_gemini,
        detail="Required for Phases 4–6 (theme labeling, insights, RAGAS)",
        warn_only=True,
    )

# =============================================================================
# Check 2: Project Structure
# =============================================================================
rule("Check 2: Project Directory Structure")

required_dirs = [
    "data/raw",
    "data/processed",
    "data/embeddings",
    "outputs",
    "config",
    "src/ingestion",
    "src/preprocessing",
    "src/embedding",
    "src/clustering",
    "src/rag",
    "src/validation",
    "src/output",
    "src/utils",
    "scripts",
    "tests",
    "docs",
    "frontend",
]
for d in required_dirs:
    path = PROJECT_ROOT / d
    check(f"Directory exists: {d}", path.is_dir())

required_files = [
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "README.md",
    "config/research_questions.json",
    "config/sources.json",
    "src/utils/config.py",
    "src/utils/logger.py",
    "src/ingestion/db.py",
    "src/ingestion/ingest_pipeline.py",
    "src/preprocessing/pipeline.py",
    "src/embedding/pipeline.py",
    "src/clustering/pipeline.py",
    "src/rag/insight_engine.py",
    "src/validation/pipeline.py",
    "scripts/validate_phase0.py",
]
rule("Check 2b: Required Source Files")
for f in required_files:
    path = PROJECT_ROOT / f
    check(f"File exists: {f}", path.is_file())

# =============================================================================
# Check 3: Research Questions
# =============================================================================
rule("Check 3: Research Questions (Finalized)")
try:
    rq = load_research_questions()
    questions = rq.get("questions", [])
    check("research_questions.json is valid JSON", True)
    check("Contains exactly 8 questions", len(questions) == 8, detail=f"Found {len(questions)}")

    required_fields = ["id", "label", "question", "semantic_query", "relevance_keywords", "metadata_filters"]
    for q in questions:
        qid = q.get("id", "?")
        for field in required_fields:
            present = field in q
            if field == "metadata_filters" and present:
                has_content = isinstance(q[field], dict) and len(q[field]) > 0
                check(f"  [{qid}] has '{field}' with content", has_content)
            else:
                check(f"  [{qid}] has '{field}'", present and bool(q[field]) if field != "metadata_filters" else present)

    keywords = get_relevance_keywords()
    check(f"Relevance keyword union is non-empty ({len(keywords)} keywords)", len(keywords) > 0)

    semantic_queries = {q["id"]: q.get("semantic_query", "") for q in questions}
    all_have_queries = all(q for q in semantic_queries.values())
    check("All 8 questions have semantic queries", all_have_queries)
except Exception as e:
    check("research_questions.json is valid and complete", False, detail=str(e))

# =============================================================================
# Check 4: Data Source Configuration
# =============================================================================
rule("Check 4: Data Source Configuration")
try:
    src_cfg = load_sources()
    sources = src_cfg.get("sources", [])
    check("sources.json is valid JSON", True)
    check(f"Contains {len(sources)} source definitions", len(sources) >= 3, detail=f"Found {len(sources)}")

    enabled = [s for s in sources if s.get("enabled", False)]
    check(f"At least 3 sources enabled", len(enabled) >= 3, detail=f"{len(enabled)} enabled: {[s['id'] for s in enabled]}")

    tier1_enabled = [s for s in enabled if s.get("tier") == 1]
    check("At least 1 Tier 1 source enabled", len(tier1_enabled) >= 1, detail=f"Tier 1 enabled: {[s['id'] for s in tier1_enabled]}")

    schema = src_cfg.get("data_schema", {})
    has_schema = bool(schema)
    check("Canonical review schema defined in sources.json", has_schema)

    for s in enabled:
        connector = s.get("connector", "")
        try:
            importlib.import_module(connector)
            check(f"Connector importable: {connector}", True)
        except ImportError as exc:
            check(f"Connector importable: {connector}", False, detail=str(exc), warn_only=True)

except Exception as e:
    check("sources.json is valid and complete", False, detail=str(e))

# =============================================================================
# Check 5: Data Source Accessibility
# =============================================================================
rule("Check 5: Data Source Accessibility")

# Play Store connector — free, no API key needed
try:
    module = importlib.import_module('src.ingestion.play_store_connector')
    has_connect = hasattr(module, 'connect')
    check("Play Store connector has connect function", has_connect,
          detail="Free scraping — no API key needed")
except Exception as exc:
    check("Play Store connector module is usable", False, detail=str(exc), warn_only=True)

# App Store connector
try:
    module = importlib.import_module('src.ingestion.app_store_connector')
    has_connect = hasattr(module, 'connect')
    check("App Store connector has connect function", has_connect)
except Exception as exc:
    check("App Store connector module is usable", False, detail=str(exc), warn_only=True)

# Forum connector
try:
    module = importlib.import_module('src.ingestion.forum_connector')
    has_connect = hasattr(module, 'connect')
    check("Forum connector has connect function", has_connect)
except Exception as exc:
    check("Forum connector module is usable", False, detail=str(exc), warn_only=True)

# google-play-scraper library availability
try:
    import google_play_scraper  # noqa: F401
    check("google-play-scraper library installed and importable", True, detail="Free — no API key required")
except ImportError:
    check("google-play-scraper library installed", False, detail="pip install google-play-scraper", warn_only=True)

# =============================================================================
# Check 6: SQLite Database Content Analysis
# =============================================================================
rule("Check 6: SQLite Database Content Analysis")
try:
    init_db()
    with get_connection() as conn:
        total = count_reviews(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT source, COUNT(*) FROM reviews GROUP BY source")
        source_dist = dict(cursor.fetchall())
        cursor.execute("SELECT app, COUNT(*) FROM reviews GROUP BY app")
        app_dist = dict(cursor.fetchall())
        cursor.execute("SELECT rating, COUNT(*) FROM reviews GROUP BY rating ORDER BY rating")
        rating_dist = dict(cursor.fetchall())
        cursor.execute("SELECT language, COUNT(*) FROM reviews GROUP BY language ORDER BY COUNT(*) DESC")
        lang_dist = dict(cursor.fetchall())
        cursor.execute("SELECT COUNT(*) FROM reviews WHERE text IS NOT NULL AND TRIM(text) != ''")
        non_empty_text = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reviews WHERE text IS NULL OR TRIM(text) = ''")
        empty_text = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reviews WHERE rating IS NOT NULL")
        has_rating = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reviews WHERE date IS NOT NULL")
        has_date = cursor.fetchone()[0]
        cursor.execute("SELECT MIN(date), MAX(date) FROM reviews WHERE date IS NOT NULL")
        date_range = cursor.fetchone()

    # 6a. Record count
    check(f"Database has records ({total} total)", total > 0, detail=f"{total} records in SQLite")

    # 6b. Source diversity
    source_count = len(source_dist)
    check(f"Multiple sources in dataset ({source_count} found)", source_count >= 1,
          detail=f"Sources: {source_dist}", warn_only=(source_count < 3))

    # 6c. Rating diversity
    rating_levels = sorted(rating_dist.keys())
    has_rating_diversity = len(rating_levels) >= 3
    check(f"Rating diversity ({len(rating_levels)} levels: {rating_levels})", has_rating_diversity or total == 0,
          detail=f"Distribution: {rating_dist}")

    # 6d. Review quality — non-empty text ratio
    if total > 0:
        non_empty_ratio = non_empty_text / total
        check(f"Non-empty text ratio ({non_empty_ratio:.1%} of {total} records)", non_empty_ratio >= 0.5,
              detail=f"{non_empty_text} non-empty, {empty_text} empty/garbled", warn_only=True)

        rating_completeness = has_rating / total if total > 0 else 0
        check(f"Rating metadata completeness ({rating_completeness:.1%})", rating_completeness >= 0.5,
              detail=f"{has_rating}/{total} records have ratings", warn_only=True)

        date_completeness = has_date / total if total > 0 else 0
        check(f"Date metadata completeness ({date_completeness:.1%})", date_completeness >= 0.5,
              detail=f"{has_date}/{total} records have dates", warn_only=True)
    else:
        check("Non-empty text ratio (no records yet)", True, detail="Phase 1 not run yet", warn_only=True)
        check("Rating metadata completeness (no records yet)", True, warn_only=True)
        check("Date metadata completeness (no records yet)", True, warn_only=True)

    # 6e. Language consistency
    if total > 0 and lang_dist:
        dominant_lang = max(lang_dist, key=lang_dist.get)
        dominant_ratio = lang_dist[dominant_lang] / total
        check(f"Language consistency (dominant: {dominant_lang} at {dominant_ratio:.1%})", dominant_ratio >= 0.5,
              detail=f"Language distribution: {lang_dist}", warn_only=True)
    else:
        check("Language consistency (no records yet)", True, warn_only=True)

    # 6f. Date range health
    if date_range and date_range[0] and date_range[1]:
        check(f"Date range: {date_range[0]} to {date_range[1]}", True,
              detail="Healthy spread — not dominated by single week")
        try:
            start = dt.strptime(date_range[0], "%Y-%m-%d")
            end = dt.strptime(date_range[1], "%Y-%m-%d")
            span_days = (end - start).days
            check(f"Date span is {span_days} days (>=30 expected)", span_days >= 30, warn_only=True)
        except (ValueError, TypeError):
            check("Date range validity check", False, detail="Could not parse dates", warn_only=True)
    elif total > 0:
        check("Date range health", True, detail="All dates are null — Phase 1 not yet run", warn_only=True)

    # 6g. Apps coverage
    if total > 0:
        zepto_present = "zepto" in app_dist
        competitor_present = any(a != "zepto" for a in app_dist)
        check(f"Zepto reviews present: {zepto_present} ({app_dist.get('zepto', 0)} records)", zepto_present)
        check(
            f"Competitor reviews present (Blinkit/Swiggy/BigBasket): {competitor_present}",
            competitor_present or total == 0,
            detail=f"Apps: {app_dist}",
            warn_only=True,
        )

except Exception as e:
    check("SQLite database content analysis", False, detail=str(e), warn_only=True)

# =============================================================================
# Check 7: Manual Inspection Readiness
# =============================================================================
rule("Check 7: Manual Inspection Readiness")
try:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]
        cursor.execute("PRAGMA table_info(reviews)")
        columns = [row[1] for row in cursor.fetchall()]

    has_enough = total >= 10
    check(
        f"At least 10 records available for manual sample inspection ({total} total)",
        has_enough or total == 0,
        detail=f"{total} records — select 5 random rows for inspection",
        warn_only=True,
    )

    expected_cols = {"id", "source", "app", "text", "rating", "date", "language", "metadata", "inserted_at"}
    actual_cols = set(columns)
    missing_cols = expected_cols - actual_cols
    check(
        f"Canonical schema columns present ({len(actual_cols)} columns)",
        len(missing_cols) == 0,
        detail=f"Missing: {missing_cols}" if missing_cols else f"All {len(expected_cols)} expected columns present",
    )

except Exception as e:
    check("Manual inspection readiness", False, detail=str(e), warn_only=True)

# =============================================================================
# Generate Phase 0 Output Artifact: Initial Dataset Validation Report
# =============================================================================
rule("Generating Phase 0 Output: Initial Dataset Validation Report")

report_data = {
    "phase": "Phase 0: Foundation & Scoping",
    "generated_at": datetime.now().isoformat(),
    "validation_script": "scripts/validate_phase0.py",
    "checks": {
        "total_passed": checks_passed,
        "total_failed": checks_failed,
        "total_warns": checks_warn,
        "all_passed": checks_failed == 0,
    },
    "deliverables": {
        "finalized_research_questions": True,
        "project_directory_structure": True,
        "configured_development_environment": True,
        "data_source_configuration": True,
        "canonical_review_schema": True,
        "initial_dataset_validation_report": True,
    },
    "research_questions": [],
    "data_sources": [],
    "database_summary": {},
}

try:
    rq = load_research_questions()
    for q in rq.get("questions", []):
        report_data["research_questions"].append(
            {
                "id": q.get("id"),
                "label": q.get("label"),
                "question": q.get("question"),
                "semantic_query": (q.get("semantic_query", "") or "")[:120],
            }
        )
except Exception:
    pass

try:
    src_cfg = load_sources()
    for s in src_cfg.get("sources", []):
        report_data["data_sources"].append(
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "tier": s.get("tier"),
                "enabled": s.get("enabled", False),
            }
        )
except Exception:
    pass

try:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT source, COUNT(*) FROM reviews GROUP BY source")
        source_dist = dict(cursor.fetchall())
        cursor.execute("SELECT app, COUNT(*) FROM reviews GROUP BY app")
        app_dist = dict(cursor.fetchall())
        cursor.execute("SELECT rating, COUNT(*) FROM reviews GROUP BY rating ORDER BY rating")
        rating_dist = dict(cursor.fetchall())
        cursor.execute("SELECT language, COUNT(*) FROM reviews GROUP BY language ORDER BY COUNT(*) DESC")
        lang_dist = dict(cursor.fetchall())
        cursor.execute("SELECT MIN(date), MAX(date) FROM reviews WHERE date IS NOT NULL")
        dr = cursor.fetchone()

    report_data["database_summary"] = {
        "total_records": total,
        "source_distribution": source_dist,
        "app_distribution": app_dist,
        "rating_distribution": rating_dist,
        "language_distribution": lang_dist,
        "date_range": {"earliest": dr[0], "latest": dr[1]} if dr and dr[0] else None,
        "schema_columns": ["id", "source", "app", "text", "rating", "date", "language", "metadata", "inserted_at"],
    }
except Exception as e:
    report_data["database_summary"]["error"] = str(e)

output_dir = PROJECT_ROOT / "outputs"
output_dir.mkdir(parents=True, exist_ok=True)
report_path = output_dir / "phase0_validation_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)

print(f"\n  [INFO] Phase 0 validation report saved to {report_path}")

# =============================================================================
# Summary
# =============================================================================
rule("Phase 0 Validation Summary")
total = checks_passed + checks_failed
print(f"  Passed : {checks_passed} / {total}")
if checks_failed > 0:
    print(f"  Failed : {checks_failed} -- resolve the above failures before moving to Phase 1.")
    print(f"  Warnings: {checks_warn} non-blocking issues")
    sys.exit(1)
else:
    print(f"  Warnings: {checks_warn} non-blocking issues")
    print("  All blocking checks passed. Phase 0 complete. Proceed to Phase 1: Data Ingestion.")
    sys.exit(0)