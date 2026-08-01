# Evaluation & Exit Criteria: Zepto AI Review Engine

## Purpose

This document defines the **testing checklist and exit criteria** for each phase of the implementation. A phase must meet all its exit criteria before work on the next phase begins.

---

## Phase 0: Setup & Scoping

### Tests
- [ ] `python --version` returns 3.11+.
- [ ] All required packages install without conflicts.
- [ ] `.env` loads correctly and API keys are accessible in code.
- [ ] Folder structure (`data/raw/`, `data/processed/`, `src/`, `outputs/`) exists.

### Exit Criteria
- Dev environment is reproducible from a clean clone (e.g., via `pip install -r requirements.txt`).
- API credentials validated for at least **3 of 5** target data sources.
- The 8 research questions are documented and agreed upon.

---

## Phase 1: Data Ingestion

### Tests
- [ ] Each scraper/connector runs end-to-end without crashing.
- [ ] Output records conform to the shared review schema (validated with a schema checker or `pydantic` model).
- [ ] Spot-check 10 random records per source for data quality (text is not empty, date is valid, source is tagged correctly).
- [ ] Duplicate records within the same source are < 5% of total.

### Exit Criteria
- **≥ 1,000 total raw records** stored in the raw data store.
- **≥ 3 distinct sources** represented in the data.
- Schema validation passes with 0 critical errors.
- Duplicate rate < 5% per source.

---

## Phase 2: Preprocessing & Chunking

### Tests
- [ ] Language filter correctly retains English reviews and drops non-English (spot-check 20 records).
- [ ] Noise filter removes reviews ≤ 15 words (validate with `len(text.split()) > 15` assertion).
- [ ] Relevance filter keeps at least 30% of raw records (not over-filtering).
- [ ] Chunked segments are within 300–600 tokens (validate with tokenizer).
- [ ] No chunk is empty or whitespace-only.
- [ ] Preprocessing stats are logged (raw count → filtered → clean count).

### Exit Criteria
- **≥ 500 clean, chunked segments** in `data/processed/`.
- Noise filter removes ≥ 20% of raw data (confirms it's doing meaningful work).
- Relevance filter retains ≥ 30% of data (not over-filtering).
- Zero empty chunks in the processed output.

---

## Phase 3: Embedding & Vector Indexing

### Tests
- [ ] Embedding call returns a vector of the correct dimension (1536 for `text-embedding-3-small`).
- [ ] All chunks are embedded without API errors (retry logic handles rate limits).
- [ ] ChromaDB collection is created with the correct metadata schema.
- [ ] Total vector count in collection matches total clean chunk count.
- [ ] Retrieval test: query "users who are afraid to try new product categories" returns at least 3 clearly relevant chunks in top-5 results.
- [ ] Metadata filtering works correctly (e.g., filter by `source = "forum"` returns only forum chunks).

### Exit Criteria
- **100% of clean chunks are indexed** (vector count = chunk count).
- At least **3 of 5 test queries** return ≥ 3 clearly relevant results in top-5.
- Metadata filter queries return correct subsets.
- End-to-end embedding + indexing pipeline completes in under 30 minutes for the full corpus.

---

## Phase 4: Theme Identification

### Tests
- [ ] UMAP runs without errors and produces a 2D visualization.
- [ ] HDBSCAN produces at least 8 non-noise clusters.
- [ ] Each cluster has at least 10 members.
- [ ] LLM labeling prompt returns a valid JSON with: `theme_name`, `summary`, `verbatim_quotes` (3 items).
- [ ] Theme names are distinct — no two themes share > 50% overlap in wording.
- [ ] Noise cluster (`cluster_id = -1`) contains < 20% of total chunks.

### Exit Criteria
- **8–20 labeled themes** in the final taxonomy JSON.
- Each theme has a clear, distinct label and at least 3 verbatim quotes.
- HDBSCAN noise cluster < 20% of corpus.
- 2D UMAP visualization shows visually separable clusters.
- Manual review confirms themes are meaningful and non-redundant.

---

## Phase 5: RAG Insight Generation

### Tests
- [ ] Retrieval for each of the 8 research questions returns ≥ 5 relevant chunks (manually verified for 3 questions).
- [ ] LLM output conforms to the required JSON schema: `{ "finding": str, "evidence": [str], "implication": str, "segment": str }`.
- [ ] Every insight's `evidence` field contains at least 2 verbatim quotes from retrieved chunks.
- [ ] Source chunk IDs in `insights.json` can be traced back to records in the processed data store.
- [ ] No insight is generated without retrieved context (RAG grounding is mandatory, not optional).

### Exit Criteria
- **≥ 8 structured insights** in `outputs/insights.json`, one per research question.
- Every insight is grounded in **≥ 2 verbatim chunks**.
- All chunk IDs in insights are traceable to the vector DB.
- No insight is a rephrased version of another (no near-duplicates).

---

## Phase 6: Validation & Quality Checks

### Tests

#### Faithfulness (RAGAS or LLM-as-judge)
- For each insight, score: *"Is the finding fully supported by the provided evidence?"* on a 0–1 scale.
- Target: all insights score ≥ 0.7.

#### Coverage
- Confirm that all 8 research questions have a corresponding insight.

#### Contradiction Check
- For each pair of insights, check: *"Does Insight A contradict Insight B?"*
- Flag any contradictory pairs for manual review.

#### Manual Spot-Check
- Reviewer reads 5 randomly selected insights and rates them as: Grounded / Partially Grounded / Hallucinated.
- Target: 0 hallucinated, ≤ 1 partially grounded.

### Exit Criteria
- **All 8 insights have faithfulness score ≥ 0.7.**
- **0 insights rated as hallucinated** in manual spot-check.
- All 8 research questions are covered.
- Zero unresolved contradictions in the final insight set.
- `outputs/eval_report.json` is populated with per-insight scores.

---

## Phase 7: Output & Report Generation

### Tests
- [ ] `outputs/final_report.md` renders correctly in a Markdown viewer.
- [ ] All 8 insight cards are present in the report.
- [ ] Each insight card contains: finding, ≥ 2 verbatim quotes, implication, and affected segment.
- [ ] 2–3 user segment profiles are included.
- [ ] `outputs/insights.json` and `outputs/themes.json` are valid JSON (parse without error).
- [ ] Demo notebook / script runs end-to-end on a fresh environment.

### Exit Criteria
- Final report is **complete, readable, and self-contained**.
- All required sections are present: executive summary, theme taxonomy, insight cards, segment profiles, methodology note.
- JSON exports are valid and match the content in the report.
- Demo script runs without errors from a clean install.
- Report is ready to share with product stakeholders without further editing.

---

## Summary Table

| Phase | Key Exit Metric | Threshold |
|---|---|---|
| 0 | API sources validated | ≥ 3 of 5 |
| 1 | Raw records ingested | ≥ 1,000 |
| 2 | Clean chunks produced | ≥ 500 |
| 3 | Retrieval test queries passing | ≥ 3 of 5 |
| 4 | Distinct labeled themes | 8–20 |
| 5 | Grounded insights generated | ≥ 8 |
| 6 | Insight faithfulness score | ≥ 0.7 all |
| 7 | Report complete & demo runs | Pass |
