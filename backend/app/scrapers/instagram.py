"""
Instagram scraper - free-first approach.
1. Prefer Instaloader for public posts when possible.
2. Fall back to Apify Instagram Comments actor (uses free $5 monthly credit).
"""
from typing import List, Optional
import os
import logging
import requests
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class InstagramScraper(BaseScraper):
    platform = "instagram"

    def __init__(self, max_results: int = 50, apify_token: Optional[str] = None):
        super().__init__(max_results)
        self.apify_token = apify_token or os.getenv("APIFY_TOKEN")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        # # Optional Apify path removed for pure free. Public methods preferred. (most reliable for comments in 2026)
        if self.apify_token:
            try:
                results = self._scrape_via_apify(target_url)
            except Exception as e:
                logger.warning(f"Apify Instagram failed: {e}")

        # Fallback note: Instaloader is great for profiles/posts but comment extraction
        # on arbitrary posts is limited without login. We keep the interface ready.
        if not results:
            logger.info("No results from Apify. Consider adding APIFY_TOKEN or using a public profile URL.")

        if keywords:
            results = self.filter_by_keywords(results, keywords)

        return results[: self.max_results]

    def _scrape_via_apify(self, post_url: str) -> List[CommentResult]:
        """Use popular Apify Instagram comments actors (free credits apply)."""
        # Common working actor IDs (check Apify store for latest)
        # Examples: apify/instagram-comment-scraper, krazee_kaushik/instagram-comments-extractor, etc.
        actor_id = "apify~instagram-scraper"  # or more specific comments actor

        api_url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        params = {
            "token": self.apify_token,
        }
        payload = {
            "directUrls": [post_url],
            "resultsType": "comments",
            "resultsLimit": self.max_results,
            "searchType": "hashtag",  # adjust per actor docs
        }

        # Many comment-specific actors accept simpler input
        # Prefer a dedicated comments actor when available
        alt_actors = [
            "apify/instagram-comment-scraper",
            "krazee_kaushik/instagram-comments-extractor",
        ]

        for act in [actor_id] + alt_actors:
            try:
                url = f"https://api.apify.com/v2/acts/{act.replace('/', '~')}/run-sync-get-dataset-items"
                resp = requests.post(
                    url,
                    params={"token": self.apify_token},
                    json={"postUrls": [post_url], "resultsLimit": self.max_results},
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_apify_items(data, post_url)
            except Exception as e:
                logger.debug(f"Actor {act} failed: {e}")
                continue

        return []

    def _parse_apify_items(self, items: list, post_url: str) -> List[CommentResult]:
        results = []
        for item in items or []:
            username = (
                item.get("ownerUsername")
                or item.get("username")
                or item.get("user", {}).get("username")
                or ""
            )
            text = (
                item.get("text")
                or item.get("commentText")
                or item.get("textOriginal")
                or ""
            )
            if not username or not text:
                continue

            results.append(
                CommentResult(
                    platform="instagram",
                    username=username,
                    display_name=item.get("ownerFullName") or item.get("fullName"),
                    profile_url=f"https://www.instagram.com/{username}/",
                    comment_text=text,
                    comment_url=item.get("url") or post_url,
                    post_url=post_url,
                    follower_count=int(item.get("ownerFollowerCount") or item.get("followers") or 0),
                    bio_text=item.get("ownerBiography") or item.get("bio"),
                    is_verified=bool(item.get("ownerIsVerified") or item.get("isVerified")),
                    engagement={
                        "likes": item.get("likesCount") or item.get("likeCount") or 0,
                    },
                    raw=item,
                )
            )
        return results
