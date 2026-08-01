# Implementation Plan: Zepto AI Review Engine

## Overview

This document describes the phase-wise approach to building the AI Review Engine. Each phase represents a logical unit of work with clear goals, a description of what we are doing and why, key decisions to make within that phase, risks, and edge cases to watch for. Detailed testing checklists and numeric exit criteria for each phase are in [eval.md](./eval.md).

The pipeline is deliberately sequential — the output of each phase is the input to the next. This means a quality failure in an early phase (e.g., poor data collection or over-aggressive filtering) silently degrades everything downstream. The phase structure exists to catch those failures early with explicit exit gates.

---

## Phase 0: Foundation & Scoping

### What We Are Doing
Before any data is touched or any model is called, we establish the complete context that every subsequent phase depends on. This includes: confirming we can access the data sources we plan to use, defining the exact questions the system must answer, agreeing on the canonical data schema, and setting up the development environment in a way that is reproducible by others.

The most important output of this phase is not technical — it is the **8 canonical research questions**. Every downstream component (the relevance filter, the semantic queries, the RAG prompts, the report structure) is calibrated against these 8 questions. If they change mid-project, significant rework follows. Getting them right here prevents churn.

### Key Decisions in This Phase
- **Finalize the 8 research questions.** The questions in the problem statement are a starting point, not a specification. They need to be made precise enough to drive both the relevance filter (what data to keep) and the semantic queries (what to retrieve).
- **Confirm data source priority.** Not all sources will be accessible or rich enough to justify effort. Play Store and App Store are the highest-priority sources. App Store (India) and forums are second-tier. Twitter/X is third-tier given API cost and short-form noise.
- **Agree on whether Hinglish is in scope.** This determines whether the preprocessing and embedding approach needs to handle mixed-language text. It is a non-trivial decision — see [decision.md](./decision.md) open decisions.

### Risks
- API access for some sources may be restricted or require paid tiers (Twitter/X in particular).
- Research questions may be underspecified, leading to a relevance filter that is either too broad or too narrow.

### Edge Cases
- **Fewer than 3 sources are accessible.** If only 1–2 sources can be confirmed (e.g., Twitter/X API is blocked and forums require registration), the corpus will be source-biased. Mitigation: increase volume from available sources and explicitly flag the missing sources in the final report. Do not proceed with a single source — the insight quality will be too narrow.
- **Research questions overlap significantly.** Two questions may address essentially the same behavior (e.g., "What prevents exploration?" and "What frustrations emerge?"). If this is discovered in Phase 0, consolidate them into one precise question and add a new distinct question. Proceeding with overlapping questions wastes retrieval budget and produces duplicate insights.
- **Stakeholders change the research questions mid-project.** If a question changes after Phase 2 (preprocessing), the relevance filter keyword list may no longer capture the right data. Track which research questions drove which keywords — if a question is replaced, assess whether the existing corpus already covers it before deciding to re-collect data.


## Validation

Before proceeding to Phase 1, verify that:

- The development environment is fully configured.
- All required dependencies install successfully.
- Project structure has been created.
- Data sources are accessible.
- The eight research questions have been finalized.
- A sample of raw reviews has been manually inspected to verify:
  - Rating diversity
  - Review quality
  - Metadata completeness
  - Language consistency

  ## Outputs

- Finalized research questions
- Project directory structure
- Configured development environment
- Data source configuration
- Canonical review schema
- Initial dataset validation report

---

## Phase 1: Data Ingestion

### What We Are Doing
We build the connectors that pull raw data from each confirmed source and write it into a single, normalized data store. The goal of this phase is purely **breadth and volume** — we are not filtering or judging quality yet, we are collecting as much potentially relevant data as possible.

Each source requires its own connector because each source has a completely different access mechanism: the Play Store uses a third-party scraper library, App Store uses a scraper library, and forums require HTML scraping. Despite these differences, every connector produces the same output schema so that the rest of the pipeline is source-agnostic.

The raw data store (SQLite) is the single source of truth for the entire project. If anything goes wrong downstream, we can always return to this store and re-process from scratch. Nothing in later phases modifies the raw store — it is append-only.

### What "Good" Looks Like
- At least 1,000 raw records, spread across at least 3 distinct sources.
- Records span both Zepto and at least 2 competitors (Blinkit, Swiggy Instamart).
- The data store has a healthy date distribution — not dominated by a single week or event.
- Each record has a non-empty text field and a valid source tag.

