"""
Twitter / X scraper.
Official API is paid-only in 2026.
Free paths:
- Apify X/Twitter comments actors (recommended, uses free credits)
- Optional: twscrape / Twikit (require user cookies - higher ban risk, not enabled by default)
"""
from typing import List, Optional
import os
import logging
import requests
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class TwitterScraper(BaseScraper):
    platform = "twitter"

    def __init__(self, max_results: int = 50, apify_token: Optional[str] = None):
        super().__init__(max_results)
        self.apify_token = apify_token or os.getenv("APIFY_TOKEN")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        if self.apify_token:
            try:
                results = self._scrape_via_apify(target_url)
            except Exception as e:
                logger.warning(f"Apify Twitter failed: {e}")

        if keywords:
            results = self.filter_by_keywords(results, keywords)

        return results[: self.max_results]

    def _scrape_via_apify(self, tweet_url: str) -> List[CommentResult]:
        # Popular actors: clappi/x-twitter-comments-scraper, vulnv/twitter-comments-scraper, etc.
        actors = [
            "clappi/x-twitter-comments-scraper",
            "vulnv/twitter-comments-scraper",
            "apidojo/tweet-scraper",
        ]

        for act in actors:
            try:
                url = f"https://api.apify.com/v2/acts/{act.replace('/', '~')}/run-sync-get-dataset-items"
                payload = {
                    "startUrls": [{"url": tweet_url}],
                    "maxItems": self.max_results,
                    "includeReplies": True,
                }
                resp = requests.post(
                    url,
                    params={"token": self.apify_token},
                    json=payload,
                    timeout=180,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = self._parse(data, tweet_url)
                    if parsed:
                        return parsed
            except Exception as e:
                logger.debug(f"Twitter actor {act} error: {e}")
                continue
        return []

    def _parse(self, items: list, post_url: str) -> List[CommentResult]:
        results = []
        for item in items or []:
            # Different actors return different shapes
            user = item.get("user") or item.get("author") or {}
            username = (
                user.get("screen_name")
                or user.get("username")
                or item.get("username")
                or item.get("userName")
                or ""
            )
            text = (
                item.get("full_text")
                or item.get("text")
                or item.get("comment")
                or item.get("reply_text")
                or ""
            )
            if not username or not text:
                continue

            results.append(
                CommentResult(
                    platform="twitter",
                    username=username.lstrip("@"),
                    display_name=user.get("name") or item.get("name"),
                    profile_url=f"https://x.com/{username.lstrip('@')}",
                    comment_text=text,
                    comment_url=item.get("url") or item.get("tweet_url") or post_url,
                    post_url=post_url,
                    follower_count=int(user.get("followers_count") or user.get("followers") or 0),
                    bio_text=user.get("description") or user.get("bio"),
                    is_verified=bool(user.get("verified") or user.get("is_blue_verified")),
                    engagement={
                        "likes": item.get("favorite_count") or item.get("likes") or 0,
                        "replies": item.get("reply_count") or 0,
                        "retweets": item.get("retweet_count") or 0,
                    },
                    raw=item,
                )
            )
        return results
