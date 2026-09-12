"""
Facebook scraper - STRICTLY FREE / local only.
Uses Playwright browser automation on public pages/posts (no Apify, no paid).
Requires: pip install playwright && playwright install chromium
User must supply optional cookies for better access; public data preferred.
High risk of blocks — use slowly, with delays, for public content only.
"""
from typing import List, Optional
import os
import logging
import re
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    platform = "facebook"

    def __init__(self, max_results: int = 30):
        super().__init__(max_results)

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        try:
            results = self._scrape_public_with_playwright(target_url)
        except Exception as e:
            logger.warning(f"Facebook Playwright scrape failed: {e}. "
                           "Install playwright + chromium, or use a public post URL. "
                           "Facebook heavily restricts automated access.")

        if keywords:
            results = self.filter_by_keywords(results, keywords)
        return results[: self.max_results]

    def _scrape_public_with_playwright(self, post_url: str) -> List[CommentResult]:
        """Best-effort public post comments via headless Chromium.
        This is fragile and against aggressive ToS enforcement — educational / low-volume only.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            try:
                page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)

                # Try to expand comments if button present
                for sel in ['div[aria-label*="comment"]', 'div[role="button"]:has-text("View")', 'span:has-text("comments")']:
                    try:
                        page.click(sel, timeout=2000)
                        page.wait_for_timeout(1500)
                    except Exception:
                        pass

                # Collect visible comment-like elements (best-effort selectors — FB changes often)
                elements = page.query_selector_all('div[data-ad-preview="message"], div[dir="auto"], span[dir="auto"]')
                seen = set()
                for el in elements[: self.max_results * 3]:
                    text = (el.inner_text() or "").strip()
                    if len(text) < 15 or text in seen:
                        continue
                    # crude filter for actual comments
                    if any(x in text.lower() for x in ["like", "reply", "share", "see more"]):
                        continue
                    seen.add(text)
                    # username extraction is extremely limited without login
                    results.append(
                        CommentResult(
                            platform="facebook",
                            username="facebook_user",  # limited without auth
                            comment_text=text[:800],
                            comment_url=post_url,
                            post_url=post_url,
                            engagement={},
                            raw={"source": "playwright_public"},
                        )
                    )
                    if len(results) >= self.max_results:
                        break
            finally:
                browser.close()
        return results