### Key Decisions in This Phase
- **How far back to scrape.** 12 months is the default. Going further back risks including reviews that predate Zepto's current feature set and catalog, making them less actionable.
- **Rating distribution.** We scrape all ratings (1–5 stars), not just negative ones. Positive reviews sometimes contain the most useful information about why users *do* explore — which is equally important for understanding barriers.
- **Competitor app inclusion.** Confirmed in [decision.md](./decision.md). All competitor records are tagged with the `app` field so they can be filtered out if needed.

### Risks
- Rate limiting from Play Store or App Store scrapers may slow collection significantly.
- Forum scraping may be fragile due to HTML structure changes or rate limits.
- Forum scraping (MouthShut, LocalCircles) may be fragile due to HTML structure changes.

### Edge Cases
- **Limited Data Collection** If fewer reviews are collected than expected, increase the scraping range or continue collecting additional batches until sufficient data is available.
- **A scraper returns data but the text field is empty or garbled.** Some Play Store reviews are returned with only a star rating and no text body, or with HTML entities (`&amp;`, `&#39;`) that were not decoded. These must be caught at schema validation — records with empty or non-UTF-8 text after decoding are discarded at ingestion, not silently stored.
- **Date field is missing or unreliable.** Certain forum scrapers return "3 months ago" rather than an absolute date. Relative dates must be resolved to absolute dates at ingestion time using the scrape timestamp as the reference. If resolution is impossible, store `null` and flag the record — do not fabricate a date.
- **A single forum thread dominates the corpus.** A viral discussion with hundreds of replies could contribute many near-duplicate records from one event. This creates artificial cluster density in Phase 4. Mitigation: cap per-thread record count and log threads that hit the cap.
- **All scraped data comes from a single time window.** If the scraper is configured incorrectly and only pulls the last 2 weeks of reviews, the corpus will reflect a specific period's events (e.g., a major outage or sale) rather than general user behavior. Check the date distribution histogram before exiting this phase.
- **A source returns content in a language other than expected.** Community forums may contain Hindi or Hinglish posts. If Hinglish is not in scope, these records will be filtered in Phase 2 — but the raw store should keep them unchanged. Never discard at ingestion; filter decisions belong in preprocessing.

## Validation

Before proceeding to Phase 2, verify that:

- At least 1,000 reviews have been collected.
- Reviews contain meaningful text.
- Multiple rating levels are represented.
- The dataset spans a reasonable time period.
- Required metadata fields are present.
- Reviews have been successfully stored in the SQLite database.
- The rating distribution appears representative and is not heavily biased toward a single rating.

### Deliverables
- SQLite database containing raw customer reviews
- Standardized review dataset
- Data collection summary including:
  - Total reviews collected
  - Source-wise distribution
  - Rating distribution
  - Date distribution
  - Collection errors (if any)

---

## Phase 2: Preprocessing & Corpus Refinement

### What We Are Doing
This phase transforms the raw, messy corpus into a clean, focused set of text chunks that are genuinely worth embedding and retrieving. It is the most consequential phase for overall system quality — every downstream component (clustering, retrieval, insight generation) operates on this corpus, so its quality directly determines the quality of the final output.

The preprocessing pipeline is a sequential filter chain. Records pass through each step in order: language filtering first (cheapest to compute), then near-duplicate removal, then noise removal, then relevance filtering (most expensive to compute), and finally chunking.

**The hardest judgment call in this phase is the relevance filter.** If set too aggressively, we discard reviews that mention category exploration indirectly. If set too loosely, we flood the index with irrelevant content about delivery speed or app crashes. The keyword-based pass is fast but blunt — a semantic similarity pass using an anchor embedding is more accurate but costs more to compute. We use both: keywords as a fast first pass, semantic scoring as a secondary check on borderline cases.

**Chunking strategy** deserves specific attention. Short app store reviews (typically 1–4 sentences) are kept as a single chunk. Long forum posts can run to several paragraphs — these are split into overlapping 300–500 token windows. The overlap ensures that a sentence at the boundary of two windows is not artificially separated from its context.

### Key Decisions in This Phase
- **Keyword list for the relevance filter.** This is hand-curated and should be reviewed against a sample of raw data before finalizing. The list should capture direct mentions of category exploration as well as indirect signals (e.g., "I only buy groceries here", "I didn't know they had pet food").
- **Minimum review length.** Set at 6 words. Reviews shorter than this are almost always uninformative ("great app", "love it", "pathetic service"). This is a calibration point — too high and we lose genuine short-form feedback.
- **Chunk size.** 300–500 tokens with 50-token overlap is the default. Smaller chunks give more precise retrieval but lose context. Larger chunks give more context but reduce precision.

