from backend.app.scrapers.google_search import GoogleSearchScraper

s = GoogleSearchScraper(max_results=10)

queries = s._service_queries("website", "Nigeria")

for i, query in enumerate(queries, 1):
    print("\n" + "=" * 100)
    print(f"QUERY {i}: {query}")
    print("=" * 100)

    results = s._search(query, max_results=5)

    print("RESULTS:", len(results))

    for j, result in enumerate(results, 1):
        print(
            f"{j}. {result.get('title')} | "
            f"{result.get('href')} | "
            f"{result.get('source')}"
        )
