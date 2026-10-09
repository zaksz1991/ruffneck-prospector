import re
"""
Free job-board scrapers – expanded.
Sources (all free/public):
- RemoteOK (public JSON)
- We Work Remotely
- Indeed (best-effort)
- Remotive (public API)
- Arbeitnow (public)
- Jobicy (public RSS-ish / API)
Used to surface companies hiring for roles that signal need for digital services.
"""
from typing import List, Optional
import logging
import requests
from urllib.parse import quote_plus, parse_qsl, urlencode, urlsplit, urlunsplit
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class JobBoardScraper(BaseScraper):
    platform = "jobs"

    def __init__(self, max_results: int = 40):
        super().__init__(max_results)

    # Service-demand patterns relevant to RuffNeck services.
    # Title matches are intentionally stronger than description/tag matches.
    SERVICE_INTENTS = {
        "digital_marketing": [
            "digital marketing",
            "marketing specialist",
            "marketing manager",
            "marketing coordinator",
            "marketing assistant",
            "marketing student assistant",
            "marketing intern",
            "marketing trainee",
            "marketing operations specialist",
            "marketing operations manager",
            "marketing operations",
            "marketing analyst",
            "marketing associate",
            "marketing executive",
            "social media manager",
            "social media specialist",
            "social media coordinator",
            "seo specialist",
            "seo manager",
            "seo analyst",
            "content marketing",
            "growth marketing",
            "email marketing",
        ],
        "web_development": [
            "web developer",
            "web development",
            "frontend developer",
            "front end developer",
            "backend developer",
            "back end developer",
            "full stack developer",
            "full-stack developer",
            "wordpress developer",
            "wordpress specialist",
            "software developer",
            "software engineer",
        ],
        "graphic_design": [
            "graphic designer",
            "graphic design",
            "ui designer",
            "ux designer",
            "ui/ux designer",
            "visual designer",
            "brand designer",
        ],
        "content_creation": [
            "content creator",
            "content writer",
            "copywriter",
            "technical writer",
            "content specialist",
            "content manager",
        ],
        "video_creative": [
            "video editor",
            "video producer",
            "motion designer",
            "motion graphics",
            "multimedia designer",
        ],
        "data_analysis": [
            "data analyst",
            "business analyst",
            "business intelligence",
            "bi analyst",
            "power bi",
            "data visualization",
        ],
        "data_entry": [
            "data entry",
            "data entry clerk",
            "data entry administrator",
            "data entry specialist",
            "data processing",
        ],
        "excel": [
            "excel specialist",
            "excel analyst",
            "excel reporting",
            "spreadsheet specialist",
            "spreadsheet analyst",
        ],
        "virtual_assistance": [
            "virtual assistant",
            "virtual administrative assistant",
            "remote assistant",
            "executive assistant",
            "administrative assistant",
            "admin assistant",
        ],
        "administration": [
            "administrative officer",
            "administrative coordinator",
            "office administrator",
            "office assistant",
            "operations assistant",
            "project assistant",
        ],
        "ai": [
            "ai specialist",
            "artificial intelligence specialist",
            "ai engineer",
            "machine learning engineer",
            "machine learning specialist",
            "generative ai",
        ],
    }

    def _classify_job_intent(
        self,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> dict:
        """
        Classify a job according to RuffNeck-relevant service demand.

        Title matches are strongest. Description matches provide supporting
        evidence. Generic board tags are deliberately not sufficient on their
        own because job boards often attach broad tags unrelated to the actual
        role.
        """
        title_text = (title or "").lower()
        description_text = (description or "").lower()
        tag_text = " ".join(tags or []).lower()

        matches = []
        title_matches = []
        supporting_matches = []

        for category, patterns in self.SERVICE_INTENTS.items():
            for pattern in patterns:
                if pattern in title_text:
                    title_matches.append((category, pattern))
                elif pattern in description_text:
                    supporting_matches.append((category, pattern))

        # Strong signal: explicit service-related title.
        if title_matches:
            for category, pattern in title_matches:
                if (category, pattern) not in matches:
                    matches.append((category, pattern))

            category = matches[0][0]
            return {
                "job_intent": True,
                "job_intent_level": "high",
                "job_intent_category": category,
                "job_intent_matches": [p for _, p in matches],
                "job_intent_score": min(100, 80 + len(matches) * 5),
            }

        # Supporting description evidence is weaker and requires an
        # explicit phrase, not a generic word such as "marketing" or "data".
        if supporting_matches:
            category = supporting_matches[0][0]
            return {
                "job_intent": True,
                "job_intent_level": "medium",
                "job_intent_category": category,
                "job_intent_matches": [p for _, p in supporting_matches[:5]],
                "job_intent_score": 50,
            }

        return {
            "job_intent": False,
            "job_intent_level": "low",
            "job_intent_category": None,
            "job_intent_matches": [],
            "job_intent_score": 0,
        }

    def _expand_job_query(self, query: str) -> List[str]:
        """
        Expand a RuffNeck service/job query into related job-title terms.

        The board scrapers perform literal substring matching, so a query
        such as "web developer" would otherwise miss "Frontend Developer",
        "Backend Developer", etc.
        """
        q = (query or "").strip().lower()

        expansions = {
            "excel": [
                "excel",
                "spreadsheet",
                "spreadsheets",
                "excel specialist",
                "excel analyst",
                "excel reporting",
                "microsoft excel",
                "advanced excel",
                "spreadsheet specialist",
                "spreadsheet analyst",
                "excel data analyst",
            ],
            "web developer": [
                "web developer",
                "web development",
                "frontend developer",
                "front end developer",
                "backend developer",
                "back end developer",
                "full stack developer",
                "full-stack developer",
                "wordpress developer",
            ],
            "graphic designer": [
                "graphic designer",
                "graphic design",
                "visual designer",
                "ui designer",
                "ux designer",
                "ui/ux designer",
                "brand designer",
            ],
            "virtual assistant": [
                "virtual assistant",
                "virtual administrative assistant",
                "remote assistant",
                "executive assistant",
                "administrative assistant",
                "admin assistant",
            ],
            "ai specialist": [
                "ai specialist",
                "artificial intelligence specialist",
                "ai engineer",
                "machine learning engineer",
                "machine learning specialist",
                "generative ai",
            ],
            "marketing": [
                "marketing",
                "digital marketing",
                "marketing specialist",
                "marketing manager",
                "marketing coordinator",
                "marketing assistant",
                "marketing student assistant",
                "marketing intern",
                "marketing trainee",
                "marketing operations specialist",
                "marketing operations manager",
                "marketing analyst",
                "marketing associate",
                "marketing executive",
                "social media manager",
                "social media specialist",
                "social media coordinator",
                "seo specialist",
                "seo manager",
                "seo analyst",
                "content marketing",
                "growth marketing",
                "email marketing",
            ],
            "data analyst": [
                "data analyst",
                "data analyst assistant",
                "business analyst",
                "business intelligence",
                "bi analyst",
                "data visualization",
                "power bi",
            ],
            "content creator": [
                "content creator",
                "content creation",
                "content writer",
                "copywriter",
                "technical writer",
                "content specialist",
                "content manager",
            ],
        }

        return expansions.get(q, [query] if query else [])

    def _classify_query_intent(self, query, title="", description="", tags=None):
        """
        Classify a job against the specific service/query being searched.

        Query intent is stricter than general job intent:
        - Title matches are high-confidence.
        - Description-only matches are supporting/medium.
        - Generic mentions must not turn an unrelated job into a high-intent result.
        """
        q = (query or "").strip().lower()
        title_text = (title or "").lower()
        description_text = (description or "").lower()

        if not q:
            return {
                "query_match": False,
                "query_intent_level": "low",
                "query_intent_category": None,
                "query_intent_matches": [],
            }

        query_aliases = {
            "marketing": "digital_marketing",
            "digital marketing": "digital_marketing",
            "social media": "digital_marketing",
            "seo": "digital_marketing",
            "web developer": "web_development",
            "web development": "web_development",
            "frontend developer": "web_development",
            "backend developer": "web_development",
            "full stack developer": "web_development",
            "graphic designer": "graphic_design",
            "graphic design": "graphic_design",
            "ui designer": "graphic_design",
            "ux designer": "graphic_design",
            "data analyst": "data_analysis",
            "business analyst": "data_analysis",
            "excel": "excel",
            "excel specialist": "excel",
            "virtual assistant": "virtual_assistance",
            "administrative assistant": "virtual_assistance",
            "admin assistant": "administration",
            "content creator": "content_creation",
            "content creation": "content_creation",
            "copywriter": "content_creation",
            "ai specialist": "ai",
            "artificial intelligence": "ai",
            "machine learning": "ai",
        }

        category = query_aliases.get(q)

        # Excel-specific query intent.
        # Distinguish Excel-centered roles from jobs that merely mention
        # Excel as an incidental, optional, or unrelated skill.
        if q == "excel":
            excel_terms = [
                "excel",
                "microsoft excel",
                "ms excel",
            ]

            spreadsheet_terms = [
                "spreadsheet",
                "spreadsheets",
            ]

            title_excel_matches = [
                term
                for term in excel_terms + spreadsheet_terms
                if re.search(r"\b" + re.escape(term) + r"\b", title_text)
            ]

            if title_excel_matches:
                return {
                    "query_match": True,
                    "query_intent_level": "high",
                    "query_intent_category": "excel",
                    "query_intent_matches": title_excel_matches,
                }

            # Explicit negative/optional Excel wording should not qualify
            # an otherwise unrelated role.
            excel_negative_patterns = [
                r"\bexcel\s+is\s+not\s+required\b",
                r"\bexcel\s+is\s+not\s+necessary\b",
                r"\bexcel\s+not\s+required\b",
                r"\bno\s+excel\s+(?:experience|skills?)\s+(?:required|needed)\b",
                r"\bwithout\s+excel\b",
                r"\bexcel\s+is\s+(?:optional|a\s+plus|helpful)\b",
                r"\bexcel\s+(?:is\s+)?(?:optional|a\s+plus|helpful)\b",
            ]

            if any(
                re.search(pattern, description_text)
                for pattern in excel_negative_patterns
            ):
                return {
                    "query_match": True,
                    "query_intent_level": "low",
                    "query_intent_category": "excel",
                    "query_intent_matches": [],
                }

            description_excel_matches = [
                term
                for term in excel_terms
                if re.search(r"\b" + re.escape(term) + r"\b", description_text)
            ]

            description_spreadsheet_matches = [
                term
                for term in spreadsheet_terms
                if re.search(r"\b" + re.escape(term) + r"\b", description_text)
            ]

            if description_excel_matches or description_spreadsheet_matches:
                # Roles where Excel is normally a substantial part of the
                # day-to-day work. These receive high intent when Excel is
                # explicitly mentioned in the description.
                high_relevance_terms = [
                    "reporting analyst",
                    "data analyst",
                    "data analysis",
                    "data entry",
                    "administrative assistant",
                    "office assistant",
                    "virtual assistant",
                    "operations coordinator",
                    "operations assistant",
                    "accountant",
                    "accounting",
                    "bookkeeper",
                    "bookkeeping",
                    "inventory coordinator",
                    "spreadsheet analyst",
                    "spreadsheet management",
                    "spreadsheet reporting",
                    "spreadsheet analysis",
                    "report generation",
                ]

                # Roles where Excel is useful and materially relevant, but
                # is normally a supporting responsibility rather than the
                # central function.
                medium_relevance_terms = [
                    "payroll assistant",
                    "payroll",
                    "project scheduler",
                    "project scheduling",
                    "scheduler",
                    "finance",
                    "accounts payable",
                    "accounts receivable",
                    "reporting",
                    "administration",
                ]

                title_high_matches = [
                    term
                    for term in high_relevance_terms
                    if re.search(r"\b" + re.escape(term) + r"\b", title_text)
                ]

                title_medium_matches = [
                    term
                    for term in medium_relevance_terms
                    if re.search(r"\b" + re.escape(term) + r"\b", title_text)
                ]

                if title_high_matches:
                    return {
                        "query_match": True,
                        "query_intent_level": "high",
                        "query_intent_category": "excel",
                        "query_intent_matches": (
                            description_excel_matches[:2]
                            + description_spreadsheet_matches[:2]
                            + title_high_matches[:2]
                        ),
                    }

                if title_medium_matches:
                    return {
                        "query_match": True,
                        "query_intent_level": "medium",
                        "query_intent_category": "excel",
                        "query_intent_matches": (
                            description_excel_matches[:2]
                            + description_spreadsheet_matches[:2]
                            + title_medium_matches[:2]
                        ),
                    }

                # A bare spreadsheet mention without a recognized
                # Excel-relevant role context is only low intent.
                # Do not promote unrelated technical/software roles merely
                # because their description mentions spreadsheets or reporting.
                # intent. It remains a match for diagnostics, but the
                # aggregate query will not use it as a specific result.
                return {
                    "query_match": True,
                    "query_intent_level": "low",
                    "query_intent_category": "excel",
                    "query_intent_matches": (
                        description_excel_matches[:3]
                        + description_spreadsheet_matches[:2]
                    ),
                }
        # Exact query in the job title is the strongest signal.
        if q in title_text:
            return {
                "query_match": True,
                "query_intent_level": "high",
                "query_intent_category": category,
                "query_intent_matches": [q],
            }

        # Graphic-design query intent.
        # Use role/title context rather than incidental mentions of
        # graphic design in unrelated technical or writing jobs.
        if q == "graphic designer":
            graphic_design_title_patterns = [
                "graphic designer",
                "graphic design",
                "visual designer",
                "brand designer",
                "ui designer",
                "ux designer",
                "ui/ux designer",
                "product designer",
                "digital designer",
                "interaction designer",
                "experience designer",
                "design director",
                "design lead",
                "design manager",
                "creative designer",
                "creative design",
                "art director",
                "creative director",
                "course director",
                "education designer",
            ]

            graphic_design_exclusions = [
                "course writer",
                "writer",
                "editor",
                "software engineer",
                "senior ai engineer",
                "devops",
                "qa engineer",
                "data scientist",
                "full-stack developer",
                "full stack developer",
                "developer",
            ]

            title_matches = [
                pattern
                for pattern in graphic_design_title_patterns
                if re.search(r"\b" + re.escape(pattern) + r"\b", title_text)
            ]

            excluded_matches = [
                pattern
                for pattern in graphic_design_exclusions
                if re.search(r"\b" + re.escape(pattern) + r"\b", title_text)
            ]

            if title_matches and not excluded_matches:
                return {
                    "query_match": True,
                    "query_intent_level": "high",
                    "query_intent_category": "graphic_design",
                    "query_intent_matches": title_matches[:5],
                }

            return {
                "query_match": False,
                "query_intent_level": "low",
                "query_intent_category": "graphic_design",
                "query_intent_matches": [],
            }
        # If we know the RuffNeck service category, check its title patterns.
        if category and category in self.SERVICE_INTENTS:
            title_matches = [
                pattern
                for pattern in self.SERVICE_INTENTS[category]
                if re.search(r"\b" + re.escape(pattern) + r"\b", title_text)
            ]

            if title_matches:
                return {
                    "query_match": True,
                    "query_intent_level": "high",
                    "query_intent_category": category,
                    "query_intent_matches": title_matches[:5],
                }

            # Description-only service mentions are not sufficient by
            # themselves to classify a job as a relevant service role.
            # Query-specific role relevance must be established from
            # the job title rather than incidental skill mentions.
        # Unknown query: only treat an exact title match as strong evidence.
        return {
            "query_match": False,
            "query_intent_level": "low",
            "query_intent_category": category,
            "query_intent_matches": [],
        }

    def _enrich_job_engagement(
        self,
        engagement: dict,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> dict:
        engagement = dict(engagement or {})
        engagement.update(
            self._classify_job_intent(
                title=title,
                description=description,
                tags=tags,
            )
        )
        return engagement

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """Collect and rank job-board records for one board or many queries.

        When ``target_url`` is ``all``, every supplied keyword participates in
        retrieval and intent classification. Results are deduplicated across
        boards, with title-level matches ranked ahead of description-only
        matches and service categories interleaved to reduce single-category
        dominance.
        """
        keywords = keywords or []
        query = (target_url or "").strip().lower()
        results: List[CommentResult] = []

        if query in ("all", "jobs", ""):
            boards = [
                ("remoteok", self._remoteok),
                ("remotive", self._remotive),
                ("arbeitnow", self._arbeitnow),
                ("jobicy", self._jobicy),
                ("weworkremotely", self._weworkremotely),
            ]
            board_order = {name: index for index, (name, _) in enumerate(boards)}

            # Keep every distinct requested query. Previously only keywords[0]
            # was used, so the daily discovery list effectively searched for
            # marketing and ignored most of the other service categories.
            requested_queries: List[str] = []
            seen_queries = set()
            for value in keywords:
                value = re.sub(r"\s+", " ", str(value or "").strip())
                normalized = value.casefold()
                if value and normalized not in seen_queries:
                    requested_queries.append(value)
                    seen_queries.add(normalized)

            # Fetch once per board using the union of all requested terms and
            # their existing expansions. This avoids one HTTP request per
            # keyword while allowing every service category to participate.
            expanded_keywords: List[str] = []
            seen_expansions = set()
            for requested_query in requested_queries:
                for term in self._expand_job_query(requested_query):
                    term = re.sub(r"\s+", " ", str(term or "").strip())
                    normalized = term.casefold()
                    if term and normalized not in seen_expansions:
                        expanded_keywords.append(term)
                        seen_expansions.add(normalized)

            logger.debug(
                "Job query expansion: %s -> %s",
                requested_queries,
                expanded_keywords,
            )

            # Each board used to stop at the final requested result count. Pull
            # a larger bounded candidate pool so one early category does not
            # exhaust every board before other categories can be considered.
            requested_limit = max(1, int(self.max_results or 1))
            fetch_limit = min(max(requested_limit * 3, requested_limit), 120)
            board_results = []
            try:
                self.max_results = fetch_limit
                for board_name, board_fn in boards:
                    try:
                        board_items = board_fn(expanded_keywords)
                        board_results.append((board_name, board_items or []))
                    except Exception as exc:
                        logger.debug("Job board %s failed: %s", board_name, exc)
            finally:
                self.max_results = requested_limit

            def canonical_job_key(item: CommentResult) -> str:
                """Build a stable dedupe key without removing job ID params."""
                for candidate_url in (item.post_url, item.profile_url):
                    candidate_url = str(candidate_url or "").strip()
                    if not candidate_url:
                        continue
                    try:
                        parts = urlsplit(candidate_url)
                        if not parts.netloc:
                            continue
                        host = (parts.hostname or "").casefold()
                        if host.startswith("www."):
                            host = host[4:]
                        if not host:
                            continue
                        # Drop tracking-only parameters, but preserve IDs such
                        # as job keys that distinguish separate vacancies.
                        tracking = {
                            "utm_source", "utm_medium", "utm_campaign",
                            "utm_term", "utm_content", "fbclid", "gclid",
                            "mc_cid", "mc_eid", "referrer", "source",
                        }
                        params = [
                            (key, value)
                            for key, value in parse_qsl(parts.query, keep_blank_values=True)
                            if key.casefold() not in tracking
                        ]
                        normalized_query = urlencode(sorted(params))
                        path = parts.path.rstrip("/") or "/"
                        return "url:" + urlunsplit(("https", host, path, normalized_query, ""))
                    except (TypeError, ValueError):
                        continue

                company = re.sub(
                    r"[^a-z0-9]+", " ",
                    str(item.username or item.display_name or "").casefold(),
                ).strip()
                title = str(
                    (item.engagement or {}).get("job_title")
                    or item.display_name
                    or (item.comment_text or "").split(":", 1)[0]
                ).casefold()
                location = str(item.bio_text or "").casefold().strip()
                if company or title:
                    return "fallback:" + "|".join((company, title, location))
                source = str((item.engagement or {}).get("source") or "").casefold()
                text_key = re.sub(r"\s+", " ", str(item.comment_text or "").casefold()).strip()
                return "fallback:" + "|".join((source, text_key[:240]))

            def intent_rank(level: str) -> int:
                return {"high": 2, "medium": 1, "low": 0}.get(
                    str(level or "low").lower(), 0
                )

            candidates_by_key = {}
            for board_name, items in board_results:
                for item in items:
                    engagement = dict(item.engagement or {})
                    raw = item.raw or {}
                    title = (
                        engagement.get("job_title")
                        or raw.get("position")
                        or raw.get("title")
                        or item.display_name
                        or ""
                    )
                    full_description = (
                        raw.get("description")
                        or raw.get("jobDescription")
                        or raw.get("job_description")
                        or raw.get("jobExcerpt")
                        or raw.get("excerpt")
                        or item.comment_text
                        or ""
                    )
                    tags = engagement.get("tags") or raw.get("tags") or []

                    query_matches = []
                    if requested_queries:
                        for query_index, requested_query in enumerate(requested_queries):
                            intent = self._classify_query_intent(
                                query=requested_query,
                                title=title,
                                description=full_description,
                                tags=tags,
                            )
                            level = str(intent.get("query_intent_level") or "low").lower()
                            # Low-level matches include incidental terms and
                            # explicitly weak signals (e.g. optional Excel).
                            if intent.get("query_match") and level in ("high", "medium"):
                                query_matches.append({
                                    "query": requested_query,
                                    "query_index": query_index,
                                    "intent": intent,
                                    "rank": intent_rank(level),
                                })

                        # Do not let broad keyword retrieval reintroduce jobs
                        # that failed the stricter title/intent classification.
                        if not query_matches:
                            continue

                        query_matches.sort(
                            key=lambda match: (
                                match["rank"],
                                bool(match["intent"].get("query_intent_category")),
                                len(match["query"]),
                                -match["query_index"],
                            ),
                            reverse=True,
                        )
                        best_match = query_matches[0]
                        best_intent = dict(best_match["intent"])
                        best_level = str(best_intent.get("query_intent_level") or "low")
                        matched_queries = list(dict.fromkeys(
                            match["query"] for match in sorted(
                                query_matches, key=lambda match: match["query_index"]
                            )
                        ))
                        matched_categories = list(dict.fromkeys(
                            match["intent"].get("query_intent_category")
                            or engagement.get("job_intent_category")
                            for match in query_matches
                            if (
                                match["intent"].get("query_intent_category")
                                or engagement.get("job_intent_category")
                            )
                        ))
                        category = (
                            best_intent.get("query_intent_category")
                            or engagement.get("job_intent_category")
                            or best_match["query"]
                        )
                        engagement.update(best_intent)
                        engagement.update({
                            "query_match": True,
                            "query_intent_level": best_level,
                            "query_intent_category": category,
                            "discovery_query": best_match["query"],
                            "matched_queries": matched_queries,
                            "matching_service_categories": matched_categories,
                        })
                        score = intent_rank(best_level)
                        query_index = min(match["query_index"] for match in query_matches)
                    else:
                        # Preserve general-board behavior when no keywords are
                        # supplied: relevant jobs first, then other listings.
                        level = str(engagement.get("job_intent_level") or "low").lower()
                        category = engagement.get("job_intent_category") or "other"
                        engagement.update({
                            "query_match": False,
                            "query_intent_level": level,
                            "query_intent_category": category,
                            "discovery_query": "",
                            "matched_queries": [],
                            "matching_service_categories": (
                                [category] if category != "other" else []
                            ),
                        })
                        score = intent_rank(level)
                        query_index = len(requested_queries)

                    item.engagement = engagement
                    dedupe_key = canonical_job_key(item)
                    candidate = {
                        "item": item,
                        "board": board_name,
                        "score": score,
                        "category": str(category or "other"),
                        "query_index": query_index,
                    }

                    previous = candidates_by_key.get(dedupe_key)
                    if previous is None:
                        candidates_by_key[dedupe_key] = candidate
                        continue

                    # Keep the best-scoring representation of a duplicate and
                    # merge the query/category evidence gathered from both.
                    previous_item = previous["item"]
                    previous_engagement = dict(previous_item.engagement or {})
                    incoming_engagement = dict(item.engagement or {})
                    merged_queries = list(dict.fromkeys(
                        (previous_engagement.get("matched_queries") or [])
                        + (incoming_engagement.get("matched_queries") or [])
                    ))
                    merged_categories = list(dict.fromkeys(
                        (previous_engagement.get("matching_service_categories") or [])
                        + (incoming_engagement.get("matching_service_categories") or [])
                    ))
                    if candidate["score"] > previous["score"]:
                        winner = candidate
                        winner_engagement = dict(item.engagement or {})
                    else:
                        winner = previous
                        winner_engagement = previous_engagement
                    winner_engagement["matched_queries"] = merged_queries
                    winner_engagement["matching_service_categories"] = merged_categories
                    winner["item"].engagement = winner_engagement
                    winner["query_index"] = min(
                        previous["query_index"], candidate["query_index"]
                    )
                    candidates_by_key[dedupe_key] = winner

            candidates = list(candidates_by_key.values())

            # Interleave categories within each confidence tier. This prevents
            # the first few marketing listings from crowding out data, design,
            # development, AI, and administration results.
            ordered = []
            tiers = (2, 1) if requested_queries else (2, 1, 0)
            for tier in tiers:
                eligible = [candidate for candidate in candidates if candidate["score"] == tier]
                category_pools = {}
                category_first_seen = {}
                for candidate in eligible:
                    category = candidate["category"] or "other"
                    category_pools.setdefault(category, []).append(candidate)
                    category_first_seen[category] = min(
                        category_first_seen.get(category, candidate["query_index"]),
                        candidate["query_index"],
                    )

                categories = sorted(
                    category_pools,
                    key=lambda category: (category_first_seen[category], category),
                )
                for category in categories:
                    category_pools[category].sort(
                        key=lambda candidate: (
                            board_order.get(candidate["board"], 999),
                            candidate["query_index"],
                        )
                    )

                while len(ordered) < requested_limit and any(category_pools.values()):
                    for category in categories:
                        pool = category_pools.get(category) or []
                        if pool:
                            ordered.append(pool.pop(0))
                            if len(ordered) >= requested_limit:
                                break

                if len(ordered) >= requested_limit:
                    break

            results = [candidate["item"] for candidate in ordered]

            # Indeed is intentionally not part of the default aggregate because
            # its HTML endpoint is more likely to block automated requests.
        elif query in ("remoteok", "remote ok"):
            results = self._remoteok(keywords)
        elif query in ("weworkremotely", "wwr", "we work remotely"):
            results = self._weworkremotely(keywords)
        elif query in ("remotive",):
            results = self._remotive(keywords)
        elif query in ("arbeitnow", "arbeit"):
            results = self._arbeitnow(keywords)
        elif query in ("jobicy",):
            results = self._jobicy(keywords)
        elif query.startswith("indeed") or "indeed.com" in query:
            results = self._indeed(
                query if "indeed.com" in query else " ".join(keywords) or "developer"
            )
        else:
            # Treat a direct free-text target as another keyword, rather than
            # dropping any additional supplied terms.
            free_text_keywords = [target_url] + keywords
            results = self._remoteok(free_text_keywords)
            results.extend(self._remotive(free_text_keywords))

        # Individual job-board methods already filter against full job text.
        # Avoid the generic BaseScraper filter because comment_text is truncated.
        return results[: max(1, int(self.max_results or 1))]

    def _remoteok(self, keywords: List[str]) -> List[CommentResult]:
        try:
            resp = requests.get(
                "https://remoteok.com/api",
                headers={"User-Agent": "RuffNeckProspector/1.3 (educational)"},
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for job in data[1:]:
                position = (job.get("position") or job.get("title") or "").lower()
                description = (job.get("description") or "").lower()
                company = job.get("company") or "unknown"
                text = position + " " + description
                if keywords and not any(k.lower() in text for k in keywords):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=job.get("url") or job.get("apply_url"),
                        comment_text=f"{job.get('position') or job.get('title')}: {(job.get('description') or '')[:400]}",
                        post_url=job.get("url"),
                        bio_text=job.get("location") or "Remote",
                        engagement=self._enrich_job_engagement(
                            {
                                "tags": job.get("tags") or [],
                                "source": "remoteok",
                                "job_signal": True,
                                "job_title": job.get("position") or job.get("title"),
                                "job_company": company,
                                "job_location": job.get("location") or "Remote",
                            },
                            title=job.get("position") or job.get("title") or "",
                            description=job.get("description") or "",
                            tags=job.get("tags") or [],
                        ),
                        raw=job,
                    )
                )
                if len(results) >= self.max_results:
                    break
            return results
        except Exception as e:
            logger.warning(f"RemoteOK failed: {e}")
            return []

    def _remotive(self, keywords: List[str]) -> List[CommentResult]:
        """Remotive public API – free."""
        try:
            resp = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"limit": self.max_results},
                headers={"User-Agent": "RuffNeckProspector/1.3"},
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for job in data.get("jobs", []):
                title = (job.get("title") or "").lower()
                desc = (job.get("description") or "").lower()
                company = job.get("company_name") or "unknown"
                text = title + " " + desc
                if keywords and not any(k.lower() in text for k in keywords):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=job.get("url"),
                        comment_text=f"{job.get('title')}: {(job.get('description') or '')[:400]}",
                        post_url=job.get("url"),
                        bio_text=job.get("candidate_required_location") or "Remote",
                        engagement=self._enrich_job_engagement(
                            {
                                "category": job.get("category"),
                                "source": "remotive",
                                "job_signal": True,
                                "job_title": job.get("title"),
                                "job_company": company,
                                "job_location": job.get("candidate_required_location") or "Remote",
                            },
                            title=job.get("title") or "",
                            description=job.get("description") or "",
                            tags=[],
                        ),
                        raw=job,
                    )
                )
                if len(results) >= self.max_results:
                    break
            return results
        except Exception as e:
            logger.warning(f"Remotive failed: {e}")
            return []

    def _arbeitnow(self, keywords: List[str]) -> List[CommentResult]:
        """Arbeitnow public job API – free."""
        try:
            resp = requests.get(
                "https://www.arbeitnow.com/api/job-board-api",
                headers={"User-Agent": "RuffNeckProspector/1.3"},
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for job in data.get("data", [])[: self.max_results]:
                title = (job.get("title") or "").lower()
                desc = (job.get("description") or "").lower()
                company = job.get("company_name") or "unknown"
                text = title + " " + desc
                if keywords and not any(k.lower() in text for k in keywords):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=job.get("url"),
                        comment_text=f"{job.get('title')}: {(job.get('description') or '')[:400]}",
                        post_url=job.get("url"),
                        bio_text=", ".join(job.get("location") or []) or "Remote",
                        engagement=self._enrich_job_engagement(
                            {
                                "tags": job.get("tags") or [],
                                "source": "arbeitnow",
                                "job_signal": True,
                                "job_title": job.get("title"),
                                "job_company": company,
                                "job_location": ", ".join(job.get("location") or []) or "Remote",
                            },
                            title=job.get("title") or "",
                            description=job.get("description") or "",
                            tags=job.get("tags") or [],
                        ),
                        raw=job,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Arbeitnow failed: {e}")
            return []

    def _jobicy(self, keywords: List[str]) -> List[CommentResult]:
        """Jobicy public API – free remote jobs."""
        try:
            resp = requests.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={"count": self.max_results},
                headers={"User-Agent": "RuffNeckProspector/1.3"},
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for job in data.get("jobs", []):
                title_raw = job.get("jobTitle") or ""
                excerpt_raw = job.get("jobExcerpt") or ""
                company = job.get("companyName") or "unknown"

                search_text = (
                    f"{title_raw} {excerpt_raw}"
                ).lower()

                if keywords and not any(
                    k.lower() in search_text
                    for k in keywords
                ):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=job.get("url"),
                        comment_text=f"{job.get('jobTitle')}: {(job.get('jobExcerpt') or '')[:400]}",
                        post_url=job.get("url"),
                        bio_text=job.get("jobGeo") or "Remote",
                        engagement=self._enrich_job_engagement(
                            {
                                "source": "jobicy",
                                "job_signal": True,
                                "job_title": job.get("jobTitle"),
                                "job_company": company,
                                "job_location": job.get("jobGeo") or "Remote",
                            },
                            title=job.get("jobTitle") or "",
                            description=job.get("jobExcerpt") or "",
                            tags=[],
                        ),
                        raw=job,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Jobicy failed: {e}")
            return []

    def _weworkremotely(self, keywords: List[str]) -> List[CommentResult]:
        try:
            from bs4 import BeautifulSoup
            url = "https://weworkremotely.com/categories/remote-programming-jobs"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "xml")
            results = []
            for li in soup.select("li.feature, section.jobs article")[: self.max_results]:
                title_el = li.select_one("span.title, a")
                company_el = li.select_one("span.company")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "unknown"
                link = title_el.get("href") or ""
                if link and not link.startswith("http"):
                    link = "https://weworkremotely.com" + link
                search_text = (
                    f"{title} {company}"
                ).lower()

                if keywords and not any(
                    k.lower() in search_text
                    for k in keywords
                ):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=link,
                        comment_text=title,
                        post_url=link,
                        engagement=self._enrich_job_engagement(
                            {
                                "source": "weworkremotely",
                                "job_signal": True,
                                "job_title": title,
                                "job_company": company,
                            },
                            title=title or "",
                            description="",
                            tags=[],
                        ),
                        raw={},
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"We Work Remotely failed: {e}")
            return []

    def _indeed(self, query: str) -> List[CommentResult]:
        try:
            from bs4 import BeautifulSoup
            url = f"https://www.indeed.com/jobs?q={quote_plus(query)}&l="
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; educational-bot)"}, timeout=20)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for card in soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")[: self.max_results]:
                title_el = card.select_one("h2 a, a.jcs-JobTitle")
                company_el = card.select_one("span.companyName, span[data-testid='company-name']")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "unknown"
                link = title_el.get("href") or ""
                if link and not link.startswith("http"):
                    link = "https://www.indeed.com" + link
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=link,
                        comment_text=title,
                        post_url=link,
                        engagement={"source": "indeed"},
                        raw={},
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Indeed failed: {e}")
            return []