### Risks
- Over-aggressive relevance filtering may discard too many records, leaving an insufficient corpus for robust clustering and retrieval.
- Chunking long posts may split a single coherent opinion across two chunks, making retrieval less precise.

### Edge Cases
- **Relevance filter drops more than 70% of records.** This signals that the keyword list is too restrictive, or that the raw corpus is dominated by off-topic content. Before relaxing the filter, inspect 50 discarded records manually — if they are genuinely off-topic, the corpus collection strategy (source selection or search queries) needs adjustment. If many are relevant but phrased differently, expand the keyword list.
- **Relevance filter retains fewer than 300 records after all steps.** This is below the minimum viable corpus for meaningful clustering. Options: expand the keyword list, add more data sources, or extend the scraping time window. Do not proceed to embedding with fewer than 300 chunks — the clustering and retrieval results will be unreliable.
- **Near-duplicate detection is too aggressive.** Paraphrase detection using MinHash may flag distinct reviews that happen to use similar language (e.g., multiple different users saying "I never explore other categories"). These are genuine signal, not duplicates — they confirm the prevalence of the behavior. Calibrate MinHash similarity threshold carefully; cosine similarity > 0.97 is a safer threshold than exact match for this use case.
- **A review contains a mix of relevant and irrelevant content in the same paragraph.** For example: "Delivery is great but I wish there was an easier way to discover new categories." The first half is off-topic; the second half is the most relevant sentence in the corpus. Chunking at the paragraph level keeps these together. Do not chunk at the sentence level — single sentences lose too much context for embedding quality.
- **Chunks inherit metadata but the parent record's date is null.** If a parent record had a null date (from Phase 1), its chunks inherit `null` date. This means they cannot be used in time-filtered queries. These chunks are still valid for theme clustering and unfiltered retrieval — tag them explicitly as `date_unknown` rather than omitting them.

## Validation
Before proceeding to Phase 3, verify that:
- Review text has been cleaned successfully.
- Duplicate reviews have been removed.
- Metadata has been preserved correctly.
- Long reviews have been chunked appropriately.
- No meaningful customer feedback has been unintentionally removed.
- A random sample of processed reviews has been manually inspected to verify text quality and metadata accuracy.

### Deliverables
- Clean, chunked JSONL corpus stored in `data/processed/`.
- Preprocessing stats: raw count → after language filter → after deduplication → after noise removal → after relevance filter → final chunk count.
- At least 500 clean chunks ready for embedding.

---

## Phase 3: Embedding & Vector Indexing

### What We Are Doing
Every clean text chunk is converted into a dense numerical vector (an embedding) that encodes its semantic meaning, and all vectors are loaded into a vector database alongside their metadata. This is the infrastructure that makes semantic search possible.

Embedding is computationally straightforward but operationally careful. We use sentence-transformers locally — zero API cost, no rate limits. Each chunk is embedded exactly once — embeddings are cached to avoid re-spending API cost if the index needs to be rebuilt.

The vector database stores each embedding alongside a metadata payload that enables filtered retrieval. The metadata schema is designed to answer real analyst questions like: "What do low-rated Zepto reviewers say?", "What do forum discussions say vs. what do the Play Store reviews say?", "Has this pattern changed over the last 6 months?". Without metadata, these questions can only be answered by re-running the full pipeline with a filtered corpus. With metadata, they are a single parameterized query.

After loading, we validate retrieval quality using a set of 5 test queries drawn directly from the 8 research questions. We manually inspect the top-5 results for each test query and confirm that they are semantically relevant. If retrieval looks poor, we investigate the relevance filter (too much noise in the corpus) or the chunking strategy (chunks too large or too small) before proceeding.

### Key Decisions in This Phase
- **Metadata schema.** The fields stored alongside each vector are finalized here. Adding a new metadata field later requires re-indexing the entire corpus.
- **Top-K retrieval count.** We default to K=10 during insight generation. This is set here and should be calibrated against the test queries: does K=5 give enough evidence? Does K=15 introduce too much noise?

### Risks
- OpenAI API rate limits may slow batch embedding significantly for a large corpus.
- Retrieval quality checks reveal that the corpus is too noisy — this sends us back to Phase 2 to tighten the relevance filter.

