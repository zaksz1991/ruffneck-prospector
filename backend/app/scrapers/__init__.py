"""
Unified free scrapers registry – expanded.
All platforms use free / open-source methods only.
"""
from typing import Optional, List
from .base import BaseScraper, CommentResult
from .instagram import InstagramScraper
from .twitter import TwitterScraper
from .reddit import RedditScraper
from .youtube import YouTubeScraper
from .competitors import CompetitorScraper
from .google_search import GoogleSearchScraper
from .tiktok import TikTokScraper
from .facebook import FacebookScraper
from .linkedin import LinkedInScraper
from .jobs import JobBoardScraper
from .maps import GoogleMapsScraper
import logging

logger = logging.getLogger(__name__)

SUPPORTED = {
    "instagram": InstagramScraper,
    "ig": InstagramScraper,
    "twitter": TwitterScraper,
    "x": TwitterScraper,
    "reddit": RedditScraper,
    "youtube": YouTubeScraper,
    "yt": YouTubeScraper,
    "google": GoogleSearchScraper,
    "search": GoogleSearchScraper,
    "tiktok": TikTokScraper,
    "tt": TikTokScraper,
    "facebook": FacebookScraper,
    "fb": FacebookScraper,
    "linkedin": LinkedInScraper,
    "li": LinkedInScraper,
    "jobs": JobBoardScraper,
    "job": JobBoardScraper,
    "remoteok": JobBoardScraper,
    "maps": GoogleMapsScraper,
    "google_maps": GoogleMapsScraper,
    "local": GoogleMapsScraper,
    "competitors": CompetitorScraper,
    "competitor": CompetitorScraper,
    "lookalike": CompetitorScraper,
}


def get_scraper(platform: str, max_results: int = 50, **kwargs) -> BaseScraper:
    platform = platform.lower().strip()
    cls = SUPPORTED.get(platform)
    if not cls:
        raise ValueError(
            f"Unsupported platform: {platform}. "
            f"Supported (all free): {sorted(set(SUPPORTED.keys()))}"
        )
    return cls(max_results=max_results, **kwargs)


def scrape_platform(
    platform: str,
    target_url: str,
    keywords: Optional[List[str]] = None,
    max_results: int = 50,
) -> List[CommentResult]:
    scraper = get_scraper(platform, max_results=max_results)
    return scraper.scrape_comments(target_url, keywords=keywords or [])


def discover_service_leads(
    service: str,
    extra_keywords: Optional[List[str]] = None,
    max_results: int = 30,
    location: str = "Nigeria",
) -> List[CommentResult]:
    """
    Free Google/DuckDuckGo discovery for service-intent leads.

    extra_keywords are additional search terms.
    They are not interpreted as the location argument.
    """
    scraper = GoogleSearchScraper(max_results=max_results)

    # USED_ITEMS_QUERY_BUDGET_V1
    # Used-item demand is unusually social/marketplace-heavy.
    # Give it a larger search budget without increasing the runtime
    # of every other Service Intent category.
    query_budget = (
        40
        if str(service or "").strip().lower() == "used_items"
        else 6
    )

    return scraper.search_service_leads(
        service,
        location=(location or "Nigeria").strip(),
        extra_keywords=extra_keywords or [],
        max_results=max_results,
        max_queries=query_budget,
    )


def discover_product_demand(
    product_or_service: str,
    location: str = "",
    max_results: int = 30,
) -> List[CommentResult]:
    """Find people online expressing need for any product or service."""
    scraper = GoogleSearchScraper(max_results=max_results)
    return scraper.search_product_demand(product_or_service, location=location)


def discover_competitors(
    seed: str,
    location: str = "",
    category: str = "",
    max_results: int = 25,
) -> List[CommentResult]:
    scraper = CompetitorScraper(max_results=max_results)
    return scraper.discover(seed, location=location, category=category)


