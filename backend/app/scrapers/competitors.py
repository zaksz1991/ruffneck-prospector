"""
Free competitor / lookalike discovery.
Seed: company name or website domain.
Methods:
  1. Google related:domain
  2. "alternatives to [name]" / "[name] vs" / "competitors of [name]"
  3. Category + location style queries when industry hint present
  4. Optional Maps category search when location provided
All free (DuckDuckGo / optional Google CSE).
"""
from typing import List, Optional, Dict, Any
import re
import logging
from urllib.parse import urlparse
from .base import BaseScraper, CommentResult
from .google_search import GoogleSearchScraper

logger = logging.getLogger(__name__)


def _normalize_domain(seed: str) -> Optional[str]:
    seed = (seed or "").strip()
    if not seed:
        return None
    if "://" in seed or seed.startswith("www."):
        try:
            host = urlparse(seed if "://" in seed else f"https://{seed}").netloc.lower()
            return host.replace("www.", "") or None
        except Exception:
            return None
    if "." in seed and " " not in seed:
        return seed.lower().replace("www.", "")
    return None


def _company_label(seed: str, domain: Optional[str]) -> str:
    if domain:
        return domain.split(".")[0].replace("-", " ").title()
    return seed.strip()[:60]


class CompetitorScraper(BaseScraper):
    platform = "competitors"

    def __init__(self, max_results: int = 25):
        super().__init__(max_results)

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """
        target_url = seed company name or website.
        keywords may include: location, industry/category hints.
        """
        keywords = keywords or []
        location = ""
        category = ""
        for k in keywords:
            kl = k.lower()
            if kl.startswith("location:"):
                location = k.split(":", 1)[1].strip()
            elif kl.startswith("category:") or kl.startswith("industry:"):
                category = k.split(":", 1)[1].strip()
            elif not location and len(k) < 40:
                # heuristic: short tokens without : treated as location if multiple keywords
                pass
        # Simpler: first extra keyword as location, second as category if not prefixed
        plain = [k for k in keywords if ":" not in k]
        if plain and not location:
            location = plain[0]
        if len(plain) > 1 and not category:
            category = plain[1]

        return self.discover(target_url, location=location, category=category)

    def discover(
        self,
        seed: str,
        location: str = "",
        category: str = "",
    ) -> List[CommentResult]:
        domain = _normalize_domain(seed)
        name = _company_label(seed, domain)
        g = GoogleSearchScraper(max_results=self.max_results)
        results: List[CommentResult] = []
        seen_urls = set()

        queries = []
        if domain:
            queries.append(f"related:{domain}")
            queries.append(f"alternatives to {domain}")
            queries.append(f'"{name}" competitors OR alternatives')
        else:
            queries.append(f'alternatives to "{name}"')
            queries.append(f'"{name}" vs OR competitors')
            queries.append(f'companies like "{name}"')

        if category:
            q = f'best {category} companies'
            if location:
                q += f" {location}"
            queries.append(q)
        elif location:
            queries.append(f'"{name}" competitors {location}')

        for q in queries[:5]:
            try:
                batch = g._search(q)
                for r in batch:
                    url = (r.profile_url or r.post_url or "").lower()
                    if url and url in seen_urls:
                        continue
                    if url:
                        seen_urls.add(url)
                    # Skip if it's clearly the seed itself
                    if domain and domain in url:
                        continue
                    if name.lower() in (r.display_name or "").lower() and domain and domain in url:
                        continue
                    r.platform = "competitors"
                    r.engagement = {
                        **(r.engagement or {}),
                        "seed": seed,
                        "seed_domain": domain,
                        "discovery_query": q,
                        "source": "competitor_lookalike",
                    }
                    r.comment_text = (r.comment_text or "")[:500]
                    if not r.bio_text:
                        r.bio_text = f"Lookalike / competitor of {name}"
                    results.append(r)
                    if len(results) >= self.max_results:
                        break
            except Exception as e:
                logger.warning(f"Competitor query failed ({q}): {e}")
            if len(results) >= self.max_results:
                break

        # Optional: local Maps category if location + category
        if location and category and len(results) < self.max_results:
            try:
                from .maps import GoogleMapsScraper
                maps = GoogleMapsScraper(max_results=min(10, self.max_results - len(results)))
                map_hits = maps.scrape_comments(f"{category} {location}", keywords=["no_website"])
                for r in map_hits:
                    r.platform = "competitors"
                    r.engagement = {
                        **(r.engagement or {}),
                        "seed": seed,
                        "source": "maps_lookalike",
                    }
                    results.append(r)
            except Exception as e:
                logger.debug(f"Maps lookalike skipped: {e}")

        return results[: self.max_results]
