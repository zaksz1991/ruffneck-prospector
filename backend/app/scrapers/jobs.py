import re
"""
Free job-board scrapers â€“ expanded.
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
from urllib.parse import quote_plus
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
        """
        target_url can be a board name or free-text query.
        Supported boards: remoteok, weworkremotely, indeed, remotive, arbeitnow, jobicy, all
        """
        keywords = keywords or []
        query = target_url.strip().lower()
        results: List[CommentResult] = []

        if query in ("all", "jobs", ""):
            # Aggregate supported free/public boards.
            # Prefer RuffNeck service-intent jobs and balance results across
            # boards instead of allowing the first board to consume the limit.
            boards = [
                ("remoteok", self._remoteok),
                ("remotive", self._remotive),
                ("arbeitnow", self._arbeitnow),
                ("jobicy", self._jobicy),
                ("weworkremotely", self._weworkremotely),
            ]

            requested_query = keywords[0] if keywords else ""
            expanded_keywords = self._expand_job_query(requested_query)

            logger.debug(
                "Job query expansion: %s -> %s",
                requested_query,
                expanded_keywords,
            )

            board_results = []

            for board_name, board_fn in boards:
                try:
                    board_items = board_fn(expanded_keywords)
                    board_results.append((board_name, board_items))
                except Exception as e:
                    logger.debug(
                        f"Job board {board_name} failed: {e}"
                    )

            # Classify each result against the actual requested service/query.
            # General job intent remains available, but query intent controls
            # prioritization for the current discovery request.
            high_intent = []
            query_medium = []
            remaining = []

            for board_name, items in board_results:
                for item in items:
                    engagement = dict(item.engagement or {})

                    raw = item.raw or {}

                    full_description = (
                        raw.get("description")
                        or raw.get("jobDescription")
                        or raw.get("job_description")
                        or raw.get("jobExcerpt")
                        or raw.get("excerpt")
                        or item.comment_text
                        or ""
                    )

                    query_intent = self._classify_query_intent(
                        query=requested_query,
                        title=engagement.get("job_title") or item.display_name or "",
                        description=full_description,
                        tags=engagement.get("tags") or [],
                    )

                    engagement.update(query_intent)
                    item.engagement = engagement

                    if query_intent["query_intent_level"] == "high":
                        high_intent.append(item)
                    elif query_intent["query_intent_level"] == "medium":
                        query_medium.append(item)
                    else:
                        remaining.append(item)

            # Round-robin high query-intent jobs by board.
            ordered = []
            pools = {}

            for board_name, items in board_results:
                pools[board_name] = [
                    item for item in items
                    if item in high_intent
                ]

            while any(pools.values()) and len(ordered) < self.max_results:
                for board_name, _ in board_results:
                    pool = pools.get(board_name) or []
                    if pool:
                        ordered.append(pool.pop(0))
                        if len(ordered) >= self.max_results:
                            break

            # Prefer medium query-intent results before unrelated records.
            if len(ordered) < self.max_results:
                for item in query_medium:
                    if item not in ordered:
                        ordered.append(item)
                    if len(ordered) >= self.max_results:
                        break

            # For a specific keyword/service query, do not pad the result set
            # with unrelated low-intent jobs. Only return jobs that matched
            # the requested query at high or medium intent.
            #
            # For an empty query, retain the general-result fallback.
            if not requested_query and len(ordered) < self.max_results:
                for item in remaining:
                    if item not in ordered:
                        ordered.append(item)
                    if len(ordered) >= self.max_results:
                        break

            results = ordered

            # Indeed is intentionally not part of the default aggregate.
            # Its HTML endpoint is more likely to block automated requests.
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
            results = self._indeed(query if "indeed.com" in query else " ".join(keywords) or "developer")
        else:
            # Treat as keyword search across RemoteOK + Remotive
            results = self._remoteok([target_url] + keywords)
            results.extend(self._remotive([target_url] + keywords))

        # Individual job-board methods already apply keyword filtering
        # against the full job title/description. Do not run the generic
        # BaseScraper filter again because CommentResult.comment_text is
        # intentionally truncated for storage/display.
        return results[: self.max_results]

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
        """Remotive public API â€“ free."""
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
        """Arbeitnow public job API â€“ free."""
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
        """Jobicy public API â€“ free remote jobs."""
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








