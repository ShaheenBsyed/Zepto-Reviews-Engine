from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from google.genai import types as genai_types

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RPM = 15
MAX_TOKENS_PER_DAY = 1_000_000
COOLDOWN_SECONDS = 60.0 / MAX_RPM

PRODUCT_CATEGORIES = [
    "Fresh Fruits & Vegetables",
    "Dairy, Bread & Eggs",
    "Packaged Groceries",
    "Snacks & Beverages",
    "Household Essentials",
    "Personal Care",
    "Baby Products",
    "Pet Supplies",
    "Gourmet / Organic / Health Foods",
    "General / Multiple Categories",
]

BARRIERS = [
    "Freshness Concerns",
    "Quality Concerns",
    "High Prices",
    "Delivery Delays",
    "Limited Availability",
    "Out of Stock",
    "Trust Issues",
    "Prefer Offline Shopping",
    "Refund Concerns",
    "Poor Customer Support",
    "App Usability Issues",
    "Lack of Awareness",
    "Low Purchase Frequency",
    "Limited Assortment",
]

PLACEHOLDER_PATTERNS = [
    "unlabeled theme",
    "cluster ",
    "no samples available",
]

SYSTEM_PROMPT = (
    "You are a product research analyst analyzing customer reviews for an online grocery platform. "
    "You are given a set of user review chunks that belong to the same thematic cluster. "
    "Your job is to identify the product category being discussed, the customer barrier preventing purchase, "
    "and synthesize a short description.\n\n"
    "Rules:\n"
    "- Identify the primary product category from the list provided.\n"
    "- Identify the primary customer barrier from the list provided.\n"
    "- Write a short description summarizing what unifies these reviews.\n"
    "- Extract 5-8 keywords that capture the main topics.\n"
    "- The 3 verbatim quotes MUST come directly from the provided text. Do NOT paraphrase or invent quotes.\n"
    "- Do NOT include any quotes that are not present verbatim in the provided text.\n"
    "- Do NOT invent themes or behaviors not supported by the data.\n"
    "- Never use placeholder names like 'Unlabeled Theme', 'Cluster X', or similar."
)

CATEGORY_KEYWORDS = {
    "Fresh Fruits & Vegetables": [
        "fruit", "vegetable", "fresh", "produce", "organic", "greens", "salad",
        "tomato", "potato", "onion", "carrot", "spinach", "broccoli", "cauliflower",
        "mango", "banana", "apple", "orange", "grapes", "pomegranate", "guava",
        "lettuce", "cucumber", "bell pepper", "chilli", "herb", "leafy",
    ],
    "Dairy, Bread & Eggs": [
        "milk", "bread", "egg", "butter", "cheese", "yogurt", "cream", "paneer",
        "curd", "buttermilk", "biscuit", "cake", "cookie", "dough", "bakery",
        "breakfast", "omlette", "boiled egg", "cheese", "ghee",
    ],
    "Packaged Groceries": [
        "rice", "dal", "pulse", "lentil", "flour", "wheat", "oil", "spice",
        "salt", "sugar", "jaggery", "atta", "maida", "packaged", "tin", "can",
        "sachet", "instant", "noodles", "pasta", "cereal", "oats",
    ],
    "Snacks & Beverages": [
        "snack", "chips", "cookie", "biscuit", "chocolate", "candy", "soda",
        "juice", "tea", "coffee", "beverage", "drink", "cold drink", "fizzy",
        "popcorn", "namkeen", "munch", "lollipop", "gum", "candy", "ice cream",
    ],
    "Household Essentials": [
        "cleaning", "detergent", "soap", "shampoo", "toothpaste", "broom",
        "dustbin", "napkin", "tissue", "razor", "battery", "bulb", "match",
        "household", "utility", "supply", "grocery", "stationery",
    ],
    "Personal Care": [
        "shampoo", "soap", "lotion", "cream", "perfume", "deodorant", "razor",
        "hair", "skin", "face", "body", "tooth", "brush", "personal care",
        "beauty", "makeup", "cosmetic", "nail", "hair oil",
    ],
    "Baby Products": [
        "baby", "infant", "toddler", "child", "kid", "diaper", "powder", "cream",
        "baby food", "milk powder", "baby oil", "baby soap", "baby lotion",
        "feeding", "bottle", "toy", "crib", "stroller",
    ],
    "Pet Supplies": [
        "pet", "dog", "cat", "animal", "food", "treat", "toy", "leash",
        "collar", "groom", "pet care", "puppy", "kitten", "bird", "fish",
    ],
    "Gourmet / Organic / Health Foods": [
        "organic", "healthy", "gourmet", "superfood", "supplement", "vitamin",
        "protein", "granola", "quinoa", "chia", "flax", "almond", "walnut",
        "dry fruit", "nut", "seed", "gluten", "sugar-free", "low-fat",
    ],
}

