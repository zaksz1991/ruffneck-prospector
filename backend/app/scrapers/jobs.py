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
from urllib.parse import quote_plus
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class JobBoardScraper(BaseScraper):
    platform = "jobs"

    def __init__(self, max_results: int = 40):
        super().__init__(max_results)

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        """
        target_url can be a board name or free-text query.
        Supported boards: remoteok, weworkremotely, indeed, remotive, arbeitnow, jobicy, all
        """
        keywords = keywords or []
        query = target_url.strip().lower()
        results: List[CommentResult] = []

        if query in ("all", "jobs", ""):
            # Aggregate several free boards
            for board_fn in [self._remoteok, self._remotive, self._arbeitnow]:
                try:
                    results.extend(board_fn(keywords))
                except Exception as e:
                    logger.debug(f"Board failed: {e}")
            results = results[: self.max_results]
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

        if keywords:
            results = self.filter_by_keywords(results, keywords)
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
                        engagement={"tags": job.get("tags") or [], "source": "remoteok"},
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
                        engagement={"category": job.get("category"), "source": "remotive"},
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
                        engagement={"tags": job.get("tags") or [], "source": "arbeitnow"},
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
                title = (job.get("jobTitle") or "").lower()
                company = job.get("companyName") or "unknown"
                if keywords and not any(k.lower() in title for k in keywords):
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
                        engagement={"source": "jobicy"},
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
            soup = BeautifulSoup(resp.text, "lxml")
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
                if keywords and not any(k.lower() in title.lower() for k in keywords):
                    continue
                results.append(
                    CommentResult(
                        platform="jobs",
                        username=company.replace(" ", "_").lower()[:40],
                        display_name=company,
                        profile_url=link,
                        comment_text=title,
                        post_url=link,
                        engagement={"source": "weworkremotely"},
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
