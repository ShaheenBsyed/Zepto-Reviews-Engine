# Problem Statement: Zepto AI Review Engine

## Role & Context

You are a **Product Manager on the Growth Team at Zepto** — one of India's fastest-growing quick-commerce platforms. Zepto operates on a 10-minute delivery model and serves millions of urban customers across major Indian metros, offering a catalog spanning groceries, snacks & beverages, household essentials, personal care, baby products, pet supplies, and more.

Quick commerce has successfully embedded itself into users' weekly routines. The platform sees strong repeat purchase behavior, particularly in core categories like fresh produce, dairy, and everyday staples.

---

## The Business Problem

Over time, **shopping behavior on the platform has become highly repetitive**. The majority of Monthly Active Customers (MACs) return repeatedly to purchase the same narrow set of products and rarely venture beyond the 1–2 categories they originally joined for.

This behavior creates a compounding problem:

- **Revenue ceiling per user** — customers with narrow category exposure have lower basket sizes and lifetime value.
- **Churn risk** — users locked into a single category are more likely to switch platforms the moment a competitor offers a better price or availability for that one category.
- **Catalog underutilization** — large portions of Zepto's growing catalog (e.g., pet supplies, beauty, baby products) remain invisible to users who would likely buy them if surfaced at the right moment.

### Strategic Goal

> **Increase the percentage of Monthly Active Customers who purchase products from at least one new category every month.**

**Target examples:**
| Current Behavior | Desired New Behavior |
|---|---|
| User buys only groceries | Starts buying pet supplies |
| User buys only snacks | Starts buying personal care products |
| User buys only household essentials | Starts buying baby products |
| User buys only dairy & produce | Starts buying ready-to-eat / meal kits |

---

## The Challenge: Lack of Qualitative Signal

The growth team has **quantitative data** on what users buy, but lacks **qualitative understanding** of *why* they do not explore new categories. Standard analytics dashboards cannot explain:

- What psychological or habitual barriers prevent exploration.
- What information gaps or trust deficits exist for new categories.
- Which user segments are already open to experimentation vs. deeply entrenched.
- What frustrations (delivery reliability, pricing, product quality) suppress willingness to try.

To design any effective intervention — whether a feature, nudge, or campaign — the team first needs to understand the **user's voice at scale**.

---

## The Task: Build an AI-Powered Review & Insights Engine

Before proposing any product or growth solution, you must **build an AI-powered system that analyzes unstructured user feedback at scale** to surface actionable insights.

### Data Sources

The engine should be capable of ingesting and analyzing feedback from the following sources:

| Source | Examples |
|---|---|
| **App Store Reviews** | Google Play Store, Apple App Store reviews for Zepto and competitors (Blinkit, Swiggy Instamart, BigBasket) |
| **Community Forum Discussions** | LocalCircles, MouthShut, consumer complaint boards, and other public discussion threads |
| **Community Forums** | LocalCircles, MouthShut, consumer complaint boards |
| **Social Media** | Twitter/X threads, Instagram comments on Zepto's official posts |
| **Product Reviews** | In-app product-level ratings and text reviews |
| **Quick Commerce Discourse** | News article comment sections, YouTube video comments on delivery app comparisons |

### Key Research Questions

The discovery engine must be able to help answer the following:

1. **Habit & Repetition** — Why do users repeatedly buy from the same categories? Is it convenience, trust, or lack of awareness?
2. **Exploration Barriers** — What prevents users from trying new categories? (e.g., price anxiety, unfamiliarity, no trigger)
3. **Discovery Pathways** — How do users currently discover products or categories they were not already buying?
4. **Role of Habit** — How strongly do established routines suppress willingness to experiment?
5. **Information Needs** — What information do users need before they feel confident trying a new category for the first time?
6. **Recurring Frustrations** — What pain points surface consistently across reviews and discussions? How do these suppress exploration?
7. **Experimental Segments** — Which user personas or life-stage segments (e.g., new parents, pet owners, health-conscious users) are more likely to try new categories?
8. **Unmet Needs** — What needs do users consistently express that the platform is not currently addressing?

---

## Deliverables & Demonstration Requirements

Your submission must demonstrate the full pipeline. Specifically, you must show:

### 1. Data Gathering Workflow
- How the system collects reviews and discussions from multiple sources.
- What filtering, deduplication, or relevance scoring is applied before analysis.
- How data is stored and prepared for processing.

### 2. Theme Identification
- How the AI identifies recurring topics, patterns, and clusters from raw text.
- The methodology used (e.g., embedding-based clustering, LLM classification, topic modeling).
- How themes are labeled and organized into a coherent taxonomy.

### 3. Insight Generation
- How raw themes are elevated into actionable product or growth insights.
- How the system connects user language to business-relevant framing.
- What the format and structure of output insights looks like.
- **RAG (Retrieval-Augmented Generation):** Retrieved reviews are indexed in a vector database. During insight generation, relevant user feedback is retrieved using semantic search to ground LLM outputs and reduce hallucinations.

### 4. Insight Quality Validation
- How you verified that generated insights are accurate and grounded in the data.
- What human-in-the-loop or automated checks are applied.
- How you handle noise, outliers, or contradictory signals.

---

## Success Criteria

A successful AI Review Engine will:

- Surface at least **5–8 distinct, non-overlapping insight themes** with supporting evidence.
- Identify **at least 2 user segments** that differ meaningfully in their exploration behavior.
- Pinpoint **specific barriers to category exploration** that are actionable by the product or growth team.
- Provide **verbatim examples** from source data to ground every insight.
- Operate with **minimal manual effort** — the pipeline should be largely automated and repeatable.