### Edge Cases
- **Embedding API returns an error mid-batch.** Partial batches must not be silently dropped. The embedding pipeline must track which chunk IDs have been successfully embedded and resume from the last successful point. Running the embedding step twice should be idempotent — chunks that are already indexed should not be re-embedded.
- **Retrieval test queries return no results.** This means the query text has no semantic neighbors in the index — either the corpus has no relevant content on that topic (data gap), or the query is phrased in a way that is semantically distant from how users write. Try multiple phrasings of the same query before concluding it is a data gap.
- **All retrieved chunks for a test query come from a single source.** If all top-10 results for "exploring new categories" come only from one source, it suggests a strong source imbalance in the corpus. This is acceptable if that source genuinely dominates the corpus, but should be noted — insights based on a single source type may not generalize.
- **Metadata filtering returns zero results.** A query like `source = "app_store" AND rating = 1` may return nothing if no low-rated App Store reviews passed the relevance filter. This is a valid outcome — document it. Do not artificially loosen the filter to force results.
- **ChromaDB index becomes corrupted or is accidentally deleted.** Since ChromaDB stores on disk, the index is not durable in the same way a managed DB is. The SQLite raw store + processed JSONL files are the source of truth. The vector index can always be rebuilt from these files. Ensure both are backed up before proceeding to Phase 4.


### Deliverables
- Fully indexed ChromaDB collection with all clean chunks and their metadata.
- Index stats report: total vectors, embedding dimensions, metadata schema.
- Retrieval validation report: test queries + top-5 results + manual quality assessment.

---

## Phase 4: Theme Identification

### What We Are Doing
Before we answer specific research questions, we first want to understand what topics exist in the corpus — without any prior hypothesis. This is the exploratory track of the pipeline, and it runs independently of the RAG Insight Engine.

The process works in three stages. First, we reduce the dimensionality of the embeddings from 384 dimensions to 5 dimensions using UMAP. This is necessary because clustering algorithms degrade severely in high-dimensional spaces — distances become meaningless above a few dozen dimensions. UMAP is chosen over PCA because it preserves local neighborhood structure, which is what we care about for semantic clustering.

Second, we cluster the reduced embeddings using HDBSCAN. Unlike K-Means, HDBSCAN does not require us to specify how many clusters exist in advance. It finds clusters of varying density and marks outliers as noise. This is important because we genuinely do not know how many distinct themes exist in the corpus before we run the algorithm.

Third, for each cluster, we extract the most representative samples (those closest to the cluster centroid) and pass them to an LLM to generate a human-readable theme label, a one-paragraph description, and 3 verbatim quotes. The LLM is rate-limited to 15 requests/minute and 1M tokens/day on the free tier. The LLM's role here is purely synthesis and labeling — it reads real user text and describes what it sees. It is not inventing themes.

The output is manually reviewed. Clusters that are too similar are consolidated. Clusters that are genuinely ambiguous are re-inspected to decide whether they represent a single theme or two overlapping ones. This manual step is necessary — automated clustering produces mathematical clusters, not necessarily human-meaningful themes.

### What We Expect to Find
Based on the problem space, we expect themes to include (but not be limited to): habitual purchasing behavior, price sensitivity as a barrier to trying new categories, trust issues with unfamiliar category quality, discovery via deals or promotions, frustration with search/browsing UX, life-event triggers (new pet, baby, health goal), and comparison with competitor platforms.

### Key Decisions in This Phase
- **HDBSCAN `min_cluster_size`.** Larger values produce fewer, broader clusters. Smaller values produce more, narrower clusters. The right value depends on corpus size. We target 10–20 final themes.
- **Noise threshold.** If more than 20% of chunks fall into the noise cluster, either our corpus needs further cleaning or the clustering parameters need tuning. This is a forcing function to revisit earlier phases.
- **Consolidation criteria.** Two themes are consolidated if they share more than 70% of their top-10 representative chunks when checked by overlap.

### Risks
- Poorly tuned HDBSCAN produces either too many micro-clusters (hard to interpret) or too few mega-clusters (too abstract to be actionable).
- Themes may overlap significantly if the relevance filter was too narrow, producing a corpus that is semantically too homogeneous to cluster well.

