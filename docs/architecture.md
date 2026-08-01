# System Architecture: Zepto AI Review Engine

## Overview

The Zepto AI Review Engine is a RAG (Retrieval-Augmented Generation) pipeline that transforms raw customer feedback from app stores and community forums into structured, evidence-backed product insights. The system operates as a sequential 7-phase pipeline where each phase's output is the next phase's input. A two-track analytical architecture runs in parallel: an exploratory track (clustering) discovers what topics exist in the corpus, and a confirmatory track (RAG) answers pre-defined research questions with grounded evidence.

The pipeline is designed so that a quality failure in an early phase silently degrades everything downstream. Each phase has explicit exit gates and validation criteria.

---

## Mermaid Diagrams

### 1. System Data Flow (End-to-End)

```mermaid
flowchart TD
    A["📦 Data Sources"] --> B["⚙️ PHASE 0: Foundation"]
    B --> C["📥 PHASE 1: Data Ingestion"]
    C --> D["🧹 PHASE 2: Preprocessing"]
    D --> E["🧮 PHASE 3: Embedding & Indexing"]

    E --> F["🔍 PHASE 4: Theme Identification (Exploratory Track)"]
    E --> G["💡 PHASE 5: RAG Insight Generation (Confirmatory Track)"]

    F --> H["✅ PHASE 6: Validation & QA"]
    G --> H

    H --> I["🌐 PHASE 7: Insight Explorer & Deployment"]

    I --> J["📊 Frontend (Next.js)"]
    I --> K["📁 Output Artifacts (JSON)"]

    style A fill:#e1f5fe
    style J fill:#fff3e0
    style K fill:#e8f5e9
```

### 2. Data Ingestion Workflow (Phase 1)

```mermaid
flowchart TD
    START["🚀 Start Ingestion"] --> CHECK{"Tier 1 source<br/>available?"}
    CHECK -- "No" --> FAIL["❌ Pipeline halted"]
    CHECK -- "Yes" --> P1["🔌 Play Store Connector<br/>google-play-scraper"]
    P1 --> P2["🔌 App Store Connector<br/>app-store-scraper (India)"]
    P2 --> P3["🔌 Forum Connector<br/>BeautifulSoup4 + lxml"]
    P3 --> CHECK2{"Tier 1+2 corpus<br/>≥ 800 records?"}
    CHECK2 -- "No" --> P4["🔌 Twitter/X Connector<br/>API v2 (Tier 3, opt)"]
    CHECK2 -- "Yes (enough data)" --> SKIP["⏭ Skip Twitter/X"]
    P4 --> NORMALIZE["📋 Normalize to Canonical Schema"]
    SKIP --> NORMALIZE
    NORMALIZE --> VALIDATE["🔍 Schema Validation"]
    VALIDATE --> DISCARDBAD["🗑 Discard records:<br/>empty text, non-UTF-8,<br/>missing source tag"]
    DISCARDBAD --> STORE["💾 Write to SQLite<br/>(data/raw/reviews.db)<br/>Append-only, immutable"]
    STORE --> REPORT["📊 Generate Ingestion Report:<br/>total, source distribution,<br/>rating distribution, date distribution"]
    STORE --> EXITGATE{"≥ 1,000 records?<br/≥ 3 sources?<br/Healthy date dist?"}
    EXITGATE -- "No" --> REMEDIATE["🔁 Increase scraping range<br/>or add batch collection"]
    REMEDIATE --> P1
    EXITGATE -- "Yes" --> DONE1["✅ Phase 1 Complete"]

    style START fill:#e3f2fd
    style FAIL fill:#ffcdd2
    style DONE1 fill:#c8e6c9
```

### 3. Preprocessing Pipeline (Phase 2)

