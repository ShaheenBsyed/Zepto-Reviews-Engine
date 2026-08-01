# Decision Log: Zepto AI Review Engine

## Purpose

This document captures the significant architectural and logical decisions made while building this system — choices where the alternative paths were meaningfully different and where future contributors need to understand *why* the approach was taken, not just *what* was chosen. Small tooling selections (e.g., which HTTP library to use) are not recorded here.

---

## [D-01] Use RAG Instead of Direct LLM Summarization

**Status:** Decided
**Impact:** Fundamental — affects the entire insight generation architecture.

### The Decision
The system uses Retrieval-Augmented Generation (RAG) to produce insights: user reviews are first indexed in a vector database, and during insight generation, relevant reviews are retrieved semantically and provided as grounding context to the LLM.

The alternative — feeding all reviews directly into an LLM prompt and asking it to summarize — was explicitly rejected.

### Why This Matters
This is the most important architectural decision in the project. It determines whether the system's outputs are trustworthy.

**The problem with direct LLM summarization:**
1. **Scale:** Thousands of reviews cannot fit in a single context window. Chunking and summarizing in batches loses cross-document signals and introduces aggregation bias.
2. **Hallucination:** LLMs generate plausible-sounding insights even when the data does not support them. There is no way to catch this without grounding every claim in a specific retrieved chunk.
3. **Auditability:** A stakeholder who questions an insight cannot trace it back to specific users. This destroys trust in the output.

**Why RAG solves these problems:**
- The vector index handles unlimited corpus size — retrieval is always bounded.
- Every insight claim is required to cite a specific retrieved chunk, making hallucination detectable.
- Every evidence quote maps back to a chunk ID, which maps back to a source record — full provenance chain.

### Trade-off Accepted
RAG adds significant complexity: vector DB setup, metadata schema design, query formulation, and a separate validation step (RAGAS) to verify faithfulness. This is worth it because the alternative (ungrounded LLM summarization) would produce outputs that cannot be trusted or defended to stakeholders.

---

## [D-02] Two-Track Pipeline: Theme Identification + RAG Insight Engine

**Status:** Decided
**Impact:** High — shapes the scope and structure of the analysis.

### The Decision
The pipeline has two parallel tracks that both read from the same vector index:
1. **Theme Identification** — exploratory, hypothesis-free discovery of what topics exist in the corpus using clustering.
2. **RAG Insight Engine** — confirmatory, hypothesis-driven answering of the 8 pre-defined research questions.

The alternative was to use only one track — either clustering alone (pure exploration) or RAG alone (pure confirmation).

### Why Both Tracks Are Necessary
**Clustering alone** is insufficient because it answers "what is people talking about?" but not "what does the data say about X?" — the specific business questions the PM team needs answered. Cluster labels like "delivery complaints" or "product selection" are descriptive but not actionable.

**RAG alone** is insufficient because it is constrained to the 8 research questions defined upfront. If an important theme exists in the data that nobody anticipated (e.g., a strong signal about gift-buying behavior), it would be invisible to a query-only system.

