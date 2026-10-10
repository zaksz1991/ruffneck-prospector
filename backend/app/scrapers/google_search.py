"""
RuffNeck Prospector - Search Engine Lead Discovery

Discovers real people and businesses from public search results.

Rules:
- DDGS is primary; Google CSE and Bing are fallbacks.
- DDGS uses automatic/provider fallback instead of forcing DuckDuckGo.
- Reject jobs, marketplaces, directories, articles and informational pages.
- Prefer company homepages over internal pages.
- Deduplicate by registrable/root domain.
- Generic service pages are lower priority than company homepages.
- Discovery never generates or guesses email addresses.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from .base import CommentResult


logger = logging.getLogger(__name__)


class GoogleSearchScraper:

    GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
    BING_URL = "https://www.bing.com/search"

    BLOCKED_DOMAINS = {
        "google.com",
        "bing.com",
        "duckduckgo.com",
        "yahoo.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "youtube.com",
        "reddit.com",
        "indeed.com",
        "glassdoor.com",
        "myjobmag.com",
        "crossover.com",
        "jobgether.com",
        "himalayas.app",
        "bebee.com",
        "web3.career",
        "upwork.com",
        "fiverr.com",
        "freelancer.com",
        "toptal.com",
        "peopleperhour.com",
        "guru.com",
        "workana.com",
        "gomycode.com",
        "coursera.org",
        "udemy.com",
        "edx.org",
        "substack.com",
        "businessinsider.com",
        "restofworld.org",
        "themanifest.com",
        "topsoftwarecompanies.co",
        "clutch.co",
        "goodfirms.co",
        "goodtal.com",
        "tracxn.com",
        "statista.com",
        "rfpmart.com",
        "scribd.com",
        "startuplist.africa",
        "wellfound.com",
        "f6s.com",
        "techbehemoths.com",
        "readycontacts.com",
        "quora.com",
        "ssrn.com",
        "researchgate.net",
        "academia.edu",
        "wikipedia.org",
        "marketresearch.com",
        "neuralcatalog.com",
        "aibase.ng",
        "nairametrics.com",
        "papers.com.ng",
        "fundsforngos.org",
        "remoteok.com",
        "creativepool.com",
        "grokipedia.com",
        "theradar.ng",
        "sortlist.com",
        "jumia.com.ng",
        "jumia.com",
        "konga.com",
        "jiji.ng",
        "jiji.com",
        "etsy.com",
        "amazon.com",
        "amazon.co.uk",
        "ebay.com",
        "aliexpress.com",
        "fiverr.com",
        "upwork.com",
        "freelancer.com",
        "peopleperhour.com",
        "guru.com",
        "toptal.com",
        "contra.com",
    }

    MARKETPLACE_DOMAINS = {
        "jumia.com.ng",
        "jumia.com",
        "konga.com",
        "jiji.ng",
        "jiji.com",
        "etsy.com",
        "amazon.com",
        "amazon.co.uk",
        "ebay.com",
        "aliexpress.com",
        "fiverr.com",
        "upwork.com",
        "freelancer.com",
        "peopleperhour.com",
        "guru.com",
        "toptal.com",
        "contra.com",
    }

    SEARCH_ENGINE_DOMAINS = {
        "google.com",
        "bing.com",
        "duckduckgo.com",
        "yahoo.com",
    }

    JOB_PATH_MARKERS = {
        "/jobs/",
        "/job/",
        "/careers/",
        "/career/",
        "/vacancy/",
        "/vacancies/",
        "/employment/",
        "/apply/",
        "/positions/",
        "/position/",
        "/opportunities/",
        "/opportunity/",
        "/internship/",
        "/internships/",
        "/hiring/",
    }

    MARKETPLACE_PATH_MARKERS = {
        "/hire/",
        "/freelancers/",
        "/freelancer/",
        "/freelance/",
        "/marketplace/",
        "/talent/",
        "/talents/",
        "/profiles/",
        "/profile/",
        "/users/",
        "/user/",
        "/gigs/",
        "/gig/",
        "/projects/",
        "/project/",
        "/services-for-hire/",
    }

    DIRECTORY_PATH_MARKERS = {
        "/directory/",
        "/directories/",
        "/listing/",
        "/listings/",
        "/rankings/",
        "/ranking/",
        "/reviews/",
        "/review/",
        "/database/",
        "/databases/",
        "/explore/",
        "/startups/",
        "/startup/",
        "/companies/",
        "/company/",
        "/catalog/",
        "/catalogue/",
        "/vendors/",
        "/vendor/",
        "/providers/",
        "/provider/",
        "/firms/",
        "/firm/",
        "/agencies/",
        "/agency/",
        "/country/",
        "/countries/",
    }

    ARTICLE_PATH_MARKERS = {
        "/blog/",
        "/blogs/",
        "/article/",
        "/articles/",
        "/grant/",
        "/grants/",
        "/fund/",
        "/funds/",
        "/funding/",
        "/scholarship/",
        "/scholarships/",
        "/news/",
        "/stories/",
        "/story/",
        "/resources/",
        "/resource/",
        "/insights/",
        "/insight/",
        "/reports/",
        "/report/",
        "/research/",
        "/papers/",
        "/paper/",
        "/whitepaper/",
        "/whitepapers/",
        "/guides/",
        "/guide/",
        "/learn/",
        "/learning/",
        "/knowledge/",
        "/press/",
        "/media/",
        "/publications/",
        "/publication/",
        "/mentions/",
        "/mention/",
        "/author/",
        "/authors/",
        "/tag/",
        "/tags/",
        "/category/",
        "/categories/",
        "/topic/",
        "/topics/",
    }

    NON_PROSPECT_PATH_MARKERS = {
        "/search/",
        "/query/",
        "/results/",
        "/result/",
        "/feed/",
        "/feeds/",
        "/rss/",
        "/sitemap/",
        "/events/",
        "/event/",
        "/forum/",
        "/forums/",
        "/community/",
        "/communities/",
        "/questions/",
        "/question/",
        "/tools/",
        "/tool/",
        "/mentions/",
        "/mention/",
        "/author/",
        "/authors/",
        "/tag/",
        "/tags/",
        "/category/",
        "/categories/",
        "/topic/",
        "/topics/",
    }

    ARTICLE_SLUG_TERMS = {
        "business-plan",
        "how-to",
        "what-is",
        "what-are",
        "why-",
        "guide-",
        "tutorial",
        "review-",
        "best-",
        "top-",
        "list-of-",
        "market-report",
        "market-size",
        "market-analysis",
        "research-paper",
        "research-study",
        "case-study",
        "news-",
        "meet-",
        "apply-for-",
        "founder-left-",
        "second-time-founder",
        "startup-founders",
        "empower-",
        "funding-",
        "grant-",
        "million-",
        "billion-",
    }

    PROVIDER_TITLE_PATTERNS = (
        # Website / web development providers
        r"\bweb design\b.*\b(agency|company|studio|services?|solutions?)\b",
        r"\bweb design\b.*\b&\b.*\bseo\b",
        r"\bweb design\b.*\b&\b.*\bmarketing\b",
        r"\bweb development\b.*\b(agency|company|studio|services?|solutions?)\b",
        r"\bwebsite design\b.*\b(agency|company|studio|services?|solutions?)\b",
        r"\bwebsite development\b.*\b(agency|company|studio|services?|solutions?)\b",
        r"\bwebsite redesign\b.*\b(agency|company|studio|services?)\b",
        r"\bsoftware development\b.*\b(agency|company|studio|services?|solutions?)\b",
        r"\bcustom software\b.*\b(development|solutions?)\b",
        r"\bcustom web\b.*\b(development|design|solutions?)\b",
        r"\bweb\s*&\s*app\b.*\b(development|design|solutions?)\b",
        r"\bweb\s+and\s+app\b.*\b(development|design|solutions?)\b",
        r"\bweb solutions?\b",
        r"\bwebsite solutions?\b",
        r"\bweb services?\b",
        r"\bwebsite maintenance\b",
        r"\bwebsite hosting\b",
        r"\bweb hosting\b",
        r"\bwebsite builder\b",
        r"\bweb developer\b",
        r"\bweb designer\b",
        r"\bwebsite designer\b",
        r"\bfrontend developer\b",
        r"\bfront-end developer\b",
        r"\bui/ux designer\b",
        r"\bui/ux developer\b",

        # Explicit provider/agency identity
        r"\b(web|website|software|digital|creative|design|branding|marketing)\b.*\bagenc(y|ies)\b",
        r"\b(web|website|software|digital|creative|design|branding|marketing)\b.*\bcompany\b",
        r"\b(web|website|software|digital|creative|design|branding|marketing)\b.*\bstudio\b",
        r"\bdigital agency\b",
        r"\bdigital services?\b.*\b(company|agency|provider)\b",
        r"\bsolutions?\s+provider\b",
        r"\btechnology solutions?\b.*\b(provider|company|agency)\b",

        # Marketing / design providers
        r"\bdigital marketing agency\b",
        r"\bsocial media agency\b",
        r"\bsocial media marketing agency\b",
        r"\bgraphic design agency\b",
        r"\bbranding agency\b",
        r"\bcreative agency\b",
        r"\bseo agency\b",
        r"\bseo company\b",

        # AI / consulting providers
        r"\bai consulting\b",
        r"\bai consultant\b",
        r"\bai solutions?\b.*\b(provider|company|agency)\b",
        r"\bai automation\b.*\b(company|agency|solutions?)\b",
        r"\bdigital transformation\b.*\b(company|agency|consulting|solutions?)\b",
        r"\bautomation\b.*\b(ai|solutions?)\b.*\b(company|agency|provider)\b",
        r"\bconsulting services\b",
        r"\bconsulting company\b",
        r"\bconsultancy\b",

        # Recruitment / HR providers
        r"\brecruitment agency\b",
        r"\bstaffing agency\b",
        r"\bhr consultancy\b",
        r"\bhr consulting\b",
        r"\bexecutive search\b",
        r"\brecruitment\b.*\b(agency|company|services?)\b",

        # CV / career service providers
        r"\bcv writing\b",
        r"\bresume writing\b",
        r"\bcareer services?\b",
        r"\bcv writer\b",
        r"\bresume writer\b",

        # Strong portfolio/provider signals
        r"\bportfolio\b",
        r"\bservices?\b.*\b(web design|web development|graphic design|digital marketing)\b",

        # Common exact provider titles
        r"^website design$",
        r"^web design$",
        r"^website development$",
        r"^web design nigeria$",
        r"^website developer nigeria$",
        r"^nigeria web design company\b",
        r"^best web designers? in nigeria\b",
        r"^best web app development company\b",
    )

    NON_PROSPECT_TITLE_PATTERNS = (
          r"^pdf\s+request for (?:proposal|proposals)\b",
        r"\bjob(s)?\b",
        r"\bcareer(s)?\b",
        r"\bvacanc(y|ies)\b",
        r"\bhiring\b",
        r"\bapply now\b",
        r"\binternship(s)?\b",
        r"\bfreelance job(s)?\b",
        r"\bremote job(s)?\b",
        r"\bmarket forecast\b",
        r"\bmarket size\b",
        r"\bmarket report\b",
        r"\bindustry report\b",
        r"\bresearch paper\b",
        r"\bacademic paper\b",
        r"\bwhite ?paper\b",
        r"\bcase study\b",
        r"\bhow to\b",
        r"\bwhat is\b",
        r"\bwhat are\b",
        r"\bhow does\b",
        r"\bhow do\b",
        r"\bguide to\b",
        r"\bcomplete guide\b",
        r"\btutorial\b",
        r"\bcourse(s)?\b",
        r"\bbootcamp\b",
        r"\btraining\b",
        r"\bwebinar\b",
        r"\bnews\b",
        r"\barticle(s)?\b",
        r"\breport(s)?\b",
        r"\bstud(y|ies)\b",
        r"\bstatistics\b",
        r"\bmarket research\b",
        r"\blist of\b",
        r"\btop \d+\b",
        r"\bbest \d+\b",
        r"\bbest companies\b",
        r"\blist of companies\b",
        r"\bwhich companies\b",
        r"\bcompanies in\b",
        r"\btop ai companies\b",
        r"\bstartup with\b",
        r"\btop entrepreneurs\b",
        r"\bhire the best\b",
        r"\bfind the best\b",
        r"\bmarketplace\b",
        r"\bservices for hire\b",
        r"\bsearch results\b",
        r"\bdirectory\b",
        r"\bmentions\b",
        r"\bapply for\b",
        r"\bgrant(s)?\b",
        r"\bfunding\b",
        r"\bmeet \d+\b",
        r"\bstartup founders\b",
        r"\bthis .* founder\b",
        r"\bfounder left\b",
        r"\bempower\b",
        r"\b\d+ million\b",
        r"\b\d+ billion\b",
    )

    BUYING_INTENT_PHRASES = (
        "looking for",
        "looking to",
        "need a ",
        "need an ",
        "need help",
        "seeking",
        "in need of",
        "outsource",
        "outsourcing",
        "request for proposal",
        "rfp",
        "vendor needed",
        "service provider needed",
        "want to hire",
        "partner needed",
        "implementation partner",
    )

    SERVICE_PROVIDER_PHRASES = (
        "web design agency",
        "web design company",
        "website design company",
        "website development company",
        "graphic design agency",
        "branding agency",
        "digital marketing agency",
        "social media agency",
        "seo agency",
        "recruitment agency",
        "staffing agency",
        "hr consultancy",
        "hr consulting",
        "consulting company",
        "consulting services",
        "cv writing",
        "resume writing",
        "web developer",
        "website developer",
        "graphic designer",
        "ai consultant",
        "ai consulting",
        "ai consulting services",
        "outsourcing services",
        "business support services",
        "software development company",
        "it support company",
        "technology consulting",
        "data analytics consulting",
    )

    INFORMATIONAL_PHRASES = (
        "what is",
        "what are",
        "how to",
        "how does",
        "how do",
        "meaning of",
        "definition of",
        "tutorial",
        "research paper",
        "research study",
        "market forecast",
        "market report",
        "market size",
        "industry report",
        "case study",
        "list of companies",
        "best companies",
        "top companies",
        "which companies",
        "challenges and opportunities",
        "legal framework",
        "regulation",
        "regulating",
    )

    PERSON_SIGNALS = (
        "founder",
        "co-founder",
        "cofounder",
        "ceo",
        "chief executive",
        "director",
        "developer",
        "engineer",
        "designer",
        "consultant",
        "advisor",
        "architect",
        "manager",
        "specialist",
        "professional",
        "entrepreneur",
        "data scientist",
        "data analyst",
        "software engineer",
        "technology professional",
    )

    BUSINESS_SIGNALS = (
        "company",
        "consulting",
        "consultancy",
        "agency",
        "solutions",
        "technologies",
        "technology",
        "software",
        "digital",
        "services",
        "platform",
        "products",
        "artificial intelligence",
        "ai company",
        "ai solutions",
        "machine learning",
        "automation",
        "laboratory",
        "labs",
        "studio",
        "systems",
        "robotics",
        "innovation",
        "development",
          "digital transformation center",
          "digital transformation centre",
          "official website",
        "development company",
    )

    ORGANIZATION_SIGNALS = (
        "about us",
        "about",
        "our company",
        "our team",
        "our mission",
        "our vision",
        "contact us",
        "contact",
        "services",
        "solutions",
        "products",
        "portfolio",
        "technology",
        "technologies",
        "software",
        "platform",
        "innovation",
        "artificial intelligence",
        "machine learning",
        "robotics",
        "automation",
        "data",
        "digital",
        "engineering",
        "development",
        "consulting",
        "company",
        "organization",
        "enterprise",
        "startup",
        "laboratory",
        "laboratories",
        "labs",
        "africa",
        "nigeria",
    )

    STRONG_ORGANIZATION_SIGNALS = (
        "about us",
        "our company",
        "our team",
        "our mission",
        "our vision",
        "contact us",
        "company",
        "limited",
        "ltd",
        "llc",
        "inc",
        "technologies",
        "technology",
        "solutions",
        "artificial intelligence",
        "machine learning",
        "robotics",
        "software",
        "platform",
        "laboratory",
        "labs",
        "innovation",
        "engineering",
        "development",
    )

    GENERIC_SERVICE_PATHS = {
        "/services/",
        "/service/",
        "/solutions/",
        "/solution/",
        "/consulting/",
        "/consultancy/",
    }

    SERVICE_TITLE_PATTERNS = (
        r"^ai consulting services?$",
        r"^artificial intelligence consulting$",
        r"^ai consulting$",
        r"^consulting services?$",
        r"^digital marketing services?$",
        r"^web design services?$",
        r"^website development services?$",
        r"^graphic design services?$",
        r"^artificial intelligence services?$",
        r"^ai services?$",
        r"^ai solutions?$",
    )

    GENERIC_TITLES = {
        "ai",
        "artificial intelligence",
        "ai consultant",
        "ai consultants",
        "ai consulting",
        "ai consulting services",
        "artificial intelligence consulting",
        "ai engineer",
        "ai engineers",
        "ai engineering",
        "certified ai consultant",
        "certified artificial intelligence consultant",
        "company",
        "search results",
        "services",
        "solutions",
        "consulting services",
        "consultant",
        "consultants",
        "ai companies",
    }

    MULTI_PART_SUFFIXES = {
        "co.uk",
        "org.uk",
        "ac.uk",
        "com.ng",
        "org.ng",
        "net.ng",
        "gov.ng",
        "edu.ng",
        "com.au",
        "net.au",
        "org.au",
        "co.za",
        "org.za",
        "co.ke",
        "or.ke",
        "co.in",
        "firm.in",
    }

    def __init__(
        self,
        max_results: int = 20,
        timeout: int = 8,
    ):
        self.max_results = max(
            1,
            int(max_results),
        )

        self.timeout = max(
            1,
            int(timeout),
        )

        self.google_api_key = os.getenv(
            "GOOGLE_CSE_API_KEY",
            "",
        ).strip()

        self.google_cx = os.getenv(
            "GOOGLE_CSE_CX",
            "",
        ).strip()

        self.bing_api_key = os.getenv(
            "BING_API_KEY",
            "",
        ).strip()

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/142.0 Safari/537.36"
            )
        })

    # ============================================================
    # SEARCH
    # ============================================================

    def _search(
        self,
        query: str,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        limit = max_results or self.max_results

        # Primary: DDGS
        results = self._via_ddgs(
            query,
            limit,
        )

        if results:
            return results

        # Fallback: Google CSE
        results = self._via_google_cse(
            query,
            limit,
        )

        if results:
            return results

        # Fallback: Bing
        return self._via_bing(
            query,
            limit,
        )

    def _via_ddgs(
        self,
        query: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """
        Search DDGS providers independently.

        One backend failure or empty response must never discard
        successful results from other backends.
        """

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from ddgs import DDGS
        except ImportError:
            logger.warning("DDGS package is not installed.")
            return []

        requested = min(max(int(max_results), 5), 15)

        # Limit default provider fan-out to reduce slow discovery runs.
        default_backends = (
            "yahoo",
            "duckduckgo",
        )

        configured_backends = os.getenv(
            "DDGS_BACKENDS",
            "",
        ).strip()

        # Treat "auto" as the configured request to use the complete
        # provider fallback set, rather than passing the literal backend
        # name "auto" to DDGS.
        if configured_backends.lower() in {
            "",
            "auto",
            "default",
            "defaults",
        }:
            backends = default_backends
        else:
            backends = tuple(
                dict.fromkeys(
                    backend.strip().lower()
                    for backend in configured_backends.split(",")
                    if backend.strip()
                )
            )

        if not backends:
            logger.warning("No DDGS backends configured.")
            return []

        def search_backend(backend: str) -> Dict[str, Any]:
            result = {
                "backend": backend,
                "status": "failed",
                "results": [],
                "error": "",
            }

            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    raw_results = list(
                        ddgs.text(
                            query=query,
                            max_results=requested,
                            backend=backend,
                        )
                    )

                if not raw_results:
                    result["status"] = "empty"
                    return result

                output: List[Dict[str, Any]] = []

                for item in raw_results:
                    if not isinstance(item, dict):
                        continue

                    title = (
                        item.get("title", "")
                        or ""
                    )

                    href = (
                        item.get("href", "")
                        or item.get("url", "")
                        or ""
                    )

                    body = (
                        item.get("body", "")
                        or item.get("snippet", "")
                        or ""
                    )

                    if not href:
                        continue

                    output.append(
                        {
                            "title": title,
                            "href": href,
                            "body": body,
                            "source": f"ddgs:{backend}",
                        }
                    )

                if output:
                    result["status"] = "success"
                    result["results"] = output
                else:
                    result["status"] = "empty"

            except Exception as exc:
                result["status"] = "failed"
                result["error"] = str(exc)

            return result

        backend_results: Dict[str, Dict[str, Any]] = {}

        if len(backends) == 1:
            backend = backends[0]
            backend_results[backend] = search_backend(backend)
        else:
            with ThreadPoolExecutor(
                max_workers=min(len(backends), 7)
            ) as executor:

                futures = {
                    executor.submit(
                        search_backend,
                        backend,
                    ): backend
                    for backend in backends
                }

                for future in as_completed(futures):
                    backend = futures[future]

                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {
                            "backend": backend,
                            "status": "failed",
                            "results": [],
                            "error": str(exc),
                        }

                    backend_results[backend] = result

        aggregated: List[Dict[str, Any]] = []

        successful_backends = []
        empty_backends = []
        failed_backends = []

        # Preserve deterministic backend order.
        for backend in backends:
            result = backend_results.get(
                backend,
                {
                    "backend": backend,
                    "status": "failed",
                    "results": [],
                    "error": "No backend result returned.",
                },
            )

            status = result.get("status", "failed")

            if status == "success":
                successful_backends.append(backend)
                aggregated.extend(
                    result.get("results", [])
                )

            elif status == "empty":
                empty_backends.append(backend)

            else:
                failed_backends.append(backend)

                logger.warning(
                    "DDGS backend failed [%s] for query [%s]: %s",
                    backend,
                    query,
                    result.get(
                        "error",
                        "unknown error",
                    ),
                )

        deduplicated = self._deduplicate_results(
            aggregated
        )

        deduplicated = deduplicated[:requested]

        logger.info(
            (
                "DDGS search completed: query=%r "
                "successful=%s empty=%s failed=%s "
                "raw=%d unique=%d"
            ),
            query,
            successful_backends,
            empty_backends,
            failed_backends,
            len(aggregated),
            len(deduplicated),
        )

        if not successful_backends:
            if failed_backends:
                logger.warning(
                    "No DDGS backend produced usable results for query: %s",
                    query,
                )
            else:
                logger.debug(
                    "All DDGS backends returned no results for query: %s",
                    query,
                )
            return []

        if len(successful_backends) < len(backends):
            logger.info(
                (
                    "DDGS returned partial results for query=%r: "
                    "%d/%d backends produced results."
                ),
                query,
                len(successful_backends),
                len(backends),
            )

        return deduplicated

    def _via_google_cse(
        self,
        query: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:

        if not self.google_api_key:
            return []

        if not self.google_cx:
            return []

        try:

            response = self.session.get(
                self.GOOGLE_CSE_URL,
                params={
                    "key": self.google_api_key,
                    "cx": self.google_cx,
                    "q": query,
                    "num": min(
                        max_results,
                        10,
                    ),
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            data = response.json()

            items = data.get(
                "items",
                [],
            )

            if not isinstance(
                items,
                list,
            ):
                return []

            return [
                {
                    "title": item.get(
                        "title",
                        "",
                    ),
                    "href": item.get(
                        "link",
                        "",
                    ),
                    "body": item.get(
                        "snippet",
                        "",
                    ),
                    "source": "google_cse",
                }
                for item in items
                if isinstance(
                    item,
                    dict,
                )
            ]

        except Exception as exc:

            logger.warning(
                "Google CSE search failed: %s",
                exc,
            )

            return []

    def _via_bing(
        self,
        query: str,
        max_results: int,
    ) -> List[Dict[str, Any]]:

        if not self.bing_api_key:
            return []

        try:

            response = self.session.get(
                self.BING_URL,
                params={
                    "q": query,
                    "count": min(
                        max_results,
                        50,
                    ),
                },
                headers={
                    "Ocp-Apim-Subscription-Key":
                        self.bing_api_key,
                },
                timeout=self.timeout,
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if "json" not in content_type:
                return []

            data = response.json()

            web_pages = data.get(
                "webPages",
                {},
            )

            if not isinstance(
                web_pages,
                dict,
            ):
                return []

            values = web_pages.get(
                "value",
                [],
            )

            if not isinstance(
                values,
                list,
            ):
                return []

            return [
                {
                    "title": item.get(
                        "name",
                        "",
                    ),
                    "href": item.get(
                        "url",
                        "",
                    ),
                    "body": item.get(
                        "snippet",
                        "",
                    ),
                    "source": "bing",
                }
                for item in values
                if isinstance(
                    item,
                    dict,
                )
            ]

        except Exception as exc:

            logger.warning(
                "Bing search failed: %s",
                exc,
            )

            return []

    # ============================================================
    # SERVICE LEADS
    # ============================================================

    def search_service_leads(
        self,
        service: str,
        location: str = "Nigeria",
        extra_keywords: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        max_queries: Optional[int] = None,
    ) -> List[CommentResult]:
        """
        Discover service leads using two distinct tracks:

        1. organization discovery
           - find real organizations
           - reject organizations selling the requested service

        2. opportunity discovery
           - find procurement/project pages
           - extract the original issuer
           - keep the source page as evidence
           - never treat the publishing site as the prospect
        """
        limit = max_results or self.max_results

        service_key = re.sub(
            r"[^a-z0-9]+",
            "_",
            str(service or "").lower(),
        ).strip("_")

        queries = self._service_queries(
            service,
            location,
            extra_keywords=extra_keywords or [],
        )

        organization_candidates = []
        opportunity_candidates = []

        if max_queries is not None:
            queries = queries[:max_queries]

        for query in queries:
            try:
                results = self._search(
                    query,
                    max_results=max(
                        limit * 2,
                        10,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Service discovery search failed for %r: %s",
                    query,
                    exc,
                )
                continue

            query_is_opportunity = self._is_opportunity_query(
                query
            )

            for result in results or []:
                if not isinstance(result, dict):
                    continue

                result = dict(result)

                result["search_query"] = query

                title = self._clean_text(
                    result.get("title", "")
                )
                snippet = self._clean_text(
                    result.get("body", "")
                )

                url = self._unwrap_url(
                    result.get("href", "")
                )

                if not url:
                    continue

                domain = self._domain_from_url(url)

                if not domain:
                    continue

                result["href"] = url
                result["domain"] = domain

                # Reject jobs, directories, marketplaces, articles, and other
                # obvious non-prospects before deciding which discovery track
                # the result belongs to. This prevents procurement query terms
                # from promoting a job or directory page into an opportunity.
                opportunity_path = urlparse(url).path

                if self._is_obvious_non_prospect(
                    title,
                    snippet,
                    opportunity_path,
                    domain,
                ):
                    continue

                # Procurement queries provide opportunity context, but the
                # result must still contain evidence for the requested service.
                # Ordinary non-procurement queries do not promote arbitrary
                # pages into the opportunity track.
                opportunity_query = (
                    query
                    if query_is_opportunity
                    else ""
                )

                is_opportunity = self._is_opportunity_result(
                    opportunity_query,
                    title,
                    snippet,
                )

                if is_opportunity:
                    # buying_intent targets Nigeria; reject foreign opportunity pages
                    # that contain no Nigerian location evidence.
                    if location.strip().lower() == "nigeria":
                        location_text_evidence = (
                            f"{title} {snippet}"
                        ).lower()

                        nigeria_text_signals = (
                            "nigeria",
                            "nigerian",
                            "lagos",
                            "abuja",
                            "kano",
                            "ibadan",
                            "port harcourt",
                            "benin city",
                            "enugu",
                            "kaduna",
                            "jos",
                            "calabar",
                            "ilorin",
                            "maiduguri",
                            "owerri",
                            "onitsha",
                        )

                        nigeria_domain_signal = (
                            domain.lower() == "ng"
                            or domain.lower().endswith(".ng")
                        )

                        verified_nigerian_domains = {
                            "paradigmhq.org",
                        }

                        has_verified_nigerian_domain = (
                            domain in verified_nigerian_domains
                            or any(
                                domain.endswith(
                                    "." + verified_domain
                                )
                                for verified_domain in verified_nigerian_domains
                            )
                        )

                        if (
                            not any(
                                signal in location_text_evidence
                                for signal in nigeria_text_signals
                            )
                            and not nigeria_domain_signal
                            and not has_verified_nigerian_domain
                        ):
                            continue

                    # Opportunity sources are evidence pages, but obvious
                    # procurement aggregators and blocked content domains
                    # must never become prospect records.
                    opportunity_path = urlparse(url).path
                    opportunity_text = f"{title} {snippet} {opportunity_path}".lower()

                    # Keep only opportunities that actually concern the
                    # requested service.
                    service_opportunity_signals = {
                        "website": (
                            "website",
                            "web design",
                            "web development",
                            "web developer",
                            "web designer",
                            "website redesign",
                            "website redevelopment",
                            "website development",
                            "website design",
                        ),
                        "digital_marketing": (
                            "digital marketing",
                            "digital marketing services",
                            "social media marketing",
                            "social media management",
                            "seo services",
                            "seo",
                            "online marketing",
                            "content marketing",
                            "marketing services",
                        ),
                    }

                    required_service_signals = service_opportunity_signals.get(
                        service_key
                    )

                    if (
                        required_service_signals
                        and not any(
                            signal in opportunity_text
                            for signal in required_service_signals
                        )
                    ):
                        continue

                    # A generic homepage is not itself an opportunity simply
                    # because its snippet mentions procurement language.
                    if self._page_type(url) == "homepage":
                        opportunity_title_path = (
                            f"{title} {opportunity_path}"
                        ).lower()

                        explicit_opportunity_markers = (
                            "request for proposal",
                            "request for proposals",
                            "request for quotation",
                            "request for expressions of interest",
                            "expression of interest",
                            "call for proposals",
                            "invitation to bid",
                            "terms of reference",
                            "tender",
                            "rfp",
                            "rfq",
                            "eoi",
                        )

                        if not any(
                            marker in opportunity_title_path
                            for marker in explicit_opportunity_markers
                        ):
                            continue
                    has_procurement_language = re.search(
                        r"\b(?:rfp|request for proposals?|request for quotations?|request for expressions? of interest|expression of interest|terms of reference|invitation to bid)\b",
                        opportunity_text,
                        re.IGNORECASE,
                    )
                    has_template_or_instruction_language = re.search(
                        r"\b(?:template|templates|sample|samples|what is|how to|guide|tutorial)\b",
                        opportunity_text,
                        re.IGNORECASE,
                    )
                    if has_procurement_language and has_template_or_instruction_language:
                        continue


                    if not self._is_allowed_domain(domain):
                        continue
                    opportunity_hostname = (
                        urlparse(url).hostname
                        or domain
                    ).lower().removeprefix("www.")
                    if (
                        opportunity_hostname == "tender.ng"
                        and opportunity_path.rstrip("/") == ""
                    ):
                        continue


                    if self._is_obvious_non_prospect(
                        title,
                        snippet,
                        opportunity_path,
                        domain,
                    ):
                        continue

                    # Procurement aggregators, intelligence platforms, and
                    # tender-search portals are evidence sources, not buyers.
                    # Reject them before issuer extraction so their own
                    # brand/title cannot become original_issuer.
                    blocked_opportunity_source_domains = {
                        "highergov.com",
                        "govtribe.com",
                        "bidbanana.com",
                        "ungm.org",
                        "globaltenders.com",
                        "tendersinfo.com",
                        "bidassist.com",
                        "tenderimpulse.com",
                        "biddetail.com",
                        "tendersontime.com",
                        "nigeriantenders.com",
                        "nigeriatenders.com",
                        "thebiddaily.com",
                        "etenders.com.ng",
                        "ebid.com.ng",
                        "app.tendersgo.com",
                        "folyo.me",
                    }

                    normalized_opportunity_domain = (
                        domain.lower()
                        .removeprefix("www.")
                        .strip(".")
                    )

                    if (
                        normalized_opportunity_domain
                        in blocked_opportunity_source_domains
                        or any(
                            normalized_opportunity_domain.endswith(
                                "." + blocked_domain
                            )
                            for blocked_domain
                            in blocked_opportunity_source_domains
                        )
                    ):
                        continue

                    if re.search(r"\bidice\b", url, re.IGNORECASE):
                        issuer = "Bank of Industry"
                    else:
                        issuer = self._extract_opportunity_issuer(
                            title,
                            snippet,
                        )

                    # Some genuine procurement PDFs expose only the
                    # procurement title and the issuer's own domain.
                    # Use the hosting root domain as a conservative fallback
                    # only for explicit procurement documents.
                    if (
                        not issuer
                        and service_key == "buying_intent"
                        and re.search(
                            r"\.(?:pdf|doc|docx|ppt|pptx|xls|xlsx)$",
                            opportunity_path,
                            re.IGNORECASE,
                        )
                        and re.search(
                            r"\b(?:rfp|rfq|rft|itt|itb|"
                            r"request for proposals?|"
                            r"request for quotations?|"
                            r"request for expressions? of interest|"
                            r"expression of interest|"
                            r"terms of reference|"
                            r"invitation to bid|"
                            r"call for proposals)\b",
                            f"{title} {snippet}",
                            re.IGNORECASE,
                        )
                    ):
                        issuer_domain = (
                            domain
                            .lower()
                            .removeprefix("www.")
                            .strip(".")
                        )
                        issuer_candidate = issuer_domain.split(".")[0]

                        if self._looks_like_issuer_name(
                            issuer_candidate
                        ):
                            issuer = issuer_candidate.upper()

                    # Procurement platforms are evidence sources,
                    # not buyers. Keep their pages only when a distinct
                    # issuer has been identified.
                    source_platform_issuer_aliases = {
                        "ungm.org": {
                            "ungm",
                            "united nations global marketplace",
                        },
                    }

                    normalized_issuer = re.sub(
                        r"[^a-z0-9]+",
                        " ",
                        (issuer or "").lower(),
                    ).strip()

                    platform_aliases = (
                        source_platform_issuer_aliases.get(
                            domain.lower(),
                            set(),
                        )
                    )

                    if (
                        platform_aliases
                        and normalized_issuer in platform_aliases
                    ):
                        issuer = None

                    if not issuer:
                        continue

                    result["discovery_type"] = "opportunity"
                    result["original_issuer"] = issuer
                    result["source_url"] = url
                    result["source_domain"] = domain

                    opportunity_candidates.append(result)
                    continue
                # Nigerian service discovery should not return foreign
                # organizations unless the result itself contains Nigerian
                # location evidence.
                if location.strip().lower() == "nigeria":
                    nigeria_text_evidence = (
                        f"{title} {snippet}"
                    ).lower()

                    nigeria_text_signals = (
                        "nigeria",
                        "nigerian",
                        "lagos",
                        "abuja",
                        "kano",
                        "ibadan",
                        "port harcourt",
                        "benin city",
                        "enugu",
                        "kaduna",
                        "jos",
                        "calabar",
                        "ilorin",
                        "maiduguri",
                        "owerri",
                        "onitsha",
                    )

                    nigeria_domain_signal = (
                        domain.lower() == "ng"
                        or domain.lower().endswith(".ng")
                    )

                    if (
                        not any(
                            signal in nigeria_text_evidence
                            for signal in nigeria_text_signals
                        )
                        and not nigeria_domain_signal
                    ):
                        continue

                # Organization track uses the normal prospect safeguards.
                # Require evidence that the page is actually relevant to the
                # requested service before allowing it into the organization
                # candidate pool.
                service_relevance_signals = {
                    "website": (
                        "website",
                        "web design",
                        "web development",
                        "web developer",
                        "web designer",
                    ),
                    "digital_marketing": (
                        "digital marketing",
                        "social media marketing",
                        "social media management",
                        "seo",
                        "online marketing",
                        "content marketing",
                        "marketing services",
                        "marketing agency",
                    ),
                    "ai_solution": (
                        "artificial intelligence",
                        "machine learning",
                        "ai automation",
                        "ai-powered",
                        "ai solution",
                        "ai solutions",
                        "ai technology",
                        "automation",
                    ),
                    "graphics": (
                        "graphic design",
                        "branding",
                        "brand identity",
                        "brand strategy",
                        "creative agency",
                        "creative studio",
                        "printing",
                        "packaging design",
                    ),
                    "excel": (
                        "excel",
                        "spreadsheet",
                        "dashboard",
                        "reporting",
                        "business intelligence",
                        "data analysis",
                        "data analytics",
                    ),
                    "software_app": (
                        "software",
                        "application",
                        "app development",
                        "mobile app",
                        "custom software",
                    ),
                    "ai_automation": (
                        "automation",
                        "workflow automation",
                        "business automation",
                        "process automation",
                    ),
                    "ai_data_annotation": (
                        "data annotation",
                        "data labeling",
                        "data labelling",
                        "ai evaluation",
                        "model evaluation",
                    ),
                    "ai_content_writing": (
                        "content writing",
                        "technical writing",
                        "copywriting",
                        "content development",
                        "AI content",
                    ),
                    "ai_video_creation": (
                        "video creation",
                        "video production",
                        "video editing",
                        "AI video",
                    ),
                    "ai_training": (
                        "AI training",
                        "digital training",
                        "technology training",
                        "AI literacy",
                        "AI fluency",
                    ),
                    "it_support": (
                        "IT support",
                        "technical support",
                        "IT services",
                        "computer support",
                    ),
                    "computer_setup": (
                        "computer setup",
                        "computer installation",
                        "computer repair",
                        "computer maintenance",
                    ),
                    "microsoft_office": (
                        "Microsoft Office",
                        "Excel",
                        "Word",
                        "PowerPoint",
                        "Google Sheets",
                        "spreadsheet",
                    ),
                    "network_support": (
                        "network",
                        "WiFi",
                        "Wi-Fi",
                        "printer support",
                        "network installation",
                    ),
                    "web_hosting": (
                        "web hosting",
                        "domain",
                        "website maintenance",
                        "website support",
                    ),
                    "ecommerce": (
                        "ecommerce",
                        "e-commerce",
                        "online store",
                        "Shopify",
                        "WooCommerce",
                    ),
                    "social_media_management": (
                        "social media management",
                        "social media manager",
                        "social media marketing",
                        "social media services",
                    ),
                    "content_creation": (
                        "content creation",
                        "content creator",
                        "content production",
                        "creative content",
                    ),
                    "data_management": (
                        "data management",
                        "data analysis",
                        "data analytics",
                        "data management services",
                    ),
                    "data_entry": (
                        "data entry",
                        "data processing",
                        "data capture",
                    ),
                    "transcription": (
                        "transcription",
                        "audio transcription",
                        "transcription services",
                        "transcriptionist",
                    ),
                    "virtual_assistant": (
                        "virtual assistant",
                        "virtual assistance",
                        "administrative support",
                        "admin support",
                    ),
                    "business_operations": (
                        "business operations",
                        "operations support",
                        "operations management",
                        "business process",
                    ),
                    "customer_support": (
                        "customer support",
                        "customer service",
                        "customer care",
                        "call center",
                    ),
                    "used_items": (
                        "used item",
                        "used items",
                        "used goods",
                        "second hand",
                        "second-hand",
                        "secondhand",
                        "fairly used",
                        "fairly-used",
                        "pre-owned",
                        "preowned",
                        "foreign used",
                        "uk used",
                        "tokunbo",
                        "used equipment",
                        "used electronics",
                        "used furniture",
                        "used appliances",
                        "used phone",
                        "used phones",
                        "used laptop",
                        "used laptops",
                        "used tv",
                        "used television",
                        "ina neman",
                        "ina so in saya",
                        "wa ke sayar",
                        "kayan da aka yi amfani da su",
                        "kayan hannu na biyu",
                        "i dey find",
                        "i wan buy",
                        "who get",
                        "who dey sell",
                        "where i fit buy",
                    ),
                    "sales_lead_generation": (
                        "lead generation",
                        "sales outsourcing",
                        "sales support",
                        "business development",
                        "sales consultant",
                        "customer acquisition",
                    ),
                    "herbal_islamic_medicine": (
                        "herbal medicine",
                        "herbal products",
                        "traditional medicine",
                        "Islamic medicine",
                        "prophetic medicine",
                        "ruqyah",
                        "hijama",
                    ),
                    "logistics_warehousing": (
                        "logistics",
                        "warehousing",
                        "warehouse",
                        "supply chain",
                        "distribution",
                    ),
                }

                required_service_signals = service_relevance_signals.get(
                    service_key
                )

                if (
                    required_service_signals
                    and not any(
                        signal in f"{title} {snippet}".lower()
                        for signal in required_service_signals
                    )
                ):
                    continue

                # buying_intent spans multiple service categories. Reuse the
                # existing provider classifier for each underlying category.
                if service_key == "buying_intent":
                    provider_services = (
                        "website",
                        "digital_marketing",
                        "ai_solution",
                        "graphics",
                        "excel",
                        "cv_resume",
                        "resume_writing",
                    )
                    if any(
                        self._is_service_provider_result(
                            provider_service,
                            title,
                            snippet,
                            domain,
                        )
                        for provider_service in provider_services
                    ):
                        continue
                elif self._is_service_provider_result(
                    service,
                    title,
                    snippet,
                    domain,
                ):
                    continue

                if service_key == "buying_intent":
                    buyer_text = f"{title} {snippet}".lower()
                    buyer_signals = (
                        "looking for",
                        "looking to hire",
                        "seeking",
                        "need a website",
                        "needs a website",
                        "website redesign",
                        "website redevelopment",
                        "website rebuild",
                        "website upgrade",
                        "request for proposal",
                        "request for proposals",
                        "request for quotation",
                        "request for expression of interest",
                        "request for expressions of interest",
                        "expression of interest",
                        "terms of reference",
                        "invitation to bid",
                        "call for proposals",
                        "rfp",
                        "rfq",
                    )
                    if not any(signal in buyer_text for signal in buyer_signals):
                        continue

                score = self._prospect_score(result)

                if not self._is_prospect_candidate(
                    result,
                    score,
                ):
                    continue

                result["discovery_type"] = "organization"
                result["prospect_score"] = score

                organization_candidates.append(result)

        selected = []

        # --------------------------------------------------------
        # Organization track: one prospect per root domain.
        # --------------------------------------------------------
        selected_by_domain = {}

        organization_candidates.sort(
            key=lambda item: (
                item.get("prospect_score", 0),
                self._page_priority(
                    item.get("href", "")
                ),
            ),
            reverse=True,
        )

        for result in organization_candidates:
            url = result.get("href", "")

            root_domain = self._domain_from_url(url)

            if not root_domain:
                continue

            if root_domain in selected_by_domain:
                continue

            selected_by_domain[root_domain] = result
            selected.append(result)

            if len(selected) >= limit:
                break

        # --------------------------------------------------------
        # Opportunity track: one opportunity per issuer.
        # The source domain is NOT used as the prospect identity.
        # --------------------------------------------------------
        seen_issuers = set()

        for result in opportunity_candidates:
            issuer = (
                result.get("original_issuer")
                or ""
            ).strip()

            issuer_key = re.sub(
                r"[^a-z0-9]+",
                " ",
                issuer.lower(),
            ).strip()

            if not issuer_key:
                continue

            if issuer_key in seen_issuers:
                continue

            seen_issuers.add(issuer_key)

            result["prospect_score"] = max(
                self._prospect_score(result),
                60,
            )

            selected.append(result)

            if len(selected) >= limit:
                break

        # --------------------------------------------------------
        # Convert both tracks into the existing CommentResult shape.
        # --------------------------------------------------------
        comments = []

        for result in selected[:limit]:
            title = self._clean_text(
                result.get("title", "")
            )
            snippet = self._clean_text(
                result.get("body", "")
            )
            url = result.get("href", "")

            discovery_type = result.get(
                "discovery_type",
                "organization",
            )

            if discovery_type == "opportunity":
                display_name = result.get(
                    "original_issuer"
                ) or self._display_name(
                    title,
                    url,
                )

                source_url = result.get(
                    "source_url"
                ) or url

                engagement = {
                    "source": "google_search",
                    "discovery_type": "opportunity",
                    "original_issuer": display_name,
                    "source_url": source_url,
                    "source_domain": result.get(
                        "source_domain"
                    ),
                    "search_query": result.get(
                        "search_query"
                    ),
                    "score": result.get(
                        "prospect_score",
                        0,
                    ),
                    "page_type": "opportunity",
                    "root_domain": result.get(
                        "source_domain"
                    ),
                }

                raw = {
                    "title": title,
                    "url": source_url,
                    "snippet": snippet,
                    "source": "google_search",
                    "service": service,
                    "location": location,
                    "discovery_type": "opportunity",
                    "original_issuer": display_name,
                    "source_url": source_url,
                    "source_domain": result.get(
                        "source_domain"
                    ),
                    "search_query": result.get(
                        "search_query"
                    ),
                    "prospect_score": result.get(
                        "prospect_score",
                        0,
                    ),
                    "page_type": "opportunity",
                }

                comments.append(
                    CommentResult(
                        platform="google_search",
                        username=display_name,
                        display_name=display_name,
                        profile_url=source_url,
                        comment_text=snippet,
                        post_url=source_url,
                        bio_text=snippet,
                        engagement=engagement,
                        raw=raw,
                    )
                )

                continue

            root_domain = self._domain_from_url(
                url
            )

            score = result.get(
                "prospect_score",
                self._prospect_score(result),
            )

            display_name = self._display_name(
                title,
                url,
            )

            engagement = {
                "source": "google_search",
                "discovery_type": "organization",
                "search_query": result.get(
                    "search_query"
                ),
                "domain": root_domain,
                "root_domain": root_domain,
                "score": score,
                "page_type": result.get(
                    "page_type"
                ),
            }

            raw = {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": "google_search",
                "service": service,
                "location": location,
                "discovery_type": "organization",
                "score": score,
                "root_domain": root_domain,
                "page_type": result.get(
                    "page_type"
                ),
            }

            comments.append(
                CommentResult(
                    platform="google_search",
                    username=display_name,
                    display_name=display_name,
                    profile_url=url,
                    comment_text=snippet,
                    post_url=url,
                    bio_text=snippet,
                    engagement=engagement,
                    raw=raw,
                )
            )

        return comments

    def _service_queries(
        self,
        service: Any,
        location: Any,
        extra_keywords: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Build discovery queries around commercial need and procurement.

        Queries deliberately avoid putting every search term inside quotes.
        Exact-phrase searches were producing very sparse DDGS results.

        Strategy:
        - natural buyer-intent searches
        - hiring / outsourcing searches
        - procurement / tender searches
        - sector-specific searches
        - public-sector opportunity searches
        """

        service_text = str(service or "").strip()
        location_text = str(location or "Nigeria").strip()

        service_key = re.sub(
            r"[^a-z0-9]+",
            "_",
            service_text.lower(),
        ).strip("_")

        aliases = {
            "website": "website development",
            "website_design": "website development",
            "website_development": "website development",
            "web_design": "website development",
            "website_design_development": "website development",

            "digital_marketing": "digital marketing",
            "digital_marketing_services": "digital marketing",
            "marketing": "digital marketing",

            "ai_solution": "AI solutions",
            "ai_solutions": "AI solutions",
            "ai_automation": "AI automation",
            "ai": "AI solutions",

            "graphics": "graphic design",
            "graphic_design": "graphic design",
            "graphic_design_branding": "graphic design",

            "cv_resume": "CV writing",
            "cv": "CV writing",
            "resume": "resume writing",
            "resume_writing": "resume writing",

            "excel": "Excel automation",
            "excel_data_analysis": "Excel automation",
            "data_analysis": "data analysis",
            "data_analytics": "data analysis",

            "virtual_assistant": "virtual assistant",
            "va": "virtual assistant",
            "hiring_services": "virtual assistant",

            "data_entry": "data entry",
            "transcription": "transcription",

            "it_support": "IT support",
            "it_admin": "IT support",
            "it_administrative": "IT support",

            "social_media": "social media management",
            "social_media_management": "social media management",
            "sales_lead_generation": "sales and lead generation",
            "used_items": "used and second-hand items",
            "second_hand_items": "used and second-hand items",
            "fairly_used_items": "used and second-hand items",

            "sales": "sales and lead generation",
            "lead_generation": "sales and lead generation",
            "business_development": "sales and lead generation",

            "herbal_islamic_medicine": "herbal and Islamic medicine",
            "herbal_medicine": "herbal and Islamic medicine",
            "islamic_medicine": "herbal and Islamic medicine",
        
            "software_app": "software and app development",
            "software_development": "software and app development",

            "ai_automation": "business automation",
            "business_automation": "business automation",
            "workflow_automation": "business automation",

            "ai_data_annotation": "AI data annotation",
            "data_annotation": "AI data annotation",

            "ai_content_writing": "AI content writing",
            "ai_video_creation": "AI video creation",
            "ai_training": "AI and digital training",
            "digital_training": "AI and digital training",

            "it_support": "IT support",
            "technical_support": "IT support",

            "computer_setup": "computer setup and support",
            "computer_repair": "computer setup and support",

            "microsoft_office": "Microsoft Office and Excel support",
            "office_support": "Microsoft Office and Excel support",

            "network_support": "network and printer support",
            "network_wifi": "network and printer support",

            "web_hosting": "web hosting and maintenance",
            "website_maintenance": "web hosting and maintenance",

            "ecommerce": "ecommerce development",

            "social_media_management": "social media management",
            "content_creation": "content creation",

            "data_management": "data management",
            "data_entry": "data entry",
            "transcription": "transcription",

            "virtual_assistant": "virtual assistant",
            "business_operations": "business operations support",
            "customer_support": "customer support",
            "logistics_warehousing": "logistics and warehousing support",


            "buying_intent": "buying_intent",
        }

        target = aliases.get(
            service_key,
            service_text or "business services",
        )

        query_groups = {

            "software and app development": [
                f"{location_text} software development needed",
                f"{location_text} company needs custom software",
                f"{location_text} looking for software developer",
                f"{location_text} seeking app developer",
                f"{location_text} software development RFP",
                f"{location_text} software development RFQ",
                f"{location_text} software development tender",
                f"{location_text} custom application development",
            ],

            "business automation": [
                f"{location_text} business automation needed",
                f"{location_text} company needs workflow automation",
                f"{location_text} looking for automation consultant",
                f"{location_text} seeking business process automation",
                f"{location_text} outsource workflow automation",
                f"{location_text} automation RFP",
                f"{location_text} automation RFQ",
                f"{location_text} process automation procurement",
            ],

            "AI data annotation": [
                f"{location_text} AI data annotation needed",
                f"{location_text} company needs data annotators",
                f"{location_text} looking for data annotation team",
                f"{location_text} seeking AI evaluation services",
                f"{location_text} outsource data annotation",
                f"{location_text} data annotation RFP",
                f"{location_text} data annotation RFQ",
                f"{location_text} AI data evaluation procurement",
            ],

            "AI content writing": [
                f"{location_text} AI content writing needed",
                f"{location_text} company needs content writer",
                f"{location_text} looking for technical content writer",
                f"{location_text} seeking AI content services",
                f"{location_text} outsource content writing",
                f"{location_text} content writing RFP",
                f"{location_text} content writing RFQ",
                f"{location_text} content development procurement",
            ],

            "AI video creation": [
                f"{location_text} AI video creation needed",
                f"{location_text} company needs video creator",
                f"{location_text} looking for video production services",
                f"{location_text} seeking video editor",
                f"{location_text} outsource video creation",
                f"{location_text} video production RFP",
                f"{location_text} video production RFQ",
                f"{location_text} video content procurement",
            ],

            "AI and digital training": [
                f"{location_text} AI training needed",
                f"{location_text} company needs AI training",
                f"{location_text} looking for digital skills trainer",
                f"{location_text} seeking AI consultant trainer",
                f"{location_text} outsource AI training",
                f"{location_text} AI training RFP",
                f"{location_text} digital training RFQ",
                f"{location_text} technology training procurement",
            ],

            "IT support": [
                f"{location_text} IT support needed",
                f"{location_text} company needs technical support",
                f"{location_text} looking for IT support provider",
                f"{location_text} seeking computer support",
                f"{location_text} outsource IT support",
                f"{location_text} IT support RFP",
                f"{location_text} IT support RFQ",
                f"{location_text} technical support procurement",
            ],

            "computer setup and support": [
                f"{location_text} computer setup service needed",
                f"{location_text} company needs computer installation",
                f"{location_text} looking for computer technician",
                f"{location_text} seeking computer repair service",
                f"{location_text} outsource computer support",
                f"{location_text} computer setup RFP",
                f"{location_text} computer maintenance RFQ",
                f"{location_text} computer support procurement",
            ],

            "Microsoft Office and Excel support": [
                f"{location_text} Microsoft Office support needed",
                f"{location_text} company needs Excel support",
                f"{location_text} looking for Excel consultant",
                f"{location_text} seeking spreadsheet support",
                f"{location_text} outsource Microsoft Office support",
                f"{location_text} Excel automation RFP",
                f"{location_text} Excel support RFQ",
                f"{location_text} spreadsheet services procurement",
            ],

            "network and printer support": [
                f"{location_text} network support needed",
                f"{location_text} company needs WiFi installation",
                f"{location_text} looking for network technician",
                f"{location_text} seeking printer support",
                f"{location_text} outsource network maintenance",
                f"{location_text} network support RFP",
                f"{location_text} network services RFQ",
                f"{location_text} IT network procurement",
            ],

            "web hosting and maintenance": [
                f"{location_text} website maintenance needed",
                f"{location_text} company needs web hosting",
                f"{location_text} looking for website maintenance",
                f"{location_text} seeking domain and hosting service",
                f"{location_text} outsource website maintenance",
                f"{location_text} website maintenance RFP",
                f"{location_text} web hosting RFQ",
                f"{location_text} website support procurement",
            ],

            "ecommerce development": [
                f"{location_text} ecommerce website needed",
                f"{location_text} company needs online store",
                f"{location_text} looking for ecommerce developer",
                f"{location_text} seeking Shopify developer",
                f"{location_text} seeking WooCommerce developer",
                f"{location_text} ecommerce development RFP",
                f"{location_text} ecommerce development RFQ",
                f"{location_text} online store procurement",
            ],

            "social media management": [
                f"{location_text} social media management needed",
                f"{location_text} company needs social media manager",
                f"{location_text} looking for social media manager",
                f"{location_text} seeking social media services",
                f"{location_text} outsource social media management",
                f"{location_text} social media management RFP",
                f"{location_text} social media management RFQ",
                f"{location_text} social media services procurement",
            ],

            "content creation": [
                f"{location_text} content creator needed",
                f"{location_text} company needs content creator",
                f"{location_text} looking for content production",
                f"{location_text} seeking content creator",
                f"{location_text} outsource content creation",
                f"{location_text} content creation RFP",
                f"{location_text} content creation RFQ",
                f"{location_text} content production procurement",
            ],

            "data management": [
                f"{location_text} data management needed",
                f"{location_text} company needs data management",
                f"{location_text} looking for data analyst",
                f"{location_text} seeking data management consultant",
                f"{location_text} outsource data management",
                f"{location_text} data management RFP",
                f"{location_text} data management RFQ",
                f"{location_text} data services procurement",
            ],

            "data entry": [
                f"{location_text} data entry needed",
                f"{location_text} company needs data entry",
                f"{location_text} looking for data entry specialist",
                f"{location_text} seeking data processing service",
                f"{location_text} outsource data entry",
                f"{location_text} data entry RFP",
                f"{location_text} data entry RFQ",
                f"{location_text} data processing procurement",
            ],

            "transcription": [
                f"{location_text} transcription service needed",
                f"{location_text} company needs transcription",
                f"{location_text} looking for transcriptionist",
                f"{location_text} seeking audio transcription",
                f"{location_text} outsource transcription",
                f"{location_text} transcription RFP",
                f"{location_text} transcription RFQ",
                f"{location_text} transcription services procurement",
            ],

            "virtual assistant": [
                f"{location_text} virtual assistant needed",
                f"{location_text} company needs virtual assistant",
                f"{location_text} looking for virtual assistant",
                f"{location_text} seeking administrative assistant",
                f"{location_text} outsource virtual assistant",
                f"{location_text} virtual assistant RFP",
                f"{location_text} virtual assistant RFQ",
                f"{location_text} administrative support procurement",
            ],

            "business operations support": [
                f"{location_text} operations support needed",
                f"{location_text} company needs operations support",
                f"{location_text} looking for operations consultant",
                f"{location_text} seeking business operations support",
                f"{location_text} outsource operations support",
                f"{location_text} operations support RFP",
                f"{location_text} operations support RFQ",
                f"{location_text} business operations procurement",
            ],

            "customer support": [
                f"{location_text} customer support needed",
                f"{location_text} company needs customer service team",
                f"{location_text} looking for customer support provider",
                f"{location_text} seeking customer service outsourcing",
                f"{location_text} outsource customer support",
                f"{location_text} customer support RFP",
                f"{location_text} customer support RFQ",
                f"{location_text} customer service procurement",
            ],

            "logistics and warehousing support": [
                f"{location_text} logistics support needed",
                f"{location_text} company needs warehouse support",
                f"{location_text} looking for logistics provider",
                f"{location_text} seeking warehousing services",
                f"{location_text} outsource logistics operations",
                f"{location_text} logistics RFP",
                f"{location_text} warehousing RFQ",
                f"{location_text} logistics services procurement",
            ],

            "sales and lead generation": [
                f"{location_text} lead generation service needed",
                f"{location_text} company needs lead generation",
                f"{location_text} looking for lead generation provider",
                f"{location_text} seeking sales consultant",
                f"{location_text} company needs sales outsourcing",
                f"{location_text} looking for business development support",
                f"{location_text} outsource sales and lead generation",
                f"{location_text} lead generation RFP",
                f"{location_text} lead generation RFQ",
                f"{location_text} sales support procurement",
            ],

            "herbal and Islamic medicine": [
                f"{location_text} herbal medicine service needed",
                f"{location_text} herbal medicine consultation",
                f"{location_text} Islamic medicine services",
                f"{location_text} prophetic medicine services",
                f"{location_text} herbal products supplier",
                f"{location_text} ruqyah service needed",
                f"{location_text} hijama service needed",
                f"{location_text} herbal medicine RFP",
                f"{location_text} herbal medicine RFQ",
                f"{location_text} traditional medicine procurement",
            ],

            "used and second-hand items": [
                # ------------------------------------------------
                # General Nigerian buyer / seller intent
                # ------------------------------------------------
                f"{location_text} looking for used items",
                f"{location_text} looking for second hand items",
                f"{location_text} looking for fairly used items",
                f"{location_text} need fairly used items",
                f"{location_text} looking to buy used items",
                f"{location_text} want to buy used items",
                f"{location_text} where can I buy used items",
                f"{location_text} where can I find used items",
                f"{location_text} used items wanted",
                f"{location_text} second hand items wanted",
                f"{location_text} used goods wanted",
                f"{location_text} used equipment wanted",
                f"{location_text} used electronics wanted",
                f"{location_text} used furniture wanted",
                f"{location_text} used phones wanted",
                f"{location_text} used laptops wanted",

                # ------------------------------------------------
                # Nigerian terminology
                # ------------------------------------------------
                f"{location_text} fairly used items Nigeria",
                f"{location_text} foreign used items",
                f"{location_text} UK used items",
                f"{location_text} tokunbo items",
                f"{location_text} used goods Nigeria",
                f"{location_text} pre-owned items Nigeria",
                f"{location_text} secondhand goods Nigeria",

                # ------------------------------------------------
                # Hausa demand language
                # ------------------------------------------------
                f"{location_text} Hausa ina neman kaya",
                f"{location_text} Hausa ina neman kayan amfani",
                f"{location_text} Hausa ina neman kayan daki",
                f"{location_text} Hausa ina neman waya",
                f"{location_text} Hausa ina neman laptop",
                f"{location_text} Hausa ina neman TV",
                f"{location_text} Hausa ina neman fridge",
                f"{location_text} Hausa ina so in saya",
                f"{location_text} Hausa wa ke sayar da kaya",
                f"{location_text} Hausa ana sayar da kayan amfani",
                f"{location_text} kayan da aka yi amfani da su",
                f"{location_text} kayan hannu na biyu",

                # ------------------------------------------------
                # Nigerian Pidgin demand language
                # ------------------------------------------------
                f"{location_text} Pidgin I dey find used items",
                f"{location_text} Pidgin I dey find fairly used",
                f"{location_text} Pidgin I wan buy used",
                f"{location_text} Pidgin who get used items",
                f"{location_text} Pidgin who dey sell used items",
                f"{location_text} Pidgin where I fit buy used",
                f"{location_text} Pidgin I need fairly used",
                f"{location_text} Pidgin used phone wanted",
                f"{location_text} Pidgin used laptop wanted",
                f"{location_text} Pidgin used furniture wanted",

                # ------------------------------------------------
                # Facebook public/indexed groups and Marketplace
                # ------------------------------------------------
                f'site:facebook.com/marketplace {location_text} used items',
                f'site:facebook.com/marketplace {location_text} fairly used',
                f'site:facebook.com/marketplace {location_text} second hand',
                f'site:facebook.com/marketplace {location_text} used phones',
                f'site:facebook.com/marketplace {location_text} used electronics',
                f'site:facebook.com/marketplace {location_text} used furniture',

                f'site:facebook.com/groups {location_text} "used items"',
                f'site:facebook.com/groups {location_text} "fairly used"',
                f'site:facebook.com/groups {location_text} "second hand"',
                f'site:facebook.com/groups {location_text} "looking for" "used"',
                f'site:facebook.com/groups {location_text} "wanted" "used"',
                f'site:facebook.com/groups {location_text} "who is selling" "used"',
                f'site:facebook.com/groups {location_text} "ina neman" kaya',
                f'site:facebook.com/groups {location_text} "ina neman" waya',
                f'site:facebook.com/groups {location_text} "ina neman" laptop',
                f'site:facebook.com/groups {location_text} "ina neman" kayan daki',
                f'site:facebook.com/groups {location_text} "I dey find" used',
                f'site:facebook.com/groups {location_text} "I wan buy" used',

                # ------------------------------------------------
                # Jiji
                # ------------------------------------------------
                f'site:jiji.ng {location_text} used items',
                f'site:jiji.ng {location_text} fairly used',
                f'site:jiji.ng {location_text} second hand',
                f'site:jiji.ng {location_text} foreign used',
                f'site:jiji.ng {location_text} used phones',
                f'site:jiji.ng {location_text} used laptops',
                f'site:jiji.ng {location_text} used electronics',
                f'site:jiji.ng {location_text} used furniture',
                f'site:jiji.ng {location_text} used appliances',
                f'site:jiji.ng {location_text} used equipment',

                # ------------------------------------------------
                # Konga
                # ------------------------------------------------
                f'site:konga.com {location_text} used items',
                f'site:konga.com {location_text} used electronics',
                f'site:konga.com {location_text} used phones',
                f'site:konga.com {location_text} used laptops',
                f'site:konga.com {location_text} second hand',

                # ------------------------------------------------
                # Nigerian marketplaces / classifieds
                # ------------------------------------------------
                f'site:naijamart.com {location_text} used items',
                f'site:naijamart.com {location_text} second hand',
                f'site:naijamart.com {location_text} fairly used',

                f'site:naijamarketplace.com.ng {location_text} used items',
                f'site:naijamarketplace.com.ng {location_text} second hand',

                f'site:naijads.ng {location_text} used items',
                f'site:naijads.ng {location_text} fairly used',
                f'site:naijads.ng {location_text} used electronics',

                f'site:naijaresell.com {location_text} used items',
                f'site:naijaresell.com {location_text} used phones',
                f'site:naijaresell.com {location_text} used electronics',

                f'site:marketplace.ng {location_text} used items',
                f'site:marketplace.ng {location_text} second hand',

                f'site:marketa.com.ng {location_text} used items',
                f'site:marketa.com.ng {location_text} fairly used',

                f'site:agora.com.ng {location_text} used items',
                f'site:agora.com.ng {location_text} second hand',

                f'site:classimall.com {location_text} used items',
                f'site:classimall.com {location_text} fairly used',

                f'site:sortedexpress.com {location_text} used items',
                f'site:sortedexpress.com {location_text} pre-owned',
            ],


            "website development": [
                f'{location_text} "website redesign" "request for proposal"',
                f'{location_text} "website development" "request for proposal"',
                f'{location_text} "website design" "request for proposal"',
                f'{location_text} "website redesign" "request for quotation"',
                f'{location_text} "website development" "request for quotation"',
                f'{location_text} "website redesign" "terms of reference"',
                f'{location_text} "website development" "terms of reference"',
                f'{location_text} "website redevelopment" procurement',
                f'{location_text} "website redesign" project',
                f'{location_text} "website development" project',
            ], 
            "digital marketing": [
                                f'{location_text} "digital marketing" "request for proposal"',
                f'{location_text} "digital marketing services" "request for proposal"',
                f'{location_text} "digital marketing" "request for quotation"',
                f'{location_text} "digital marketing services" "request for quotation"',
                f'{location_text} "digital marketing" "terms of reference"',
                f'{location_text} "digital marketing" procurement',
                f'{location_text} "digital marketing" tender',
                f'{location_text} "social media management" "request for proposal"',
                f'{location_text} "digital marketing" EOI',
                f'{location_text} "marketing services" procurement',
            ],

            "AI solutions": [
                f"{location_text} AI solution needed",
                f"{location_text} AI automation needed",
                f"{location_text} company needs AI solution",
                f"{location_text} organization needs AI automation",
                f"{location_text} looking for AI consultant",
                f"{location_text} seeking AI solution provider",
                f"{location_text} outsource AI development",
                f"{location_text} AI solutions RFP",
                f"{location_text} AI automation RFQ",
                f"{location_text} artificial intelligence tender",
                f"{location_text} AI procurement",
                f"{location_text} AI EOI",
                f"site:.gov.ng {location_text} AI procurement",
                f"site:.gov.ng {location_text} artificial intelligence RFP",
                f"site:.org.ng {location_text} AI solution RFP",
            ],

            "graphic design": [
                f"{location_text} graphic design needed",
                f"{location_text} graphic designer needed",
                f"{location_text} company needs graphic design",
                f"{location_text} seeking graphic design services",
                f"{location_text} graphic design RFP",
                f"{location_text} graphic design RFQ",
                f"{location_text} seeking graphic design services",
                f"{location_text} outsource graphic design",
                f"{location_text} graphic design RFP",
                f"{location_text} graphic design RFQ",
                f"{location_text} branding tender",
                f"{location_text} creative services procurement",
                f"{location_text} graphic design EOI",
                f"site:.gov.ng {location_text} graphic design tender",
                f"site:.org.ng {location_text} graphic design RFP",
            ],

            "CV writing": [
                f"{location_text} CV writing needed",
                f"{location_text} CV writer needed",
                f"{location_text} resume writer needed",
                f"{location_text} looking for CV writer",
                f"{location_text} seeking CV writing service",
                f"{location_text} professional CV writing",
                f"{location_text} CV writing services",
                f"{location_text} resume writing services",
            ],

            "resume writing": [
                f"{location_text} resume writing needed",
                f"{location_text} resume writer needed",
                f"{location_text} looking for resume writer",
                f"{location_text} seeking resume writing service",
                f"{location_text} professional resume writing",
                f"{location_text} resume writing services",
            ],

            "Excel automation": [
                f"{location_text} Excel automation needed",
                f"{location_text} Excel consultant needed",
                f"{location_text} spreadsheet automation needed",
                f"{location_text} company needs Excel automation",
                f"{location_text} organization needs Excel dashboard",
                f"{location_text} looking for Excel consultant",
                f"{location_text} seeking Excel automation",
                f"{location_text} outsource Excel automation",
                f"{location_text} Excel automation RFP",
                f"{location_text} Excel automation RFQ",
                f"{location_text} reporting automation procurement",
                f"{location_text} dashboard development RFP",
                f"site:.gov.ng {location_text} Excel dashboard procurement",
                f"site:.org.ng {location_text} data reporting RFP",
            ],

            "data analysis": [
                f"{location_text} data analyst needed",
                f"{location_text} data analysis needed",
                f"{location_text} company needs data analysis",
                f"{location_text} organization needs data analyst",
                f"{location_text} looking for data analyst",
                f"{location_text} seeking data analysis consultant",
                f"{location_text} outsource data analysis",
                f"{location_text} data analysis RFP",
                f"{location_text} data analytics RFQ",
                f"{location_text} data reporting tender",
                f"{location_text} dashboard development procurement",
                f"{location_text} data analysis EOI",
                f"site:.gov.ng {location_text} data analysis procurement",
                f"site:.org.ng {location_text} data analysis RFP",
            ],

            "virtual assistant": [
                f"{location_text} virtual assistant needed",
                f"{location_text} company needs virtual assistant",
                f"{location_text} business needs virtual assistant",
                f"{location_text} looking for virtual assistant",
                f"{location_text} seeking virtual assistant",
                f"{location_text} hire virtual assistant",
                f"{location_text} outsource administrative support",
                f"{location_text} virtual assistant services needed",
            ],

            "virtual assistant": [
                f"{location_text} virtual assistant needed",
                f"{location_text} company needs virtual assistant",
                f"{location_text} business needs virtual assistant",
                f"{location_text} looking for virtual assistant",
                f"{location_text} seeking virtual assistant",
                f"{location_text} hire virtual assistant",
                f"{location_text} outsource administrative support",
                f"{location_text} virtual assistant services needed",
            ],

            "data entry": [
                f"{location_text} data entry needed",
                f"{location_text} data entry services needed",
                f"{location_text} company needs data entry",
                f"{location_text} organization needs data entry",
                f"{location_text} looking for data entry services",
                f"{location_text} seeking data entry provider",
                f"{location_text} outsource data entry",
                f"{location_text} data entry RFQ",
            ],

            "transcription": [
                f"{location_text} transcription needed",
                f"{location_text} transcription services needed",
                f"{location_text} organization needs transcription",
                f"{location_text} looking for transcriptionist",
                f"{location_text} seeking transcription services",
                f"{location_text} outsource transcription",
                f"{location_text} transcription RFQ",
            ],

            "IT support": [
                f"{location_text} IT support needed",
                f"{location_text} company needs IT support",
                f"{location_text} organization needs IT services",
                f"{location_text} looking for IT support provider",
                f"{location_text} RFP website development",
                f"{location_text} request for proposals website design",
                f"{location_text} request for proposals website redesign",
                f"{location_text} request for quotation graphic design",
                f"{location_text} RFP digital marketing",
                f"{location_text} request for proposals AI enabled system",
                f"site:.gov.ng {location_text} IT support tender",
                f"site:.org.ng {location_text} IT support RFP",
            ],

            "social media management": [
                f"{location_text} social media manager needed",
                f"{location_text} social media management needed",
                f"{location_text} company needs social media management",
                f"{location_text} organization needs social media management",
                f"{location_text} looking for social media manager",
                f"{location_text} seeking social media services",
                f"{location_text} outsource social media management",
                f"{location_text} social media management RFP",
                f"{location_text} social media RFQ",
                f"{location_text} social media procurement",
            ],

            "buying_intent": [
                f"{location_text} website development RFP",
                f"{location_text} website design RFP",
                f"{location_text} website redesign RFP",
                f"{location_text} website redevelopment RFP",
                f"{location_text} graphic design RFP",
                f"{location_text} digital marketing RFP",
                f"{location_text} AI enabled system RFP",
            ],
        }

        queries = list(
            query_groups.get(
                target,
                [
                    f"{location_text} {target} needed",
                    f"{location_text} looking for {target}",
                    f"{location_text} seeking {target}",
                    f"{location_text} outsource {target}",
                    f"{location_text} {target} RFP",
                    f"{location_text} {target} RFQ",
                    f"{location_text} {target} tender",
                    f"{location_text} {target} procurement",
                    f"{location_text} {target} EOI",
                    f"site:.gov.ng {location_text} {target} tender",
                    f"site:.org.ng {location_text} {target} RFP",
                ],
            )
        )

        # Frontend extra keywords are complete search queries and must
        # execute before the predefined query set because callers may cap
        # the final query list with max_queries.
        extra_queries = []

        if extra_keywords:
            for keyword in extra_keywords:
                keyword = str(keyword or "").strip()
                if not keyword:
                    continue

                extra_queries.append(keyword)

        queries = extra_queries + queries

        unique_queries = []
        seen = set()

        for query in queries:
            query = re.sub(r"\s+", " ", query).strip()
            normalized = query.casefold()

            if not query or normalized in seen:
                continue

            seen.add(normalized)
            unique_queries.append(query)

        # USED_ITEMS_PRIORITY_V1
        # Used/second-hand discovery is intentionally high-volume and
        # marketplace/social-heavy. Keep the first query budget diverse
        # instead of spending it entirely on generic web queries.
        if service_key == "used_items":
            facebook_marketplace = [
                q for q in unique_queries
                if q.startswith("site:facebook.com/marketplace")
            ]

            facebook_groups = [
                q for q in unique_queries
                if q.startswith("site:facebook.com/groups")
            ]

            jiji_queries = [
                q for q in unique_queries
                if q.startswith("site:jiji.ng")
            ]

            konga_queries = [
                q for q in unique_queries
                if q.startswith("site:konga.com")
            ]

            other_marketplace_prefixes = (
                "site:naijamart.com",
                "site:naijamarketplace.com.ng",
                "site:naijads.ng",
                "site:naijaresell.com",
                "site:marketplace.ng",
                "site:marketa.com.ng",
                "site:agora.com.ng",
                "site:classimall.com",
                "site:sortedexpress.com",
            )

            other_marketplaces = [
                q for q in unique_queries
                if q.startswith(other_marketplace_prefixes)
            ]

            language_queries = [
                q for q in unique_queries
                if (
                    "Hausa" in q
                    or "Pidgin" in q
                    or "ina neman" in q.lower()
                    or "ina so in saya" in q.lower()
                    or "I dey find" in q
                    or "I dey find" in q
                    or "I wan buy" in q
                    or "who get" in q
                    or "who dey sell" in q
                    or "where I fit buy" in q
                )
            ]

            general_queries = [
                q for q in unique_queries
                if q not in (
                    facebook_marketplace
                    + facebook_groups
                    + jiji_queries
                    + konga_queries
                    + other_marketplaces
                    + language_queries
                )
            ]

            priority = []

            # 1. Facebook Marketplace
            priority.extend(facebook_marketplace[:5])

            # 2. Facebook Groups
            priority.extend(facebook_groups[:7])

            # 3. Jiji
            priority.extend(jiji_queries[:5])

            # 4. Konga
            priority.extend(konga_queries[:4])

            # 5. Other Nigerian marketplaces
            priority.extend(other_marketplaces[:4])

            # 6. Hausa / Pidgin demand language
            priority.extend(language_queries[:7])

            # 7. General Nigerian used-item demand
            priority.extend(general_queries[:8])

            # Preserve uniqueness in the prioritized list.
            prioritized_unique = []
            seen_priority = set()

            for q in priority:
                normalized = q.casefold()
                if normalized in seen_priority:
                    continue

                seen_priority.add(normalized)
                prioritized_unique.append(q)

            # Fill any remaining slots from the original query list so
            # marketplace coverage never reduces the total query budget.
            for q in unique_queries:
                normalized = q.casefold()
                if normalized in seen_priority:
                    continue

                seen_priority.add(normalized)
                prioritized_unique.append(q)

            unique_queries = prioritized_unique

        return unique_queries


    def _is_opportunity_query(self, query: str) -> bool:
        """Return True when the search query targets an active opportunity."""
        q = (query or "").lower()

        signals = (
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for expression of interest",
              "request for expressions of interest",
            "expression of interest",
            "call for proposals",
            "invitation to bid",
            "terms of reference",
            "rfp",
            "rfq",
            "eoi",
            "vendor",
            "contractor",
            "consultant",
            "consultancy",
        )

        return any(signal in q for signal in signals)

    def _is_service_provider_result(
        self,
        service: str,
        title: str,
        snippet: str,
        domain: str,
    ) -> bool:
        """
        Detect organizations that are actively selling the requested service.

        Detection is service-specific. Generic technology, software, AI,
        consulting, or business language alone is not enough.

        A provider match normally requires:
        - a service-specific signal, and
        - a provider-role signal such as agency, company, services,
          solutions, consultant, developer, designer, etc.

        Strong service-provider titles can also qualify directly.
        Buyer/project language is intentionally not treated as provider
        evidence.
        """
        title_text = (title or "").strip().lower()
        snippet_text = (snippet or "").strip().lower()
        domain_text = (domain or "").strip().lower()

        text = " ".join(
            (
                title_text,
                snippet_text,
                domain_text,
            )
        )

        provider_roles = (
            "agency",
            "agencies",
            "company",
            "companies",
            "studio",
            "studios",
            "services",
            "service provider",
            "solutions",
            "solution provider",
            "provider",
            "consultant",
            "consultants",
            "consulting",
            "consultancy",
            "developer",
            "developers",
            "designer",
            "designers",
            "specialist",
            "specialists",
            "expert",
            "experts",
        )

        def has_role(value: str) -> bool:
            return any(
                re.search(
                    rf"\b{re.escape(role)}\b",
                    value,
                    re.IGNORECASE,
                )
                for role in provider_roles
            )

        def has_any(value: str, signals: tuple[str, ...]) -> bool:
            return any(signal in value for signal in signals)

        if service == "website":
            direct_signals = (
                "web design",
                "website design",
                "web development",
                "website development",
                "web solutions",
                "website solutions",
                "web services",
                "website services",
                "web developer",
                "website developer",
                "web designer",
                "website designer",
            )

            strong_title_signals = (
                "web design",
                "website design",
                "web development",
                "website development",
                "web developer",
                "website developer",
                "web designer",
                "website designer",
            )

            # Clear provider title:
            if has_any(title_text, strong_title_signals):
                if has_role(title_text) or has_role(snippet_text):
                    return True

            # Multiple website-service signals + provider language:
            service_hits = sum(
                signal in text
                for signal in direct_signals
            )

            if service_hits >= 1 and has_role(text):
                # Do not classify ordinary buyer language such as
                # "website redesign" as a provider.
                buyer_signals = (
                    "looking for",
                    "looking to hire",
                    "need a web",
                    "need a website",
                    "seeking a web",
                    "seeking a website",
                    "new website",
                    "website redesign",
                    "website redevelopment",
                    "request for proposal",
                    "request for quotation",
                    "expression of interest",
                    "invitation to bid",
                    "terms of reference",
                    "rfp",
                    "rfq",
                )

                if any(signal in title_text for signal in buyer_signals):
                    return False

                return True

            return False

        if service == "digital_marketing":
            service_signals = (
                "digital marketing",
                "digital marketing services",
                "digital marketing agency",
                "digital marketing company",
                "social media marketing",
                "social media agency",
                "social media management",
                "seo agency",
                "seo services",
                "seo company",
                "online marketing",
                "content marketing",
                "performance marketing",
                "brand strategy",
                "marketing services",
                "marketing agency",
                "marketing company",
            )

            if has_any(text, service_signals) and has_role(text):
                buyer_signals = (
                    "looking for",
                    "looking to hire",
                    "seeking",
                    "need a marketing",
                    "need digital marketing",
                    "marketing campaign",
                    "request for proposal",
                    "request for quotation",
                    "expression of interest",
                    "invitation to bid",
                    "rfp",
                    "rfq",
                )

                if any(signal in title_text for signal in buyer_signals):
                    return False

                return True

            return False

        if service == "ai_solution":
            service_signals = (
                "ai solutions",
                "ai solution provider",
                "ai consulting",
                "ai consultant",
                "ai development",
                "ai development company",
                "ai automation",
                "ai workflow automation",
                "ai solution",
                "ai services",
                "ai partner",
                "ai-powered automation",
                "automation solutions",
                "automation services",
                "machine learning company",
                "artificial intelligence company",
                "custom enterprise software",
                "enterprise software",
                "software and automation",
                "software & automation",
                "digital transformation",
            )

            if has_any(text, service_signals) and has_role(text):
                return True

            # Some software/automation firms describe what they build
            # without using an explicit provider-role word such as
            # "company", "agency", or "consultant".
            ai_delivery_signals = (
                "custom enterprise software",
                "enterprise software",
                "ai workflow automation",
                "ai-powered automation",
                "build custom tools",
                "build custom software",
                "custom software",
                "digital transformation for businesses",
                "help businesses automate",
                "helping businesses automate",
                "automate operations",
                "partner for a nigerianised ai solution",
                "partner for an ai solution",
                "adapt ai for companies",
                "adapt ai for businesses",
                "ai for companies",
                "ai for businesses",
                "ai for enterprises",
                "our ai solution",
            )

            ai_client_context = (
                "for companies",
                "for businesses",
                "for organizations",
                "for organisations",
                "for enterprises",
                "local partner",
                "we help",
                "we build",
                "we develop",
                "our solution",
                "our solutions",
            )

            if (
                has_any(text, service_signals)
                and (
                    has_any(text, ai_delivery_signals)
                    or has_any(text, ai_client_context)
                )
            ):
                return True

            return False

        if service == "graphics":
            service_signals = (
                "graphic design",
                "graphic design services",
                "graphic design agency",
                "graphic design company",
                "branding",
                "creative branding",
                "branding and marketing",
                "branding and design",
                "branding agency",
                "branding company",
                "brand identity",
                "brand strategy",
                "creative agency",
                "creative studio",
                "printing services",
                "printing company",
                "packaging design",
                "packaging solutions",
            )

            if has_any(text, service_signals) and has_role(text):
                buyer_signals = (
                    "rebranding",
                    "brand refresh",
                    "new brand identity",
                    "marketing materials",
                    "packaging design",
                    "looking for",
                    "seeking",
                    "request for proposal",
                    "request for quotation",
                    "expression of interest",
                    "rfp",
                    "rfq",
                )

                if any(signal in title_text for signal in buyer_signals):
                    return False

                return True

            return False

        if service == "hiring_services":
            provider_signals = (
                "recruitment agency",
                "recruitment company",
                "recruitment services",
                "recruitment consultancy",
                "recruitment consultant",
                "staffing agency",
                "staffing company",
                "staffing services",
                "staffing consultancy",
                "hr consultancy",
                "hr consulting",
                "hr services",
                "human resources consultancy",
                "human resources consulting",
                "executive search",
                "talent acquisition",
                "workforce outsourcing",
                "staff outsourcing",
                "recruitment outsourcing",
                "outsourcing services",
            )

            if has_any(text, provider_signals):
                buyer_signals = (
                    "recruitment services needed",
                    "recruitment support needed",
                    "staffing support needed",
                    "hiring support needed",
                    "looking for recruitment agency",
                    "seeking recruitment services",
                    "seeking staffing partner",
                    "hr outsourcing needed",
                    "workforce outsourcing needed",
                    "outsource recruitment",
                    "request for proposal",
                    "request for quotation",
                    "expression of interest",
                    "rfp",
                    "rfq",
                )

                if any(signal in title_text for signal in buyer_signals):
                    return False

                return True

            return False

        if service == "cv_resume":
            strong_provider_signals = (
                "cv writing",
                "cv writer",
                "cv writing services",
                "cv builder",
                "resume writing",
                "resume writer",
                "resume writing services",
                "resume builder",
                "career services",
                "career coaching",
            )

            return has_any(text, strong_provider_signals)

        if service == "excel":
            service_signals = (
                "excel consultant",
                "excel consulting",
                "excel automation",
                "spreadsheet consultant",
                "spreadsheet consulting",
                "data analytics consultancy",
                "data analytics consulting",
                "data analysis consulting",
                "business intelligence services",
                "business intelligence consulting",
                "business intelligence solutions",
                "dashboard development services",
                "reporting automation",
                "automated reporting services",
            )

            if has_any(text, service_signals) and has_role(text):
                return True

            return False

        return False

    def _extract_opportunity_issuer(
        self,
        title: str,
        snippet: str,
    ) -> str | None:
        """
        Extract an opportunity issuer conservatively.

        Procurement markers such as RFP, RFQ, Tender and EOI are
        opportunity types, never issuer names.
        """

        title = self._clean_text(title or "")
        snippet = self._clean_text(snippet or "")
        combined = f"{title}. {snippet}"

        # ----------------------------------------------------------
        # Conservative canonical issuer shortcuts.
        # ----------------------------------------------------------

        if re.search(
            r"\bidice\b",
            title,
            re.IGNORECASE,
        ):
            return "Bank of Industry"

        if re.search(
            r"\bboi\s+nigeria\b",
            title,
            re.IGNORECASE,
        ):
            return "Bank of Industry"

        # Issuer after a procurement phrase in the title.
        procurement_tail = re.search(
            r"(?:request\s+for\s+(?:proposal|proposals|quotation|quotations|tender|tenders)|"
            r"expression\s+of\s+interest|invitation\s+to\s+(?:bid|tender)|"
            r"rfp|rfq|rft|itt|itb|eoi|tender)"
            r"\s*[.!:]\s*"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"\s*$",
            title,
            re.IGNORECASE,
        )

        if procurement_tail:
            issuer = procurement_tail.group(1).strip(" .,:;-")

            if re.fullmatch(
                r"boi\s+nigeria",
                issuer,
                re.IGNORECASE,
            ):
                return "Bank of Industry"

            if re.fullmatch(
                r"bank\s+of\s+industry(?:\s+nigeria)?",
                issuer,
                re.IGNORECASE,
            ):
                return "Bank of Industry"

            if self._looks_like_issuer_name(issuer):
                return issuer

        # Generic procurement-title prefix followed by issuer.
        #
        # Some Unicode separators are normalized by _clean_text()
        # into "?", so support that normalized form as well.
        generic_procurement_prefix = re.match(
            r"^(?:current\s+tenders?|tender\s+notices?|"
            r"procurement\s+notices?|bidding\s+notices?)"
            r"\s*[?|:\-??]\s*"
            r"(.+?)\s*$",
            title,
            re.IGNORECASE,
        )

        if generic_procurement_prefix:
            issuer = generic_procurement_prefix.group(1).strip(
                " .,:;?-??"
            )

            if self._looks_like_issuer_name(issuer):
                return issuer

        # Bare organization-title fallback.
        #
        # Do not consume titles that contain procurement markers or
        # self-identification wording; those must continue to the
        # specialized issuer extraction logic below.
        if (
            self._looks_like_issuer_name(title)
            and not re.search(
                r"\b(?:rfp|rfq|rft|itt|itb|eoi|tender|"
                r"request\s+for\s+(?:proposal|proposals|quotation|"
                r"quotations|tender|tenders)|"
                r"expression\s+of\s+interest|"
                r"invitation\s+to\s+(?:bid|tender))\b",
                title,
                re.IGNORECASE,
            )
            and not re.search(
                r"\bis\s+(?:currently\s+)?"
                r"(?:seeking|looking\s+for|requesting|inviting)\b",
                title,
                re.IGNORECASE,
            )
            and not re.search(
                r"\bis\s+pleased\s+to\s+invite\b",
                title,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:foundation|initiative|agency|commission|ministry|"
                r"bank|university|institute|council|company|corporation|"
                r"organization|organisation|limited|ltd|plc|ngo)\b",
                title,
                re.IGNORECASE,
            )
        ):
            return re.sub(
                r"\s+",
                " ",
                title.strip(" .,:;-"),
            )

        # Known programme alias: iDICE is a Bank of Industry programme.
        if (
            re.search(r"\bidice\b", combined, re.IGNORECASE)
            and re.search(
                r"(?:website|expression of interest|rfp|rfq|tender|"
                r"request for proposal|design and development)",
                combined,
                re.IGNORECASE,
            )
        ):
            return "Bank of Industry"

        # Canonical IOM requester form found in procurement notices.
        iom_requester = re.search(
            r"\b(?:International\s+Organisation\s+for\s+Migration|"
            r"International\s+Organization\s+for\s+Migration)"
            r"\s*\(\s*IOM\s*\)"
            r"\s+kindly\s+requests?\b",
            combined,
            re.IGNORECASE,
        )

        if iom_requester:
            return re.sub(
                r"\s+",
                " ",
                iom_requester.group(0).rsplit(
                    " kindly ",
                    1,
                )[0].strip(),
                flags=re.IGNORECASE,
            )

        # Explicit issuer labels are the strongest evidence.
        explicit_patterns = (
            r"(?:issued|published|advertised|posted|released)\s+by\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,80}?)"
            r"(?=\s+(?:for|to|on|that|which|who)\b|[.;]|$)",

            r"\bon behalf of\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,80}?)"
            r"(?=\s+(?:for|to|on|that|which|who)\b|[,.;]|$)",

            r"(?:organization|organisation|client|buyer|issuer|"
            r"procuring entity|requesting organization|"
            r"requesting organisation)"
            r"\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,80}?)"
            r"(?=\s+(?:is|are|has|have|seeks|seeking|invites?|"
            r"inviting|applications?|proposals?|requests?)\b|[.;]|$)",

            # Procurement notices commonly identify the recipient as:
            # "Proposals SHOULD BE SENT TO: UNICEF Nigeria official email"
            r"(?:sent|submitted|forwarded)\s+to\s*[:\-]?\s*"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"(?=\s+(?:official\s+email|email|address|"
            r"for\s+submission)\b|[.;]|$)",

            # Some notices say simply "UNICEF Nigeria official email".
            r"\b([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7}?)"
            r"\s+official\s+email\b",

            # Procurement notices may identify the requester explicitly:
            # "International Organisation for Migration (IOM) kindly requests
            # your quotation..."
            r"(?:^|[.!?]\s+)"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,10}?)"
            r"\s+kindly\s+requests?\s+"
            r"(?:your\s+)?(?:quotation|quotations|proposal|proposals|"
            r"response|responses)\b",
        )

        for pattern in explicit_patterns:
            match = re.search(pattern, combined, re.IGNORECASE)

            if not match:
                continue

            issuer = re.sub(
                r"\s+",
                " ",
                match.group(1).strip(" .,:;-"),
            )

            # "official email" is submission metadata, not part of
            # the issuer name.
            issuer = re.sub(
                r"\s+official\s+email\b.*$",
                "",
                issuer,
                flags=re.IGNORECASE,
            ).strip(" .,:;-")

            issuer = re.sub(
                r"\s+(?:is|are|has|have|seeks|seeking|"
                r"invites?|inviting|applications?|proposals?|"
                r"requests?)$",
                "",
                issuer,
                flags=re.IGNORECASE,
            ).strip(" .,:;-")

            if self._looks_like_issuer_name(issuer):
                issuer_lower = re.sub(
                    r"\s+",
                    " ",
                    issuer.lower(),
                ).strip()

                if re.search(
                    r"\bboi\s+nigeria\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                if re.search(
                    r"\bbank\s+of\s+industry(?:\s+nigeria)?\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                return issuer

        # ----------------------------------------------------------
        # Leading issuer before procurement marker.
        #
        # Example:
        #   "UNICEF-REQUEST FOR PROPOSAL ... | Public Procurement NG"
        #
        # The trailing publisher/source segment must not become the issuer.
        # ----------------------------------------------------------
        leading_procurement_issuer = re.match(
            r"^([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"\s*[-|:]\s*"
            r"(?:request\s+for\s+(?:proposal|proposals|quotation|quotations|tender|tenders)|"
            r"expression\s+of\s+interest|"
            r"invitation\s+to\s+(?:bid|tender)|"
            r"rfp|rfq|rft|itt|itb|eoi|tender)\b",
            title,
            re.IGNORECASE,
        )

        if leading_procurement_issuer:
            issuer = leading_procurement_issuer.group(1).strip(
                " .,:;-"
            )

            if self._looks_like_issuer_name(issuer):
                issuer_lower = re.sub(
                    r"\s+",
                    " ",
                    issuer.lower(),
                ).strip()

                if re.search(
                    r"\bboi\s+nigeria\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                if re.search(
                    r"\bbank\s+of\s+industry(?:\s+nigeria)?\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                return issuer

        # ----------------------------------------------------------
        # Title-based organization extraction.
        #
        # Opportunity markers are never accepted as issuers.
        # ----------------------------------------------------------
        title_parts = re.split(
            r"\s+[-|:??]\s+",
            title,
        )

        opportunity_markers = {
            "rfp",
            "rfq",
            "rft",
            "itt",
            "itb",
            "eoi",
            "tender",
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for tender",
            "request for expression of interest",
            "expression of interest",
            "invitation to bid",
            "invitation to tender",
            "terms of reference",
            "call for proposals",
        }

        if len(title_parts) >= 2:
            for part in reversed(title_parts):
                candidate = part.strip(" .,:;-")

                normalized = re.sub(
                    r"\s+",
                    " ",
                    candidate.lower(),
                ).strip()

                if normalized in opportunity_markers:
                    continue

                # Generic context labels are not issuer identities.
                if normalized in {
                    "multinational",
                    "international",
                    "national",
                    "local",
                    "regional",
                }:
                    continue

                # Procurement titles can contain job/service descriptions.
                # Do not promote those descriptions to issuer names.
                if (
                    re.search(
                        r"\b(?:graphic\s+designer|web\s+designer|"
                        r"web\s+developer|software\s+developer|"
                        r"data\s+analyst|project\s+manager|"
                        r"designer|developer|consultant|trainer|"
                        r"writer|editor)\b",
                        candidate,
                        re.IGNORECASE,
                    )
                    and re.search(
                        r"\b(?:rfp|rfq|rft|itt|itb|eoi|tender|"
                        r"request\s+for\s+(?:proposal|proposals|"
                        r"quotation|quotations|tender|tenders)|"
                        r"expression\s+of\s+interest|"
                        r"invitation\s+to\s+(?:bid|tender))\b",
                        title,
                        re.IGNORECASE,
                    )
                ):
                    continue

                # A bare domain is not an issuer identity.
                if re.fullmatch(
                    r"(?:https?://)?(?:www\.)?"
                    r"[a-z0-9.-]+\.[a-z]{2,}"
                    r"(?:/.*)?",
                    candidate,
                    re.IGNORECASE,
                ):
                    continue

                # A title fragment that merely describes the
                # requested project/service is not an issuer.
                # Examples:
                #   Meridian Website Redesign
                #   Website Development Project
                #   Graphic Design Services
                candidate_lower = re.sub(
                    r"\\s+",
                    " ",
                    candidate.lower(),
                ).strip()

                project_description_markers = (
                    "website redesign",
                    "website redevelopment",
                    "website development",
                    "web development",
                    "website design",
                    "web design",
                    "software development",
                    "software design",
                    "graphic design",
                    "digital marketing",
                    "ai solution",
                    "ai automation",
                    "data analysis",
                    "data entry",
                    "consultancy services",
                    "consulting services",
                    "training services",
                    "professional services",
                )

                if any(
                    marker in candidate_lower
                    for marker in project_description_markers
                ):
                    identity_markers = (
                        "foundation",
                        "initiative",
                        "agency",
                        "commission",
                        "ministry",
                        "bank",
                        "university",
                        "institute",
                        "council",
                        "company",
                        "corporation",
                        "organization",
                        "organisation",
                        "limited",
                        "ltd",
                        "plc",
                        "ngo",
                        "authority",
                    )

                    if not any(
                        marker in candidate_lower
                        for marker in identity_markers
                    ):
                        continue

                if self._looks_like_issuer_name(candidate):
                    return candidate

        # ----------------------------------------------------------
        # Self-identifying issuer patterns.
        #
        # Common procurement wording places the issuer immediately
        # before an action such as "is seeking" or "is pleased to invite".
        # Examples:
        #   "NEAR is seeking qualified graphic design firms..."
        #   "UNICEF Nigeria is pleased to invite your company..."
        #   "UNICEF has now issued a Request for Proposals..."
        # ----------------------------------------------------------
        self_identification_patterns = (
            r"(?:^|[.!?]\s+)"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"\s+is\s+(?:currently\s+)?"
            r"(?:seeking|looking for|requesting|inviting)\b",

            r"(?:^|[.!?]\s+)"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"\s+is\s+pleased\s+to\s+invite\b",

            r"(?:^|[.!?]\s+)"
            r"([A-Z][A-Za-z0-9&'()\-]*(?:\s+[A-Z][A-Za-z0-9&'()\-]*){0,7})"
            r"\s+has\s+(?:now\s+)?"
            r"(?:issued|published|released|advertised)\b",
        )

        for pattern in self_identification_patterns:
            match = re.search(
                pattern,
                combined,
            )

            if not match:
                continue

            issuer = re.sub(
                r"\\s+",
                " ",
                match.group(1).strip(" .,:;-"),
            ).strip(" .,:;-")

            if self._looks_like_issuer_name(issuer):
                issuer_lower = re.sub(
                    r"\\s+",
                    " ",
                    issuer.lower(),
                ).strip()

                if re.search(
                    r"\\bboi\\s+nigeria\\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                if re.search(
                    r"\\bbank\\s+of\\s+industry(?:\\s+nigeria)?\\b",
                    issuer_lower,
                    re.IGNORECASE,
                ):
                    return "Bank of Industry"

                return issuer

        # Organization relationships commonly found in opportunity documents.
        # Example: "NORCAP, part of Norwegian Refugee Council, is an international NGO."
        relationship_patterns = (
            r"\b[A-Z][A-Za-z0-9&.'()\- ]{1,50},\s+part of\s+"
            r"([A-Z][A-Za-z0-9&.'()\- ]{2,100}?)"
            r"(?=\s*,?\s+is\s+)",
            r"\b[A-Z][A-Za-z0-9&.'()\- ]{1,50},\s+a programme of\s+"
            r"([A-Z][A-Za-z0-9&.'()\- ]{2,100}?)"
            r"(?=\s*,?\s+)",
        )

        for pattern in relationship_patterns:
            match = re.search(pattern, combined, re.IGNORECASE)

            if not match:
                continue

            issuer = re.sub(
                r"\s+",
                " ",
                match.group(1).strip(" .,:;-"),
            )

            if self._looks_like_issuer_name(issuer):
                return issuer

        # Common Nigerian institutional names.
        institutional_patterns = (
            r"\bBank of Industry\b",
            r"\bCentral Bank of Nigeria\b",
            r"\bFederal Ministry of [A-Z][A-Za-z& ]+",
            r"\bMinistry of [A-Z][A-Za-z& ]+",
            r"\bNational [A-Z][A-Za-z& ]+ Agency\b",
            r"\bNigerian [A-Z][A-Za-z& ]+ Commission\b",
        )

        for pattern in institutional_patterns:
            match = re.search(
                pattern,
                combined,
                re.IGNORECASE,
            )

            if match:
                issuer = re.sub(
                    r"\s+",
                    " ",
                    match.group(0).strip(" .,:;-"),
                )

                if self._looks_like_issuer_name(issuer):
                    return issuer

        # Conservative opportunity-title fallback.
        opportunity_tail = (
            r"(?:request for proposal|request for proposals|"
            r"request for quotation|request for expression of interest|"
            r"request for tender|expression of interest|"
            r"invitation to bid|invitation to tender|"
            r"terms of reference|call for proposals|"
            r"rfp|rfq|rft|itt|itb|eoi|tender)"
        )

        match = re.match(
            rf"^(.{{3,100}}?)\s*(?:[-|:])\s*{opportunity_tail}\s*$",
            title,
            re.IGNORECASE,
        )

        if match:
            issuer = match.group(1).strip(" .,:;-")

            if self._looks_like_issuer_name(issuer):
                return issuer

        return None

    def _looks_like_issuer_name(self, value: str) -> bool:
        """Reject obvious document/service terms masquerading as issuers."""
        value = re.sub(r"\s+", " ", (value or "").strip())

        if len(value) < 3 or len(value) > 120:
            return False

        lowered = value.lower()

        # Search engines may prepend metadata labels such as "[PDF]".
        # These labels must never become part of an issuer identity.
        if re.match(r"^\[[a-z0-9 _-]+\]\s+", value, re.IGNORECASE):
            return False

        # A bare country/location token is not an issuer identity.
        if lowered in {
            "nigeria",
            "ghana",
            "kenya",
            "uganda",
            "south africa",
        }:
            return False

        # Reject generic document/page labels that cannot be an issuer.
        if lowered in {
            "pdf",
            "document",
            "template",
            "rfp",
            "rfq",
            "rft",
            "itt",
            "itb",
            "eoi",
            "tender",
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for quotations",
            "request for expression of interest",
            "request for expressions of interest",
        }:
            return False

        # Generic procurement/page titles are not issuer identities.
        # Examples:
        #   Country Office Tender Notice
        #   Tender Notice
        #   Procurement Notice
        #   Bidding Notice
        #   Solicitation Notice
        #   Contract Notice
        generic_procurement_titles = {
            "country office tender notice",
            "country office procurement notice",
            "tender notice",
            "procurement notice",
            "bidding notice",
            "bid notice",
            "solicitation notice",
            "contract notice",
            "tender document",
            "procurement document",
            "procurement announcement",
            "tender announcement",
        }

        if lowered in generic_procurement_titles:
            return False

        # Do not accept generic "X Tender Notice" / "X Procurement Notice"
        # labels unless X itself contains a clear organizational identity.
        if re.fullmatch(
            r"(?:country office|regional office|field office|"
            r"head office|main office|project office|"
            r"procurement|tender|bidding|solicitation|contract)"
            r"(?:\s+(?:notice|document|announcement))",
            lowered,
            re.IGNORECASE,
        ):
            return False

        # Procurement labels with parenthetical abbreviations are still
        # document labels, not issuer identities.
        if re.fullmatch(
            r"(?:pdf\s+)?"
            r"(?:request for proposals?|"
            r"request for quotations?|"
            r"request for expressions? of interest|"
            r"request for tenders?|"
            r"expression of interest|"
            r"invitation to (?:bid|tender)|"
            r"terms of reference|"
            r"call for proposals)"
            r"(?:\s*\((?:rfp|rfq|rft|itt|itb|eoi)\))?",
            lowered,
            re.IGNORECASE,
        ):
            return False

        # Reject filename-like document tokens masquerading as issuers.
        # Examples: VKEAK_JIPS_Final, Project_Proposal_Final, RFP_Draft_v2.
        if "_" in value:
            issuer_terms = (
                "limited", "ltd", "llc", "inc", "plc", "company",
                "corporation", "bank", "agency", "ministry", "commission",
                "council", "foundation", "university", "institute",
                "organization", "organisation", "ngo",
            )

            if not any(term in lowered.split() for term in issuer_terms):
                if re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)+", lowered):
                    return False

                if re.search(
                    r"_(?:final|draft|revised|revision|rev|v\d+|\d+[a-z]{3,9})$",
                    lowered,
                ):
                    return False

        # Reject obvious RFP directory/category titles rather than treating them as issuers.
        if re.search(r"\b(?:rfp|rfqs|tenders|procurement)\b", lowered) and re.search(r"\b(?:web design|website design|web development|website development)\b", lowered):
            return False

        rejected = (
            "request for proposal",
            "request for quotation",
            "expression of interest",
            "terms of reference",
            "invitation to bid",
            "call for proposals",
            "website development",
            "website design",
            "website redesign",
            "website redevelopment",
            "web development",
            "graphic design",
            "digital marketing",
            "ai solution",
            "ai automation",
            "consultancy",
            "consultant",
        )

        if lowered in rejected:
            return False

        # A bare domain is a source identifier, not an issuer identity.
        # Do not promote values such as "ipcng.org" or "example.com"
        # to original_issuer.
        if re.fullmatch(
            r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+/?",
            lowered,
        ):
            return False

        return True

    def _is_opportunity_result(
        self,
        query: str,
        title: str,
        snippet: str,
    ) -> bool:
        """Detect an opportunity even when the query itself is broad."""
        # IMPORTANT:
        # The search query is context only and must never count as evidence.
        # Opportunity evidence must come from the returned result itself.
        combined = " ".join(
            (
                title or "",
                snippet or "",
            )
        ).lower()

        signals = (
            "request for proposal",
            "request for proposals",
            "requests for proposal",
            "requests for proposals",
            "request for quotation",
            "request for quotations",
            "requests for quotation",
            "requests for quotations",
            "request for expression of interest",
            "request for expressions of interest",
            "requests for expression of interest",
            "requests for expressions of interest",
            "expression of interest",
            "expressions of interest",
            "call for proposals",
            "invitation to bid",
            "terms of reference",
            "rfp",
            "rfq",
            "eoi",
            "vendor needed",
            "contractor needed",
            "consultant needed",
            "seeking a consultant",
            "seeking consultant",
        )

        return any(signal in combined for signal in signals)

    def _prospect_score(
        self,
        result: Dict[str, Any],
    ) -> int:

        title = self._clean_text(
            result.get(
                "title",
                "",
            )
        )

        snippet = self._clean_text(
            result.get(
                "body",
                "",
            )
        )

        title_lower = title.lower()
        snippet_lower = snippet.lower()

        url = self._unwrap_url(
            result.get(
                "href",
                "",
            )
        )

        if not url:
            return -100

        domain = (
            self._domain_from_url(
                url
            )
        )

        if not self._is_allowed_domain(
            domain
        ):
            return -100

        path = urlparse(
            url
        ).path.lower()

        if self._is_obvious_non_prospect(
            title,
            snippet,
            path,
            domain,
        ):
            return -100

        score = 0

        combined = (
            f"{title_lower} "
            f"{snippet_lower} "
            f"{domain} "
            f"{path}"
        )

        # BUYER_PROVIDER_SCORING_ADDITIONS
        buying_intent_hits = sum(
            phrase in combined
            for phrase in self.BUYING_INTENT_PHRASES
        )

        provider_hits = sum(
            phrase in combined
            for phrase in self.SERVICE_PROVIDER_PHRASES
        )

        score += min(buying_intent_hits * 20, 40)
        score -= min(provider_hits * 18, 54)


        if any(
            phrase in combined
            for phrase in self.INFORMATIONAL_PHRASES
        ):
            score -= 100

        for pattern in self.NON_PROSPECT_TITLE_PATTERNS:

            if re.search(
                pattern,
                title_lower,
                re.IGNORECASE,
            ):
                score -= 100

        marker_sets = (
            self.JOB_PATH_MARKERS,
            self.MARKETPLACE_PATH_MARKERS,
            self.DIRECTORY_PATH_MARKERS,
            self.ARTICLE_PATH_MARKERS,
            self.NON_PROSPECT_PATH_MARKERS,
        )

        for marker_set in marker_sets:

            if any(
                marker in path
                for marker in marker_set
            ):
                score -= 100

        if self._looks_like_article_slug(
            path
        ):
            score -= 100

        if re.search(
            r"\.(pdf|doc|docx|ppt|pptx|xls|xlsx)$",
            path,
            re.IGNORECASE,
        ):
            score -= 100

        person_hits = sum(
            signal in combined
            for signal in self.PERSON_SIGNALS
        )

        business_hits = sum(
            signal in combined
            for signal in self.BUSINESS_SIGNALS
        )

        organization_hits = sum(
            signal in combined
            for signal in self.ORGANIZATION_SIGNALS
        )

        strong_org_hits = sum(
            signal in combined
            for signal in self.STRONG_ORGANIZATION_SIGNALS
        )

        score += min(
            person_hits * 12,
            36,
        )

        score += min(
            business_hits * 10,
            50,
        )

        score += min(
            organization_hits * 5,
            30,
        )

        score += min(
            strong_org_hits * 7,
            35,
        )

        if domain:
            score += 10

        page_type = self._page_type(
            url
        )

        if page_type == "homepage":
            score += 30

        elif page_type == "about":
            score += 15

        elif page_type == "contact":
            score += 10

        elif page_type == "service":
            score -= 15

        if self._looks_like_real_organization(
            title,
            snippet,
            domain,
            path,
        ):
            score += 15

        if self._is_generic_title(
            title
        ):
            score -= 30

        return score

    # ============================================================
    # NON-PROSPECT DETECTION
    # ============================================================

    def _is_obvious_non_prospect(
        self,
        title: str,
        snippet: str,
        path: str,
        domain: str,
    ) -> bool:

        title = title.lower()
        snippet = snippet.lower()
        path = path.lower()
        domain = domain.lower()

        # Normalize URL path before recruitment checks.
        # Search-result URLs may append query strings such as:
        #   /jobs?search_keyword=graphic+designer
        #   /careers?page=2
        # The query string must not prevent the root recruitment path
        # from being recognized.
        path = path.split("?", 1)[0].split("#", 1)[0].rstrip("/")

        # Reject generic PDF procurement labels with no issuer identity.
        # Legitimate issuer-named procurement PDFs are handled normally.
        if re.fullmatch(
            r"pdf\s+request for proposals?\s*\(?(?:rfp)?\)?",
            title.strip(),
            re.IGNORECASE,
        ):
            return True

        blocked_procurement_domains = {
            "tendersontime.com",
            "nigeriantenders.com",
            "nigeriatenders.com",
            "thebiddaily.com",
            "getawebsite.com.ng",
            "etenders.com.ng",
            "ebid.com.ng",
            "globaltenders.com",
            "tendersinfo.com",
            "app.tendersgo.com",
            "bidassist.com",
            "tenderimpulse.com",
              "ngojobsite.com",
            "bpp.gov.ng",
            "publicprocurement.org",
            "connectnigeria.com",
            "biddetail.com",
        }
        blocked_content_domains = {
            "nigeriaworld.com",
            "nairametrics.com",
            "papers.com.ng",
            "fundsforngos.org",
            "template.net",
        }

        if (
            domain in blocked_procurement_domains
            or any(
                domain.endswith(
                    "." + blocked
                )
                for blocked in blocked_procurement_domains
            )
        ):
            return True

        if (
            domain in blocked_content_domains
            or any(
                domain.endswith(
                    "." + blocked
                )
                for blocked in blocked_content_domains
            )
        ):
            return True
        if (
            domain == "articles.connectnigeria.com"
            or domain.endswith(".articles.connectnigeria.com")
        ):
            return True

        combined_nonprospect = f"{title} {snippet}"
        # Reject obvious pagination, sample/template, job-alert, and
        # directory/index pages that can otherwise accumulate generic
        # organization signals and pass the prospect score gate.
        # Keep this conservative: legitimate company pages and genuine
        # procurement/opportunity pages are handled by the existing gates.
        if re.fullmatch(
            r"(?:pg|p\.|page)\s*\d+",
            title.strip(),
            re.IGNORECASE,
        ):
            return True

        informational_sample = re.search(
            r"\b(?:cv|resume)\s+(?:sample|samples|example|examples|template|templates)\b"
            r"|\b(?:writing guide|how to write|step[- ]by[- ]step guide)\b"
            r"|\b(?:template|templates)\s+(?:for|of)\b",
            combined_nonprospect,
            re.IGNORECASE,
        )
        if informational_sample:
            return True

        job_aggregator = re.search(
            r"\b(?:latest|latest job|new)\s+(?:job )?vacanc(?:y|ies)\b"
            r"|\bjob\s+alerts?\b"
            r"|\bjob\s+listings?\b"
            r"|\bvacanc(?:y|ies)\s+listings?\b"
            r"|\b(?:jobs|vacancies)\s+in\s+(?:nigeria|lagos|abuja|kano)\b",
            combined_nonprospect,
            re.IGNORECASE,
        )
        if job_aggregator:
            return True

        directory_index = re.search(
            r"\b(?:directory|directories|rankings?|ranking|index|indices|"
            r"marketplace|listing|listings|search results|top \d+)\b",
            combined_nonprospect,
            re.IGNORECASE,
        )
        if directory_index:
            return True


        # Policy / legislation pages.
        if re.search(
            r"\b(?:bill for an act|act to regulate|proposed bill|"
            r"draft bill|legislation|legislative framework|policy framework|"
            r"regulatory framework)\b",
            combined_nonprospect,
            re.IGNORECASE,
        ):
            return True

        if (
            re.search(r"\bnational\b", title, re.IGNORECASE)
            and re.search(r"\b(?:strategy|policy)\b", title, re.IGNORECASE)
            and re.search(
                r"\b(?:government|governance|policy|sustainable development|"
                r"federal|national)\b",
                combined_nonprospect,
                re.IGNORECASE,
            )
        ):
            return True

        # Tender/procurement intelligence and e-procurement platforms.
        procurement_platform = re.search(
            r"\b(?:tender|tenders|procurement|contract)\b"
            r".{0,80}"
            r"\b(?:platform|portal|intelligence|database|tracker|tracking|"
            r"transparency|analytics|data)\b",
            combined_nonprospect,
            re.IGNORECASE | re.DOTALL,
        ) or re.search(
            r"\b(?:platform|portal|intelligence|database|tracker|tracking|"
            r"transparency|analytics|data)\b"
            r".{0,80}"
            r"\b(?:tender|tenders|procurement|contract)\b",
            combined_nonprospect,
            re.IGNORECASE | re.DOTALL,
        )

        if procurement_platform:
            return True

        # Public/open-data portals.
        if re.search(
            r"\b(?:data portal|open data|open-data|data catalog|"
            r"data catalogue|data explorer|data repository)\b",
            combined_nonprospect,
            re.IGNORECASE,
        ):
            return True

        if (
            re.search(r"\b(?:explore|analyze|analyse|browse)\b", snippet)
            and re.search(r"\b(?:government|public)\b", snippet)
            and re.search(r"\b(?:procurement|contracts?|budgets?)\b", snippet)
            and re.search(r"\b(?:data|projects?)\b", snippet)
        ):
            return True

        # AI ecosystem pages are informational unless they clearly sell
        # AI services.
        if (
            re.search(
                r"\b(?:ai|artificial intelligence)\b",
                combined_nonprospect,
                re.IGNORECASE,
            )
            and re.search(
                r"\bai ecosystem\b",
                combined_nonprospect,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:stakeholders|global partners|localising|localizing|"
                r"ecosystem)\b",
                combined_nonprospect,
                re.IGNORECASE,
            )
            and not re.search(
                r"\b(?:agency|consulting|consultancy|developer|"
                r"development company|solution provider)\b",
                combined_nonprospect,
                re.IGNORECASE,
            )
        ):
            return True


        if (
            domain in self.MARKETPLACE_DOMAINS
            or any(
                domain.endswith(
                    "." + marketplace
                )
                for marketplace in self.MARKETPLACE_DOMAINS
            )
        ):
            return True

        dated_path = re.search(
            r"/20\d{2}/\d{1,2}(?:/\d{1,2})?/",
            path,
        )

        document_path = re.search(
            r"\.(?:pdf|doc|docx|ppt|pptx|xls|xlsx)$",
            path,
            re.IGNORECASE,
        )

        procurement_text = f"{title} {snippet}"

        explicit_procurement_document = (
            document_path
            and re.search(
                r"\b(?:rfp|rfq|rft|itt|itb|"
                r"request for proposals?|"
                r"request for quotations?|"
                r"request for expressions? of interest|"
                r"expression of interest|"
                r"terms of reference|"
                r"invitation to bid|"
                r"call for proposals)\b",
                procurement_text,
                re.IGNORECASE,
            )
        )

        if dated_path and not explicit_procurement_document:
            return True

        if any(
            marker in path
            for marker in (
                "/grant/",
                "/grants/",
                "/fund/",
                "/funds/",
                "/funding/",
                "/scholarship/",
                "/scholarships/",
            )
        ):
            return True

        # Recruitment and role pages are not sales opportunities.
        recruitment_path_markers = (
            "/job/",
            "/jobs/",
            "/career/",
            "/careers/",
            "/vacancy/",
            "/vacancies/",
            "/position/",
            "/positions/",
            "/hiring/",
            "/employment/",
            "/internship/",
            "/internships/",
            "/role/",
            "/roles/",
        )

        recruitment_title_patterns = (
            r"\bdigital marketer\b",
            r"\bmarketing manager\b",
            r"\bgraphic designer\b",
            r"\bweb developer\b",
            r"\bwebsite developer\b",
            r"\bsoftware developer\b",
            r"\bdata analyst\b",
            r"\bproject manager\b",
            r"\bvacancy\b",
            r"\bjob description\b",
            r"\bopen jobs?\b",
            r"\bjob openings?\b",
            r"\blatest jobs?\b",
            r"\b(?:we are|is|are) recruiting\b",
        )

        # Root recruitment pages are commonly returned without a
        # trailing slash, e.g. /jobs or /career.
        recruitment_root_paths = {
            "/job",
            "/jobs",
            "/career",
            "/careers",
            "/vacancy",
            "/vacancies",
            "/position",
            "/positions",
            "/hiring",
            "/employment",
            "/internship",
            "/internships",
            "/role",
            "/roles",
        }

        if path.rstrip("/") in recruitment_root_paths:
            return True

        if any(marker in path for marker in recruitment_path_markers):
            return True

        # Job aggregators frequently use URLs such as /jobs-keyword/
        # instead of the conventional /jobs/ path.
        if re.search(
            r"/(?:jobs?|careers?|vacancies?|positions?|roles?)-",
            path,
            re.IGNORECASE,
        ):
            return True

        # Marketplace/category paths such as:
        # /excel-freelancers-in-nigeria
        # /hire-excel-experts/
        if re.search(
            r"/[^/]*(?:freelancers?|freelance|gigs?|"
            r"experts?|professionals?)(?:-|/)",
            path,
            re.IGNORECASE,
        ):
            return True

        if re.search(
            r"/(?:hire|find|book)-[^/]*(?:experts?|freelancers?|"
            r"professionals?|specialists?)(?:-|/)",
            path,
            re.IGNORECASE,
        ):
            return True

        if any(
            re.search(pattern, title, re.IGNORECASE)
            for pattern in recruitment_title_patterns
        ):
            recruitment_language = (
                "apply",
                "candidate",
                "qualifications",
                "responsibilities",
                "job description",
                "employment",
                "salary",
                "position",
                "vacancy",
                "hiring",
            )

            if any(term in snippet for term in recruitment_language):
                return True

        if re.search(
            r"^(meet \d+|apply for|this .* founder|"
            r"how to|what is|what are|why |guide|"
            r"top |best |list of)",
            title,
            re.IGNORECASE,
        ):
            return True

        if re.search(
            r"\b(startup founders?|founders?)\b.*\b"
            r"(million|billion|ecosystem|funding|grant)\b",
            title,
            re.IGNORECASE,
        ):
            return True

        # Generic institutional/project pages are not opportunity evidence
        # merely because their snippets mention procurement-related terms.
        # Require an explicit opportunity signal in the title or URL path.
        opportunity_markers = (
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for expression of interest",
            "request for expressions of interest",
            "expression of interest",
            "expressions of interest",
            "invitation to bid",
            "invitation for bids",
            "call for proposals",
            "terms of reference",
            "tender notice",
            "tender",
            "rfp",
            "rfq",
            "eoi",
        )

        title_or_path = f"{title} {path}"

        has_explicit_opportunity_marker = any(
            marker in title_or_path
            for marker in opportunity_markers
        )

        if (
            self._looks_like_article_slug(path)
            and not has_explicit_opportunity_marker
        ):
            return True

        blocked_fragments = (
            *self.DIRECTORY_PATH_MARKERS,
            *self.MARKETPLACE_PATH_MARKERS,
            *self.NON_PROSPECT_PATH_MARKERS,
            "/mentions/",
            "/mention/",
        )

        if any(
            marker in path
            for marker in blocked_fragments
        ):
            return True

        if any(
            term in title
            for term in (
                "market research",
                "market report",
                "market forecast",
                "market size",
                "industry report",
                "research paper",
                "research study",
                "white paper",
                "whitepaper",
                "mentions",
            )
        ):
            return True

        if any(
            phrase in snippet
            for phrase in (
                "this article",
                "this report",
                "this study",
                "download the report",
                "directory of",
                "list of companies",
            )
        ):
            return True

        if re.search(
            r"^(top|best|list of|companies in|"
            r"ai companies|startups in|"
            r"top entrepreneurs)",
            title,
            re.IGNORECASE,
        ):
            return True

        directory_terms = (
            "catalog",
            "directory",
            "ranking",
            "rankings",
            "marketresearch",
            "research",
            "database",
            "readycontacts",
            "techbehemoths",
            "wellfound",
            "f6s",
        )

        if any(
            term in domain
            for term in directory_terms
        ):
            return True

        return False

    def _is_prospect_candidate(
        self,
        result: Dict[str, Any],
        score: Optional[int] = None,
    ) -> bool:

        if score is None:
            score = self._prospect_score(
                result
            )

        if score < 45:
            return False

        url = self._unwrap_url(
            result.get(
                "href",
                "",
            )
        )

        if not url:
            return False

        title = self._clean_text(
            result.get(
                "title",
                "",
            )
        )

        snippet = self._clean_text(
            result.get(
                "body",
                "",
            )
        )

        domain = (
            self._domain_from_url(
                url
            )
        )

        path = urlparse(
            url
        ).path.lower()

        if not self._is_allowed_domain(
            domain
        ):
            return False

        if self._is_obvious_non_prospect(
            title,
            snippet,
            path,
            domain,
        ):
            return False

        if self._looks_like_article_slug(
            path
        ):
            return False

        if self._is_generic_title(
            title
        ):
            if not self._has_strong_organization_identity(
                title,
                snippet,
                domain,
            ):
                return False

        combined = (
            f"{title.lower()} "
            f"{snippet.lower()} "
            f"{domain}"
        )

        # PROVIDER_ONLY_GATE_ADDITION
        buying_intent_hits = sum(
            phrase in combined
            for phrase in self.BUYING_INTENT_PHRASES
        )

        # GENERIC_HOME_PROVIDER_FILTER_ADDITION
        title_normalized = re.sub(
            r"\s+",
            " ",
            title.strip().lower(),
        )

        generic_home_title = (
            title_normalized in {
                "home",
                "welcome",
            }
            or title_normalized.startswith("welcome to ")
        )

        provider_context = (
            f'{title_normalized} '
            f'{snippet.lower()} '
            f'{domain}'
        )

        provider_context_hits = sum(
            phrase in provider_context
            for phrase in (
                "web design",
                "website design",
                "web development",
                "website development",
                "web solutions",
                "website builder",
                "website builders",
                "digital marketing",
                "graphic design",
                "software development",
                "ecommerce",
            )
        )

        if generic_home_title and provider_context_hits >= 2:
            return False

        # PROVIDER_TITLE_FILTER_ADDITION
        provider_title_match = any(
            re.search(
                pattern,
                title,
                re.IGNORECASE,
            )
            for pattern in self.PROVIDER_TITLE_PATTERNS
        )

        # Search-engine snippets from provider pages often contain
        # incidental buyer-language such as "need a website".
        # Do not allow that snippet language to override a clear
        # provider identity in the page title.
        buyer_title_match = any(
            phrase in title.lower()
            for phrase in self.BUYING_INTENT_PHRASES
        )

        if provider_title_match and not buyer_title_match:
            return False

        provider_hits = sum(
            phrase in combined
            for phrase in self.SERVICE_PROVIDER_PHRASES
        )

        if provider_hits >= 2 and buying_intent_hits == 0:
            return False


        identity_hits = sum(
            signal in combined
            for signal in self.PERSON_SIGNALS
        )

        business_hits = sum(
            signal in combined
            for signal in self.BUSINESS_SIGNALS
        )

        organization_hits = sum(
            signal in combined
            for signal in self.ORGANIZATION_SIGNALS
        )

        real_org = (
            self._looks_like_real_organization(
                title,
                snippet,
                domain,
                path,
            )
        )

        if (
            identity_hits == 0
            and business_hits < 2
            and organization_hits < 3
            and not real_org
        ):
            return False

        for pattern in self.SERVICE_TITLE_PATTERNS:

            if re.search(
                pattern,
                title.lower(),
                re.IGNORECASE,
            ):

                if not self._has_strong_organization_identity(
                    title,
                    snippet,
                    domain,
                ):
                    return False

        return True

    # ============================================================
    # ARTICLE SLUG DETECTION
    # ============================================================

    def _looks_like_article_slug(
        self,
        path: str,
    ) -> bool:

        path = (
            path
            .lower()
            .strip("/")
        )

        if not path:
            return False

        segments = [
            segment
            for segment in path.split("/")
            if segment
        ]

        for segment in segments:

            for term in self.ARTICLE_SLUG_TERMS:

                if term.endswith("-"):

                    if segment.startswith(
                        term
                    ):
                        return True

                elif term in segment:
                    return True

        if re.search(
            r"/20\d{2}/\d{1,2}(?:/\d{1,2})?/",
            "/" + path + "/",
        ):
            return True

        if len(segments) == 1:

            slug = segments[0]

            if slug.count("-") >= 5:

                editorial_words = (
                    "business",
                    "artificial",
                    "intelligence",
                    "consulting",
                    "implementation",
                    "technology",
                    "nigeria",
                    "company",
                    "founder",
                    "startup",
                    "grant",
                    "fund",
                    "funding",
                    "empower",
                    "million",
                    "billion",
                    "ecosystem",
                )

                if any(
                    word in slug
                    for word in editorial_words
                ):
                    return True

            if any(
                slug.startswith(prefix)
                for prefix in (
                    "meet-",
                    "apply-for-",
                    "this-",
                    "how-to-",
                    "what-is-",
                    "what-are-",
                    "why-",
                    "guide-",
                    "best-",
                    "top-",
                    "list-of-",
                )
            ):
                return True

            if any(
                phrase in slug
                for phrase in (
                    "founder-left-",
                    "startup-founders",
                    "second-time-founder",
                    "grant-",
                    "funding-",
                    "empower-",
                )
            ):
                return True

        return False

    # ============================================================
    # PAGE TYPE
    # ============================================================

    def _page_type(
        self,
        url: str,
    ) -> str:

        path = urlparse(
            url
        ).path.lower()

        if path in (
            "",
            "/",
        ):
            return "homepage"

        normalized = (
            path.rstrip("/")
            + "/"
        )

        if normalized in {
            "/about/",
            "/about-us/",
        }:
            return "about"

        if normalized in {
            "/contact/",
            "/contact-us/",
        }:
            return "contact"

        if normalized in self.GENERIC_SERVICE_PATHS:
            return "service"

        if any(
            marker in path
            for marker in self.GENERIC_SERVICE_PATHS
        ):
            return "service"

        if self._looks_like_article_slug(
            path
        ):
            return "article"

        if re.search(
            r"/20\d{2}/\d{1,2}(?:/\d{1,2})?/",
            path,
        ):
            return "article"

        if any(
            marker in path
            for marker in (
                "/grant/",
                "/grants/",
                "/fund/",
                "/funds/",
                "/funding/",
                "/scholarship/",
                "/scholarships/",
            )
        ):
            return "article"

        return "internal"

    def _page_priority(
        self,
        url: str,
    ) -> int:

        page_type = self._page_type(
            url
        )

        return {
            "homepage": 4,
            "about": 3,
            "contact": 2,
            "internal": 1,
            "service": 0,
            "article": -1,
        }.get(
            page_type,
            1,
        )

    # ============================================================
    # ORGANIZATION DETECTION
    # ============================================================

    def _looks_like_real_organization(
        self,
        title: str,
        snippet: str,
        domain: str,
        path: str,
    ) -> bool:

        combined = (
            f"{title.lower()} "
            f"{snippet.lower()} "
            f"{domain.lower()}"
        )

        strong_hits = sum(
            signal in combined
            for signal in self.STRONG_ORGANIZATION_SIGNALS
        )

        organization_hits = sum(
            signal in combined
            for signal in self.ORGANIZATION_SIGNALS
        )

        if path in (
            "",
            "/",
        ):

            if strong_hits >= 1:
                return True

            if organization_hits >= 3:
                return True

            if re.search(
                r"\b(ltd|limited|llc|inc|corp|"
                r"technologies|technology|solutions|"
                r"systems|labs|robotics|ai)\b",
                title.lower(),
            ):
                return True

        return strong_hits >= 2

    def _has_strong_organization_identity(
        self,
        title: str,
        snippet: str,
        domain: str,
    ) -> bool:

        combined = (
            f"{title.lower()} "
            f"{snippet.lower()} "
            f"{domain.lower()}"
        )

        strong_hits = sum(
            signal in combined
            for signal in self.STRONG_ORGANIZATION_SIGNALS
        )

        organization_hits = sum(
            signal in combined
            for signal in self.ORGANIZATION_SIGNALS
        )

        return (
            bool(domain)
            and (
                strong_hits >= 2
                or organization_hits >= 4
            )
        )

    def _is_generic_title(
        self,
        title: str,
    ) -> bool:

        normalized = (
            self._clean_text(
                title
            ).lower()
        )

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return (
            normalized
            in self.GENERIC_TITLES
        )

    # ============================================================
    # DOMAIN HANDLING
    # ============================================================

    def _is_allowed_domain(
        self,
        domain: str,
    ) -> bool:

        if not domain:
            return False

        domain = (
            domain
            .lower()
            .strip()
        )

        if domain.startswith(
            "www."
        ):
            domain = domain[4:]

        for blocked in self.BLOCKED_DOMAINS:

            blocked = (
                blocked
                .lower()
                .strip()
            )

            if blocked.startswith(
                "www."
            ):
                blocked = blocked[4:]

            if (
                domain == blocked
                or domain.endswith(
                    "." + blocked
                )
            ):
                return False

        return not any(
            value in domain
            for value in (
                "google.",
                "bing.",
                "duckduckgo.",
                "yahoo.",
            )
        )

    def _unwrap_url(
        self,
        url: Any,
    ) -> str:

        if not url:
            return ""

        url = unquote(
            str(url).strip()
        )

        parsed = urlparse(
            url
        )

        query = parse_qs(
            parsed.query
        )

        for key in (
            "uddg",
            "url",
            "target",
            "dest",
            "destination",
        ):

            values = query.get(
                key
            )

            if values:

                candidate = unquote(
                    values[0]
                )

                if candidate.startswith(
                    (
                        "http://",
                        "https://",
                    )
                ):
                    url = candidate
                    break

        if not url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return ""

        parsed = urlparse(
            url
        )

        if not parsed.netloc:
            return ""

        return parsed._replace(
            fragment=""
        ).geturl()

    def _domain_from_url(
        self,
        url: str,
    ) -> str:

        try:

            hostname = (
                urlparse(
                    url
                ).hostname
                or ""
            )

            hostname = (
                hostname
                .lower()
                .strip()
            )

            if hostname.startswith(
                "www."
            ):
                hostname = hostname[4:]

            return hostname

        except Exception:
            return ""

    def _root_domain(
        self,
        url: str,
    ) -> str:

        domain = (
            self._domain_from_url(
                url
            )
        )

        if not domain:
            return ""

        parts = domain.split(
            "."
        )

        if len(parts) <= 2:
            return domain

        suffix = ".".join(
            parts[-2:]
        )

        if suffix in self.MULTI_PART_SUFFIXES:

            if len(parts) >= 3:
                return ".".join(
                    parts[-3:]
                )

        return ".".join(
            parts[-2:]
        )

    # ============================================================
    # DISPLAY / USERNAME
    # ============================================================

    def _display_name(
        self,
        title: str,
        url: str,
    ) -> str:

        title = self._clean_text(
            title
        )

        if title:

            cleaned = re.split(
                r"\s*(?:\||\s-\s|\sÃ¢â‚¬â€œ\s|\sÃ¢â‚¬â€\s)\s*",
                title,
                maxsplit=1,
            )[0].strip()

            if cleaned:
                return cleaned[:250]

        domain = (
            self._domain_from_url(
                url
            )
        )

        return (
            domain
            or "Unknown Prospect"
        )

    def _username_from_url(
        self,
        url: str,
    ) -> str:

        parts = [
            part.strip()
            for part in urlparse(
                url
            ).path.split("/")
            if part.strip()
        ]

        blocked = {
            "search",
            "results",
            "result",
            "services",
            "service",
            "solutions",
            "solution",
            "about",
            "about-us",
            "contact",
            "contact-us",
            "company",
            "companies",
            "ai",
            "consulting",
            "consultancy",
            "consultant",
            "consultants",
            "profile",
            "profiles",
            "users",
            "user",
            "hire",
            "freelancers",
            "freelancer",
            "jobs",
            "job",
        }

        for candidate in reversed(
            parts
        ):

            candidate = re.sub(
                r"\.(html?|php|aspx?)$",
                "",
                candidate,
                flags=re.IGNORECASE,
            )

            candidate = re.sub(
                r"[^A-Za-z0-9_.-]+",
                "",
                candidate,
            )

            if (
                candidate
                and candidate.lower()
                not in blocked
            ):
                return candidate[:100]

        domain = (
            self._domain_from_url(
                url
            )
        )

        return (
            domain.split(".")[0][:100]
            if domain
            else "unknown"
        )

    def _safe_slug(
        self,
        value: str,
    ) -> str:

        value = re.sub(
            r"[^A-Za-z0-9]+",
            "-",
            value,
        )

        return (
            value.strip("-")
            .lower()[:100]
            or "unknown"
        )

    # ============================================================
    # DEDUPLICATION
    # ============================================================

    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        unique = []
        seen_urls = set()

        for result in results:

            if not isinstance(
                result,
                dict,
            ):
                continue

            url = self._unwrap_url(
                result.get(
                    "href",
                    "",
                )
            )

            if not url:
                continue

            normalized = (
                url.rstrip("/")
                .lower()
            )

            if normalized in seen_urls:
                continue

            seen_urls.add(
                normalized
            )

            item = dict(
                result
            )

            item["href"] = url

            unique.append(
                item
            )

        return unique

    # ============================================================
    # TEXT CLEANING
    # ============================================================

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):

            values = []

            for item in value:

                cleaned = (
                    GoogleSearchScraper._clean_text(
                        item
                    )
                )

                if cleaned:
                    values.append(
                        cleaned
                    )

            return " ".join(
                values
            )

        if isinstance(
            value,
            dict,
        ):

            values = []

            for item in value.values():

                cleaned = (
                    GoogleSearchScraper._clean_text(
                        item
                    )
                )

                if cleaned:
                    values.append(
                        cleaned
                    )

            return " ".join(
                values
            )

        text = str(
            value
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()














