```mermaid
flowchart LR
    RAW["📥 Raw Records<br/>from SQLite"] --> LANG["1️⃣ Language Filter<br/>Remove non-target language<br/>BCP 47 code check"]
    LANG --> DEDUP["2️⃣ Deduplication<br/>MinHash LSH<br/>Cosine similarity > 0.97<br/>→ near-duplicates removed"]
    DEDUP --> NOISE["3️⃣ Noise Removal<br/>Remove spam, garbled text,<br/>HTML entities, malformed records"]
    NOISE --> RELEVANCE["4️⃣ Relevance Filter<br/>Keyword pass (fast) +<br/>Semantic similarity pass (accurate)<br/>→ retains only category-exploration<br/>relevant reviews"]
    RELEVANCE --> CHUNK["5️⃣ Chunking<br/>300–500 token windows<br/>50-token overlap<br/>Short reviews kept as single chunk<br/>Long forum posts split"]
    CHUNK --> VALIDATE2{"≥ 500 chunks<br/>after all steps?"}
    VALIDATE2 -- "No" --> EXPAND["🔁 Expand keyword list<br/>or extend scraping window"]
    EXPAND --> RAW
    VALIDATE2 -- "Yes" --> PROCESSED["📄 Clean Chunked JSONL<br/>data/processed/"]
    PROCESSED --> STATS["📊 Preprocessing Stats:<br/>raw → lang filter → dedup →<br/>noise → relevance → final chunk count"]
    PROCESSED --> EXITGATE2{"≥ 300 chunks<br/>after relevance filter?"}
    EXITGATE2 -- "No" --> WARN["⚠ Minimum viable corpus<br/>not reached — block Phase 3"]
    EXITGATE2 -- "Yes" --> DONE2["✅ Phase 2 Complete"]

    style RAW fill:#fff3e0
    style DONE2 fill:#c8e6c9
    style WARN fill:#ffcdd2
```

### 4. Embedding & Vector Indexing (Phase 3)

```mermaid
flowchart TD
    CHUNKS["📄 Clean Chunked JSONL<br/>from Phase 2"] --> CHUNKLIST["📋 Iterate over each chunk"]
    CHUNKLIST --> CHECKCACHE{"Chunk already<br/>in embedding cache?"}
    CHECKCACHE -- "Yes" --> SKIPEMB["⏭ Skip — use cached<br/>embedding (idempotent)"]
    CHECKCACHE -- "No" --> GENERATE["🧮 Generate Embedding<br/>all-MiniLM-L6-v2<br/>384 dimensions<br/>Local inference, zero API cost"]
    GENERATE --> STOREVEC["💾 Store in ChromaDB<br/>Vector + metadata payload:<br/>chunk_id, parent_record_id,<br/>source, app, rating,<br/>date, language, text"]
    SKIPEMB --> CONTINUE
    STOREVEC --> CONTINUE{"More chunks to process?"}
    CONTINUE -- "Yes" --> CHUNKLIST
    CONTINUE -- "No" --> VALIDATE3["🔍 Retrieval Quality Validation<br/>5 test queries from research questions:<br/>1. 'I never explore new categories'<br/>2. 'How do I find new products on Zepto'<br/>3. 'Can you recommend something different'<br/>4. 'Is Zepto good for trying new things'<br/>5. 'Why do I always buy the same items'"]
    VALIDATE3 --> REVIEW["👁 Manual inspection of<br/>top-5 results per query<br/>Are they semantically relevant?"]
    REVIEW -- "Poor retrieval" --> TROUBLESHOOT["🔧 Investigate:<br/>Too much noise in corpus? → revisit Phase 2<br/>Chunks too large/small? → adjust chunking<br/>Relevance filter too narrow? → expand keywords"]
    TROUBLESHOOT --> CHUNKS
    REVIEW -- "Good retrieval" --> INDEXOK["✅ ChromaDB index validated"]
    INDEXOK --> BACKUP["💾 Backup:<br/>SQLite raw store + JSONL<br/>→ source of truth<br/>Index can always be rebuilt"]
    BACKUP --> DONE3["✅ Phase 3 Complete"]

    style CHUNKS fill:#e8f5e9
    style DONE3 fill:#c8e6c9
```

### 5. Theme Identification — Exploratory Track (Phase 4)