### Edge Cases
- **HDBSCAN produces fewer than 5 clusters.** This typically means the corpus is semantically too homogeneous — the relevance filter was too narrow and all retained content is about a single sub-topic. First, try reducing `min_cluster_size`. If that does not help, revisit the relevance filter and broaden it to include adjacent topics (e.g., general app satisfaction signals, not just explicit exploration mentions).
- **HDBSCAN produces more than 30 clusters.** The opposite problem — the corpus may contain too many niche micro-topics, or the `min_cluster_size` is too low. Increase `min_cluster_size` until the cluster count is in the 10–25 range. Alternatively, use hierarchical clustering to merge related micro-clusters into parent themes.
- **More than 20% of the corpus falls into the noise cluster (cluster -1).** This means a significant portion of the clean data is semantically isolated and cannot be grouped. These chunks are not wasted — they are still searchable via RAG. However, their existence suggests the corpus contains a long tail of unique, idiosyncratic opinions that do not represent broader patterns. Document this finding explicitly.
- **The LLM produces identical or near-identical labels for two different clusters.** This signals genuine semantic overlap between two clusters — they may represent the same theme. Before consolidating, manually inspect 10 random samples from each cluster. If the samples feel meaningfully different despite a similar label, keep them separate and refine the labels. If they feel interchangeable, consolidate.
- **A cluster's representative samples all come from a single source** (e.g., all from one forum thread). The theme may be an artifact of one discussion, not a generalizable pattern. Flag it as "single-source theme" in the taxonomy — include it but note its limited generalizability.
- **UMAP produces a degenerate 2D visualization** where all points are in one blob. This usually means the embeddings are too similar (corpus too homogeneous) or UMAP hyperparameters need tuning (`n_neighbors`, `min_dist`). Try `n_neighbors = 15` and `min_dist = 0.1` as a starting point. The 5D reduction used for clustering is separate from the 2D visualization — clustering may still work even if the 2D visualization looks poor.

### Deliverables
- Theme taxonomy JSON: Produce a manageable set of meaningful themes, each with a name, description, and 3 verbatim quotes.
- 2D UMAP visualization showing cluster structure (for human review and presentation).
- Manual review notes on any consolidated or discarded clusters.

---

## Phase 5: RAG Insight Generation
## Goal

Enable users to explore customer feedback by asking natural-language research questions and receiving evidence-backed insights generated using Retrieval-Augmented Generation (RAG).

Rather than searching reviews manually, users can ask product research questions such as:

- Why are users not exploring new categories?
- What are the biggest complaints about search?
- What motivates customers to try new products?
- Compare Zepto and Blinkit for product discovery.

The system retrieves the most relevant customer reviews and synthesizes them into structured insights supported by real evidence.


### What We Are Doing
This is the confirmatory track of the pipeline. For each of the 8 research questions, we retrieve the most relevant user feedback from the vector index and use it as grounding context for an LLM to generate a structured, evidence-backed insight.

Once relevant chunks are retrieved, they are provided to the LLM as the only permissible source of evidence. The LLM is rate-limited to 15 requests/minute and 1M tokens/day on the free tier. The LLM prompt explicitly instructs the model not to draw on its own training data — every claim in the output must be supported by the provided context. The output schema enforces this: the `evidence` field requires at least 2 verbatim quotes from the retrieved chunks.

Each generated insight is then linked back to its source chunk IDs so that any claim can be traced directly to the original user review in the SQLite store.

### Key Decisions in This Phase
- **Query formulation for each research question.** This is a judgment call made by the analyst and is the primary lever for retrieval quality. Poorly formulated queries produce irrelevant retrieved chunks, which produce poor insights regardless of LLM quality.
- **Top-K value.** We use K=10 as the default. This provides enough evidence for the LLM to synthesize a meaningful insight without overwhelming the context window.
- **Source filtering per question.** Some research questions may benefit from source-specific retrieval. For example, "What frustrations emerge repeatedly?" may benefit from filtering to 1–3 star reviews. The metadata in the vector DB enables this.

### Risks
- If the retrieved chunks for a given question are not actually relevant, the LLM will either hallucinate or produce a generic insight. This is caught in Phase 6.
- Some research questions may not have sufficient relevant data in the corpus — particularly niche segments like "new parents" or "pet owners". In this case, the insight may be low-confidence or absent.

