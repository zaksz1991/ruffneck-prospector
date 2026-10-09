from pathlib import Path
import re

path = Path(r".\backend\app\scrapers\google_search.py")
text = path.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. Insert two-track helper methods before _prospect_score
# ------------------------------------------------------------

marker = "    def _prospect_score("

if "def _is_opportunity_query(" not in text:
    if marker not in text:
        raise RuntimeError("Could not locate _prospect_score().")

    helpers = r'''
    def _is_opportunity_query(self, query: str) -> bool:
        """Return True when the search query targets an active opportunity."""
        q = (query or "").lower()

        signals = (
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for expression of interest",
            "expression of interest",
            "call for proposals",
            "invitation to bid",
            "terms of reference",
            "rfp",
            "rfq",
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
        Detect organizations selling the requested service.

        This is intentionally service-specific. A generic word such as
        'company' or 'technology' is not enough to reject a prospect.
        """
        text = " ".join(
            (
                title or "",
                snippet or "",
                domain or "",
            )
        ).lower()

        provider_patterns = {
            "website": (
                "web design agency",
                "web design company",
                "website design company",
                "website development company",
                "website development agency",
                "web development agency",
                "web developer",
                "website developer",
                "website designer",
                "web solutions",
                "website solutions",
                "website builder",
                "web services",
                "digital agency",
            ),
            "digital_marketing": (
                "digital marketing agency",
                "digital marketing company",
                "digital agency",
                "marketing agency",
                "social media agency",
                "social media marketing agency",
                "seo agency",
                "seo company",
                "digital marketing services",
                "social media marketing services",
            ),
            "ai_solution": (
                "ai solutions",
                "ai solution provider",
                "ai automation",
                "ai automation company",
                "ai consulting",
                "ai consultant",
                "ai development",
                "ai development company",
                "artificial intelligence company",
                "machine learning company",
                "software and automation",
                "software & automation",
                "automation solutions",
                "ai technology company",
            ),
            "graphics": (
                "graphic design agency",
                "graphic design company",
                "graphic design services",
                "branding agency",
                "branding company",
                "creative agency",
                "design studio",
                "printing company",
                "printing services",
                "packaging company",
                "packaging solutions",
            ),
            "cv_resume": (
                "cv writing",
                "cv writer",
                "cv writing services",
                "resume writing",
                "resume writer",
                "resume writing services",
                "cv builder",
                "resume builder",
                "career services",
                "career coaching",
            ),
            "excel": (
                "excel consultant",
                "excel consulting",
                "excel automation",
                "spreadsheet consultant",
                "spreadsheet consulting",
                "data analytics consultancy",
                "data analytics consulting",
                "business intelligence company",
                "business intelligence services",
                "dashboard development services",
                "data analysis consulting",
            ),
        }

        patterns = provider_patterns.get(service, ())

        return any(pattern in text for pattern in patterns)

    def _extract_opportunity_issuer(
        self,
        title: str,
        snippet: str,
    ) -> str | None:
        """
        Extract the organization that issued an opportunity.

        We only return an issuer when the search-result text provides
        an explicit organizational signal. We never invent an issuer
        from the publishing domain.
        """
        title = self._clean_text(title or "")
        snippet = self._clean_text(snippet or "")

        combined = f"{title}. {snippet}"

        # Explicit issuer labels are strongest.
        patterns = (
            r"(?:issued|published|advertised|posted|released)\s+by\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)(?:[.;]|$)",

            r"(?:on behalf of|on behalf)\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)(?:[.;]|$)",

            r"(?:organization|organisation|client|buyer|issuer|procuring entity)"
            r"\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)(?:[.;]|$)",

            r"(?:requesting organization|requesting organisation)"
            r"\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)(?:[.;]|$)",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                combined,
                re.IGNORECASE,
            )

            if match:
                issuer = re.sub(
                    r"\s+",
                    " ",
                    match.group(1).strip(" .,:;-"),
                )

                if self._looks_like_issuer_name(issuer):
                    return issuer

        # Common search-result construction:
        # "Organization Name - Request for Proposal"
        # "Organization Name | Request for Proposal"
        opportunity_tail = (
            r"(?:request for proposal|request for quotation|"
            r"expression of interest|invitation to bid|"
            r"terms of reference|call for proposals|rfp|rfq)"
        )

        match = re.match(
            rf"^(.{{3,100}}?)\s*(?:[-|:])\s*{opportunity_tail}",
            title,
            re.IGNORECASE,
        )

        if match:
            issuer = match.group(1).strip()

            if self._looks_like_issuer_name(issuer):
                return issuer

        return None

    def _looks_like_issuer_name(self, value: str) -> bool:
        """Reject obvious document/service terms masquerading as issuers."""
        value = re.sub(r"\s+", " ", (value or "").strip())

        if len(value) < 3 or len(value) > 120:
            return False

        lowered = value.lower()

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

        return True

    def _is_opportunity_result(
        self,
        query: str,
        title: str,
        snippet: str,
    ) -> bool:
        """Detect an opportunity even when the query itself is broad."""
        combined = " ".join(
            (
                query or "",
                title or "",
                snippet or "",
            )
        ).lower()

        signals = (
            "request for proposal",
            "request for proposals",
            "request for quotation",
            "request for expression of interest",
            "expression of interest",
            "call for proposals",
            "invitation to bid",
            "terms of reference",
            "rfp",
            "rfq",
            "vendor needed",
            "contractor needed",
            "consultant needed",
            "seeking a consultant",
            "seeking consultant",
        )

        return any(signal in combined for signal in signals)

'''

    text = text.replace(marker, helpers + marker, 1)


# ------------------------------------------------------------
# 2. Replace search_service_leads with two-track flow
# ------------------------------------------------------------

start_match = re.search(
    r"^    def search_service_leads\(",
    text,
    re.MULTILINE,
)

if not start_match:
    raise RuntimeError("Could not locate search_service_leads().")

start = start_match.start()

next_method = re.search(
    r"^    def \w+\(",
    text[start_match.end():],
    re.MULTILINE,
)

if not next_method:
    raise RuntimeError(
        "Could not locate the method following search_service_leads()."
    )

end = start_match.end() + next_method.start()

new_method = r'''    def search_service_leads(
        self,
        service: str,
        location: str = "Nigeria",
        extra_keywords: Optional[List[str]] = None,
        max_results: Optional[int] = None,
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

        queries = self._service_queries(
            service,
            location,
            extra_keywords=extra_keywords or [],
        )

        organization_candidates = []
        opportunity_candidates = []

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

                is_opportunity = (
                    query_is_opportunity
                    or self._is_opportunity_result(
                        query,
                        title,
                        snippet,
                    )
                )

                if is_opportunity:
                    # Opportunity sources are evidence pages, so normal
                    # article-page rejection must not discard them here.
                    issuer = self._extract_opportunity_issuer(
                        title,
                        snippet,
                    )

                    if not issuer:
                        continue

                    result["discovery_type"] = "opportunity"
                    result["original_issuer"] = issuer
                    result["source_url"] = url
                    result["source_domain"] = domain

                    opportunity_candidates.append(result)
                    continue

                # Organization track uses the normal prospect safeguards.
                if self._is_service_provider_result(
                    service,
                    title,
                    snippet,
                    domain,
                ):
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
                1
                if self._is_homepage_url(
                    item.get("href", "")
                )
                else 0,
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

'''

text = text[:start] + new_method + text[end:]

path.write_text(
    text,
    encoding="utf-8",
)

print("TWO-TRACK PATCH APPLIED")
