"""
Google-style lead discovery - STRICTLY FREE.
Primary: Google Custom Search JSON API (100 free queries/day if available).
Fallback: DuckDuckGo HTML (no key) + AI filtering.
Finds people / businesses expressing need for ANY product or service online,
plus the original digital-service niches.
"""
from typing import List, Optional, Dict, Any
import os
import logging
import requests
from urllib.parse import quote_plus
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


# Expanded: digital services + general product/service demand signals
SERVICE_QUERIES = {
    # --- Original digital niches ---
    "digital_marketing": [
        '"need digital marketing"',
        '"looking for social media manager"',
        '"hire marketing agency"',
        '"need SEO help"',
    ],
    "website": [
        '"need a website"',
        '"looking for web developer"',
        '"build me a website"',
        '"website designer needed"',
    ],
    "ai_solution": [
        '"need AI automation"',
        '"looking for ChatGPT expert"',
        '"AI solution for my business"',
        '"hire AI developer"',
    ],
    "graphics": [
        '"need graphic designer"',
        '"logo design needed"',
        '"looking for designer"',
    ],
    "cv_resume": [
        '"need resume help"',
        '"CV writing service"',
        '"cover letter help"',
        '"professional resume writer"',
    ],
    "excel": [
        '"Excel data cleaning"',
        '"need Excel expert"',
        '"spreadsheet help needed"',
        '"data cleaning service"',
    ],
    # --- General product / service demand (any vertical) ---
    "any_product_service": [
        '"looking for" "recommend" OR "anyone know"',
        '"need a" "service" OR "supplier" OR "provider"',
        '"where can I buy" OR "where can I get"',
        '"does anyone know a good"',
    ],
    "buying_intent": [
        '"looking to buy"',
        '"want to purchase"',
        '"need to buy"',
        '"shopping for"',
    ],
    "hiring_services": [
        '"looking to hire"',
        '"need someone who can"',
        '"seeking freelancer"',
        '"contractor needed"',
    ],
    "local_services": [
        '"near me" "recommend"',
        '"best" "in my area"',
        '"looking for a good" plumber OR electrician OR cleaner OR tutor',
    ],
    "b2b_suppliers": [
        '"looking for supplier"',
        '"need wholesale"',
        '"vendor recommendations"',
        '"B2B" "looking for"',
    ],
    "coaching_consulting": [
        '"looking for a coach"',
        '"need a consultant"',
        '"business coach recommendation"',
        '"mentor needed"',
    ],
    "health_wellness": [
        '"looking for a therapist"',
        '"need a personal trainer"',
        '"recommend a clinic"',
        '"looking for nutritionist"',
    ],
    "education_training": [
        '"looking for a tutor"',
        '"need online course"',
        '"recommend a teacher"',
        '"training for my team"',
    ],
    "home_services": [
        '"looking for a plumber"',
        '"need an electrician"',
        '"recommend a cleaner"',
        '"contractor for home"',
    ],
    "events_creative": [
        '"looking for a photographer"',
        '"need event planner"',
        '"videographer recommendation"',
        '"MC for event"',
    ],
    "finance_legal": [
        '"looking for an accountant"',
        '"need a lawyer"',
        '"tax help needed"',
        '"bookkeeper recommendation"',
    ],
    "custom": [],  # free-text only; queries built from extra_keywords
}


# Universal demand prefixes users can combine with any product/service name
DEMAND_TEMPLATES = [
    '"{product}" "looking for"',
    '"{product}" "need a" OR "need an"',
    '"{product}" "recommend"',
    '"{product}" "anyone know"',
    '"where can I get" "{product}"',
    '"looking to buy" "{product}"',
]


class GoogleSearchScraper(BaseScraper):
    platform = "google"

    def __init__(self, max_results: int = 20):
        super().__init__(max_results)
        self.cse_api_key = os.getenv("GOOGLE_CSE_API_KEY")
        self.cse_cx = os.getenv("GOOGLE_CSE_CX")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """target_url can be a service key or a free-text query."""
        query = target_url.strip()
        if query in SERVICE_QUERIES and SERVICE_QUERIES[query]:
            all_results = []
            for q in SERVICE_QUERIES[query][:2]:
                all_results.extend(self._search(q))
            return all_results[: self.max_results]
        return self._search(query)[: self.max_results]

    def search_service_leads(self, service: str, extra_keywords: List[str] = None) -> List[CommentResult]:
        extra_keywords = extra_keywords or []
        queries: List[str] = []

        if service == "custom" or service not in SERVICE_QUERIES:
            # Free-text product/service: build demand queries from keywords
            product = " ".join(extra_keywords).strip() if extra_keywords else service
            if not product or product in ("custom", "any"):
                product = "service"
            for tmpl in DEMAND_TEMPLATES[:4]:
                queries.append(tmpl.format(product=product))
        else:
            queries = list(SERVICE_QUERIES.get(service, [service]))
            if extra_keywords:
                # Append location / niche to first queries
                loc = " ".join(extra_keywords[:2])
                queries = [f"{q} {loc}" for q in queries[:3]] + queries[3:]

        results = []
        for q in queries[:4]:
            results.extend(self._search(q))
        return results[: self.max_results]

    def search_product_demand(self, product_or_service: str, location: str = "") -> List[CommentResult]:
        """Explicit API for any product/service demand online."""
        product = product_or_service.strip()
        queries = [tmpl.format(product=product) for tmpl in DEMAND_TEMPLATES[:4]]
        if location:
            queries = [f"{q} {location}" for q in queries]
        results = []
        for q in queries:
            results.extend(self._search(q))
        return results[: self.max_results]

    def _search(self, query: str) -> List[CommentResult]:
        if self.cse_api_key and self.cse_cx:
            try:
                return self._via_cse(query)
            except Exception as e:
                logger.warning(f"Google CSE failed: {e}")
        return self._via_duckduckgo(query)

    def _via_cse(self, query: str) -> List[CommentResult]:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.cse_api_key,
            "cx": self.cse_cx,
            "q": query,
            "num": min(10, self.max_results),
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", []):
            results.append(
                CommentResult(
                    platform="google",
                    username=item.get("displayLink", "web"),
                    display_name=item.get("title", "")[:80],
                    profile_url=item.get("link"),
                    comment_text=item.get("snippet", ""),
                    post_url=item.get("link"),
                    bio_text=item.get("title"),
                    raw=item,
                )
            )
        return results

    def _via_duckduckgo(self, query: str) -> List[CommentResult]:
        """Fully free HTML fallback."""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; RuffNeckProspector/1.9)"},
                timeout=15,
            )
            if resp.status_code != 200:
                return []
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for res in soup.select(".result, .web-result")[: self.max_results]:
                title_el = res.select_one(".result__a, a.result__a")
                snippet_el = res.select_one(".result__snippet, .result__body")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href") or ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                results.append(
                    CommentResult(
                        platform="google",
                        username="web",
                        display_name=title[:80],
                        profile_url=href,
                        comment_text=snippet[:500],
                        post_url=href,
                        bio_text=title,
                        engagement={"query": query, "source": "duckduckgo"},
                        raw={},
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []
