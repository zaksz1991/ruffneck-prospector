from backend.app.scrapers.google_search import GoogleSearchScraper

s = GoogleSearchScraper(max_results=10)

cases = [
    (
        "website",
        "Emeroject – Nigeria Web Design, Web Development & Creative ...",
        "Nigeria web design and web development services",
        "emeroject.com",
    ),
    (
        "website",
        "Kipiit , Website design, development & IT support in Nigeria",
        "Website design, development and IT support",
        "kipiit.com",
    ),
    (
        "website",
        "Digital Strategy & Website Design In Nigeria",
        "Website design and digital strategy services",
        "donaldigital.com",
    ),
    (
        "digital_marketing",
        "PliorAI Innovations — AI, Software & Digital Transformation",
        "AI software and digital transformation services",
        "pliorai.com",
    ),
    (
        "digital_marketing",
        "TDA — Automation, AI & Digital Transformation for Nigeria",
        "Digital transformation and automation services",
        "thedigitalagencyltd.com",
    ),
    (
        "excel",
        "Aileum Technologies",
        "Excel automation, reporting and business intelligence",
        "aileum.com",
    ),
    (
        "excel",
        "Tech Lift Solutions",
        "Automated reporting and business intelligence solutions",
        "techliftsolutions.com.ng",
    ),
]

for service, title, snippet, domain in cases:
    result = {
        "title": title,
        "body": snippet,
        "href": "https://" + domain + "/",
    }

    provider = s._is_service_provider_result(
        service,
        title,
        snippet,
        domain,
    )

    score = s._prospect_score(result)

    candidate = s._is_prospect_candidate(
        result,
        score,
    )

    print()
    print("=" * 90)
    print("SERVICE:", service)
    print("TITLE:", title)
    print("PROVIDER:", provider)
    print("SCORE:", score)
    print("CANDIDATE:", candidate)