BARRIER_KEYWORDS = {
    "Freshness Concerns": [
        "stale", "old", "not fresh", "rotten", "spoiled", "mold", "wilted",
        "bad smell", "smells", "off", "expired", "expiry", "shelf life",
        "freshness", "not fresh", "tastes bad", "sour", "fermented",
    ],
    "Quality Concerns": [
        "quality", "bad", "poor", "worst", "terrible", "disappointed",
        "defective", "damaged", "broken", "wrong", "inferior", "substandard",
        "not good", "disgusting", "awful", "horrible", "unusable",
    ],
    "High Prices": [
        "expensive", "price", "cost", "overpriced", "high price", "hike",
        "increase", "hiked", "pricey", "costly", "afford", "budget", "rate",
        "charges", "fee", "surge", "hidden charges",
    ],
    "Delivery Delays": [
        "delay", "late", "delayed", "waiting", "long time", "hours", "late delivery",
        "not delivered", "undelivered", "promised", "expected", "schedule",
        "delayed", "arrived late", "no update", "tracking",
    ],
    "Limited Availability": [
        "not available", "out of stock", "unavailable", "sold out", "no stock",
        "limited", "rare", "hard to find", "cannot find", "discontinued",
        "not in stock", "empty", "缺货",
    ],
    "Out of Stock": [
        "out of stock", "sold out", "no stock", "unavailable", "not available",
        "empty", "discontinued", "not in stock", "zero stock",
    ],
    "Trust Issues": [
        "trust", "fake", "fraud", "scam", "counterfeit", "not genuine",
        "doubt", "suspicious", "unreliable", "misleading", "false",
        "not original", "duplicate", "refund not", "no refund",
    ],
    "Prefer Offline Shopping": [
        "offline", "store", "physical", "market", "shop", "retail",
        "prefer", "like to buy", "better offline", "in person", "tangible",
        "inspect", "see before", "try before", "walk-in", "local shop",
    ],
    "Refund Concerns": [
        "refund", "return", "exchange", "money back", "reimburse", "cancellation",
        "no refund", "refund not", "return policy", "hard to return",
        "waste of money", "not refunded", "returned",
    ],
    "Poor Customer Support": [
        "support", "customer care", "complaint", "helpline", "chat",
        "unresponsive", "rude", "useless", "no help", "ignored",
        "no response", "frustrating", "complaint", "escalate",
    ],
    "App Usability Issues": [
        "app", "interface", "usability", "bug", "crash", "glitch",
        "slow", "freeze", "hang", "navigation", "search", "filter",
        "confusing", "difficult", "not working", "error", "buggy",
    ],
    "Lack of Awareness": [
        "didn't know", "unaware", "new", "first time", "discovered",
        "heard about", "recommend", "awareness", "promotion", "offer",
        "deal", "discount", "coupon", "newsletter",
    ],
    "Low Purchase Frequency": [
        "rarely", "occasionally", "once", "seldom", "infrequent",
        "first time", "second time", "not repeat", "won't order",
        "one time", "only once", "not again", "never again",
    ],
    "Limited Assortment": [
        "limited", "assortment", "variety", "range", "selection",
        "few options", "not enough", "missing", "no variety",
        "same old", "boring", "nothing new", "limited stock",
    ],
}


