"""
RuffNeck Prospector - Competitor Discovery

Purpose
-------
Discover likely competitor companies from public search results.

Pipeline
--------
1. Search for competitor evidence.
2. Identify genuine company-looking homepage results.
3. Extract explicit competitor names from competitor lists.
4. Resolve names to official homepages.
5. Reject products, search pages, articles, generic words and false matches.
6. Return CommentResult objects.

No email addresses are generated or guessed.
"""

from __future__ import annotations

import inspect
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from .base import CommentResult
from .google_search import GoogleSearchScraper

logger = logging.getLogger(__name__)


class CompetitorScraper:
    """Discover likely competitor companies."""

    # ================================================================
    # DOMAIN FILTERS
    # ================================================================

    BLOCKED_ROOT_DOMAINS = {
        "bing.com",
        "yahoo.com",
        "duckduckgo.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "reddit.com",
        "youtube.com",
        "wikipedia.org",

        "g2.com",
        "capterra.com",
        "getapp.com",
        "softwareadvice.com",
        "trustradius.com",
        "gartner.com",
        "crunchbase.com",
        "cbinsights.com",
        "owler.com",
        "6sense.com",
        "zoominfo.com",
        "apollo.io",
        "rocketreach.co",
        "wellfound.com",
        "techbehemoths.com",
        "clutch.co",
        "designrush.com",
        "themanifest.com",
        "ensun.io",
        "signalhire.com",

        "indeed.com",
        "glassdoor.com",
        "ziprecruiter.com",
        "simplyhired.com",

        "medium.com",
        "substack.com",
        "forbes.com",
        "reuters.com",
        "cnbc.com",
        "investopedia.com",
        "businessinsider.com",
        "techradar.com",

        "quora.com",
        "tripadvisor.com",
        "yelp.com",
        "yellowpages.com",
    }

    BLOCKED_EXACT_DOMAINS = {
        "search.google",
        "maps.google",
        "mail.google",
        "drive.google",
        "docs.google",
        "calendar.google",
        "meet.google",
        "chat.google",
        "analytics.google",
        "ads.google",
        "ai.google",
        "cloud.google",

        "cloud.com",
        "office.com",
        "m365.cloud.microsoft",
        "teams.microsoft.com",
        "azure.microsoft.com",
        "powerbi.microsoft.com",
        "learn.microsoft.com",
        "workspace.google.com",
        "aws.amazon.com",
    }

    BLOCKED_SUBDOMAIN_PREFIXES = {
        "search.",
        "docs.",
        "doc.",
        "help.",
        "support.",
        "learn.",
        "developer.",
        "developers.",
        "api.",
        "community.",
        "forum.",
        "forums.",
        "blog.",
        "news.",
        "status.",
        "careers.",
        "jobs.",
        "shop.",
        "store.",
        "mobile.",
        "m.",
        "app.",
    }

    BLOCKED_PATH_MARKERS = {
        "/blog/",
        "/blogs/",
        "/article/",
        "/articles/",
        "/news/",
        "/insights/",
        "/resources/",
        "/research/",
        "/report/",
        "/reports/",
        "/guide/",
        "/guides/",
        "/directory/",
        "/directories/",
        "/compare/",
        "/comparison/",
        "/comparisons/",
        "/alternative/",
        "/alternatives/",
        "/review/",
        "/reviews/",
        "/community/",
        "/forum/",
        "/forums/",
        "/question/",
        "/questions/",
    }

    # ================================================================
    # CANDIDATE FILTERS
    # ================================================================

    GENERIC_WORDS = {
        "ai",
        "artificial",
        "intelligence",
        "cloud",
        "software",
        "technology",
        "technologies",
        "tech",
        "digital",
        "hardware",

        "business",
        "businesses",
        "company",
        "companies",
        "platform",
        "platforms",
        "service",
        "services",
        "solution",
        "solutions",
        "provider",
        "providers",
        "vendor",
        "vendors",
        "system",
        "systems",
        "network",
        "networks",

        "website",
        "site",
        "homepage",
        "home",
        "official",

        "free",
        "top",
        "best",
        "main",
        "major",
        "leading",
        "key",

        "competitor",
        "competitors",
        "alternative",
        "alternatives",

        "review",
        "reviews",
        "comparison",
        "comparisons",
        "guide",
        "guides",
        "directory",
        "directories",
        "list",
        "lists",

        "meeting",
        "support",
        "help",
        "team",

        "there",
        "some",
        "your",
        "are",
        "for",
        "from",
        "with",
        "into",
        "about",
        "market",
        "share",
        "learn",
        "what",
        "how",
    }

    BAD_CANDIDATE_PHRASES = {
        "peer insights",
        "business strategy hub",
        "customer reviews",
        "user reviews",
        "official website",
        "official site",
        "top alternatives",
        "best alternatives",
        "competitor list",
        "comparison guide",
        "market report",
        "industry report",
        "meeting solutions",
    }

    ORGANIZATION_SUFFIXES = {
        "inc",
        "inc.",
        "ltd",
        "ltd.",
        "limited",
        "llc",
        "corp",
        "corp.",
        "corporation",
        "plc",
        "group",
        "holdings",
        "technologies",
        "technology",
        "systems",
        "solutions",
        "software",
        "services",
        "labs",
        "digital",
        "consulting",
        "ventures",
        "networks",
        "communications",
        "telecom",
    }

    STOPWORDS = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "for",
        "in",
        "on",
        "at",
        "a",
        "an",
        "by",
        "with",
        "from",
        "into",
        "about",
        "company",
        "companies",
        "official",
        "website",
        "site",
        "home",
        "homepage",
    }

    # ================================================================
    # INIT
    # ================================================================

    def __init__(
        self,
        max_results: int = 25,
        timeout: int = 15,
        search: Optional[GoogleSearchScraper] = None,
    ):
        self.max_results = max(
            1,
            int(max_results),
        )

        self.timeout = max(
            5,
            int(timeout),
        )

        self.search = search or GoogleSearchScraper(
            max_results=max(
                10,
                self.max_results,
            ),
            timeout=self.timeout,
        )

    # ================================================================
    # PUBLIC API
    # ================================================================

    def scrape_comments(
        self,
        target_url: str,
        keywords: Optional[List[str]] = None,
    ) -> List[CommentResult]:
        location = ""
        category = ""

        for keyword in keywords or []:
            value = str(keyword).strip()

            if value.lower().startswith("location:"):
                location = value.split(
                    ":",
                    1,
                )[1].strip()

            elif value.lower().startswith("category:"):
                category = value.split(
                    ":",
                    1,
                )[1].strip()

        return self.discover(
            target_url,
            location=location,
            category=category,
            max_results=self.max_results,
        )

    def discover(
        self,
        seed: str,
        location: str = "",
        category: str = "",
        max_results: Optional[int] = None,
    ) -> List[CommentResult]:
        limit = max(
            1,
            int(
                max_results
                or self.max_results
            ),
        )

        seed_domain = self._normalize_domain(
            seed
        )

        seed_name = self._company_label(
            seed
        )

        if not seed_name:
            return []

        evidence = self._collect_evidence(
            seed_name,
            location,
            category,
        )

        if not evidence:
            logger.warning(
                "No competitor evidence found for %s",
                seed,
            )
            return []

        source_domains = {
            item["domain"]
            for item in evidence
            if item.get("domain")
        }

        candidates = self._build_candidates(
            evidence,
            seed_name,
            seed_domain,
        )

        if not candidates:
            logger.warning(
                "No viable competitor candidates found for %s",
                seed,
            )
            return []

        results: List[CommentResult] = []
        seen_names: Set[str] = set()
        seen_domains: Set[str] = set()

        ordered = sorted(
            candidates.items(),
            key=lambda item: (
                -int(item[1]["score"]),
                item[0].lower(),
            ),
        )

        for candidate_name, info in ordered:
            if len(results) >= limit:
                break

            clean_name = (
                self._clean_candidate_name(
                    candidate_name
                )
            )

            if not clean_name:
                continue

            name_key = self._normalize_name(
                clean_name
            )

            if name_key in seen_names:
                continue

            seen_names.add(name_key)

            if self._is_seed_candidate(
                clean_name,
                seed_name,
                seed_domain,
            ):
                continue

            direct_result = info.get(
                "direct_result"
            )

            resolved = None

            if direct_result:
                resolved = (
                    self._evaluate_official_result(
                        candidate_name=clean_name,
                        row=direct_result,
                        seed_domain=seed_domain,
                        source_domains=source_domains,
                    )
                )

            if resolved is None:
                resolved = (
                    self._resolve_official_site(
                        candidate_name=clean_name,
                        seed_domain=seed_domain,
                        source_domains=source_domains,
                        location=location,
                    )
                )

            if not resolved:
                continue

            domain = resolved[
                "root_domain"
            ]

            if domain in seen_domains:
                continue

            seen_domains.add(domain)

            engagement = {
                "candidate_name": clean_name,
                "root_domain": domain,
                "page_type": "company_homepage",
                "prospect_score": int(
                    resolved[
                        "prospect_score"
                    ]
                ),
                "candidate_score": int(
                    info["score"]
                ),
                "discovery": "competitor",
                "seed": seed,
                "location": location,
                "category": category,
                "evidence": info[
                    "evidence"
                ][:5],
            }

            result = self._make_result(
                resolved["display_name"],
                resolved["url"],
                engagement,
            )

            if result is not None:
                results.append(result)

        results.sort(
            key=lambda item: int(
                getattr(
                    item,
                    "engagement",
                    {},
                ).get(
                    "prospect_score",
                    0,
                )
            ),
            reverse=True,
        )

        return results[:limit]

    # ================================================================
    # EVIDENCE SEARCH
    # ================================================================

    def _collect_evidence(
        self,
        seed_name: str,
        location: str,
        category: str,
    ) -> List[Dict[str, Any]]:
        queries = [
            f'"{seed_name}" competitors',
            f'"{seed_name}" main competitors',
            f'"{seed_name}" top competitors',
            f'"{seed_name}" alternatives',
        ]

        if location:
            queries.append(
                f'"{seed_name}" competitors {location}'
            )

        if category:
            queries.append(
                f'"{seed_name}" competitors {category}'
            )

        output: List[Dict[str, Any]] = []
        seen_urls: Set[str] = set()

        for query in queries:
            try:
                rows = self.search._search(
                    query,
                    max_results=max(
                        10,
                        self.max_results * 2,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Competitor search failed for %s: %s",
                    query,
                    exc,
                )
                continue

            for row in rows or []:
                if not isinstance(
                    row,
                    dict,
                ):
                    continue

                href = str(
                    row.get("href")
                    or row.get("url")
                    or ""
                ).strip()

                url = self._normalize_url(
                    href
                )

                if not url:
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                output.append(
                    {
                        "title": self._clean_text(
                            row.get(
                                "title",
                                "",
                            )
                        ),
                        "body": self._clean_text(
                            row.get(
                                "body",
                                "",
                            )
                            or row.get(
                                "snippet",
                                "",
                            )
                        ),
                        "href": url,
                        "domain": self._normalize_domain(
                            href
                        ),
                        "query": query,
                    }
                )

        return output

    # ================================================================
    # CANDIDATE BUILDING
    # ================================================================

    def _build_candidates(
        self,
        evidence: List[Dict[str, Any]],
        seed_name: str,
        seed_domain: str,
    ) -> Dict[str, Dict[str, Any]]:
        candidates: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for item in evidence:
            # --------------------------------------------------------
            # DIRECT HOMEPAGE CANDIDATE
            # --------------------------------------------------------

            direct_name = (
                self._extract_direct_company_name(
                    item,
                    seed_name,
                    seed_domain,
                )
            )

            if direct_name:
                entry = candidates.setdefault(
                    direct_name,
                    {
                        "score": 0,
                        "evidence": [],
                        "direct_result": None,
                    },
                )

                entry["score"] += 100

                if entry["direct_result"] is None:
                    entry["direct_result"] = item

                evidence_item = {
                    "title": item.get(
                        "title",
                        "",
                    ),
                    "href": item.get(
                        "href",
                        "",
                    ),
                    "query": item.get(
                        "query",
                        "",
                    ),
                }

                if evidence_item not in entry[
                    "evidence"
                ]:
                    entry["evidence"].append(
                        evidence_item
                    )

            # --------------------------------------------------------
            # EXPLICIT COMPETITOR LIST
            # --------------------------------------------------------

            text = (
                f"{item.get('title', '')} "
                f"{item.get('body', '')}"
            )

            if not self._looks_like_competitor_evidence(
                text
            ):
                continue

            extracted = (
                self._extract_explicit_competitors(
                    text
                )
            )

            for raw in extracted:
                candidate = (
                    self._clean_candidate_name(
                        raw
                    )
                )

                if not candidate:
                    continue

                if not self._looks_like_company_name(
                    candidate
                ):
                    continue

                if self._is_seed_candidate(
                    candidate,
                    seed_name,
                    seed_domain,
                ):
                    continue

                if self._candidate_matches_domain(
                    candidate,
                    item.get(
                        "domain",
                        "",
                    ),
                ):
                    continue

                score = (
                    self._candidate_evidence_score(
                        candidate,
                        item,
                    )
                )

                if score < 30:
                    continue

                entry = candidates.setdefault(
                    candidate,
                    {
                        "score": 0,
                        "evidence": [],
                        "direct_result": None,
                    },
                )

                entry["score"] += score

                evidence_item = {
                    "title": item.get(
                        "title",
                        "",
                    ),
                    "href": item.get(
                        "href",
                        "",
                    ),
                    "query": item.get(
                        "query",
                        "",
                    ),
                }

                if evidence_item not in entry[
                    "evidence"
                ]:
                    entry["evidence"].append(
                        evidence_item
                    )

        return candidates

    # ================================================================
    # DIRECT COMPANY DETECTION
    # ================================================================

    def _extract_direct_company_name(
        self,
        item: Dict[str, Any],
        seed_name: str,
        seed_domain: str,
    ) -> Optional[str]:
        href = str(
            item.get("href")
            or ""
        ).strip()

        title = self._clean_text(
            item.get("title")
            or ""
        )

        domain = self._normalize_domain(
            href
        )

        if not href or not domain:
            return None

        if self._is_seed_domain(
            domain,
            seed_domain,
        ):
            return None

        if self._is_blocked_domain(
            domain
        ):
            return None

        if self._has_blocked_subdomain(
            domain
        ):
            return None

        if self._has_blocked_path(
            href
        ):
            return None

        # Homepage only.
        path = (
            urlparse(href).path
            or ""
        ).rstrip("/")

        if path not in {
            "",
            "/",
        }:
            return None

        if self._is_informational_title(
            title
        ):
            return None

        # ------------------------------------------------------------
        # Use domain root first.
        # ------------------------------------------------------------

        root = domain.split(
            "."
        )[0]

        root_name = root.replace(
            "-",
            " ",
        ).replace(
            "_",
            " ",
        )

        # A generic root such as:
        # hardware.national...
        # is not acceptable when "hardware" is a generic word.
        root_candidate = (
            self._clean_candidate_name(
                root_name
            )
        )

        if (
            not root_candidate
            or not self._looks_like_company_name(
                root_candidate
            )
        ):
            # Try the title instead, but only when the title clearly
            # matches the domain.
            title_candidate = (
                self._clean_page_title(
                    title
                )
            )

            title_candidate = (
                self._clean_candidate_name(
                    title_candidate
                )
            )

            if not title_candidate:
                return None

            if not self._looks_like_company_name(
                title_candidate
            ):
                return None

            if self._domain_score(
                title_candidate,
                domain,
            ) < 30:
                return None

            if self._is_seed_candidate(
                title_candidate,
                seed_name,
                seed_domain,
            ):
                return None

            return title_candidate

        # The root domain itself must map to the candidate.
        if self._domain_score(
            root_candidate,
            domain,
        ) < 30:
            return None

        if self._is_seed_candidate(
            root_candidate,
            seed_name,
            seed_domain,
        ):
            return None

        # If title exists and is clearly a different generic label,
        # don't trust it over the domain.
        if title:
            title_candidate = (
                self._clean_page_title(
                    title
                )
            )

            title_candidate = (
                self._clean_candidate_name(
                    title_candidate
                )
            )

            if title_candidate:
                if (
                    self._looks_like_company_name(
                        title_candidate
                    )
                    and self._domain_score(
                        title_candidate,
                        domain,
                    ) >= 30
                ):
                    return title_candidate

        return root_candidate

    # ================================================================
    # EXPLICIT COMPETITOR EXTRACTION
    # ================================================================

    def _extract_explicit_competitors(
        self,
        text: str,
    ) -> List[str]:
        if not text:
            return []

        text = self._clean_text(
            text
        )

        patterns = [
            r"(?:competitors?|alternatives?|rivals?)"
            r".{0,100}?"
            r"(?:include|includes|are|such as|:)"
            r"\s*(.+)",

            r"(?:main|major|top|leading|key)"
            r"\s+(?:competitors?|alternatives?)"
            r".{0,100}?"
            r"(?:include|includes|are|such as|:)"
            r"\s*(.+)",
        ]

        output: List[str] = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                fragment = (
                    self._trim_fragment(
                        match.group(1)
                    )
                )

                if not fragment:
                    continue

                # Prevent snippets such as:
                # "cloud (Oracle..."
                # from passing through as a single candidate.
                fragment = re.sub(
                    r"\(([^)]*)\)",
                    r" \1",
                    fragment,
                )

                fragment = re.sub(
                    r"\s+(?:and|&)\s+",
                    ", ",
                    fragment,
                    flags=re.IGNORECASE,
                )

                parts = re.split(
                    r"\s*(?:,|;|\||"
                    r"\u2022|\u2013|\u2014)\s*",
                    fragment,
                )

                for part in parts:
                    candidate = (
                        self._clean_candidate_name(
                            part
                        )
                    )

                    if candidate:
                        output.append(
                            candidate
                        )

        return output

    # ================================================================
    # OFFICIAL WEBSITE LOOKUP
    # ================================================================

    def _resolve_official_site(
        self,
        candidate_name: str,
        seed_domain: str,
        source_domains: Set[str],
        location: str,
    ) -> Optional[Dict[str, Any]]:
        queries = [
            f'"{candidate_name}" official website',
            f'"{candidate_name}" homepage',
        ]

        if location:
            queries.append(
                f'"{candidate_name}" official website {location}'
            )

        best: Optional[Dict[str, Any]] = None

        for query in queries:
            try:
                rows = self.search._search(
                    query,
                    max_results=max(
                        8,
                        self.max_results,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Official website lookup failed for %s: %s",
                    candidate_name,
                    exc,
                )
                continue

            for row in rows or []:
                if not isinstance(
                    row,
                    dict,
                ):
                    continue

                result = (
                    self._evaluate_official_result(
                        candidate_name,
                        row,
                        seed_domain,
                        source_domains,
                    )
                )

                if not result:
                    continue

                if (
                    best is None
                    or result[
                        "prospect_score"
                    ]
                    > best[
                        "prospect_score"
                    ]
                ):
                    best = result

        return best

    def _evaluate_official_result(
        self,
        candidate_name: str,
        row: Dict[str, Any],
        seed_domain: str,
        source_domains: Set[str],
    ) -> Optional[Dict[str, Any]]:
        href = str(
            row.get("href")
            or row.get("url")
            or ""
        ).strip()

        if not href:
            return None

        domain = self._normalize_domain(
            href
        )

        if not domain:
            return None

        if self._is_seed_domain(
            domain,
            seed_domain,
        ):
            return None

        if self._is_blocked_domain(
            domain
        ):
            return None

        if self._has_blocked_subdomain(
            domain
        ):
            return None

        if self._has_blocked_path(
            href
        ):
            return None

        title = self._clean_text(
            row.get(
                "title",
                "",
            )
        )

        body = self._clean_text(
            row.get(
                "body",
                "",
            )
            or row.get(
                "snippet",
                "",
            )
        )

        if self._is_informational_title(
            title
        ):
            return None

        domain_score = self._domain_score(
            candidate_name,
            domain,
        )

        if domain_score < 30:
            return None

        title_score = self._text_score(
            candidate_name,
            title,
            body,
        )

        if title_score < 15:
            return None

        if not self._looks_like_company_name(
            candidate_name
        ):
            return None

        # Homepage preference.
        path = (
            urlparse(href).path
            or ""
        ).rstrip("/")

        homepage_score = (
            45
            if path in {
                "",
                "/",
            }
            else 5
        )

        organization_score = 0

        if self._candidate_matches_domain(
            candidate_name,
            domain,
        ):
            organization_score += 45

        if self._name_appears(
            candidate_name,
            title,
        ):
            organization_score += 25

        if self._name_appears(
            candidate_name,
            body,
        ):
            organization_score += 10

        if self._has_organization_suffix(
            candidate_name
        ):
            organization_score += 10

        if organization_score < 45:
            return None

        root_url = self._official_root_url(
            domain
        )

        if not root_url:
            return None

        score = (
            domain_score
            + title_score
            + organization_score
            + homepage_score
        )

        return {
            "display_name": self._best_display_name(
                candidate_name,
                title,
            ),
            "url": root_url,
            "root_domain": domain,
            "prospect_score": min(
                300,
                score,
            ),
        }

    # ================================================================
    # VALIDATION
    # ================================================================

    def _is_blocked_domain(
        self,
        domain: str,
    ) -> bool:
        domain = self._normalize_domain(
            domain
        )

        if not domain:
            return True

        if domain in self.BLOCKED_EXACT_DOMAINS:
            return True

        for root in self.BLOCKED_ROOT_DOMAINS:
            if (
                domain == root
                or domain.endswith(
                    "." + root
                )
            ):
                return True

        return False

    def _has_blocked_subdomain(
        self,
        domain: str,
    ) -> bool:
        domain = self._normalize_domain(
            domain
        )

        if domain.count(".") < 2:
            return False

        first = (
            domain.split(
                ".",
                1,
            )[0]
            + "."
        )

        return (
            first
            in self.BLOCKED_SUBDOMAIN_PREFIXES
        )

    def _has_blocked_path(
        self,
        url: str,
    ) -> bool:
        try:
            path = (
                urlparse(url).path
                or ""
            ).lower()
        except Exception:
            return False

        if path in {
            "",
            "/",
        }:
            return False

        normalized = (
            "/"
            + path.strip("/")
            + "/"
        )

        return any(
            marker in normalized
            for marker in self.BLOCKED_PATH_MARKERS
        )

    def _is_seed_domain(
        self,
        domain: str,
        seed_domain: str,
    ) -> bool:
        domain = self._normalize_domain(
            domain
        )

        seed_domain = self._normalize_domain(
            seed_domain
        )

        if not domain or not seed_domain:
            return False

        return (
            domain == seed_domain
            or domain.endswith(
                "."
                + seed_domain
            )
        )

    def _is_seed_candidate(
        self,
        candidate: str,
        seed_name: str,
        seed_domain: str,
    ) -> bool:
        candidate_key = self._normalize_name(
            candidate
        )

        seed_key = self._normalize_name(
            seed_name
        )

        if not candidate_key:
            return True

        if candidate_key == seed_key:
            return True

        seed_root = (
            self._normalize_domain(
                seed_domain
            )
            .split(".")[0]
            .replace(
                "-",
                " ",
            )
        )

        if candidate_key == self._normalize_name(
            seed_root
        ):
            return True

        # Reject Microsoft Teams / Microsoft Word /
        # Microsoft Azure when Microsoft is the seed.
        seed_tokens = self._tokens(
            seed_key
        )

        candidate_tokens = self._tokens(
            candidate_key
        )

        if (
            seed_tokens
            and seed_tokens.issubset(
                candidate_tokens
            )
        ):
            return True

        return False

    # ================================================================
    # TEXT / NAME HELPERS
    # ================================================================

    def _looks_like_company_name(
        self,
        value: str,
    ) -> bool:
        cleaned = self._clean_candidate_name(
            value
        )

        if not cleaned:
            return False

        words = cleaned.split()

        if len(words) > 6:
            return False

        if len(words) == 1:
            word = words[0].lower()

            if word in self.GENERIC_WORDS:
                return False

            if len(word) < 3:
                return False

            return True

        generic_count = sum(
            1
            for word in words
            if word.lower()
            in self.GENERIC_WORDS
        )

        if generic_count >= len(words):
            return False

        # Reject "cloud oracle" type fragments when the first
        # component is purely generic.
        if (
            words[0].lower()
            in self.GENERIC_WORDS
            and generic_count >= 1
        ):
            return False

        return True

    def _clean_candidate_name(
        self,
        value: Any,
    ) -> Optional[str]:
        if value is None:
            return None

        text = str(
            value
        ).strip()

        if not text:
            return None

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        text = text.strip(
            " \t\r\n,;|:-\u2022"
        )

        # Parenthetical fragments should not become company names.
        # Examples:
        #   cloud (Oracle -> Oracle
        #   Oracle (ORCL) -> Oracle
        if "(" in text:
            before = text.split(
                "(",
                1,
            )[0].strip()

            inside = text.split(
                "(",
                1,
            )[1].split(
                ")",
                1,
            )[0].strip()

            if before:
                text = before
            elif inside:
                text = inside

        # Remove numbering.
        text = re.sub(
            r"^\d{1,2}[\.\):-]\s*",
            "",
            text,
        )

        # URLs are never candidates.
        if re.search(
            r"https?://|www\.",
            text,
            flags=re.IGNORECASE,
        ):
            return None

        # Search snippets with sentence punctuation are unsafe.
        if "." in text:
            return None

        text = text.strip(
            "\"'“”‘’"
        )

        if not text:
            return None

        lower = text.lower()

        if lower in self.GENERIC_WORDS:
            return None

        if lower in self.BAD_CANDIDATE_PHRASES:
            return None

        if len(text) < 3:
            return None

        if len(text) > 70:
            return None

        words = re.findall(
            r"[A-Za-z0-9&'-]+",
            text,
        )

        if not words:
            return None

        if len(words) > 6:
            return None

        # Never allow generic list labels at the beginning.
        if words[0].lower() in {
            "top",
            "best",
            "main",
            "major",
            "leading",
            "key",
            "free",
            "official",
        }:
            return None

        # Never allow generic explanatory endings.
        if words[-1].lower() in {
            "for",
            "are",
            "from",
            "with",
            "free",
            "official",
            "website",
            "site",
            "home",
            "top",
            "best",
        }:
            return None

        # Explicit sentence fragments.
        sentence_words = {
            "who",
            "which",
            "that",
            "these",
            "those",
            "because",
            "while",
            "where",
            "when",
            "provides",
            "providing",
            "offers",
            "offering",
            "helps",
            "builds",
            "delivers",
            "called",
            "known",
            "based",
        }

        if any(
            word.lower()
            in sentence_words
            for word in words
        ):
            return None

        return text

    def _candidate_matches_domain(
        self,
        candidate: str,
        domain: str,
    ) -> bool:
        candidate_tokens = self._tokens(
            self._normalize_name(
                candidate
            )
        )

        root = (
            self._normalize_domain(
                domain
            )
            .split(".")[0]
        )

        root_tokens = self._tokens(
            root.replace(
                "-",
                " ",
            )
        )

        return bool(
            candidate_tokens
            and root_tokens
            and candidate_tokens
            & root_tokens
        )

    def _candidate_evidence_score(
        self,
        candidate: str,
        item: Dict[str, Any],
    ) -> int:
        score = 0

        key = self._normalize_name(
            candidate
        )

        title = self._normalize_name(
            item.get(
                "title",
                "",
            )
        )

        body = self._normalize_name(
            item.get(
                "body",
                "",
            )
        )

        if key and key in title:
            score += 40

        if key and key in body:
            score += 40

        if len(candidate.split()) >= 2:
            score += 10

        if self._has_organization_suffix(
            candidate
        ):
            score += 15

        return min(
            100,
            score,
        )

    def _has_organization_suffix(
        self,
        candidate: str,
    ) -> bool:
        lower = self._normalize_name(
            candidate
        )

        return any(
            lower.endswith(
                " "
                + self._normalize_name(
                    suffix
                )
            )
            for suffix in self.ORGANIZATION_SUFFIXES
        )

    def _normalize_name(
        self,
        value: str,
    ) -> str:
        text = str(
            value or ""
        ).lower()

        text = re.sub(
            r"[^a-z0-9\s]+",
            " ",
            text,
        )

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    def _tokens(
        self,
        value: str,
    ) -> Set[str]:
        return {
            token
            for token in re.findall(
                r"[a-z0-9]+",
                value.lower(),
            )
            if len(token) >= 2
            and token not in self.STOPWORDS
        }

    def _name_appears(
        self,
        candidate: str,
        text: str,
    ) -> bool:
        return (
            self._normalize_name(
                candidate
            )
            in self._normalize_name(
                text
            )
        )

    def _text_score(
        self,
        candidate: str,
        title: str,
        body: str,
    ) -> int:
        key = self._normalize_name(
            candidate
        )

        score = 0

        if key in self._normalize_name(
            title
        ):
            score += 60

        elif (
            self._tokens(key)
            & self._tokens(
                self._normalize_name(
                    title
                )
            )
        ):
            score += 20

        if key in self._normalize_name(
            body
        ):
            score += 40

        elif (
            self._tokens(key)
            & self._tokens(
                self._normalize_name(
                    body
                )
            )
        ):
            score += 15

        return min(
            100,
            score,
        )

    def _looks_like_competitor_evidence(
        self,
        text: str,
    ) -> bool:
        lower = (
            text or ""
        ).lower()

        return any(
            term in lower
            for term in (
                "competitor",
                "competitors",
                "alternative",
                "alternatives",
                "rival",
                "rivals",
            )
        )

    # ================================================================
    # URL / DISPLAY HELPERS
    # ================================================================

    def _clean_page_title(
        self,
        title: str,
    ) -> str:
        value = self._clean_text(
            title
        )

        if not value:
            return ""

        return re.split(
            r"\s+(?:\||–|—|-)\s+",
            value,
            maxsplit=1,
        )[0].strip()

    def _normalize_url(
        self,
        value: str,
    ) -> str:
        text = str(
            value or ""
        ).strip()

        if not text:
            return ""

        if not re.match(
            r"^https?://",
            text,
            flags=re.IGNORECASE,
        ):
            text = "https://" + text

        try:
            parsed = urlparse(
                text
            )

            if not parsed.netloc:
                return ""

            return (
                f"{parsed.scheme}://"
                f"{parsed.netloc}"
                f"{parsed.path or ''}"
            )

        except Exception:
            return ""

    def _normalize_domain(
        self,
        value: str,
    ) -> str:
        text = str(
            value or ""
        ).strip().lower()

        if not text:
            return ""

        try:
            if "://" in text:
                text = urlparse(
                    text
                ).netloc.lower()
            else:
                text = text.split(
                    "/"
                )[0]
        except Exception:
            return ""

        text = text.split(
            "?"
        )[0]

        text = text.split(
            "#"
        )[0]

        text = text.split(
            ":"
        )[0]

        if text.startswith(
            "www."
        ):
            text = text[4:]

        return text.strip(".")

    def _official_root_url(
        self,
        domain: str,
    ) -> Optional[str]:
        domain = self._normalize_domain(
            domain
        )

        if not domain:
            return None

        if self._is_blocked_domain(
            domain
        ):
            return None

        if self._has_blocked_subdomain(
            domain
        ):
            return None

        return (
            "https://"
            + domain
        )

    def _best_display_name(
        self,
        candidate: str,
        title: str,
    ) -> str:
        cleaned = (
            self._clean_candidate_name(
                candidate
            )
        )

        if cleaned:
            return cleaned

        title_clean = (
            self._clean_page_title(
                title
            )
        )

        return title_clean or candidate

    def _trim_fragment(
        self,
        value: str,
    ) -> str:
        text = self._clean_text(
            value
        )

        if not text:
            return ""

        text = re.split(
            r"\.\s+(?:These|This|The|They|It|For|In|As)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        return text.strip(
            " \t\r\n,;:."
        )

    # ================================================================
    # COMMENT RESULT
    # ================================================================

    def _make_result(
        self,
        display_name: str,
        profile_url: str,
        engagement: Dict[str, Any],
    ) -> Optional[CommentResult]:
        values = {
            "display_name": display_name,
            "name": display_name,
            "username": display_name,
            "title": display_name,
            "profile_url": profile_url,
            "post_url": profile_url,
            "url": profile_url,
            "source": "competitor_discovery",
            "platform": "competitors",
            "engagement": engagement,
            "metadata": engagement,
            "comment_text": "",
            "text": "",
            "content": "",
        }

        try:
            signature = inspect.signature(
                CommentResult
            )

            kwargs: Dict[str, Any] = {}

            for name, parameter in signature.parameters.items():
                if name == "self":
                    continue

                if parameter.kind not in {
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                }:
                    continue

                if name in values:
                    kwargs[name] = values[name]

                elif (
                    parameter.default
                    is inspect.Parameter.empty
                ):
                    logger.error(
                        "Unsupported required CommentResult field: %s",
                        name,
                    )
                    return None

            return CommentResult(
                **kwargs
            )

        except Exception as exc:
            logger.error(
                "CommentResult creation failed: %s",
                exc,
            )
            return None
    def _company_label(self, seed: str) -> str:
        """Return a readable company label from a domain or name."""
        domain = self._normalize_domain(seed)

        if domain:
            root = domain.split(".")[0]
            return " ".join(
                part.capitalize()
                for part in re.split(r"[-_]+", root)
                if part
            )

        value = str(seed or "").strip()
        return value

    def _clean_text(self, value: Any) -> str:
        """Normalize arbitrary text into a single clean string."""
        if value is None:
            return ""

        return re.sub(
            r"\s+",
            " ",
            str(value),
        ).strip()

    def _is_informational_title(self, title: str) -> bool:
        """Return True when a search result title is clearly informational."""
        text = str(title or "").strip().lower()

        if not text:
            return True

        informational_terms = (
            "what is ",
            "how to ",
            "guide",
            "comparison",
            " versus ",
            " vs ",
            "alternative",
            "alternatives",
            "competitor",
            "competitors",
            "review",
            "reviews",
            "directory",
            "list of ",
            "ranking",
            "rankings",
            "report",
            "article",
            "news",
            "blog",
        )

        return any(
            term in text
            for term in informational_terms
        )

    def _domain_score(self, candidate: str, domain: str) -> int:
        """Score how closely a candidate company name matches a domain."""
        candidate_tokens = self._tokens(
            self._normalize_name(candidate)
        )

        root = self._normalize_domain(domain).split(".")[0]
        root_tokens = self._tokens(
            root.replace("-", " ").replace("_", " ")
        )

        if not candidate_tokens or not root_tokens:
            return 0

        overlap = candidate_tokens & root_tokens

        if not overlap:
            return 0

        score = 35 * len(overlap)

        if candidate_tokens.issubset(root_tokens):
            score += 50
        elif root_tokens.issubset(candidate_tokens):
            score += 25

        return min(100, score)
