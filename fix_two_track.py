from pathlib import Path

path = Path(r".\backend\app\scrapers\google_search.py")
text = path.read_text(encoding="utf-8")

# ------------------------------------------------------------
# Provider detection fixes
# ------------------------------------------------------------

text = text.replace(
    '                "web services",\n                "digital agency",',
    '                "web services",\n                "web design & seo agency",\n                "web design and seo agency",\n                "web design & seo",\n                "web design and seo",\n                "digital agency",',
    1,
)

text = text.replace(
    '                "ai technology company",\n            ),',
    '                "ai technology company",\n                "software, web & growth solutions",\n                "software, web and growth solutions",\n                "web & growth solutions",\n                "web and growth solutions",\n            ),',
    1,
)

# ------------------------------------------------------------
# Replace issuer extraction with safer patterns
# ------------------------------------------------------------

start_marker = "    def _extract_opportunity_issuer("
start = text.find(start_marker)

if start == -1:
    raise RuntimeError("Could not locate _extract_opportunity_issuer().")

next_marker = "    def _looks_like_issuer_name("
end = text.find(next_marker, start)

if end == -1:
    raise RuntimeError(
        "Could not locate _looks_like_issuer_name() after issuer extractor."
    )

new_method = r'''    def _extract_opportunity_issuer(
        self,
        title: str,
        snippet: str,
    ) -> str | None:
        """
        Extract the organization that issued an opportunity.

        Only return an issuer when the result text contains an explicit
        organizational signal. Never infer the issuer from the publisher
        domain alone.
        """
        title = self._clean_text(title or "")
        snippet = self._clean_text(snippet or "")

        combined = f"{title}. {snippet}"

        patterns = (
            # "issued/published/advertised by Acme Ltd"
            r"(?:issued|published|advertised|posted|released)\s+by\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)(?=\s*(?:[.;]|$))",

            # "on behalf of Acme Ltd, applications..."
            r"\bon behalf of\s+"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)"
            r"(?=\s*(?:,|;|\.|:|\s+(?:is|are|has|have|seeks|seeking|"
            r"invites?|inviting|applications?|proposals?|requests?))|$)",

            # "client: Acme Ltd"
            r"(?:organization|organisation|client|buyer|issuer|"
            r"procuring entity|requesting organization|"
            r"requesting organisation)"
            r"\s*[:\-]\s*"
            r"([A-Z][A-Za-z0-9&.,'()\- ]{2,100}?)"
            r"(?=\s*(?:[.;]|$))",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                combined,
                re.IGNORECASE,
            )

            if not match:
                continue

            issuer = re.sub(
                r"\s+",
                " ",
                match.group(1).strip(" .,:;-"),
            )

            # Remove common trailing grammatical fragments.
            issuer = re.sub(
                r"\s+(?:is|are|has|have|seeks|seeking|"
                r"invites?|inviting|applications?|proposals?|"
                r"requests?)$",
                "",
                issuer,
                flags=re.IGNORECASE,
            ).strip(" .,:;-")

            if self._looks_like_issuer_name(issuer):
                return issuer

        # "Paradigm HQ - Request for Proposal"
        # "Paradigm HQ | Request for Proposal"
        # "Paradigm HQ: RFP"
        opportunity_tail = (
            r"(?:request for proposal|request for proposals|"
            r"request for quotation|request for expression of interest|"
            r"expression of interest|invitation to bid|"
            r"terms of reference|call for proposals|rfp|rfq)"
        )

        match = re.match(
            rf"^(.{{3,100}}?)\s*(?:[-|:])\s*{opportunity_tail}\s*$",
            title,
            re.IGNORECASE,
        )

        if match:
            issuer = match.group(1).strip()

            if self._looks_like_issuer_name(issuer):
                return issuer

        return None

'''

text = text[:start] + new_method + text[end:]

path.write_text(
    text,
    encoding="utf-8",
)

print("TARGETED TWO-TRACK FIXES APPLIED")