class ThemeLabeler:
    """
    Generates product category-specific insights from clustered review chunks.

    Each cluster's representative samples are analyzed to produce:
      - Product Category (e.g., Fresh Fruits & Vegetables)
      - Customer Barrier (e.g., Freshness Concerns)
      - A short description of the theme
      - 5-8 keywords
      - 3 verbatim quotes
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        max_rpm: int = MAX_RPM,
    ):
        self.model = model
        self.max_rpm = max_rpm
        self._last_call_time: float = 0.0
        self._call_count: int = 0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between LLM calls."""
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < COOLDOWN_SECONDS:
            sleep_time = COOLDOWN_SECONDS - elapsed
            logger.debug("Rate limiting: sleeping %.1f seconds", sleep_time)
            time.sleep(sleep_time)
        self._last_call_time = time.time()

    def _build_prompt(self, samples: List[Dict[str, Any]]) -> str:
        """Build the LLM prompt from cluster representative samples."""
        sample_texts = "\n".join(
            f"- [{i}] \"{s.get('text', '')}\" (source: {s.get('source', 'unknown')}, app: {s.get('app', 'unknown')})"
            for i, s in enumerate(samples, 1)
        )
        category_list = "\n".join(f"  - {c}" for c in PRODUCT_CATEGORIES)
        barrier_list = "\n".join(f"  - {b}" for b in BARRIERS)
        return (
            f"Here are {len(samples)} user review excerpts from this cluster:\n\n"
            f"{sample_texts}\n\n"
            f"Available Product Categories:\n{category_list}\n\n"
            f"Available Customer Barriers:\n{barrier_list}\n\n"
            f"Based on these excerpts, provide:\n"
            f"1. The primary product category (choose exactly one from the list above)\n"
            f"2. The primary customer barrier (choose exactly one from the list above)\n"
            f"3. A short description (2-3 sentences) summarizing what unifies these reviews\n"
            f"4. Five to eight keywords that capture the main topics (comma-separated)\n"
            f"5. Three verbatim quotes from the excerpts above that best illustrate the theme"
        )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into structured theme output.

        Extracts category, barrier, description, keywords, and quotes.
        Falls back to section-based parsing if JSON is not used.
        """
        response = response.strip()

        try:
            if response.startswith("```json"):
                response = response.split("```json", 1)[1]
            if response.startswith("```"):
                response = response.split("```", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]
            data = json.loads(response)
            return {
                "category": data.get("category", ""),
                "barrier": data.get("barrier", ""),
                "description": data.get("description", ""),
                "keywords": data.get("keywords", []),
                "quotes": data.get("quotes", []),
            }
        except (json.JSONDecodeError, ValueError):
            pass

        lines = response.split("\n")
        category = ""
        barrier = ""
        description = ""
        keywords: List[str] = []
        quotes: List[str] = []
        current_section = "category"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(("1.", "1 ", "Category:", "Product Category:")):
                current_section = "category"
                cat = line.lstrip("1.").strip().lstrip(" ").strip()
                if cat.startswith(":"):
                    cat = cat[1:].strip()
                category = cat
            elif line.startswith(("2.", "2 ", "Barrier:", "Customer Barrier:")):
                current_section = "barrier"
                bar = line.lstrip("2.").strip().lstrip(" ").strip()
                if bar.startswith(":"):
                    bar = bar[1:].strip()
                barrier = bar
            elif line.startswith(("3.", "3 ", "Description:")):
                current_section = "description"
                desc = line.lstrip("3.").strip().lstrip(" ").strip()
                if desc.startswith(":"):
                    desc = desc[1:].strip()
                description = desc
            elif line.startswith(("4.", "4 ", "Keywords:", "Keyword:")):
                current_section = "keywords"
                kw_text = line.lstrip("4.").strip().lstrip(" ").strip()
                if kw_text.startswith(":"):
                    kw_text = kw_text[1:].strip()
                keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
            elif line.startswith(("5.", "5 ", "Quotes:", "Quote:")):
                current_section = "quotes"
            elif current_section == "category" and not category:
                category = line
            elif current_section == "barrier" and not barrier:
                barrier = line
            elif current_section == "description" and not description:
                description = line
            elif current_section == "keywords" and not keywords:
                kw_text = line.lstrip("- ").strip()
                if kw_text:
                    keywords = [k.strip() for k in kw_text.split(",") if k.strip()]
            elif current_section == "quotes":
                clean = line.lstrip("- ").strip()
                if clean.startswith('"') or clean.startswith("'"):
                    quotes.append(clean.strip("\"'"))
                elif clean and len(clean) > 10:
                    quotes.append(clean)

        if not quotes and current_section == "quotes":
            for line in lines:
                clean = line.strip().strip("-").strip()
                if clean and len(clean) > 10 and clean not in quotes:
                    quotes.append(clean)

        return {
            "category": category,
            "barrier": barrier,
            "description": description,
            "keywords": keywords[:8],
            "quotes": quotes[:3],
        }

    def _normalize_category(self, category: str) -> str:
        """Match a raw category string to the closest known product category."""
        if not category:
            return "General / Multiple Categories"
        cat_lower = category.lower().strip()
        for known_cat in PRODUCT_CATEGORIES:
            if cat_lower == known_cat.lower():
                return known_cat
        for known_cat in PRODUCT_CATEGORIES:
            for kw in CATEGORY_KEYWORDS.get(known_cat, []):
                if kw in cat_lower:
                    return known_cat
        return "General / Multiple Categories"

    def _normalize_barrier(self, barrier: str) -> str:
        """Match a raw barrier string to the closest known customer barrier."""
        if not barrier:
            return "Trust Issues"
        bar_lower = barrier.lower().strip()
        for known_barrier in BARRIERS:
            if bar_lower == known_barrier.lower():
                return known_barrier
        for known_barrier in BARRIERS:
            for kw in BARRIER_KEYWORDS.get(known_barrier, []):
                if kw in bar_lower:
                    return known_barrier
        return "Trust Issues"

    def _detect_category_fallback(self, samples: List[Dict[str, Any]]) -> str:
        """Detect product category from sample text using keyword matching.

        Only returns a specific category if the reviews explicitly mention
        product-category-specific terms. Otherwise returns General.
        """
        text = " ".join(s.get("text", "") for s in samples).lower()

        # Check for explicit category mentions
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    # Verify the keyword appears in a product-category context
                    # not just as a generic grocery term
                    if cat == "Pet Supplies" and any(p in text for p in ["pet", "dog", "cat", "animal", "puppy", "kitten"]):
                        return cat
                    if cat == "Baby Products" and any(p in text for p in ["baby", "infant", "toddler", "child", "kid", "diaper", "powder"]):
                        return cat
                    if cat == "Gourmet / Organic / Health Foods" and any(p in text for p in ["organic", "healthy", "gourmet", "superfood", "supplement", "protein", "quinoa", "chia"]):
                        return cat
                    if cat == "Household Essentials" and any(p in text for p in ["cleaning", "detergent", "soap", "shampoo", "toothpaste", "broom", "dustbin", "napkin", "tissue"]):
                        return cat
                    if cat == "Personal Care" and any(p in text for p in ["shampoo", "soap", "lotion", "cream", "perfume", "deodorant", "razor", "hair", "skin", "face", "tooth", "brush"]):
                        return cat
                    if cat == "Snacks & Beverages" and any(p in text for p in ["snack", "chips", "cookie", "biscuit", "chocolate", "candy", "soda", "juice", "tea", "coffee", "beverage", "drink", "cold drink", "fizzy", "popcorn", "namkeen", "munch", "lollipop", "gum", "ice cream"]):
                        return cat
                    if cat == "Dairy, Bread & Eggs" and any(p in text for p in ["milk", "bread", "egg", "butter", "cheese", "yogurt", "cream", "paneer", "curd", "buttermilk", "biscuit", "cake", "cookie", "dough", "bakery", "breakfast", "omlette", "boiled egg", "ghee"]):
                        return cat
                    if cat == "Fresh Fruits & Vegetables" and any(p in text for p in ["fruit", "vegetable", "fresh", "produce", "organic", "greens", "salad", "tomato", "potato", "onion", "carrot", "spinach", "broccoli", "cauliflower", "mango", "banana", "apple", "orange", "grapes", "pomegranate", "guava", "lettuce", "cucumber", "bell pepper", "chilli", "herb", "leafy"]):
                        return cat
        return "General / Multiple Categories"

    def _detect_barrier_fallback(self, samples: List[Dict[str, Any]]) -> str:
        """Detect customer barrier from sample text using keyword matching."""
        text = " ".join(s.get("text", "") for s in samples).lower()
        scores: Dict[str, int] = {}
        for barrier, keywords in BARRIER_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[barrier] = score
        if scores:
            return max(scores, key=scores.get)
        return "Trust Issues"

    def _extract_keywords(self, samples: List[Dict[str, Any]], n: int = 8) -> List[str]:
        """Extract meaningful keywords from sample texts, excluding common stop words."""
        stop_words = {
            "this", "that", "with", "from", "have", "been", "were", "they",
            "them", "their", "what", "when", "where", "which", "who", "how",
            "will", "would", "could", "should", "there", "these", "those",
            "about", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "then", "once", "here",
            "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "only", "own", "same", "than", "too", "very",
            "just", "also", "now", "well", "much", "like", "make", "made",
            "get", "got", "use", "used", "using", "one", "two", "three",
            "even", "still", "back", "over", "can", "may", "did", "does",
        }
        text = " ".join(s.get("text", "") for s in samples)
        words = re.findall(r"\b\w{4,}\b", text.lower())
        filtered = [w for w in words if w not in stop_words]
        common = Counter(filtered).most_common(n)
        return [w for w, _ in common]

    def _generate_fallback_description(
        self, samples: List[Dict[str, Any]], category: str, barrier: str
    ) -> str:
        """Generate a meaningful fallback description from the sample texts."""
        text = " ".join(s.get("text", "") for s in samples)
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        key_sentences = sentences[:3]
        desc = (
            f"Customers discussing {category.lower()} mention concerns about "
            f"{barrier.lower()}. "
        )
        if key_sentences:
            desc += " ".join(key_sentences)
        return desc

    def label_cluster(
        self,
        samples: List[Dict[str, Any]],
        cluster_id: int,
    ) -> Dict[str, Any]:
        """
        Generate a product category and barrier label for a single cluster.

        Args:
            samples: List of representative chunk dicts for the cluster.
            cluster_id: The cluster ID.

        Returns:
            Dict with category, barrier, description, keywords, quotes, and cluster_id.
        """
        if not samples:
            return {
                "cluster_id": cluster_id,
                "category": "General / Multiple Categories",
                "barrier": "Trust Issues",
                "description": "This cluster has no representative samples for labeling.",
                "keywords": [],
                "quotes": [],
                "num_samples": 0,
                "representative_chunks": [],
            }

        self._rate_limit()

        if not settings.gemini_api_key:
            logger.warning("No GEMINI_API_KEY configured. Using fallback labeling.")
            return self._fallback_label(samples, cluster_id)

        prompt = self._build_prompt(samples)

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            logger.warning("google-genai not available. Using fallback labeling.")
            return self._fallback_label(samples, cluster_id)

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = response.text
        except Exception as exc:
            logger.warning("LLM label generation failed for cluster %d: %s", cluster_id, exc)
            return self._fallback_label(samples, cluster_id)

        parsed = self._parse_response(raw_text)

        category = self._normalize_category(parsed.get("category", ""))
        barrier = self._normalize_barrier(parsed.get("barrier", ""))

        if not category or category == "General / Multiple Categories":
            category = self._detect_category_fallback(samples)
        if not barrier or barrier == "Trust Issues":
            barrier = self._detect_barrier_fallback(samples)

        parsed["cluster_id"] = cluster_id
        parsed["category"] = category
        parsed["barrier"] = barrier
        parsed["num_samples"] = len(samples)
        parsed["representative_chunks"] = [
            s.get("chunk_id", "") for s in samples
        ]
        if not parsed.get("keywords"):
            parsed["keywords"] = self._extract_keywords(samples)

        return parsed

    def label_clusters(
        self,
        cluster_samples: Dict[int, List[Dict[str, Any]]],
        batch_size: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Label all clusters, batching multiple clusters per API request.

        Args:
            cluster_samples: Dict mapping cluster_id -> list of sample dicts.
            batch_size: Number of clusters to label per API request.

        Returns:
            List of theme dicts, one per cluster.
        """
        themes: List[Dict[str, Any]] = []
        sorted_ids = sorted(cluster_samples.keys())

        for batch_start in range(0, len(sorted_ids), batch_size):
            batch_ids = sorted_ids[batch_start : batch_start + batch_size]
            batch_samples = {cid: cluster_samples[cid] for cid in batch_ids}

            logger.info(
                "Labeling batch of %d clusters (ids %s)...",
                len(batch_ids),
                batch_ids,
            )

            if settings.gemini_api_key:
                batch_themes = self._label_clusters_batch(batch_samples)
            else:
                batch_themes = self._label_clusters_batch_fallback(batch_samples)

            themes.extend(batch_themes)

            for theme in batch_themes:
                logger.info(
                    "Cluster %d: Category=%s, Barrier=%s",
                    theme.get("cluster_id"),
                    theme.get("category", "unknown"),
                    theme.get("barrier", "unknown"),
                )

        return themes

    def _label_clusters_batch(
        self,
        batch_samples: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Label a batch of clusters using a single LLM request."""
        self._rate_limit()

        batch_prompt = self._build_batch_prompt(batch_samples)

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            return self._label_clusters_batch_fallback(batch_samples)

        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=batch_prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw_text = response.text
        except Exception as exc:
            logger.warning("Batch LLM labeling failed: %s", exc)
            return self._label_clusters_batch_fallback(batch_samples)

        return self._parse_batch_response(raw_text, batch_samples)

    def _label_clusters_batch_fallback(
        self,
        batch_samples: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Fallback labeling for a batch of clusters."""
        themes = []
        for cid in sorted(batch_samples.keys()):
            samples = batch_samples[cid]
            theme = self._fallback_label(samples, cid)
            themes.append(theme)
        return themes

    def _build_batch_prompt(
        self,
        batch_samples: Dict[int, List[Dict[str, Any]]],
    ) -> str:
        """Build a single prompt for labeling a batch of clusters."""
        cluster_texts = []
        for cid in sorted(batch_samples.keys()):
            samples = batch_samples[cid]
            sample_texts = "\n".join(
                f"- [{i}] \"{s.get('text', '')}\" (source: {s.get('source', 'unknown')}, app: {s.get('app', 'unknown')})"
                for i, s in enumerate(samples, 1)
            )
            cluster_texts.append(
                f"=== Cluster {cid} ({len(samples)} samples) ===\n{sample_texts}"
            )

        combined = "\n\n".join(cluster_texts)
        category_list = "\n".join(f"  - {c}" for c in PRODUCT_CATEGORIES)
        barrier_list = "\n".join(f"  - {b}" for b in BARRIERS)

        return (
            f"You are a product research analyst analyzing customer reviews for an online grocery platform.\n\n"
            f"You are given {len(batch_samples)} thematic clusters of user review chunks. "
            f"For EACH cluster, provide a JSON object with the following fields:\n"
            f"  - cluster_id: the cluster number\n"
            f"  - category: the primary product category (choose exactly one from the list below)\n"
            f"  - barrier: the primary customer barrier (choose exactly one from the list below)\n"
            f"  - description: a short summary (2-3 sentences)\n"
            f"  - keywords: 5-8 comma-separated keywords\n"
            f"  - quotes: 3 verbatim quotes from the provided text\n\n"
            f"Available Product Categories:\n{category_list}\n\n"
            f"Available Customer Barriers:\n{barrier_list}\n\n"
            f"Rules:\n"
            f"- The 3 quotes MUST come directly from the provided text. Do NOT paraphrase or invent quotes.\n"
            f"- Do NOT include any quotes that are not present verbatim in the provided text.\n"
            f"- Do NOT invent themes or behaviors not supported by the data.\n"
            f"- Never use placeholder names like 'Unlabeled Theme', 'Cluster X', or similar.\n\n"
            f"Clusters:\n{combined}\n\n"
            f"Return a JSON array of objects, one per cluster."
        )

    def _parse_batch_response(
        self,
        raw_text: str,
        batch_samples: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Parse a batch LLM response into structured theme dicts."""
        raw_text = raw_text.strip()
        themes: List[Dict[str, Any]] = []

        try:
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json", 1)[1]
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]

            data = json.loads(raw_text)
            if isinstance(data, list):
                for item in data:
                    cid = item.get("cluster_id")
                    if cid is not None and cid in batch_samples:
                        theme = self._normalize_theme(item, batch_samples[cid], cid)
                        themes.append(theme)
                return themes
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: parse each cluster individually from the raw text
        for cid in sorted(batch_samples.keys()):
            theme = self._fallback_label(batch_samples[cid], cid)
            themes.append(theme)

        return themes

    def _normalize_theme(
        self,
        data: Dict[str, Any],
        samples: List[Dict[str, Any]],
        cluster_id: int,
    ) -> Dict[str, Any]:
        """Normalize a single theme dict from LLM response."""
        category = self._normalize_category(data.get("category", ""))
        barrier = self._normalize_barrier(data.get("barrier", ""))

        if not category or category == "General / Multiple Categories":
            category = self._detect_category_fallback(samples)
        if not barrier or barrier == "Trust Issues":
            barrier = self._detect_barrier_fallback(samples)

        keywords = data.get("keywords", [])
        if not keywords:
            keywords = self._extract_keywords(samples)

        return {
            "cluster_id": cluster_id,
            "category": category,
            "barrier": barrier,
            "description": data.get("description", ""),
            "keywords": keywords[:8],
            "quotes": data.get("quotes", [])[:3],
            "num_samples": len(samples),
            "representative_chunks": [s.get("chunk_id", "") for s in samples],
        }

    def _fallback_label(
        self,
        samples: List[Dict[str, Any]],
        cluster_id: int,
    ) -> Dict[str, Any]:
        """Fallback labeler when LLM is unavailable. Uses keyword matching."""
        category = self._detect_category_fallback(samples)
        barrier = self._detect_barrier_fallback(samples)
        keywords = self._extract_keywords(samples)
        description = self._generate_fallback_description(samples, category, barrier)

        return {
            "cluster_id": cluster_id,
            "category": category,
            "barrier": barrier,
            "description": description,
            "keywords": keywords[:8],
            "quotes": [s.get("text", "")[:200] for s in samples[:3]],
            "num_samples": len(samples),
            "representative_chunks": [s.get("chunk_id", "") for s in samples],
        }


def main() -> Dict[str, Any]:
    """Standalone entry point: test the theme labeler."""
    labeler = ThemeLabeler()
    print(f"Labeler ready (model={labeler.model}, max_rpm={labeler.max_rpm})")
    return {"status": "ok", "model": labeler.model}


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, default=str))