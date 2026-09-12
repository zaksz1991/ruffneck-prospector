"""
YouTube comments scraper.
Free options:
- YouTube Data API v3 (official, generous free quota)
- Apify YouTube actors
"""
from typing import List, Optional
import os
import logging
import requests
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class YouTubeScraper(BaseScraper):
    platform = "youtube"

    def __init__(self, max_results: int = 50, apify_token: Optional[str] = None, youtube_api_key: Optional[str] = None):
        super().__init__(max_results)
        self.apify_token = apify_token or os.getenv("APIFY_TOKEN")
        self.youtube_api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        # Prefer official YouTube Data API if key present (free quota)
        if self.youtube_api_key:
            try:
                results = self._scrape_via_official(target_url)
            except Exception as e:
                logger.warning(f"YouTube official API failed: {e}")

        if not results and self.apify_token:
            try:
                results = self._scrape_via_apify(target_url)
            except Exception as e:
                logger.warning(f"Apify YouTube failed: {e}")

        if keywords:
            results = self.filter_by_keywords(results, keywords)

        return results[: self.max_results]

    def _extract_video_id(self, url: str) -> Optional[str]:
        import re
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"youtu\.be\/([0-9A-Za-z_-]{11})",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def _scrape_via_official(self, video_url: str) -> List[CommentResult]:
        video_id = self._extract_video_id(video_url)
        if not video_id:
            return []

        # First get comment threads
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(self.max_results, 100),
            "order": "relevance",
            "textFormat": "plainText",
            "key": self.youtube_api_key,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("items", []):
            snip = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            author = snip.get("authorDisplayName", "")
            text = snip.get("textDisplay") or snip.get("textOriginal") or ""
            if not author or not text:
                continue
            results.append(
                CommentResult(
                    platform="youtube",
                    username=author,
                    display_name=author,
                    profile_url=snip.get("authorChannelUrl"),
                    comment_text=text,
                    comment_url=f"https://www.youtube.com/watch?v={video_id}&lc={item.get('id')}",
                    post_url=video_url,
                    engagement={
                        "likes": snip.get("likeCount", 0),
                    },
                    raw=item,
                )
            )
        return results

    def _scrape_via_apify(self, video_url: str) -> List[CommentResult]:
        # Example actors - check current Apify store
        actors = ["streamers/youtube-comments-scraper", "apify/youtube-scraper"]
        for act in actors:
            try:
                url = f"https://api.apify.com/v2/acts/{act.replace('/', '~')}/run-sync-get-dataset-items"
                payload = {"startUrls": [{"url": video_url}], "maxResults": self.max_results}
                resp = requests.post(url, params={"token": self.apify_token}, json=payload, timeout=180)
                if resp.status_code == 200:
                    return self._parse(resp.json(), video_url)
            except Exception as e:
                logger.debug(f"YT actor {act}: {e}")
        return []

    def _parse(self, items: list, post_url: str) -> List[CommentResult]:
        results = []
        for item in items or []:
            username = item.get("author") or item.get("authorName") or ""
            text = item.get("text") or item.get("comment") or ""
            if not username or not text:
                continue
            results.append(
                CommentResult(
                    platform="youtube",
                    username=username,
                    comment_text=text,
                    post_url=post_url,
                    engagement={"likes": item.get("likes") or item.get("likeCount") or 0},
                    raw=item,
                )
            )
        return results
