"""
Google Maps / local business discovery – improved filters.
Finds local businesses that may need websites, digital marketing, graphics, etc.
Filters: location, business type, min rating heuristic, "likely no website" signal.
"""
from typing import List, Optional, Dict, Any
import logging
import re
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class GoogleMapsScraper(BaseScraper):
    platform = "maps"

    def __init__(self, max_results: int = 20):
        super().__init__(max_results)

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """
        target_url formats supported:
        - Simple: "restaurants Lagos"
        - Filtered via keywords: ["no_website", "min_rating:4.0"]
        """
        keywords = keywords or []
        query, filters = self._parse_query_and_filters(target_url, keywords)
        results = self._scrape_maps(query)

        filtered = []
        for r in results:
            if filters.get("no_website") and r.engagement.get("has_website_signal"):
                continue
            if filters.get("min_rating") is not None and r.engagement.get("rating", 0) < filters["min_rating"]:
                continue
            if filters.get("must_have_phone") and not r.engagement.get("has_phone"):
                continue
            filtered.append(r)

        return filtered[: self.max_results]

    def _parse_query_and_filters(self, target_url: str, keywords: List[str]):
        query = target_url.strip()
        filters: Dict[str, Any] = {
            "no_website": False,
            "min_rating": None,
            "must_have_phone": False,
        }

        clean_keywords = []
        for k in keywords:
            kl = k.lower().strip()
            if kl in ("no_website", "without_website", "no-website"):
                filters["no_website"] = True
            elif kl.startswith("min_rating:"):
                try:
                    filters["min_rating"] = float(kl.split(":")[1])
                except Exception:
                    pass
            elif kl in ("has_phone", "must_have_phone"):
                filters["must_have_phone"] = True
            else:
                clean_keywords.append(k)

        if "no_website" in query.lower() or "without website" in query.lower():
            filters["no_website"] = True
            query = re.sub(r"\b(no_website|without website)\b", "", query, flags=re.I).strip()

        if clean_keywords:
            query = f"{query} {' '.join(clean_keywords)}".strip()

        return query, filters

    def _scrape_maps(self, query: str) -> List[CommentResult]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright required for Maps")
            return []

        results = []
        search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1400, "height": 900},
                locale="en-US",
            )
            page = context.new_page()
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)

                for _ in range(4):
                    page.mouse.wheel(0, 1800)
                    page.wait_for_timeout(1000)

                cards = page.query_selector_all(
                    'div[role="article"], a[href*="/maps/place/"], div.Nv2PK, div.lI9IFe'
                )
                seen = set()
                for card in cards[: self.max_results * 3]:
                    try:
                        text = (card.inner_text() or "").strip()
                        if len(text) < 8 or text in seen:
                            continue
                        seen.add(text)
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        name = lines[0] if lines else "business"

                        has_website = any(
                            any(x in l.lower() for x in [".com", ".net", ".org", "http", "www."])
                            for l in lines
                        )
                        has_phone = any(re.search(r"\+?\d[\d\s\-\(\)]{7,}", l) for l in lines)
                        rating = 0.0
                        for l in lines:
                            m = re.search(r"(\d\.\d)", l)
                            if m:
                                try:
                                    rating = float(m.group(1))
                                    break
                                except Exception:
                                    pass

                        snippet = " | ".join(lines[:5])
                        results.append(
                            CommentResult(
                                platform="maps",
                                username=re.sub(r"[^a-z0-9_]", "", name.lower())[:40] or "business",
                                display_name=name[:80],
                                comment_text=snippet[:600],
                                post_url=search_url,
                                bio_text="Local business" + (" • possible no website" if not has_website else "") + (" • phone found" if has_phone else ""),
                                engagement={
                                    "has_website_signal": has_website,
                                    "has_phone": has_phone,
                                    "rating": rating,
                                    "source": "google_maps",
                                },
                                raw={"query": query},
                            )
                        )
                        if len(results) >= self.max_results:
                            break
                    except Exception:
                        continue
            finally:
                browser.close()
        return results
