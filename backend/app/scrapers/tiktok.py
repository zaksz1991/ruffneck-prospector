"""
TikTok scraper - STRICTLY FREE / local.
Uses public endpoints or TikTokApi (Playwright-based) when available.
No paid APIs. Rate-limit yourself heavily.
"""
from typing import List, Optional
import os
import logging
import re
import requests
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    def __init__(self, max_results: int = 40):
        super().__init__(max_results)

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        video_id = self._extract_video_id(target_url)
        if not video_id:
            logger.warning("Could not extract TikTok video ID from URL")
            return []

        # Try lightweight public endpoint first
        try:
            results = self._scrape_public_endpoint(video_id)
        except Exception as e:
            logger.debug(f"Public endpoint failed: {e}")

        # Fallback to TikTokApi if installed
        if not results:
            try:
                results = self._scrape_via_tiktokapi(video_id)
            except Exception as e:
                logger.warning(f"TikTokApi fallback failed: {e}. Install with: pip install TikTokApi playwright")

        if keywords:
            results = self.filter_by_keywords(results, keywords)
        return results[: self.max_results]

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r"/video/(\d+)",
            r"tiktok\.com/.*/(\d{15,})",
            r"vm\.tiktok\.com/([A-Za-z0-9]+)",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def _scrape_public_endpoint(self, video_id: str) -> List[CommentResult]:
        """Best-effort public comment list (may break; TikTok changes often)."""
        url = f"https://www.tiktok.com/api/comment/list/?aid=1988&aweme_id={video_id}&count={min(self.max_results, 50)}&cursor=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/",
        }
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        comments = data.get("comments") or []
        results = []
        for c in comments:
            user = c.get("user", {})
            text = c.get("text") or ""
            if not text:
                continue
            username = user.get("unique_id") or user.get("nickname") or "tiktok_user"
            results.append(
                CommentResult(
                    platform="tiktok",
                    username=username,
                    display_name=user.get("nickname"),
                    profile_url=f"https://www.tiktok.com/@{username}",
                    comment_text=text,
                    post_url=f"https://www.tiktok.com/@/video/{video_id}",
                    follower_count=int(user.get("follower_count") or 0),
                    engagement={"likes": c.get("digg_count") or 0},
                    raw=c,
                )
            )
        return results

    def _scrape_via_tiktokapi(self, video_id: str) -> List[CommentResult]:
        """Requires: pip install TikTokApi && playwright install"""
        from TikTokApi import TikTokApi
        # Note: TikTokApi often needs ms_token / browser context for reliability
        results = []
        with TikTokApi() as api:
            # Simplified; real usage usually needs session creation
            video = api.video(id=video_id)
            for c in video.comments(count=self.max_results):
                results.append(
                    CommentResult(
                        platform="tiktok",
                        username=getattr(c.author, "username", "unknown"),
                        comment_text=getattr(c, "text", ""),
                        engagement={"likes": getattr(c, "likes", 0)},
                        raw={},
                    )
                )
        return results
