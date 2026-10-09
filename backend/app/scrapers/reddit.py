"""
Reddit scraper - free-first.
Primary: PRAW (official Reddit API) - free for approved apps / low volume.
Fallback: Apify Reddit actors.
Note (2026): Reddit is tightening new app registrations. Create app early if possible.
"""
from typing import List, Optional
import os
import logging
import requests
from .base import BaseScraper, CommentResult

logger = logging.getLogger(__name__)


class RedditScraper(BaseScraper):
    platform = "reddit"

    def __init__(
        self,
        max_results: int = 100,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
        apify_token: Optional[str] = None,
    ):
        super().__init__(max_results)
        self.client_id = client_id or os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = user_agent or os.getenv("REDDIT_USER_AGENT", "RuffNeckProspector/1.0")
        self.apify_token = apify_token or os.getenv("APIFY_TOKEN")

    def scrape_comments(self, target_url: str, keywords: Optional[List[str]] = None) -> List[CommentResult]:
        keywords = keywords or []
        results: List[CommentResult] = []

        # Prefer official PRAW
        if self.client_id and self.client_secret:
            try:
                results = self._scrape_via_praw(target_url)
            except Exception as e:
                logger.warning(f"PRAW failed: {e}")

        # Fallback to Apify
        if not results and self.apify_token:
            try:
                results = self._scrape_via_apify(target_url)
            except Exception as e:
                logger.warning(f"Apify Reddit failed: {e}")

        if keywords:
            results = self.filter_by_keywords(results, keywords)

        return results[: self.max_results]

    def _scrape_via_praw(self, thread_url: str) -> List[CommentResult]:
        import praw

        reddit = praw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent,
        )
        submission = reddit.submission(url=thread_url)
        submission.comment_sort = "new"
        submission.comments.replace_more(limit=0)  # don't expand all "more comments" for free-tier safety

        results = []
        for comment in submission.comments.list()[: self.max_results]:
            if not hasattr(comment, "body") or comment.body in ("[deleted]", "[removed]"):
                continue
            author = str(comment.author) if comment.author else "[deleted]"
            results.append(
                CommentResult(
                    platform="reddit",
                    username=author,
                    display_name=author,
                    profile_url=f"https://www.reddit.com/user/{author}" if author != "[deleted]" else None,
                    comment_text=comment.body,
                    comment_url=f"https://www.reddit.com{comment.permalink}",
                    post_url=thread_url,
                    post_caption=submission.title,
                    engagement={
                        "score": comment.score,
                        "controversiality": getattr(comment, "controversiality", 0),
                    },
                    raw={"id": comment.id, "created_utc": comment.created_utc},
                )
            )
        return results

    def _scrape_via_apify(self, thread_url: str) -> List[CommentResult]:
        actors = ["trudax/reddit-scraper-lite", "trudax/reddit-scraper"]
        for act in actors:
            try:
                url = f"https://api.apify.com/v2/acts/{act.replace('/', '~')}/run-sync-get-dataset-items"
                payload = {
                    "startUrls": [{"url": thread_url}],
                    "maxItems": self.max_results,
                    "maxComments": self.max_results,
                    "skipComments": False,
                }
                resp = requests.post(
                    url,
                    params={"token": self.apify_token},
                    json=payload,
                    timeout=180,
                )
                if resp.status_code == 200:
                    return self._parse_apify(resp.json(), thread_url)
            except Exception as e:
                logger.debug(f"Reddit actor {act}: {e}")
        return []

    def _parse_apify(self, items: list, post_url: str) -> List[CommentResult]:
        results = []
        for item in items or []:
            # Flatten comments if nested
            comments = item.get("comments") or [item]
            for c in comments:
                username = c.get("author") or c.get("username") or ""
                text = c.get("body") or c.get("text") or c.get("commentText") or ""
                if not username or not text:
                    continue
                results.append(
                    CommentResult(
                        platform="reddit",
                        username=username,
                        profile_url=f"https://www.reddit.com/user/{username}",
                        comment_text=text,
                        comment_url=c.get("url") or post_url,
                        post_url=post_url,
                        engagement={"score": c.get("score") or c.get("ups") or 0},
                        raw=c,
                    )
                )
        return results
