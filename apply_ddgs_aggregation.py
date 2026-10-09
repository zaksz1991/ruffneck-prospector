from pathlib import Path
import shutil

path = Path(r".\backend\app\scrapers\google_search.py")
backup = path.with_name(path.name + ".bak-ddgs-aggregation")

text = path.read_text(encoding="utf-8")

start = text.find("    def _via_ddgs(")
end = text.find("    def _via_google_cse(", start)

if start == -1:
    raise SystemExit("ERROR: Could not find _via_ddgs(). File was not changed.")

if end == -1:
    raise SystemExit("ERROR: Could not find _via_google_cse(). File was not changed.")

new_method = '''    def _via_ddgs(
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

        requested = min(max(int(max_results), 10), 50)

        default_backends = (
            "bing",
            "yahoo",
            "duckduckgo",
            "google",
            "brave",
            "mojeek",
            "startpage",
        )

        configured_backends = os.getenv(
            "DDGS_BACKENDS",
            "",
        ).strip()

        if configured_backends:
            backends = tuple(
                dict.fromkeys(
                    backend.strip().lower()
                    for backend in configured_backends.split(",")
                    if backend.strip()
                )
            )
        else:
            backends = default_backends

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

'''

path.write_text(
    text[:start] + new_method + text[end:],
    encoding="utf-8",
)

shutil.copy2(path, backup)

print("PATCH APPLIED")
print(f"File:   {path}")
print(f"Backup: {backup}")
print("Replaced only _via_ddgs().")
