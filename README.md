# Zepto AI Review Engine

An AI-powered pipeline that transforms raw user feedback from app stores and community forums into structured, evidence-backed product insights for Zepto's Growth Team.

Built on a RAG (Retrieval-Augmented Generation) architecture: reviews are indexed in a vector database, and insights are grounded in semantically retrieved user text — not LLM hallucinations.

---

## Project Structure

```
Zepto AI Review Engine/
├── config/
│   ├── research_questions.json   # 8 canonical research questions + semantic queries
│   └── sources.json              # Data source configuration (tier, apps, config)
├── data/
│   ├── raw/                      # SQLite raw data store (append-only)
│   ├── processed/                # Clean, chunked JSONL corpus
│   └── embeddings/               # ChromaDB vector index
├── docs/
│   ├── ProblemStatement.md
│   ├── architecture.md
│   ├── implementationplan.md
│   ├── eval.md
│   └── decision.md
├── outputs/                      # Generated report and JSON exports
├── scripts/
│   └── validate_phase0.py        # Phase 0 exit-gate validation
├── src/
│   ├── ingestion/                # Phase 1: data collection connectors + SQLite DB
│   ├── preprocessing/            # Phase 2: cleaning, filtering, chunking
│   ├── embedding/                # Phase 3: embedding + ChromaDB indexing
│   ├── clustering/               # Phase 4: UMAP + HDBSCAN + LLM theme labeling
│   ├── rag/                      # Phase 5: RAG insight generation
│   ├── validation/               # Phase 6: RAGAS faithfulness + coverage checks
│   ├── output/                   # Phase 7: dashboard and JSON export generation
│   └── utils/                    # Shared config loader, logger
├── frontend/                      # Next.js React frontend (Phase 7)
│   ├── src/
│   │   ├── app/                   # App Router pages and API routes
│   │   ├── components/            # Reusable UI components
│   │   ├── lib/                   # API client and utilities
│   │   └── types/                 # TypeScript type definitions
│   ├── package.json
│   └── tsconfig.json
├── scripts/
│   ├── validate_phase0.py
│   ├── export_reviews.py          # Export reviews from SQLite to JSON for API
├── .env.example                  # API credential template
├── .gitignore
└── requirements.txt
```

---

## Setup (Phase 0)

### 1. Prerequisites

- Python 3.11+
- A virtual environment manager (`venv`, `conda`, or `uv`)

### 2. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

### 3. Configure credentials

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
```

Open `.env` and fill in:
- `GEMINI_API_KEY` — required for embedding and LLM calls (Phases 3–6)
- Everything else has a sensible default — see `.env.example` for details

### 4. Run Phase 0 validation

```bash
python scripts/validate_phase0.py
```

All checks must pass (exit code 0) before moving to Phase 1.

---

## Pipeline Phases

| Phase | Command | Duration |
|---|---|---|
| 0 — Foundation & Scoping | `python scripts/validate_phase0.py` | Day 1 |
| 1 — Data Ingestion | `python scripts/run_ingestion.py` | Days 2–3 |
| 2 — Preprocessing | `python scripts/run_preprocessing.py` | Day 4 |
| 3 — Embedding & Indexing | `python scripts/run_embedding.py` | Day 5 |
| 4 — Theme Identification | `python scripts/run_clustering.py` | Days 6–7 |
| 5 — RAG Insight Generation | `python scripts/run_rag.py` | Days 8–9 |
| 6 — Validation | `python scripts/run_validation.py` | Day 10 |
| 7 — Frontend & Deployment | `cd frontend && npm run build` | Day 11 | Next.js frontend built, API routes connected, Vercel deployment ready |

---

## Key Design Decisions

All significant technical and architectural decisions are documented in [docs/decision.md](docs/decision.md).

**TL;DR:**
- **RAG over direct LLM summarization** — every insight is grounded in retrieved user text, making hallucination detectable.
- **Two-track pipeline** — UMAP/HDBSCAN for exploratory theme discovery + RAG for confirmatory research question answering.
- **Competitor reviews included** — tagged with `app` metadata so they can be filtered at query time.
- **Focused corpus** — only category-exploration-relevant reviews are indexed, not all reviews.
- **RAG queries in user voice** — semantic search queries are written as user statements, not PM questions.

---

## Documentation

| Document | Purpose |
|---|---|
| [ProblemStatement.md](docs/ProblemStatement.md) | Business context and the 8 research questions |
| [architecture.md](docs/architecture.md) | System architecture, layer breakdown, tech stack |
| [implementationplan.md](docs/implementationplan.md) | Phase-wise plan with edge cases and exit criteria |
| [eval.md](docs/eval.md) | Numeric exit thresholds for each phase |
| [decision.md](docs/decision.md) | Key technical and logical decisions |
