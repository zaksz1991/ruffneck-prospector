from pathlib import Path

path = Path(r".\backend\app\scrapers\google_search.py")
text = path.read_text(encoding="utf-8")

start = text.index("    def _is_service_provider_result(")
end = text.index("    def _extract_opportunity_issuer(", start)

new_method = '''    def _is_service_provider_result(
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
                    rf"\\\\b{re.escape(role)}\\\\b",
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
                "automation solutions",
                "automation services",
                "machine learning company",
                "artificial intelligence company",
                "software and automation",
                "software & automation",
            )

            if has_any(text, service_signals) and has_role(text):
                return True

            return False

        if service == "graphics":
            service_signals = (
                "graphic design",
                "graphic design services",
                "graphic design agency",
                "graphic design company",
                "branding agency",
                "branding company",
                "brand identity",
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

'''

path.write_text(
    text[:start] + new_method + text[end:],
    encoding="utf-8",
)

print("PROVIDER DETECTION REPLACED")
