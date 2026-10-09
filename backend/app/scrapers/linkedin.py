"""
LinkedIn free scraper – expanded with Profile Scraping.

- Public profile pages via Playwright
- Falls back to Google/DuckDuckGo for free-text discovery
- Normalizes discovered LinkedIn profiles into CommentResult
- Cleans search-engine artifacts
- Normalizes LinkedIn profile URLs
- No login required for basic public-profile discovery
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
        self.cookies_file = os.getenv("LINKEDIN_COOKIES_FILE")

    # =============================================================
    # SAFE RESULT ACCESS
    # =============================================================

    @staticmethod
    def _get_value(
        item: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Safely retrieve a field from either:
        - a dictionary
        - an object with attributes

        GoogleSearchScraper._search() may return dictionaries,
        while other scraper paths may return CommentResult objects.
        """

        if item is None:
            return default

        if isinstance(item, dict):
            return item.get(key, default)

        return getattr(item, key, default)

    # =============================================================
    # SCRAPE COMMENTS
    # =============================================================

    def scrape_comments(
        self,
        target_url: str,
        keywords: Optional[List[str]] = None,
    ) -> List[CommentResult]:
        """
        Scrape LinkedIn profiles, public pages, or search results.

        target_url can be:
        - A LinkedIn profile URL
        - A LinkedIn post/job/company URL
        - Free-text search query
        """

        keywords = keywords or []
        results: List[CommentResult] = []

        url_lower = target_url.lower().strip()

        # ---------------------------------------------------------
        # DIRECT LINKEDIN PROFILE
        # ---------------------------------------------------------
        if (
            "linkedin.com/in/" in url_lower
            or "linkedin.com/pub/" in url_lower
        ):
            try:
                profile = self.scrape_profile(target_url)

                if profile:
                    results = [
                        self._profile_to_comment_result(
                            profile,
                            target_url,
                        )
                    ]

            except Exception as e:
                logger.warning(
                    f"LinkedIn profile scrape failed: {e}"
                )

        # ---------------------------------------------------------
        # LINKEDIN PUBLIC PAGE / POST / JOB / COMPANY
        # ---------------------------------------------------------
        elif "linkedin.com" in url_lower:
            try:
                results = self._scrape_public_page(target_url)

            except Exception as e:
                logger.warning(
                    f"LinkedIn public page failed: {e}"
                )

        # ---------------------------------------------------------
        # FREE-TEXT DISCOVERY
        # ---------------------------------------------------------
        else:
            from .google_search import GoogleSearchScraper

            g = GoogleSearchScraper(
                max_results=self.max_results
            )

            query = (
                f"(site:linkedin.com/in OR site:linkedin.com/pub) "
                f"{target_url}"
            )

            raw_results = g._search(query)
            results = []

            for item in raw_results:
                # -------------------------------------------------
                # GoogleSearchScraper._search() may return dictionaries
                # rather than CommentResult objects.
                # Always access fields safely.
                # -------------------------------------------------

                item_profile_url = self._get_value(
                    item,
                    "profile_url",
                    "",
                )

                item_post_url = self._get_value(
                    item,
                    "post_url",
                    "",
                )

                url = (
                    item_profile_url
                    or item_post_url
                    or ""
                )

                # Only keep actual LinkedIn URLs.
                if "linkedin.com/" not in str(url).lower():
                    continue

                url = str(url)

                # Normalize protocol-relative URLs.
                if url.startswith("//"):
                    url = "https:" + url

                # Remove query parameters and fragments.
                url = url.split("?", 1)[0]
                url = url.split("#", 1)[0]
                url = url.rstrip("/")

                # Normalize LinkedIn host.
                #
                # Example:
                # https://ca.linkedin.com/in/user
                #
                # becomes:
                # https://www.linkedin.com/in/user
                url = re.sub(
                    r"^https?://[^/]*linkedin\.com",
                    "https://www.linkedin.com",
                    url,
                    flags=re.IGNORECASE,
                )

                url = url.rstrip("/")

                # -------------------------------------------------
                # EXTRACT USERNAME
                # -------------------------------------------------
                username = self._get_value(
                    item,
                    "username",
                    "",
                ) or ""

                username = str(username)

                normalized_url = url.lower()

                if "/in/" in normalized_url:
                    username = (
                        normalized_url
                        .split("/in/", 1)[1]
                        .split("/", 1)[0]
                        .strip()
                    )

                    username = re.sub(
                        r"[^a-z0-9\-_.]",
                        "",
                        username,
                        flags=re.IGNORECASE,
                    )

                # Avoid invalid Google/search-engine usernames.
                if (
                    not username
                    or username.lower() == "web"
                ):
                    username = "linkedin_user"

                # -------------------------------------------------
                # CLEAN DISPLAY NAME
                # -------------------------------------------------
                display_name = self._get_value(
                    item,
                    "display_name",
                    "",
                ) or ""

                display_name = str(display_name)

                # Remove:
                # " | LinkedIn"
                # " - LinkedIn"
                display_name = re.sub(
                    r"\s*(?:\||-)\s*LinkedIn\s*$",
                    "",
                    display_name,
                    flags=re.IGNORECASE,
                ).strip()

                # Collapse repeated whitespace.
                display_name = re.sub(
                    r"\s+",
                    " ",
                    display_name,
                ).strip()

                # -------------------------------------------------
                # CLEAN BIO
                # -------------------------------------------------
                bio_text = self._get_value(
                    item,
                    "bio_text",
                    "",
                ) or ""

                bio_text = str(bio_text)

                bio_text = re.sub(
                    r"\s*(?:\||-)\s*LinkedIn\s*$",
                    "",
                    bio_text,
                    flags=re.IGNORECASE,
                ).strip()

                bio_text = re.sub(
                    r"\s+",
                    " ",
                    bio_text,
                ).strip()

                # -------------------------------------------------
                # CREATE NORMALIZED RESULT
                # -------------------------------------------------
                results.append(
                    CommentResult(
                        platform="linkedin",
                        username=username,
                        display_name=display_name,
                        profile_url=url,
                        comment_text="",
                        comment_url=self._get_value(
                            item,
                            "comment_url",
                            None,
                        ),
                        post_url=url,
                        post_caption=self._get_value(
                            item,
                            "post_caption",
                            None,
                        ),
                        follower_count=self._get_value(
                            item,
                            "follower_count",
                            0,
                        ),
                        following_count=self._get_value(
                            item,
                            "following_count",
                            0,
                        ),
                        bio_text=bio_text,
                        is_verified=self._get_value(
                            item,
                            "is_verified",
                            False,
                        ),
                        engagement=self._get_value(
                            item,
                            "engagement",
                            {},
                        ) or {},
                        raw=self._get_value(
                            item,
                            "raw",
                            item,
                        ),
                    )
                )

        # ---------------------------------------------------------
        # KEYWORD FILTERING
        #
        # LinkedIn discovery results intentionally use an empty
        # comment_text. Therefore keyword filtering searches:
        # - display name
        # - bio
        # - profile URL
        # - comment text
        # ---------------------------------------------------------
        if keywords:
            keyword_results = []

            for result in results:
                searchable_text = " ".join(
                    [
                        result.display_name or "",
                        result.bio_text or "",
                        result.profile_url or "",
                        result.comment_text or "",
                    ]
                ).lower()

                if any(
                    keyword.lower() in searchable_text
                    for keyword in keywords
                ):
                    keyword_results.append(result)

            results = keyword_results

        return results[: self.max_results]

    # =============================================================
    # DIRECT PROFILE SCRAPER
    # =============================================================

    def scrape_profile(
        self,
        profile_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape a single public LinkedIn profile.

        Returns a structured dictionary or None.
        """

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "playwright not installed"
            )
            return None

        profile_url = (
            profile_url
            .split("?")[0]
            .rstrip("/")
        )

        # Normalize LinkedIn profile host.
        profile_url = re.sub(
            r"^https?://[^/]*linkedin\.com",
            "https://www.linkedin.com",
            profile_url,
            flags=re.IGNORECASE,
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={
                    "width": 1280,
                    "height": 900,
                },
                locale="en-US",
            )

            # -----------------------------------------------------
            # OPTIONAL COOKIE SUPPORT
            # -----------------------------------------------------
            if (
                self.cookies_file
                and os.path.exists(self.cookies_file)
            ):
                try:
                    with open(
                        self.cookies_file,
                        encoding="utf-8",
                    ) as f:
                        cookies = json.load(f)

                    context.add_cookies(cookies)

                    logger.info(
                        "Loaded LinkedIn cookies"
                    )

                except Exception as e:
                    logger.warning(
                        f"Could not load cookies: {e}"
                    )

            page = context.new_page()

            try:
                page.goto(
                    profile_url,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )

                page.wait_for_timeout(3500)

                # Scroll to load additional sections.
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

                # -------------------------------------------------
                # NAME
                # -------------------------------------------------
                for sel in [
                    "h1.text-heading-xlarge",
                    "h1",
                    ".pv-text-details__left-panel h1",
                    "h1.inline",
                ]:
                    el = page.query_selector(sel)

                    if el:
                        data["name"] = (
                            el.inner_text() or ""
                        ).strip()

                        if data["name"]:
                            break

                # -------------------------------------------------
                # HEADLINE
                # -------------------------------------------------
                for sel in [
                    ".text-body-medium",
                    ".pv-text-details__left-panel "
                    ".text-body-medium",
                    "div.text-body-medium",
                ]:
                    el = page.query_selector(sel)

                    if el:
                        txt = (
                            el.inner_text() or ""
                        ).strip()

                        if txt and len(txt) > 5:
                            data["headline"] = txt
                            break

                # -------------------------------------------------
                # LOCATION
                # -------------------------------------------------
                for sel in [
                    ".text-body-small.inline",
                    "span.text-body-small",
                    ".pv-text-details__left-panel "
                    ".text-body-small",
                ]:
                    el = page.query_selector(sel)

                    if el:
                        txt = (
                            el.inner_text() or ""
                        ).strip()

                        if txt and not any(
                            x in txt.lower()
                            for x in [
                                "connection",
                                "follower",
                                "contact",
                            ]
                        ):
                            data["location"] = txt
                            break

                # -------------------------------------------------
                # ABOUT
                # -------------------------------------------------
                about_el = page.query_selector(
                    "#about ~ div .inline-show-more-text, "
                    "#about + div, "
                    "section.pv-about-section"
                )

                if about_el:
                    data["about"] = (
                        about_el.inner_text() or ""
                    ).strip()[:1200]

                # -------------------------------------------------
                # EXPERIENCE
                # -------------------------------------------------
                exp_items = page.query_selector_all(
                    "#experience ~ div li, "
                    "section#experience li, "
                    ".pvs-list__item"
                )

                for item in exp_items[:6]:
                    try:
                        text = (
                            item.inner_text() or ""
                        ).strip()

                        if len(text) > 15:
                            lines = [
                                line.strip()
                                for line in text.split("\n")
                                if line.strip()
                            ]

                            data["experience"].append(
                                {
                                    "raw": text[:400],
                                    "title": (
                                        lines[0]
                                        if lines
                                        else None
                                    ),
                                    "company": (
                                        lines[1]
                                        if len(lines) > 1
                                        else None
                                    ),
                                }
                            )

                            if (
                                not data["current_company"]
                                and len(lines) > 1
                            ):
                                data["current_company"] = (
                                    lines[1]
                                )

                    except Exception:
                        continue

                # -------------------------------------------------
                # EDUCATION
                # -------------------------------------------------
                edu_items = page.query_selector_all(
                    "#education ~ div li, "
                    "section#education li"
                )

                for item in edu_items[:3]:
                    try:
                        text = (
                            item.inner_text() or ""
                        ).strip()

                        if text:
                            data["education"].append(
                                text[:300]
                            )

                    except Exception:
                        continue

                # -------------------------------------------------
                # FOLLOWERS
                # -------------------------------------------------
                page_text = (
                    page.inner_text("body") or ""
                )

                fol = re.search(
                    r"([\d,\.]+)\s*followers?",
                    page_text,
                    re.I,
                )

                if fol:
                    try:
                        data["follower_count"] = int(
                            re.sub(
                                r"[^\d]",
                                "",
                                fol.group(1),
                            )
                        )
                    except Exception:
                        pass

                # -------------------------------------------------
                # FALLBACK IF PROFILE CONTENT IS LIMITED
                # -------------------------------------------------
                if (
                    not data["name"]
                    and not data["headline"]
                ):
                    body_text = (
                        page.inner_text("main")
                        or page.inner_text("body")
                        or ""
                    )

                    data["about"] = body_text[:800]
                    data["name"] = "linkedin_profile"

                return data

            finally:
                browser.close()

    # =============================================================
    # PROFILE -> COMMENT RESULT
    # =============================================================

    def _profile_to_comment_result(
        self,
        profile: Dict[str, Any],
        url: str,
    ) -> CommentResult:
        """
        Convert structured LinkedIn profile data into
        the unified CommentResult format.
        """

        name = (
            profile.get("name")
            or "linkedin_user"
        )

        username = (
            name.lower()
            .replace(" ", "")[:40]
        )

        # ---------------------------------------------------------
        # Extract actual LinkedIn vanity username.
        # ---------------------------------------------------------
        match = re.search(
            r"linkedin\.com/in/([^/?#]+)",
            url,
            re.I,
        )

        if match:
            username = match.group(1)

        username = re.sub(
            r"[^a-z0-9\-_.]",
            "",
            username,
            flags=re.IGNORECASE,
        )

        # ---------------------------------------------------------
        # Build useful searchable profile text.
        # ---------------------------------------------------------
        parts = [
            profile.get("headline") or "",
            profile.get("about") or "",
            (
                f"Company: {profile.get('current_company')}"
                if profile.get("current_company")
                else ""
            ),
            (
                f"Location: {profile.get('location')}"
                if profile.get("location")
                else ""
            ),
        ]

        comment_text = " | ".join(
            part for part in parts if part
        )[:1000]

        # ---------------------------------------------------------
        # Clean LinkedIn suffixes from profile fields.
        # ---------------------------------------------------------
        clean_name = re.sub(
            r"\s*(?:\||-)\s*LinkedIn\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        ).strip()

        clean_headline = re.sub(
            r"\s*(?:\||-)\s*LinkedIn\s*$",
            "",
            profile.get("headline") or "",
            flags=re.IGNORECASE,
        ).strip()

        clean_about = re.sub(
            r"\s*(?:\||-)\s*LinkedIn\s*$",
            "",
            profile.get("about") or "",
            flags=re.IGNORECASE,
        ).strip()

        return CommentResult(
            platform="linkedin",
            username=username,
            display_name=clean_name,
            profile_url=url,
            comment_text=comment_text,
            post_url=url,
            bio_text=(
                clean_about
                or clean_headline
                or None
            ),
            follower_count=(
                profile.get("follower_count") or 0
            ),
            engagement={
                "headline": clean_headline,
                "location": profile.get(
                    "location"
                ),
                "current_company": profile.get(
                    "current_company"
                ),
                "experience_count": len(
                    profile.get("experience") or []
                ),
                "education_count": len(
                    profile.get("education") or []
                ),
            },
            raw=profile,
        )

    # =============================================================
    # PUBLIC LINKEDIN PAGE
    # =============================================================

    def _scrape_public_page(
        self,
        url: str,
    ) -> List[CommentResult]:
        """
        Fallback for non-profile LinkedIn URLs
        such as posts, companies, and jobs.
        """

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []

        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True
            )

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={
                    "width": 1280,
                    "height": 900,
                },
            )

            page = context.new_page()

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=45000,
                )

                page.wait_for_timeout(3000)

                elements = page.query_selector_all(
                    "div.feed-shared-update-v2, "
                    "div.update-components-text, "
                    "span.break-words, "
                    "div.comments-comment-item, "
                    "h1"
                )

                seen = set()

                for el in elements[
                    : self.max_results * 2
                ]:
                    text = (
                        el.inner_text() or ""
                    ).strip()

                    if (
                        len(text) < 20
                        or text in seen
                    ):
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
                            raw={
                                "source": "public_page"
                            },
                        )
                    )

                    if (
                        len(results)
                        >= self.max_results
                    ):
                        break

            finally:
                browser.close()

        return results