```mermaid
flowchart TD
    VECTORIDX["🧮 ChromaDB Vector Index<br/>+ metadata from Phase 3"] --> UMAP["📉 UMAP Dimensionality Reduction<br/>384 dimensions → 5 dimensions<br/>preserves local neighborhood structure<br/>n_neighbors=15, min_dist=0.1"]

    UMAP --> HDBSCAN["🔷 HDBSCAN Density-Based Clustering<br/>No pre-specified K required<br/>Finds clusters of varying density<br/>Marks outliers as noise (cluster -1)"]

    HDBSCAN --> NUMCLUSTERS{"Cluster count<br/>in range?"}

    NUMCLUSTERS -- "< 5 clusters" --> REDUCE_MIN["🔧 Reduce min_cluster_size<br/>→ broader clusters<br/>If still < 5: revisit relevance filter<br/>→ corpus too homogeneous"]
    REDUCE_MIN --> HDBSCAN

    NUMCLUSTERS -- "> 30 clusters" --> INCREASE_MIN["🔧 Increase min_cluster_size<br/>→ fewer, broader clusters<br/>Alternatively: hierarchical clustering<br/>to merge micro-clusters"]
    INCREASE_MIN --> HDBSCAN

    NUMCLUSTERS -- "10–25 clusters ✓" --> CENTROID["🎯 Extract Representative Samples<br/>For each cluster: find chunks<br/>closest to cluster centroid<br/>Limit: 10–20 representative samples<br/>per cluster"]

    CENTROID --> LLM_LABEL["🤖 LLM Labeling<br/>Gemini 1.5 Flash (15 RPM)<br/>Input: representative samples + chunk text<br/>Output: theme_name, description,<br/>3 verbatim quotes per cluster"]

    LLM_LABEL --> TAXONOMY["📚 Taxonomy Assembly<br/>Consolidate similar themes:<br/>if >70% overlap in top-10<br/>representative chunks → merge"]

    TAXONOMY --> MANUAL["👁 Manual Review<br/>- Verify theme separation<br/>- Check for single-source themes<br/>- Review ambiguous clusters<br/>- Flag low-generalizability themes"]

    MANUAL --> NOISE_CHECK{"Noise cluster<br/>(cluster -1) > 20%?"}
    NOISE_CHECK -- "Yes" --> REVISIT["⚠ Long tail of idiosyncratic opinions<br/>Document explicitly<br/>→ revisit Phase 2 relevance filter<br/>or corpus cleaning"]
    REVISIT --> TAXONOMY

    NOISE_CHECK -- "No" --> VIS["📊 Generate Outputs:<br/>- Theme taxonomy JSON<br/>- 2D UMAP visualization (PNG)<br/>- Manual review notes"]

    VIS --> DONE4["✅ Phase 4 Complete"]

    style VECTORIDX fill:#e8eaf6
    style DONE4 fill:#c8e6c9
```

### 6. RAG Insight Generation — Confirmatory Track (Phase 5)

```mermaid
flowchart TD
    VECTORIDX2["🧮 ChromaDB Vector Index<br/>+ metadata from Phase 3"] --> QUERYBUILD["🔧 Query Formulation<br/>Each of the 8 research questions<br/>is rewritten into user voice:<br/>e.g. 'I always buy the same things<br/>every week and never try anything new'<br/>→ matches indexed chunk language"]

    QUERYBUILD --> RETRIEVE["🔍 Semantic Retrieval<br/>RAGRetriever.retrieve_all()<br/>Top-K=10 chunks per query<br/>Metadata filters applied per question:<br/>- rating_lte ≤ 3 for frustration questions<br/>- source filter when needed"]

    RETRIEVE --> DIVERSIFY["🔀 Parent Diversity Enforcement<br/>Max 2 chunks per parent_record_id<br/>Prevents single forum thread<br/>from dominating evidence base<br/>If >2 from same parent → drop excess"]

    DIVERSIFY --> CHECKZERO{"Any results<br/>for this question?"}
    CHECKZERO -- "No" --> INSUFFICIENT["🚫 Mark as<br/>'insufficient evidence'<br/>→ research question has<br/>no corresponding data in corpus"]
    INSUFFICIENT --> NEXTQ{"More questions?"}
    INSUFFICIENT --> NEXTQ
    CHECKZERO -- "Yes" → CONTINUE2{"More questions?"}
    CONTINUE2 -- "Yes" → RETRIEVE
    CONTINUE2 -- "No" -> GENERATE_PROMPT["📝 Build RAG Prompt<br/>For each question with results:<br/>- Retrieved chunks as context<br/>- Structured JSON schema:<br/>  { finding, evidence, implication,<br/>    segment, confidence }<br/>- Explicit instruction: cite only<br/>  retrieved text, no training data"]

    GENERATE_PROMPT → LLM_INFER["🤖 LLM Inference<br/>Gemini 1.5 Flash<br/>15 RPM rate limit<br/>1M tokens/day free tier<br/>Structured JSON output enforced<br/>by Pydantic schema validation"]

    LLM_INFER → VALIDATE_EVIDENCE["✅ Evidence Verification<br/>Programmatic check: each evidence<br/>quote must appear as substring in<br/>at least one retrieved chunk<br/>If paraphrase detected → fail + retry"]

    VALIDATE_EVIDENCE → CHECK_SEGMENT{"Segment field<br/>too vague?<br/>(e.g. 'all users')"}
    CHECK_SEGMENT -- "Yes" → REVISE_SEG["🔁 Return to LLM with<br/>constraint: segment must be<br/>concrete: life stage, use case,<br/>behavior pattern, or geography"]
    REVISE_SEG → LLM_INFER

    CHECK_SEGMENT -- "No" → CHECK_OVERLAP{"Same chunks retrieved<br/>for multiple questions?"}
    CHECK_OVERLAP -- "Yes" → REWRITE_QUERY["🔧 Rewrite queries with more<br/>specific framing or apply<br/>source/rating filters to differentiate"]
    REWRITE_QUERY → RETRIEVE

    CHECK_OVERLAP -- "No" → CROSS_REF["🔗 Cross-Reference Detection<br/>If two questions share >80% chunks<br/>→ consolidate into unified<br/>insight card with combined evidence"]

    CROSS_REF → SAVE["💾 Save to outputs/insights.json<br/>Each insight links back to<br/>chunk_id → SQLite record"]

    SAVE → DONE5["✅ Phase 5 Complete<br/>8 insights (or 'insufficient evidence')"]

    style VECTORIDX2 fill:#e8eaf6
    style DONE5 fill:#c8e6c9
```

