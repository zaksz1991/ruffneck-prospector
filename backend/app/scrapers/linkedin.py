"""
LinkedIn free scraper – expanded with Profile Scraping.
- Public profile pages via Playwright (no login required for many public profiles)
- Optional cookie / session support for deeper access (user-provided)
- Falls back to Google site:linkedin.com for search queries
High detection risk — rate-limit heavily, educational / low-volume use only.
"""
from typing import List, Optional, Dict, Any
import os
import logging
import re
import json
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    platform = "linkedin"

    def __init__(self, max_results: int = 25):
        super().__init__(max_results)
        # Optional: path to a cookies JSON file exported from browser (for logged-in depth)
        self.cookies_file = os.getenv("LINKEDIN_COOKIES_FILE")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """
        target_url can be:
        - A LinkedIn profile URL  → full profile scrape
        - A post / job / company URL → public page scrape
        - Free-text query → Google site:linkedin.com
        """
        keywords = keywords or []
        results: List[CommentResult] = []

        url_lower = target_url.lower().strip()

        if "linkedin.com/in/" in url_lower or "linkedin.com/pub/" in url_lower:
            # Profile URL → dedicated profile scraper
            try:
                profile = self.scrape_profile(target_url)
                if profile:
                    results = [self._profile_to_comment_result(profile, target_url)]
            except Exception as e:
                logger.warning(f"LinkedIn profile scrape failed: {e}")
        elif "linkedin.com" in url_lower:
            try:
                results = self._scrape_public_page(target_url)
            except Exception as e:
                logger.warning(f"LinkedIn public page failed: {e}")
        else:
            # Search query
            from .google_search import GoogleSearchScraper
            g = GoogleSearchScraper(max_results=self.max_results)
            query = f'site:linkedin.com/in OR site:linkedin.com/pub {target_url}'
            results = g._search(query)

        if keywords:
            results = self.filter_by_keywords(results, keywords)
        return results[: self.max_results]

    def scrape_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single public LinkedIn profile.
        Returns structured dict or None.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright not installed")
            return None

        profile_url = profile_url.split("?")[0].rstrip("/")  # clean

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )

            # Optional: load cookies for better access
            if self.cookies_file and os.path.exists(self.cookies_file):
                try:
                    with open(self.cookies_file) as f:
                        cookies = json.load(f)
                    context.add_cookies(cookies)
                    logger.info("Loaded LinkedIn cookies")
                except Exception as e:
                    logger.warning(f"Could not load cookies: {e}")

            page = context.new_page()
            try:
                page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)

                # Scroll a bit to load sections
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1500)

                data: Dict[str, Any] = {
                    "url": profile_url,
                    "name": None,
                    "headline": None,
                    "location": None,
                    "about": None,
                    "current_company": None,
                    "experience": [],
                    "education": [],
                    "follower_count": 0,
                    "connection_degree": None,
                }

                # Name
                for sel in ["h1.text-heading-xlarge", "h1", ".pv-text-details__left-panel h1", "h1.inline"]:
                    el = page.query_selector(sel)
                    if el:
                        data["name"] = (el.inner_text() or "").strip()
                        if data["name"]:
                            break

                # Headline
                for sel in [".text-body-medium", ".pv-text-details__left-panel .text-body-medium", "div.text-body-medium"]:
                    el = page.query_selector(sel)
                    if el:
                        txt = (el.inner_text() or "").strip()
                        if txt and len(txt) > 5:
                            data["headline"] = txt
                            break

                # Location
                for sel in [".text-body-small.inline", "span.text-body-small", ".pv-text-details__left-panel .text-body-small"]:
                    el = page.query_selector(sel)
                    if el:
                        txt = (el.inner_text() or "").strip()
                        if txt and not any(x in txt.lower() for x in ["connection", "follower", "contact"]):
                            data["location"] = txt
                            break

                # About section
                about_el = page.query_selector("#about ~ div .inline-show-more-text, #about + div, section.pv-about-section")
                if about_el:
                    data["about"] = (about_el.inner_text() or "").strip()[:1200]

                # Experience (best-effort)
                exp_items = page.query_selector_all("#experience ~ div li, section#experience li, .pvs-list__item")
                for item in exp_items[:6]:
                    try:
                        text = (item.inner_text() or "").strip()
                        if len(text) > 15:
                            lines = [l.strip() for l in text.split("\n") if l.strip()]
                            data["experience"].append({
                                "raw": text[:400],
                                "title": lines[0] if lines else None,
                                "company": lines[1] if len(lines) > 1 else None,
                            })
                            if not data["current_company"] and len(lines) > 1:
                                data["current_company"] = lines[1]
                    except Exception:
                        continue

                # Education
                edu_items = page.query_selector_all("#education ~ div li, section#education li")
                for item in edu_items[:3]:
                    try:
                        text = (item.inner_text() or "").strip()
                        if text:
                            data["education"].append(text[:300])
                    except Exception:
                        continue

                # Follower / connection hints
                page_text = page.inner_text("body") or ""
                fol = re.search(r"([\d,\.]+)\s*followers?", page_text, re.I)
                if fol:
                    try:
                        data["follower_count"] = int(re.sub(r"[^\d]", "", fol.group(1)))
                    except Exception:
                        pass

                if not data["name"] and not data["headline"]:
                    # Fallback: grab large visible text blocks
                    body_text = page.inner_text("main") or page.inner_text("body") or ""
                    data["about"] = body_text[:800]
                    data["name"] = "linkedin_profile"

                return data
            finally:
                browser.close()

    def _profile_to_comment_result(self, profile: Dict[str, Any], url: str) -> CommentResult:
        """Convert structured profile into a CommentResult for the unified pipeline."""
        name = profile.get("name") or "linkedin_user"
        username = name.lower().replace(" ", "")[:40]
        # Try to extract vanity from URL
        m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
        if m:
            username = m.group(1)

        parts = [
            profile.get("headline") or "",
            profile.get("about") or "",
            f"Company: {profile.get('current_company')}" if profile.get("current_company") else "",
            f"Location: {profile.get('location')}" if profile.get("location") else "",
        ]
        comment_text = " | ".join(p for p in parts if p)[:1000]

        return CommentResult(
            platform="linkedin",
            username=username,
            display_name=name,
            profile_url=url,
            comment_text=comment_text,
            post_url=url,
            bio_text=profile.get("about") or profile.get("headline"),
            follower_count=profile.get("follower_count") or 0,
            engagement={
                "headline": profile.get("headline"),
                "location": profile.get("location"),
                "current_company": profile.get("current_company"),
                "experience_count": len(profile.get("experience") or []),
                "education_count": len(profile.get("education") or []),
            },
            raw=profile,
        )

    def _scrape_public_page(self, url: str) -> List[CommentResult]:
        """Fallback for non-profile LinkedIn URLs (posts, companies, jobs)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                elements = page.query_selector_all(
                    "div.feed-shared-update-v2, div.update-components-text, "
                    "span.break-words, div.comments-comment-item, h1"
                )
                seen = set()
                for el in elements[: self.max_results * 2]:
                    text = (el.inner_text() or "").strip()
                    if len(text) < 20 or text in seen:
                        continue
                    seen.add(text)
                    results.append(
                        CommentResult(
                            platform="linkedin",
                            username="linkedin_user",
                            comment_text=text[:800],
                            comment_url=url,
                            post_url=url,
                            engagement={},
                            raw={"source": "public_page"},
                        )
                    )
                    if len(results) >= self.max_results:
                        break
            finally:
                browser.close()
        return results