### Edge Cases
- **All retrieved chunks for a question are from the same 2–3 parent records.** This means K=10 is retrieving repeated chunks from the same source post (e.g., 8 of 10 chunks are from the same long forum thread). The insight will be dominated by a single person's perspective. Mitigation: enforce a maximum of 2 chunks per parent record ID in retrieval. This forces diversity in the evidence base.
- **The LLM produces an insight where the `evidence` quotes are paraphrased, not verbatim.** The prompt instructs the model to quote literally, but LLMs sometimes rephrase. Before accepting an insight, programmatically verify that each evidence string appears as a substring in at least one of the retrieved chunks. Fail and retry if it does not.
- **Two different research questions retrieve the same top-10 chunks.** This means the two questions are semantically indistinguishable to the retrieval system — their queries land in the same part of the vector space. Try rewriting the queries with more specific framing, or apply source/rating filters to differentiate the retrieval context.
- **The LLM refuses to generate an insight because the retrieved context is "insufficient."** This is a valid and correct LLM behavior. It signals a genuine data gap — the corpus does not contain enough on-topic content for that research question. Do not force the model to generate. Mark the question as "insufficient evidence" and include a note in the report explaining the gap.
- **An insight's `segment` field is too vague** (e.g., "all users" or "most users"). This provides no actionable targeting information. The prompt should specify that the segment must be a concrete description: life stage, use case, behavior pattern, or geography. Insights with vague segments are returned for revision before being accepted.
- **The same insight finding appears across multiple research questions.** This happens when two questions address overlapping behaviors. Rather than repeating the insight, cross-reference it: note that this finding addresses both questions and synthesize a unified insight card with combined evidence from both retrieval sets.

### Validation

Before proceeding to Phase 6, verify that:

- Research questions retrieve relevant reviews.
- Generated insights are supported by retrieved evidence.
- Every insight includes supporting review excerpts.
- Evidence links correctly reference the original reviews.
- The system clearly indicates when insufficient evidence is available.


## Outputs

- AI-generated research insights
- Evidence-backed summaries
- Linked supporting reviews
- Structured JSON response for the web application

---

## Phase 6: Validation & Quality Assurance

### What We Are Doing
Before insights are shared with stakeholders, they must pass a multi-layer quality check. The goal of this phase is to catch and correct three failure modes: hallucinated claims, missing coverage, and contradictory insights.

**Faithfulness scoring** uses the RAGAS framework to automatically evaluate whether each claim in an insight is supported by its retrieved evidence. RAGAS uses Gemini as its judge LLM, subject to the same rate limits (15 RPM, 1M tokens/day). RAGAS does this by breaking the insight into individual claims and checking each one against the evidence chunks using an LLM as a judge. This is more rigorous than manual review and produces a numeric score that can be compared across insights and across pipeline runs.

**Coverage checking** confirms that all 8 research questions have been answered. A missing insight is not acceptable — if one question has no answer, we return to Phase 5 and try a different query or source filter.

**Contradiction detection** identifies pairs of insights that make opposing claims. This can happen when different user segments have genuinely different experiences (which is informative) or when the RAG pipeline retrieved different but equally valid evidence for the same question across two runs (which is a reliability concern). Contradictions are flagged for manual review and resolved before reporting.

**Human spot-check** is the final layer. Five randomly selected insights are read end-to-end by a human reviewer (the PM or analyst) who assesses whether the finding feels grounded, the evidence is genuine, and the implication is actionable. Any insight rated as "hallucinated" is removed and regenerated.

### What "Passing" Looks Like
All 8 insights have a faithfulness score of ≥0.7, zero insights are rated hallucinated by the human reviewer, all 8 research questions are covered, and no unresolved contradictions remain.

### Risks
- An insight may repeatedly fail faithfulness because the retrieved evidence genuinely does not support a strong claim for that research question. In this case, we mark it as "low-confidence" and include a note in the report rather than forcing a weak insight through.