### 7. Validation & Quality Assurance (Phase 6)

```mermaid
flowchart TD
    INSIGHTS["💡 Generated Insights<br/>from Phase 5"] --> RAGAS["📊 RAGAS Faithfulness Scoring<br/>Gemini 1.5 Flash as judge LLM<br/>Breaks each insight into individual claims<br/>Checks each claim against evidence chunks<br/>Produces numeric faithfulness score 0–1"]

    RAGAS → SCORES{"Per-insight<br/>scores consistent<br/>across runs?"}
    SCORES -- "Variance > 0.15 between runs" → CONSERVATIVE["📉 Take lower score<br/>as conservative estimate<br/>Do NOT average scores"]
    CONSERVATIVE → EVALUATE
    SCORES -- "Scores consistent" → EVALUATE["📋 Apply Passing Criteria:<br/>- All 8 insights faithfulness ≥ 0.7<br/>- Zero insights rated hallucinated<br/>  by human reviewer<br/>- All 8 research questions covered<br/>- No unresolved contradictions"]

    EVALUATE → LOWCONF{"Any insight<br/>faithfulness < 0.7?"}
    LOWCONF -- "Yes" → MARK_LOW["🏷 Mark as 'low-confidence'<br/>with explanation in report<br/>Do NOT force through if evidence<br/>genuinely doesn't support the claim"]
    MARK_LOW → COVERAGE_CHECK
    LOWCONF -- "No" → COVERAGE_CHECK

    COVERAGE_CHECK["🔍 Coverage Check<br/>Are all 8 research questions<br/>answered with insights?"] → MISSING{"Any missing<br/>insights?"}
    MISSING -- "Yes" → RETURN_P5["🔙 Return to Phase 5<br/>Try different query formulation<br/>or source/rating filter<br/>Re-run retrieval + generation"]
    RETURN_P5 → INSIGHTS
    MISSING -- "No" → CONTRADICT["🔎 Contradiction Detection<br/>Check all pairs of insights for<br/>opposing claims"]

    CONTRADICT → FOUND_CONTRADICT{"Contradictions<br/>found?"}
    FOUND_CONTRADICT -- "Yes" → CLASSIFY{"Genuinely different<br/>user segments?"}
    CLASSIFY -- "Yes" → ANNOTATE["📝 Annotate both insights<br/>with specific segment they apply to<br/>Present as segmentation finding<br/>→ both are valid, keep both"]
    ANNOTATE → HUMAN_CHECK
    CLASSIFY -- "No" → INVESTIGATE["🔍 Investigate retrieval quality<br/>→ different but equally valid evidence<br/>for same question across runs"]
    INVESTIGATE → RETRIEVE2["🔁 Redo retrieval with<br/>more diverse query"]
    RETRIEVE2 → INSIGHTS

    FOUND_CONTRADICT -- "No" → HUMAN_CHECK["👤 Human Spot-Check<br/>5 random insights selected<br/>PM/analyst reads end-to-end<br/>Assess: grounded? genuine? actionable?"]

    HUMAN_CHECK → HALLUCINATED{"Any rated<br/>'hallucinated'?"}
    HALLUCINATED -- "Yes" → REMOVE_REGEN["🗑 Remove hallucinated insight<br/>Regenerate with more specific<br/>query or source filter"]
    REMOVE_REGEN → INSIGHTS
    HALLUCINATED -- "No" → FINAL_EVAL{"All passing<br/>criteria met?"}

    FINAL_EVAL -- "No" → SOFT_FAIL["⚠ Soft failure: system worked<br/>technically but no actionable insights<br/>Revise query formulation →<br/>more specific source filters"]
    SOFT_FAIL → INSIGHTS
    FINAL_EVAL -- "Yes" → PASS["✅ PASS — All criteria met"]
    PASS → EVAL_REPORT["📊 Generate Eval Report JSON:<br/>- Per-insight faithfulness scores<br/>- Coverage status per question<br/>- Contradiction flags<br/>- Spot-check results<br/>- Low-confidence insight count"]

    EVAL_REPORT → DONE6["✅ Phase 6 Complete<br/>Validated insight set ready for deployment"]

    style INSIGHTS fill:#fff3e0
    style DONE6 fill:#c8e6c9
    style PASS fill:#c8e6c9
```

