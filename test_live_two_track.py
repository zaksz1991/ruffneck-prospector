from backend.app.scrapers.google_search import GoogleSearchScraper

s = GoogleSearchScraper(max_results=10)

services = [
    "website",
    "digital_marketing",
    "ai_solution",
    "graphics",
    "cv_resume",
    "excel",
]

for service in services:
    print()
    print("=" * 80)
    print(service.upper())
    print("=" * 80)

    results = s.search_service_leads(
        service,
        location="Nigeria",
        max_results=10,
    )

    print("COUNT:", len(results))

    for i, r in enumerate(results, 1):
        engagement = r.engagement or {}
        raw = r.raw or {}

        print()
        print(i, r.display_name)
        print("TYPE:", engagement.get("discovery_type"))
        print("URL:", r.profile_url)
        print("QUERY:", engagement.get("search_query"))
        print("SCORE:", engagement.get("score"))
        print("ISSUER:", engagement.get("original_issuer"))
        print("SOURCE:", engagement.get("source_url"))
