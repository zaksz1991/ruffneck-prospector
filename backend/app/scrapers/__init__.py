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
) -> List[CommentResult]:
    """
    Free Google/DuckDuckGo discovery for:
    - Digital service niches (website, marketing, AI, …)
    - Any product or service demand online (service='custom' + keywords)
    """
    scraper = GoogleSearchScraper(max_results=max_results)
    return scraper.search_service_leads(service, extra_keywords or [])


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