### 8. Frontend Architecture (Phase 7)

```mermaid
flowchart TD
    JSON_FILES["📁 Pipeline Output Artifacts<br/>outputs/insights.json<br/>outputs/themes.json<br/>outputs/retrieval_results.json<br/>outputs/eval_report.json<br/>outputs/umap_coords.json<br/>outputs/umap_clusters.png<br/>outputs/ingestion_report.json"]

    NEXTJS["⚡ Next.js App Router<br/>Frontend Application<br/>(TypeScript + Tailwind CSS)"]

    subgraph PAGES["🖐 Pages & Routes"]
        OVERVIEW["/ Overview<br/>Dataset stats, key findings,<br/>data coverage, summary"]
        THEMES["/themes<br/>Theme Explorer:<br/>browse taxonomy, view descriptions,<br/>explore representative reviews & evidence"]
        INSIGHTS["/insights<br/>AI Research Assistant:<br/>show insight cards with verbatim quotes,<br/>confidence levels, evidence links"]
        REVIEWS["/reviews<br/>Review Browser:<br/>search, filter, and explore<br/>retrieved customer reviews"]
        QUESTIONS["/questions<br/>Research Questions Dashboard:<br/>8 canonical questions with status<br/>and their generated insights"]
        SEGMENTS["/segments<br/>Segment Analysis:<br/>UMAP scatter plot visualization,<br/>segment-based insight breakdown"]
    end

    subgraph API["🔌 API Routes (api/index.py)"]
        API_INSIGHTS["GET /api/insights → insights.json"]
        API_THEMES["GET /api/themes → themes.json"]
        API_EVAL["GET /api/eval → eval_report.json"]
        API_SEGMENTS["GET /api/segments → umap_coords.json"]
        API_STATS["GET /api/stats → aggregated stats"]
        API_REVIEWS["GET /api/reviews → retrieval_results.json<br/>(paginated, filterable)"]
        API_FILTERS["GET /api/review-filters → sources.json config"]
        API_DIST["GET /api/review-distribution → ingestion_report.json"]
        API_UMAP["GET /api/umap → umap_clusters.png + coords"]
    end

    JSON_FILES --> NEXTJS
    NEXTJS --> PAGES
    PAGES --> API
    API --> JSON_FILES

    DEPLOY["🚀 Deploy to Vercel<br/>→ publicly accessible URL"]

    NEXTJS --> DEPLOY

    style JSON_FILES fill:#e8f5e9
    style NEXTJS fill:#fff3e0
    style DEPLOY fill:#e3f2fd
```

