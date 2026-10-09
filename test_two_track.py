from backend.app.scrapers.google_search import GoogleSearchScraper

s = GoogleSearchScraper(max_results=10)

print("=== PROVIDER REJECTION ===")

provider_cases = [
    (
        "website",
        "Nigeria's Web Design & SEO Agency- Webnotes Design",
        "Professional website design and SEO services",
        "webnotes.com.ng",
    ),
    (
        "ai_solution",
        "Software, Web & Growth Solutions in Abuja | VIS Nigeria",
        "Software, web and growth solutions for businesses",
        "visnigeria.com",
    ),
    (
        "graphics",
        "Professional Printing Company",
        "Printing, branding and graphic design services",
        "exampleprints.ng",
    ),
    (
        "cv_resume",
        "#1 Professional, ATS-Friendly CV Builder in Nigeria",
        "Create professional CVs and resumes",
        "cvbuilder.example.ng",
    ),
    (
        "excel",
        "Excel Consultant and Data Analytics Services",
        "Excel automation and business intelligence consulting",
        "exampledata.ng",
    ),
]

for service, title, snippet, domain in provider_cases:
    rejected = s._is_service_provider_result(
        service,
        title,
        snippet,
        domain,
    )

    print(
        f"{service:18} "
        f"REJECT={rejected} | {title}"
    )


print()
print("=== OPPORTUNITY DETECTION ===")

opportunity_cases = [
    (
        "WEBSITE REDESIGN REQUEST FOR PROPOSAL",
        "Paradigm HQ is requesting proposals for redesign of its website.",
    ),
    (
        "Website Development RFP",
        "The Bank of Industry is seeking a qualified vendor for website development.",
    ),
    (
        "Expression of Interest",
        "On behalf of iDICE, applications are invited for website redevelopment.",
    ),
]

for title, snippet in opportunity_cases:
    detected = s._is_opportunity_result(
        "website development Nigeria request for proposals",
        title,
        snippet,
    )

    issuer = s._extract_opportunity_issuer(
        title,
        snippet,
    )

    print(f"DETECTED={detected}")
    print(f"ISSUER={issuer}")
    print(f"TITLE={title}")
    print()
