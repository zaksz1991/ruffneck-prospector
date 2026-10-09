from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CommentResult:
    platform: str
    username: str
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    comment_text: str = ""
    comment_url: Optional[str] = None
    post_url: Optional[str] = None
    post_caption: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    bio_text: Optional[str] = None
    is_verified: bool = False
    engagement: Dict[str, Any] = None
    raw: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["engagement"] = d.get("engagement") or {}
        d["raw"] = d.get("raw") or {}
        return d


class BaseScraper(ABC):
    """Unified interface for all platform scrapers.
    Prefer free / open-source methods first, fall back to Apify free credits.
    """

    platform: str = "unknown"

    def __init__(self, max_results: int = 50):
        self.max_results = max_results

    @abstractmethod
    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """Scrape comments / replies from a post / thread URL."""
        pass

    def filter_by_keywords(self, comments: List[CommentResult], keywords: List[str]) -> List[CommentResult]:
        if not keywords:
            return comments
        keywords_lower = [k.lower() for k in keywords]
        filtered = []
        for c in comments:
            text = (c.comment_text or "").lower()
            if any(kw in text for kw in keywords_lower):
                filtered.append(c)
        return filtered

    def safe_get(self, data: dict, *keys, default=None):
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k, default)
            else:
                return default
        return data if data is not None else default