### 9. Data Provenance Chain

```mermaid
flowchart LR
    SUB["📝 Raw User Review<br/>Play Store / App Store / Forum"] --> SQLITE["💾 SQLite<br/>(data/raw/reviews.db)<br/>Schema: id, source, app,<br/>text, rating, date,<br/>language, metadata"]

    SQLITE --> PREP["🧹 Preprocessing Pipeline<br/>Phase 2"]
    PREP --> JSONL["📄 Chunked JSONL<br/>(data/processed/)"]

    JSONL --> EMBED["🧮 Embedding Layer<br/>all-MiniLM-L6-v2<br/>384-dim vectors"]
    EMBED --> CHROMA["🔷 ChromaDB Vector Index<br/>(data/embeddings/)"]

    CHROMA --> PHASE4["🔍 Phase 4<br/>Theme Identification<br/>UMAP → HDBSCAN → LLM"]
    CHROMA --> PHASE5["💡 Phase 5<br/>RAG Insight Generation<br/>Semantic Search → LLM Prompt"]

    PHASE4 --> THEMES_JSON["📁 outputs/themes.json"]
    PHASE5 --> INSIGHTS_JSON["📁 outputs/insights.json"]

    PHASE5 --> CHUNKS["📋 Retrieved Chunks<br/>linked by chunk_id<br/>→ back to SQLite record<br/>→ back to original review"]

    CHUNKS --> INSIGHTS_JSON2["📁 outputs/insights.json<br/>Each evidence quote<br/>traces to chunk_id<br/>→ SQLite record ID<br/>→ original review text,<br/>source, date, rating"]

    SQLITE --> INSIGHTS_JSON2
    JSONL --> CHROMA

    INSIGHTS_JSON --> FRONTEND["🌐 Frontend"]
    THEMES_JSON --> FRONTEND

    style SUB fill:#e3f2fd
    style SQLITE fill:#fff9c4
    style CHROMA fill:#e8eaf6
    style INSIGHTS_JSON2 fill="#c8e6c9"
    style FRONTEND fill="#fff3e0"
```

### 10. Phase Validation Gate Architecture