### Edge Cases
- **RAGAS itself produces inconsistent faithfulness scores** across two runs for the same insight. RAGAS uses an LLM as a judge, which is non-deterministic. If scores vary by more than 0.15 across two runs, take the lower score as the conservative estimate. Do not average the scores — the pessimistic score is the safer one to report.
- **A contradiction is detected between two insights that are both correctly grounded.** This happens when genuinely different user segments have opposite experiences (e.g., "Users find discovery easy via deals" and "Users say there is no discovery mechanism"). Both can be true for different segments. Resolution: do not discard either insight — annotate both with the specific segment they apply to and present them as a segmentation finding in the report.
- **Faithfulness scoring consistently fails for one specific insight across all retry attempts.** This usually means the finding is making a claim that goes beyond what the evidence actually says — even if the evidence is relevant. The LLM over-generalized. The fix is to narrow the `finding` to exactly what the evidence supports, even if it is a weaker claim. A narrow, accurate insight is more useful than a broad, unsupported one.
- **Human reviewer flags an insight as "feels hallucinated" but RAGAS gave it a score of 0.85.** Trust the human reviewer. RAGAS checks factual consistency between the finding and the evidence text, but it does not check whether the finding is *important*, *representative*, or *surprising*. A technically faithful claim can still be misleading if it is cherry-picked from unrepresentative evidence. Re-examine the retrieved chunks — if they are not representative of the broader corpus, redo the retrieval with a more diverse query.
- **All 8 research questions have insights but none of them are surprising or actionable.** This is a soft failure — the system worked technically but produced no value. Before reporting, evaluate whether each insight would change a PM's decision or prioritization. If not, revisit the query formulation and try retrieval with more specific source filters (e.g., filter to 1-star reviews or a specific source) to surface stronger signal.

### Deliverables
- Evaluation report JSON with per-insight faithfulness scores, coverage status, and contradiction flags.
- Revised insight set with low-confidence insights marked and explained.

---
# Phase 7: Frontend Development & Deployment

## Objective

Build a modern, responsive AI-powered Customer Insights platform that enables users to explore customer feedback, discover recurring themes, and interact with an AI Research Assistant through an intuitive web interface.

The frontend consumes the JSON artifacts generated in previous phases and presents them using a polished, production-ready UI suitable for customer research and product decision-making.

---
 # Phase 7

# Implementation

## Dashboard (Home)

Create a comprehensive landing dashboard that provides an executive overview of the customer feedback dataset.

### Features

- Welcome section with project overview
- AI-generated executive summary
- Dataset statistics
  - Total Reviews
  - AI-discovered Themes
  - Average Sentiment
  - Data Coverage
- Review volume trend chart
- Overall sentiment visualization
- Recent AI-generated insights
- Recently discovered themes
- Quick navigation to Theme Explorer and AI Chat

---

## Theme Explorer

Provide an interface for exploring AI-discovered customer themes.

### Features

- Browse all discovered themes
- AI-generated theme descriptions
- Priority indicators
  - High Priority
  - Medium Priority
  - Low Priority
- Sentiment score for each theme
- Number of supporting customer reviews
- Theme detail pages containing:
  - Representative customer reviews
  - Supporting evidence
  - Related observations
  - Similar themes
- Live discovery section highlighting newly emerging themes

---

## AI Research Assistant

Build a conversational AI interface for customer research powered by Retrieval-Augmented Generation (RAG).

### Features

- Natural-language question answering
- Semantic search across customer reviews
- Retrieval-Augmented Generation (RAG)
- AI-generated research summaries
- Supporting customer review excerpts
- Confidence score for generated insights
- Source citations
- Impact assessment
- Product recommendations
- Suggested follow-up questions

Example questions:

- Why are users dissatisfied with onboarding?
- What payment issues are increasing?
- Which feature requests appear most frequently?
- What themes have emerged recently?

---

# Frontend Architecture

Develop the application using a modular, JSON-driven architecture.

### Architecture

- Responsive React frontend
- Component-based architecture
- JSON-driven rendering
- Mobile-first design
- Modular pages
- Reusable UI components
- Responsive layouts for desktop, tablet, and mobile
- Optimized performance and lazy loading where appropriate

---

# UI & Design System

The application follows a modern AI SaaS design language focused on readability, simplicity, and evidence-based customer research.

## Design Style

- Modern dark theme
- Mobile-first responsive layout
- Card-based interface
- Rounded corners
- Soft shadows
- Minimalist design
- High visual hierarchy
- AI-first user experience
- Clean spacing and typography
- Smooth interactions and hover effects

---

## Color Palette

| Purpose | Color |
|----------|---------|
| Primary Purple | #8B5CF6 |
| Accent Purple | #A855F7 |
| Primary Background | #0F172A |
| Card Background | #1E293B |
| Elevated Surface | #273449 |
| Primary Text | #FFFFFF |
| Secondary Text | #CBD5E1 |
| Borders | #334155 |
| Success | #22C55E |
| Warning | #F59E0B |
| Error / High Priority | #EF4444 |

---

## UI Components

The application includes reusable components such as:

- Dashboard Cards
- Metric Cards
- Theme Cards
- Insight Cards
- AI Response Cards
- Recommendation Cards
- Search Bar
- Sidebar Navigation
- Bottom Navigation
- Review Cards
- Priority Badges
- Sentiment Indicators
- Confidence Score Indicators
- Interactive Charts
- Progress Rings
- Expandable Detail Panels

---

## Data Visualization

Display insights using intuitive visualizations:

- Review volume bar charts
- Sentiment score radial charts
- Priority badges
- Trend indicators
- Theme cards
- Review counters
- AI confidence indicators

---

## User Experience

The application is optimized for research workflows by providing:

- Fast navigation between modules
- AI-powered search experience
- Evidence-first insight presentation
- Clear information hierarchy
- Responsive layouts
- Accessible interface
- Consistent spacing and typography
- Production-ready SaaS appearance

---

# Deployment

Deploy the application as a production-ready web application.

### Tasks

- Connect frontend to generated JSON artifacts
- Load themes dynamically
- Load AI-generated insights dynamically
- Load representative reviews dynamically
- Connect semantic search outputs
- Ensure responsive layouts
- Optimize performance
- Deploy on Vercel
- Publish a publicly accessible URL

### API Routes

The Next.js frontend communicates with the backend through API routes defined in `frontend/src/app/api/`. Each route reads from the output JSON files generated by the pipeline:

| Route | File | Data Source |
|---|---|---|
| `/api/insights` | `frontend/src/app/api/insights/route.ts` | `outputs/insights.json` + `outputs/eval_report.json` |
| `/api/themes` | `frontend/src/app/api/themes/route.ts` | `outputs/themes.json` |
| `/api/eval` | `frontend/src/app/api/eval/route.ts` | `outputs/eval_report.json` |
| `/api/segments` | `frontend/src/app/api/segments/route.ts` | `outputs/insights.json` (derived) |
| `/api/stats` | `frontend/src/app/api/stats/route.ts` | `outputs/ingestion_report.json`, `data/processed/clean_chunks.jsonl` |
| `/api/reviews` | `frontend/src/app/api/reviews/route.ts` | `outputs/reviews_export.json` |
| `/api/review-filters` | `frontend/src/app/api/review-filters/route.ts` | `outputs/review_filters.json` |
| `/api/review-distribution` | `frontend/src/app/api/review-distribution/route.ts` | `outputs/review_distribution.json` |
| `/api/umap` | `frontend/src/app/api/umap/route.ts` | `outputs/umap_coords.json`, `outputs/umap_clusters.png` |

### Data Export Script

`scripts/export_reviews.py` exports reviews from the SQLite raw store to JSON files for the API routes. Run after Phase 1 to generate `outputs/reviews_export.json`, `outputs/review_distribution.json`, and `outputs/review_filters.json`.

```bash
python scripts/export_reviews.py
```

---

# Validation

Before deployment, verify that:

## Dashboard

- Dataset metrics load correctly
- Charts render successfully
- AI summaries display properly
- Recent insights are visible

## Theme Explorer

- All generated themes display correctly
- Theme descriptions load successfully
- Priority labels display correctly
- Supporting reviews are accessible
- Theme details render correctly

## AI Research Assistant

- Semantic search retrieves relevant reviews
- RAG generates evidence-backed answers
- Supporting review excerpts are displayed
- Confidence scores are shown
- Citations are included
- Follow-up suggestions appear correctly

## API Routes

- All API endpoints return valid JSON
- \/api/insights\ returns insights with faithfulness scores
- \/api/themes\ returns theme taxonomy with quotes
- \/api/reviews\ returns paginated, filterable reviews
- \/api/stats\ returns pipeline statistics
- \/api/umap\ returns cluster coordinates or image
- \/api/eval\ returns validation report

## Application

- All JSON artifacts load successfully
- Navigation works correctly
- Search and filters operate properly
- Application is responsive across desktop, tablet, and mobile
- No broken routes or missing assets
- Performance is acceptable for production deployment

---

# Outputs

The completed Phase 7 should deliver:

- Responsive AI-powered Customer Insights web application
- Executive dashboard for customer feedback analysis
- Interactive Theme Explorer
- Conversational AI Research Assistant
- JSON-driven frontend
- Fully responsive UI
- Modern AI SaaS interface
- Live Vercel deployment
- Publicly accessible application URL
- API routes serving all pipeline outputs
- Review export script for data pipeline integration