Together, the two tracks give both **breadth** (what's in the data?) and **depth** (what does the data say about our specific questions?). Themes from Track 1 can also inform or refine the queries used in Track 2.

---

## [D-03] Competitor Reviews Included in the Corpus

**Status:** Decided
**Impact:** Medium — expands the data collection scope and affects insight interpretation.

### The Decision
The data ingestion includes reviews for Blinkit, Swiggy Instamart, and BigBasket in addition to Zepto. All records are tagged with the `app` metadata field so competitor data can be excluded from any query at retrieval time.

### Why This Was Not Obvious
The strongest counterargument is: "We are building this for Zepto. Why include data about other apps?" The concern is that insights about Blinkit's UX problems might be attributed to Zepto, leading to wrong product decisions.

### Why We Included Them Anyway
The research questions are about **user behavior and psychology around category exploration** — not about Zepto's specific UX. A user who says "I never explore new categories on Blinkit because I'm not sure about quality" is expressing the same behavioral pattern as a Zepto user who says the same. The behavior is the insight, not which app it happens on.

Competitor data also surfaces **comparative signals** — cases where users explicitly say "I discovered X on [competitor] but not on Zepto" — which are highly valuable for the growth team.

The metadata tagging ensures this can be undone: any query that should be Zepto-only can simply filter on `app = "zepto"`.

---

## [D-04] Relevance Filtering Before Embedding (Focused Corpus Strategy)

**Status:** Decided
**Impact:** High — determines what goes into the vector index and thus what can be retrieved.

### The Decision
Before embedding, all records are filtered to retain only those that are topically relevant to category exploration and discovery behavior. Records about delivery speed, app crashes, customer support, and pricing (when not linked to exploration barriers) are discarded from the corpus.

The alternative was an **unfocused corpus strategy**: embed everything and rely on semantic search at retrieval time to surface only relevant chunks.

### Why Focused Corpus Was Chosen
**The unfocused strategy fails in practice** because it pollutes the vector space. If 80% of the corpus is about delivery speed and 5% is about category exploration, a semantic query about exploration behavior retrieves a mix of highly relevant chunks and marginally relevant chunks that happen to share vocabulary. The signal-to-noise ratio degrades as the corpus grows.

**The focused strategy guarantees** that every chunk in the index is relevant to the research domain. This means: higher retrieval precision, better clustering quality (themes are about exploration, not delivery), and less hallucination risk (the LLM is given focused, relevant context, not a soup of tangentially related reviews).

### Trade-off Accepted
Relevant reviews that mention exploration *indirectly* (e.g., "I only use Zepto for milk and eggs, the delivery is fast") may be filtered out if they don't contain the relevance keywords. This is mitigated by using semantic similarity scoring (not just keyword matching) as a secondary filter pass for borderline cases.

---

## [D-05] RAG Queries Are Rewritten into User Voice (Not PM Voice)

**Status:** Decided
**Impact:** High — directly determines retrieval quality and therefore insight quality.

### The Decision
When querying the vector database, the system does not use the research question as the search query. Instead, the query is rewritten into the voice of a user who is *experiencing* whatever the research question is asking about.

**Example:**
- Research question: *"What prevents users from exploring new categories?"*
- Semantic query used: *"I always buy the same products every week and never try anything new"*

### Why This Is Necessary
The vector database contains user language. The research questions are written in product manager / analyst language. These two vocabularies are semantically distant even when they are conceptually identical.

A search for "barriers to category exploration" retrieves reviews that literally contain those words — which are almost none. A search for "I just buy the same things every time" retrieves reviews from users describing exactly the behavioral pattern the research question is investigating — which are many.

This is a **fundamental property of dense retrieval**: the query and the documents that should match it must be in the same semantic space. When the domain gap between the query author's language and the document author's language is large (PM vs. consumer), explicit query rewriting is necessary.

### Who Makes This Decision
Query rewriting is done manually by the analyst for each of the 8 research questions. It is the highest-leverage human judgment call in the entire pipeline — poor query formulation directly causes poor insights regardless of how good the rest of the system is.

---

## [D-06] Insight Output Schema Enforced at the LLM Prompt Level

**Status:** Decided
**Impact:** Medium — affects output consistency and downstream usability.

### The Decision
Every LLM call in the insight generation step is required to produce output in a fixed JSON schema: `{ finding, evidence (array of verbatim quotes), implication, segment }`. The prompt instructs the model to conform to this schema, and the output is validated before being accepted.

The alternative was to ask the LLM to produce free-form text and then parse it afterward.

### Why Structured Output Was Chosen
Free-form text cannot be reliably parsed. Different LLM calls produce different structures, making downstream automation fragile. More importantly, the structured schema is a **quality enforcement mechanism**: requiring `evidence` to be an array of verbatim quotes forces the model to cite specific retrieved text rather than paraphrasing or generalizing. This is a direct hallucination prevention measure — it is not possible to produce a schema-valid insight without at least two real quotes from the context.

The schema also makes the output immediately usable in the report template without further transformation.

---

## [D-07] Separation of Raw Store (SQLite) from Vector Index

**Status:** Decided
**Impact:** Medium — affects data architecture and provenance capability.

### The Decision
Raw ingested records are stored in SQLite. The vector index (ChromaDB/Pinecone) stores only embeddings and metadata, not the full text. The two stores are linked by `chunk_id`. Full text is always retrieved from SQLite, never from the vector DB.

The alternative was to store full text inside the vector DB alongside the embedding.

### Why They Are Kept Separate
1. **The raw store is append-only and immutable.** The vector index is rebuilt. If the corpus needs to be re-processed with a different filter or re-indexed with a better embedding model, the SQLite store is always the source of truth and is never regenerated.
2. **Different access patterns.** The vector DB is optimized for approximate nearest-neighbor search. SQLite is optimized for exact-match lookups by ID. Using each for what it is good at avoids compromising either.
3. **Provenance.** An insight's `evidence` quotes are traced back to SQLite records, not vector DB payloads. The SQLite record contains the full original text, source URL, date, rating, and metadata — everything needed to verify the claim.

---

## Open Decisions

| ID | Question | Why It Matters | Target Phase |
|---|---|---|---|
| D-08 | Should Hinglish reviews be included? If so, do we translate before embedding, or use a multilingual embedding model? | Significant portion of Indian quick-commerce discourse is Hinglish. Excluding it may create a blind spot toward a large user segment. But translating introduces its own quality risk. | Phase 2 |
| D-09 | Should the report include a "low-confidence" section for insights that failed faithfulness ≥ 0.7, or should they be omitted entirely? | Including them treats them as hypotheses to investigate further. Omitting them avoids presenting weak evidence to stakeholders. | Phase 7 |
| D-10 | At what corpus size does ChromaDB need to be replaced with Pinecone? | If the project scales to more sources or longer time ranges, the vector DB choice becomes a production concern. | Post-v1 |


---

## Decision Template

```
### [ID] Decision Title
**Date:** YYYY-MM-DD
**Status:** Decided / Under Review / Superseded
**Decided by:** [Role or name]

**Context:** Why did this decision need to be made?
**Options Considered:** What alternatives were evaluated?
**Decision:** What was chosen?
**Rationale:** Why was this chosen over the alternatives?
**Trade-offs:** What are the known downsides or risks?
**Follow-up:** Any open questions or future revisits?
```

---

## Technical Decisions

---

### [T-01] Vector Database: ChromaDB (dev) → Pinecone (prod)
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The RAG pipeline requires a vector database to store embeddings and support fast semantic search with metadata filtering. The choice affects cost, setup complexity, scalability, and retrieval latency.

**Options Considered:**
| Option | Pros | Cons |
|---|---|---|
| **ChromaDB** | Open-source, local, zero cost, easy setup | Not suitable for large-scale production |
| **Pinecone** | Managed, scalable, fast, metadata filtering | Paid, requires API key |
| **Qdrant** | Open-source, can be self-hosted or cloud | More ops overhead than Pinecone |
| **Weaviate** | Feature-rich, has built-in modules | Heavier setup, steeper learning curve |

**Decision:** Use **ChromaDB** for local development and prototyping. Migrate to **Pinecone** if the corpus exceeds 50,000 vectors or if the system moves to production.

**Rationale:** ChromaDB allows zero-friction local development and demo. Pinecone provides a natural upgrade path with minimal code changes (same interface abstraction via LangChain).

**Trade-offs:** Pinecone has per-query costs. ChromaDB is not horizontally scalable.

---

### [T-02] Embedding Model: OpenAI text-embedding-3-small
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The embedding model determines the quality of semantic search and the cost of indexing the entire corpus.

**Options Considered:**
| Option | Pros | Cons |
|---|---|---|
| `text-embedding-3-small` | Cheap ($0.02/1M tokens), fast, good quality | Requires OpenAI API key |
| `text-embedding-3-large` | Best quality | 5× more expensive |
| `bge-small-en` (local) | Free, no API dependency | Requires GPU or slower CPU inference |
| `sentence-transformers/all-MiniLM-L6-v2` | Very fast, local | Lower quality for nuanced semantic search |

**Decision:** Use **`text-embedding-3-small`** as the default. Document `bge-small-en` as a local fallback.

**Rationale:** For a corpus of ~1,000–5,000 chunks, `text-embedding-3-small` costs < $0.10 total, which is negligible. Quality is significantly better than local MiniLM models for this use case.

**Trade-offs:** API dependency and cost at scale. Mitigated by the local fallback option.

---

### [T-03] Clustering: UMAP + HDBSCAN over K-Means
**Date:** 2026-07-27
**Status:** Decided

**Context:**
Theme identification requires grouping semantically similar reviews. The choice of clustering algorithm affects the quality and interpretability of themes.

**Options Considered:**
| Option | Pros | Cons |
|---|---|---|
| **K-Means** | Simple, deterministic | Requires pre-specifying K; poor with irregular cluster shapes |
| **HDBSCAN** | No K required, handles noise, density-based | Slower, sensitive to hyperparameters |
| **BERTopic** | End-to-end library, good defaults | Less control, harder to customize |
| **LLM-only classification** | No clustering needed | Expensive, not scalable to 5,000+ reviews |

**Decision:** Use **UMAP** (dimensionality reduction) + **HDBSCAN** (density-based clustering), with LLM labeling applied to cluster representatives.

**Rationale:** User reviews form irregular, overlapping clusters. HDBSCAN handles this naturally and does not require pre-specifying the number of clusters. UMAP preserves local semantic structure better than PCA for high-dimensional embeddings.

**Trade-offs:** HDBSCAN is sensitive to `min_cluster_size`. Requires tuning per corpus size.

---

### [T-04] LLM Provider: Configurable (GPT-4o default)
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The LLM is used for theme labeling, insight generation, and validation. The choice affects cost, quality, and vendor lock-in.

**Options Considered:**
- OpenAI GPT-4o
- Anthropic Claude 3.5 Sonnet
- Google Gemini 1.5 Pro
- Local open-source (Llama 3, Mistral)

**Decision:** Default to **GPT-4o** with the LLM call abstracted behind a LangChain interface, allowing easy swapping to Claude or Gemini.

**Rationale:** GPT-4o has the best balance of instruction-following, JSON output reliability, and cost for this use case. Abstraction prevents vendor lock-in.

**Trade-offs:** API cost for large batches. Mitigated by caching LLM outputs and only calling on unique content.

---

### [T-05] Evaluation Framework: RAGAS
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The pipeline needs a principled way to evaluate RAG quality — specifically, whether generated insights are faithful to retrieved context.

**Options Considered:**
- Manual review only
- RAGAS (open-source RAG evaluation framework)
- TruLens
- Custom LLM-as-judge prompts

**Decision:** Use **RAGAS** for automated faithfulness and context recall scoring, supplemented by **manual spot-checks** for 5 randomly selected insights.

**Rationale:** RAGAS is purpose-built for RAG evaluation and provides standard metrics (faithfulness, answer relevancy, context recall) that are interpretable and comparable across runs.

**Trade-offs:** RAGAS itself calls an LLM for scoring, adding API cost. Acceptable for a small evaluation set.

---

## Business Decisions

---

### [B-01] Scope: Competitor Reviews Included
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The problem is about Zepto users' shopping behavior. The question arose whether to restrict data collection to Zepto reviews only, or to also include competitor reviews (Blinkit, Swiggy Instamart, BigBasket).

**Decision:** Include **competitor app reviews** in the corpus.

**Rationale:** Users who discuss category exploration on Blinkit or Swiggy Instamart face the same behavioral patterns. Including competitor data broadens the signal set and surfaces unmet needs that Zepto can act on before competitors do. Competitor reviews are clearly tagged in metadata so they can be filtered out if needed.

**Trade-offs:** Risk of surfacing insights that are specific to a competitor's UX, not Zepto's. Mitigated by metadata tagging and the ability to run source-filtered queries.

---

### [B-02] Focus: Category Exploration, Not General Sentiment
**Date:** 2026-07-27
**Status:** Decided

**Context:**
User reviews cover a wide range of topics: delivery speed, pricing, app crashes, product quality, customer service. Without a focus, the insight engine would surface generic app feedback, not growth-relevant signals.

**Decision:** Apply a **relevance filter** at the preprocessing stage to retain only reviews and discussions that are topically related to: product discovery, category exploration, shopping habits, recommendations, and new product trials.

**Rationale:** The strategic goal is category cross-sell, not general NPS improvement. Focused data produces focused insights. Generic sentiment analysis is already handled by other tooling.

**Trade-offs:** Risk of discarding relevant reviews that mention exploration tangentially. Mitigated by using semantic relevance scoring (not just keyword matching) and keeping the filter threshold conservative (≥ 30% retention rate).

---

### [B-03] Output Format: Insight Cards (not a summary document)
**Date:** 2026-07-27
**Status:** Decided

**Context:**
The final output needs to be usable by a Product Manager, a Growth Analyst, and potentially an engineering team. The format should be scannable and actionable, not a wall of text.

**Decision:** Structure each insight as an **Insight Card** with four required fields: Finding, Evidence (verbatim quotes), Implication (so what?), and Segment (who is affected).

**Rationale:** This format mirrors how PMs already work — "What did we learn?", "What's the proof?", "What should we do?", "Who does this affect?" It also makes it easy to slot insights directly into PRDs or strategy decks.

**Trade-offs:** Structured output requires stricter LLM prompting and output parsing. Handled by a JSON schema in the prompt and `pydantic` validation on the output.

---

## Open / Pending Decisions

| ID | Question | Owner | Target Date |
|---|---|---|---|
| T-06 | Should Hinglish reviews be included? If so, which translation/embedding approach? | ML Lead | Phase 2 |
| T-07 | Should we build a UI/dashboard for the insight report, or keep it as Markdown? | PM | Phase 7 |
| B-04 | Should in-app product review data be requested from the data team, or is this out of scope for v1? | PM + Data | Phase 0 |

---

## [D-08] Zero-Cost Technology Stack

**Status:** Decided
**Impact:** Affects every component that touches an external API. Resolves technology selection for LLM, embedding model, and vector DB.

### The Decision
The entire pipeline must run at zero financial cost — no paid APIs, no cloud services with billing. This is a hard constraint, not a preference.

**Substitutions made:**

| Component | Rejected (paid) | Chosen (free) | Trade-off |
|---|---|---|---|
| LLM | GPT-4o (OpenAI) | Gemini 1.5 Flash (Google AI Studio free tier) | Slightly lower instruction-following precision than GPT-4o, but free tier is 15 RPM and 1M tokens/day — sufficient for this corpus size. JSON output mode is supported. |
| Embedding | `text-embedding-3-small` (OpenAI API) | `all-MiniLM-L6-v2` (sentence-transformers, local) | 384-dim vs. 1536-dim vectors — lower dimensional but entirely sufficient for semantic search at this scale. Runs locally with no API call, no latency, no cost. |
| Vector DB (prod) | Pinecone (paid managed service) | ChromaDB (local, open-source) | No managed scaling, but the project is a single-run pipeline, not a production service. ChromaDB persists to disk and handles the expected corpus size (< 10K chunks) comfortably. |
| Twitter/X Ingestion | Twitter API v2 (not free for this use case) | Disabled | Play Store, App Store, and community forums provide sufficient signal for category exploration research. Twitter's short-form content has low signal density for this domain anyway. |

### Why Gemini over other free LLMs
- **Groq** (free tier with Llama 3): Generous rate limits but the free API may not be available in all regions.
- **Ollama** (fully local): No API needed but requires GPU/RAM capable of running a 7B+ model — not safe to assume as a project constraint.
- **Gemini 1.5 Flash**: Free via Google AI Studio, available globally, has an official Python SDK and LangChain integration, supports structured JSON output natively. Best fit.

### Rate Limit Management
Gemini 1.5 Flash free tier allows 15 requests per minute. The pipeline makes LLM calls in three places:
1. **Phase 4 (Theme Labeling):** 10–20 clusters × 1 LLM call each = 10–20 calls total.
2. **Phase 5 (RAG Insight Generation):** 8 research questions × 1 LLM call each = 8 calls total.
3. **Phase 6 (Contradiction Check):** Up to 28 pairwise comparisons (8 choose 2) = 28 calls total.

Total: ~50–60 LLM calls across the entire pipeline. At 15 RPM, this completes in 4–5 minutes with no throttling.