```mermaid
flowchart TD
    P0["🔷 Phase 0: Foundation"] --> G0{"Exit Gate:<br/>Env configured?<br/>Sources accessible?<br/>8 questions finalized?<br/>Sample raw reviews OK?"}
    G0 -- "Fail" --> FIX0["🔧 Fix configuration<br/>Re-validate"]
    FIX0 --> P0
    G0 -- "Pass" --> P1["🔷 Phase 1: Ingestion"]

    P1 --> G1{"Exit Gate:<br/>≥ 1,000 records?<br/>≥ 3 sources?<br/>Multiple rating levels?<br/>Healthy date distribution?<br/>All metadata present?"}
    G1 -- "Fail" --> FIX1["🔧 Increase scraping range<br/>Check connector health"]
    FIX1 --> P1
    G1 -- "Pass" --> P2["🔷 Phase 2: Preprocessing"]

    P2 --> G2{"Exit Gate:<br/>≥ 500 clean chunks?<br/>≥ 300 after relevance filter?<br/>No meaningful data removed?<br/>Sample quality verified?"}
    G2 -- "Fail" --> FIX2["🔧 Adjust relevance keywords<br/>Expand keyword list<br/>Relax filter threshold"]
    FIX2 --> P2
    G2 -- "Pass" --> P3["🔷 Phase 3: Embedding"]

    P3 --> G3{"Exit Gate:<br/>All chunks embedded?<br/>5 test queries return<br/>relevant results?<br/>Index validated?"}
    G3 -- "Fail" --> FIX3["🔧 Revisit Phase 2<br/>Tighten relevance filter<br/>or adjust chunking"]
    FIX3 --> P2
    G3 -- "Pass" --> P4["🔷 Phase 4: Clustering"]

    P4 --> G4{"Exit Gate:<br/>10–20 meaningful themes?<br/>Noise < 20%?<br/>Themes manually reviewed?"}
    G4 -- "Fail" --> FIX4["🔧 Tune HDBSCAN<br/>Revisit relevance filter<br/>or chunking strategy"]
    FIX4 --> P2
    G4 -- "Pass" --> P5["🔷 Phase 5: RAG Insights"]

    P5 --> G5{"Exit Gate:<br/>All 8 questions answered?<br/>Evidence verified?<br/>No vague segments?"}
    G5 -- "Fail" --> FIX5["🔧 Rewrite queries<br/>Try different source/rating filters<br/>Expand corpus"]
    FIX5 --> P2
    G5 -- "Pass" --> P6["🔷 Phase 6: Validation"]

    P6 --> G6{"Exit Gate:<br/>All insights faithfulness ≥ 0.7?<br/>Zero hallucinated?<br/>All 8 covered?<br/>No unresolved contradictions?"}
    G6 -- "Fail" --> FIX6["🔧 Regenerate low-score insights<br/>Revise queries for missing coverage<br/>Resolve contradictions"]
    FIX6 --> P5
    G6 -- "Pass" --> P7["🔷 Phase 7: Deployment"]

    P7 --> G7{"Exit Gate:<br/>All themes displayed?<br/>Insights show evidence?<br/>Search works?<br/>JSON artifacts load?<br/>Responsive?"}
    G7 -- "Fail" --> FIX7["🔧 Fix frontend<br/>Check API routes<br/>Validate JSON artifacts"]
    FIX7 --> P7
    G7 -- "Pass" --> FINAL["🚀 SYSTEM READY<br/>Insights Explorer Live"]

    style P0 fill:#e3f2fd
    style FINAL fill:#c8e6c9
    style FIX0 fill:#ffcdd2
    style FIX1 fill:#ffcdd2
    style FIX2 fill:#ffcdd2
    style FIX3 fill:#ffcdd2
    style FIX4 fill:#ffcdd2
    style FIX5 fill:#ffcdd2
    style FIX6 fill:#ffcdd2
    style FIX7 fill:#ffcdd2
```

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Standard ML/data engineering environment |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local inference, zero API cost, 384-dim vectors |
| Vector DB | ChromaDB (local disk) | Free, zero-config, sufficient for <10K chunks |
| Raw Store | SQLite | Append-only, immutable, single source of truth |
| LLM (free tier) | Gemini 1.5 Flash via Google AI Studio | Free tier (15 RPM, 1M tokens/day), structured JSON output |
| Orchestration | Python scripts (`scripts/run_*.py`) | Sequential pipeline execution |
| Frontend | Next.js + TypeScript + Tailwind CSS | Responsive, API-driven, Vercel deployment |
| Validation | RAGAS (automated) + human spot-check | Faithfulness scoring + qualitative human judgment |
| Testing | Pytest | Standard Python testing framework |

### Rate Limit Management

Gemini 1.5 Flash free tier allows 15 requests/minute. The pipeline makes ~50–60 LLM calls total:
- Phase 4: 10–20 cluster labeling calls
- Phase 5: 8 research question insight calls
- Phase 6: Up to 28 contradiction-check calls

Total completes in 4–5 minutes with no throttling.

---

## Key Design Decisions

### Structural Decisions

1. **RAG over direct LLM summarization** — Every insight claim must cite a retrieved chunk, making hallucination detectable and providing full provenance traceability from insight → chunk → SQLite record.

2. **Two-track pipeline** — Clustering (exploratory) and RAG (confirmatory) both read from the same vector index. Themes from clustering can inform or refine queries in the RAG track.

3. **Focused corpus strategy** — The relevance filter at Phase 2 removes off-topic reviews before embedding. This guarantees high retrieval precision and better clustering quality compared to embedding everything.

4. **SQLite + ChromaDB separation** — The raw store is append-only and immutable. The vector index is rebuilt. Full text always comes from SQLite, never from ChromaDB.

5. **User-voice query formulation** — Research questions are rewritten into the voice of a user experiencing the behavior, not the product manager's analyst language. This matches the semantic space of the indexed chunks.

6. **Structured insight output** — Every insight conforms to a fixed schema (`finding`, `evidence`, `implication`, `segment`). The schema is enforced both at the LLM prompt level and via Pydantic validation.

### Open Decisions

See `docs/decision.md` for the open decision table (D-08 through D-10), covering Hinglish inclusion, low-confidence insight handling, and ChromaDB vs. Pinecone migration.