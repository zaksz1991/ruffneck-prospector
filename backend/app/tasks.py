"""
Celery tasks Ã¢â‚¬â€œ 100% free stack
LinkedIn + jobs + maps + enrichment + scoring + outreach + sequences.
"""

from celery import Celery
import os
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit, urlunsplit

from supabase import create_client

from .scrapers import scrape_platform, discover_service_leads
from .ai.scorer import LeadScorer
from .ai.copywriter import Copywriter
from .generators import create_ebook_pdf, create_slides_pptx
from .email_campaigns import FreeEmailSender, build_sequence
from .enrichment import enrich_prospect


logger = logging.getLogger(__name__)


# ============================================================
# CELERY
# ============================================================

REDIS_URL = os.getenv("REDIS_URL", "").strip().strip('"').strip("'")

if not REDIS_URL.startswith(("redis://", "rediss://")):
    raise RuntimeError(
        "REDIS_URL is missing or invalid. Check the Render environment variables."
    )

celery_app = Celery(
    "ruffneck",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_use_ssl=(
        {"ssl_cert_reqs": "required"}
        if REDIS_URL.startswith("rediss://")
        else None
    ),
)

try:
    from .celeryconfig import beat_schedule, timezone as beat_tz

    celery_app.conf.beat_schedule = beat_schedule
    celery_app.conf.timezone = beat_tz

except Exception:
    pass


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)


# ============================================================
# SUPABASE
# ============================================================

def get_supabase():
    """
    Create and return a Supabase client.
    """

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY required"
        )

    return create_client(url, key)


# ============================================================
# URL / DUPLICATE HELPERS
# ============================================================

def _normalize_url(url: Optional[str]) -> str:
    """
    Normalize URLs for safer duplicate detection.

    LinkedIn domains such as:
        linkedin.com
        www.linkedin.com
        uk.linkedin.com
        ca.linkedin.com

    are normalized to:
        https://www.linkedin.com/...

    Query strings and fragments are removed.
    """

    if not url:
        return ""

    value = str(url).strip()

    if not value:
        return ""

    if value.startswith("//"):
        value = "https:" + value

    if not value.startswith(
        ("http://", "https://")
    ):
        return value.rstrip("/")

    try:
        parts = urlsplit(value)

        scheme = "https"

        host = (
            parts.netloc
            .lower()
            .split("@")[-1]
        )

        if host.startswith("www."):
            bare_host = host[4:]
        else:
            bare_host = host

        if (
            bare_host == "linkedin.com"
            or bare_host.endswith(".linkedin.com")
        ):
            host = "www.linkedin.com"

        path = parts.path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                host,
                path,
                "",
                "",
            )
        )

    except Exception:
        return value.rstrip("/")


def _profile_url_candidates(
    url: Optional[str],
) -> List[str]:
    """
    Build URL variants used when matching existing prospects.

    Supports records stored with or without a trailing slash.
    """

    normalized = _normalize_url(
        url
    )

    if not normalized:
        return []

    candidates = [
        normalized,
        normalized + "/",
    ]

    return list(
        dict.fromkeys(
            candidates
        )
    )

def _clean_linkedin_username(
    username: Optional[str],
) -> str:
    """
    Normalize a LinkedIn username.
    """

    if not username:
        return ""

    value = str(username).strip()

    if not value:
        return ""

    value = value.lower().strip("/")

    if value == "web":
        return ""

    return value


def _is_fake_linkedin_email(
    email: Optional[str],
) -> bool:
    """
    Prevent enrichment from creating fake-looking
    LinkedIn-domain email addresses.
    """

    if not email:
        return False

    value = str(email).strip().lower()

    return value.endswith("@linkedin.com")


def _prospect_exists(
    sb,
    row: Dict[str, Any],
    workspace_id: Optional[str] = None,
) -> bool:
    """
    Check whether a prospect already exists.

    Priority:

    1. LinkedIn username + platform
    2. Profile URL + platform
    3. Generic username + platform

    Workspace is respected when supplied.

    No database migration or unique constraint is required.
    """

    platform = (
        str(row.get("platform") or "")
        .strip()
        .lower()
    )

    username = (
        str(row.get("username") or "")
        .strip()
    )

    profile_url = _normalize_url(
        row.get("profile_url")
    )

    if not platform:
        return False

    try:
        # ----------------------------------------------------
        # LinkedIn username
        # ----------------------------------------------------

        if platform == "linkedin":

            clean_username = _clean_linkedin_username(
                username
            )

            if clean_username:

                query = (
                    sb.table("prospects")
                    .select("id")
                    .eq(
                        "platform",
                        "linkedin",
                    )
                    .eq(
                        "username",
                        clean_username,
                    )
                )

                if workspace_id:
                    query = query.eq(
                        "workspace_id",
                        workspace_id,
                    )

                result = (
                    query
                    .limit(1)
                    .execute()
                )

                if result.data:
                    return True

        # ----------------------------------------------------
        # Profile URL
        # ----------------------------------------------------

        if profile_url:

            # Check both canonical forms independently.
            # A transient Supabase/TLS failure on one candidate
            # must not prevent the remaining candidate from being
            # checked.
            for candidate_url in _profile_url_candidates(
                row.get("profile_url")
            ):

                try:

                    query = (
                        sb.table("prospects")
                        .select("id")
                        .eq(
                            "platform",
                            platform,
                        )
                        .eq(
                            "profile_url",
                            candidate_url,
                        )
                    )

                    if workspace_id:
                        query = query.eq(
                            "workspace_id",
                            workspace_id,
                        )

                    result = (
                        query
                        .limit(1)
                        .execute()
                    )

                    if result.data:
                        return True

                except Exception as e:

                    logger.warning(
                        "Profile URL duplicate lookup failed "
                        f"for {candidate_url!r}: {e}"
                    )

                    continue

        # ----------------------------------------------------
        # Generic username
        # ----------------------------------------------------

        if (
            username
            and username.lower() != "web"
        ):

            query = (
                sb.table("prospects")
                .select("id")
                .eq(
                    "platform",
                    platform,
                )
                .eq(
                    "username",
                    username,
                )
            )

            if workspace_id:
                query = query.eq(
                    "workspace_id",
                    workspace_id,
                )

            result = (
                query
                .limit(1)
                .execute()
            )

            if result.data:
                return True

    except Exception as e:

        logger.warning(
            f"Duplicate check failed: {e}"
        )

    return False


def _prepare_enrichment(
    row: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run free enrichment and safely attach its results.

    Also prevents @linkedin.com enrichment results.

    IMPORTANT:
    This function is intentionally NOT used by discovery.
    Discovery must never invent or guess email addresses.
    """

    try:

        enrich = enrich_prospect(
            row
        )

    except Exception as e:

        logger.warning(
            f"Enrichment failed: {e}"
        )

        enrich = {
            "enrichment_status": "error",
            "email_candidates": [],
            "email_source": None,
        }

    email = (
        enrich.get("email") or ""
    ).strip()

    if _is_fake_linkedin_email(
        email
    ):

        logger.warning(
            "Rejected @linkedin.com enrichment result"
        )

        email = ""

    if email:

        row["email"] = email

        row["email_confidence"] = (
            enrich.get(
                "email_confidence",
                0,
            )
        )

    phone = (
        enrich.get(
            "phone"
        )
        or ""
    ).strip()

    if phone:
        row["phone"] = phone

    if enrich.get(
        "company_domain"
    ):

        metadata = (
            row.get("metadata")
            or {}
        )

        metadata[
            "company_domain"
        ] = enrich[
            "company_domain"
        ]

        row["metadata"] = metadata

    metadata = (
        row.get("metadata")
        or {}
    )

    metadata[
        "email_source"
    ] = enrich.get(
        "email_source"
    )

    metadata[
        "email_candidates"
    ] = enrich.get(
        "email_candidates",
        [],
    )

    metadata[
        "enrichment_status"
    ] = enrich.get(
        "enrichment_status",
        "none",
    )

    row["metadata"] = metadata

    return row


# ============================================================
# SCRAPE PROSPECTS
# ============================================================

@celery_app.task(
    bind=True,
    name="scrape_prospects",
)
def scrape_prospects_task(
    self,
    platform: str,
    target_url: str,
    keywords: List[str] = None,
    max_results: int = 40,
    workspace_id: str = None,
):
    """
    Scrape prospects from a platform and insert only
    new prospects.

    Duplicate prospects are skipped.
    """

    keywords = keywords or []

    sb = get_supabase()

    try:

        self.update_state(
            state="PROGRESS",
            meta={
                "status": "scraping",
                "platform": platform,
            },
        )

        comments = scrape_platform(
            platform,
            target_url,
            keywords=keywords,
            max_results=max_results,
        )

        inserted = 0
        duplicates = 0
        failed = 0

        for c in comments:

            try:

                row = {
                    "platform": c.platform,
                    "username": c.username,
                    "display_name": c.display_name,
                    "profile_url": c.profile_url,
                    "comment_text": c.comment_text,
                    "comment_url": c.comment_url,
                    "post_url": (
                        c.post_url
                        or target_url
                    ),
                    "post_caption": c.post_caption,
                    "follower_count": (
                        c.follower_count
                        or 0
                    ),
                    "bio_text": c.bio_text,
                    "is_verified": c.is_verified,
                    "data_source": (
                        f"{c.platform}_public"
                    ),
                    "workspace_id": workspace_id,
                    "tags": (
                        [
                            "competitor",
                            "lookalike",
                        ]
                        if c.platform
                        == "competitors"
                        else []
                    ),
                    "metadata": {
                        "engagement": (
                            c.engagement
                            or {}
                        ),
                        "seed": (
                            c.engagement
                            or {}
                        ).get(
                            "seed"
                        ),
                    },
                }

                # Duplicate protection
                if _prospect_exists(
                    sb,
                    row,
                    workspace_id=workspace_id,
                ):

                    duplicates += 1

                    logger.info(
                        "Duplicate prospect skipped: "
                        f"{row.get('platform')} / "
                        f"{row.get('username')}"
                    )

                    continue

                # Normal scraping is allowed to enrich.
                row = _prepare_enrichment(
                    row
                )

                # Insert
                ins = (
                    sb.table(
                        "prospects"
                    )
                    .insert(row)
                    .execute()
                )

                inserted += 1

                # Tech detection for site-based leads
                try:

                    pid = (
                        (ins.data or [{}])[0]
                        .get("id")
                    )

                    url = (
                        row.get(
                            "profile_url"
                        )
                        or (
                            row.get(
                                "metadata"
                            )
                            or {}
                        ).get(
                            "company_domain"
                        )
                    )

                    if (
                        pid
                        and url
                        and row.get(
                            "platform"
                        )
                        in (
                            "maps",
                            "google",
                            "competitors",
                            "google_maps",
                        )
                    ):

                        from .tech_detect import (
                            detect_tech,
                        )

                        tech = detect_tech(
                            str(url)
                        )

                        if tech.get(
                            "ok"
                        ):

                            meta = (
                                row.get(
                                    "metadata"
                                )
                                or {}
                            )

                            meta[
                                "tech"
                            ] = tech

                            (
                                sb.table(
                                    "prospects"
                                )
                                .update(
                                    {
                                        "metadata": meta
                                    }
                                )
                                .eq(
                                    "id",
                                    pid,
                                )
                                .execute()
                            )

                except Exception as e:
                    logger.warning(
                        "Positive-reply notification failed for "
                        f"prospect {pid}: {e}"
                    )

            except Exception as e:

                failed += 1

                logger.warning(
                    f"Insert skip: {e}"
                )

        return {
            "status": "completed",
            "scraped": len(
                comments
            ),
            "inserted": inserted,
            "duplicates": duplicates,
            "failed": failed,
            "platform": platform,
        }

    except Exception as e:

        logger.exception(
            "Scrape failed"
        )

        return {
            "status": "failed",
            "error": str(e),
        }


# ============================================================
# DISCOVER SERVICE LEADS
# ============================================================

@celery_app.task(
    bind=True,
    name="discover_service_leads",
)
def discover_service_leads_task(
    self,
    service: str,
    extra_keywords: List[str] = None,
    max_results: int = 25,
    location: str = "Nigeria",
):
    """
    Discover service-intent leads.

    IMPORTANT:
    Discovery does NOT run enrichment.
    This prevents guessed/pattern-generated emails
    from being inserted during discovery.

    Enrichment is performed separately by the explicit
    enrichment tasks.
    """

    sb = get_supabase()

    try:

        leads = discover_service_leads(
            service,
            extra_keywords or [],
            max_results=max_results,
            location=location or "Nigeria",
        )

        inserted = 0
        duplicates = 0

        for c in leads:

            try:

                engagement = (
                    c.engagement
                    or {}
                )

                row = {
                    "platform": (
                        c.platform
                        or "google"
                    ),
                    "username": (
                        c.username
                        or "web"
                    ),
                    "display_name": (
                        c.display_name
                    ),
                    "profile_url": (
                        c.profile_url
                    ),
                    "comment_text": (
                        c.comment_text
                    ),
                    "post_url": (
                        c.post_url
                    ),
                    "bio_text": (
                        c.bio_text
                    ),
                    "data_source": (
                        "google_intent_search"
                    ),
                    "tags": [
                        service
                    ],
                    "metadata": {
                        "query_service": service,
                        "discovery": True,
                        "enrichment_status": "not_run",
                        "root_domain": engagement.get(
                            "root_domain"
                        ),
                        "page_type": engagement.get(
                            "page_type"
                        ),
                        "search_score": engagement.get(
                            "score"
                        ),
                        "original_issuer": engagement.get(
                            "original_issuer"
                        ),
                        "source_url": engagement.get(
                            "source_url"
                        ),
                        "source_domain": engagement.get(
                            "source_domain"
                        ),
                    },
                }

                if _prospect_exists(
                    sb,
                    row,
                ):

                    duplicates += 1

                    # Reconcile corrected issuer metadata for
                    # existing Google opportunity prospects.
                    incoming_meta = (
                        row.get("metadata")
                        or {}
                    )

                    incoming_issuer = (
                        incoming_meta.get(
                            "original_issuer"
                        )
                        or ""
                    ).strip()

                    if (
                        incoming_meta.get(
                            "page_type"
                        ) == "opportunity"
                        and incoming_issuer
                        and row.get("profile_url")
                    ):

                        try:

                            existing = (
                                sb.table(
                                    "prospects"
                                )
                                .select(
                                    "id, metadata"
                                )
                                .eq(
                                    "platform",
                                    row.get(
                                        "platform"
                                    ),
                                )
                                .in_(
                                    "profile_url",
                                    [
                                        _normalize_url(
                                            row.get(
                                                "profile_url"
                                            )
                                        ),
                                        _normalize_url(
                                            row.get(
                                                "profile_url"
                                            )
                                        ) + "/",
                                    ],
                                )
                                .execute()
                            )

                            for prospect in (
                                existing.data or []
                            ):

                                existing_meta = {
                                    **(
                                        prospect.get(
                                            "metadata"
                                        )
                                        or {}
                                    )
                                }

                                current_issuer = (
                                    existing_meta.get(
                                        "original_issuer"
                                    )
                                    or ""
                                ).strip()

                                if (
                                    current_issuer
                                    != incoming_issuer
                                ):

                                    existing_meta[
                                        "original_issuer"
                                    ] = incoming_issuer

                                    (
                                        sb.table(
                                            "prospects"
                                        )
                                        .update(
                                            {
                                                "metadata": (
                                                    existing_meta
                                                )
                                            }
                                        )
                                        .eq(
                                            "id",
                                            prospect.get(
                                                "id"
                                            ),
                                        )
                                        .execute()
                                    )

                                    logger.info(
                                        "Reconciled opportunity issuer: "
                                        f"{current_issuer!r} -> "
                                        f"{incoming_issuer!r} "
                                        f"for {row.get('profile_url')}"
                                    )

                        except Exception as e:

                            logger.warning(
                                "Opportunity issuer reconciliation "
                                f"failed: {e}"
                            )

                    continue

                # IMPORTANT:
                # Do NOT call _prepare_enrichment(row) here.
                # Discovery must never create guessed emails.

                (
                    sb.table(
                        "prospects"
                    )
                    .insert(row)
                    .execute()
                )

                inserted += 1

            except Exception as e:

                logger.warning(
                    f"Discover insert skip: {e}"
                )

        return {
            "status": "completed",
            "found": len(leads),
            "inserted": inserted,
            "duplicates": duplicates,
            "service": service,
        }

    except Exception as e:

        logger.exception(
            "Service discovery failed"
        )

        return {
            "status": "failed",
            "error": str(e),
        }


# ============================================================
# ENRICH EXISTING PROSPECTS
# ============================================================

@celery_app.task(
    bind=True,
    name="enrich_prospects",
)
def enrich_prospects_task(
    self,
    prospect_ids: List[str],
):
    """
    Run free email enrichment on existing prospects.
    """

    sb = get_supabase()

    enriched = 0

    for pid in prospect_ids:

        try:

            res = (
                sb.table(
                    "prospects"
                )
                .select("*")
                .eq(
                    "id",
                    pid,
                )
                .single()
                .execute()
            )

            prospect = res.data

            data = enrich_prospect(
                prospect
            )

            meta = {
                **(
                    prospect.get(
                        "metadata"
                    )
                    or {}
                )
            }

            meta[
                "email_source"
            ] = data.get(
                "email_source"
            )

            meta[
                "email_candidates"
            ] = data.get(
                "email_candidates",
                [],
            )

            meta[
                "phone_source"
            ] = data.get(
                "phone_source"
            )

            meta[
                "phone_candidates"
            ] = data.get(
                "phone_candidates",
                [],
            )

            meta[
                "phone_confidence"
            ] = data.get(
                "phone_confidence",
                0,
            )

            meta[
                "enrichment_status"
            ] = data.get(
                "enrichment_status",
                "none",
            )

            meta[
                "email_valid"
            ] = data.get(
                "email_valid"
            )

            meta[
                "email_status"
            ] = data.get(
                "email_status"
            )

            meta[
                "email_verify_confidence"
            ] = data.get(
                "email_verify_confidence"
            )

            if data.get(
                "company_domain"
            ):

                meta[
                    "company_domain"
                ] = data[
                    "company_domain"
                ]

            update = {
                "metadata": meta,
                "status": (
                    "enriched"
                    if prospect.get(
                        "status"
                    )
                    in (
                        "new",
                        "scored",
                    )
                    else prospect.get(
                        "status"
                    )
                ),
            }

            email = (
                data.get(
                    "email"
                )
                or ""
            ).strip()

            if data.get(
                "email_source"
            ) == "pattern_guess":

                update[
                    "email"
                ] = None

                update[
                    "email_confidence"
                ] = 0

            elif (
                email
                and not _is_fake_linkedin_email(
                    email
                )
            ):

                update[
                    "email"
                ] = email

                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )

            phone = (
                data.get(
                    "phone"
                )
                or ""
            ).strip()

            update[
                "phone"
            ] = phone or None

            (
                sb.table(
                    "prospects"
                )
                .update(update)
                .eq(
                    "id",
                    pid,
                )
                .execute()
            )

            if (
                email
                or phone
                or data.get(
                    "company_domain"
                )
            ):

                enriched += 1

        except Exception as e:

            logger.warning(
                f"Enrich failed {pid}: {e}"
            )

    return {
        "status": "completed",
        "enriched": enriched,
    }


# ============================================================
# SCORE PROSPECTS
# ============================================================

@celery_app.task(
    bind=True,
    name="score_prospects",
)
def score_prospects_task(
    self,
    prospect_ids: List[str],
    scoring_rules: Dict[str, Any] = None,
):
    sb = get_supabase()

    scorer = LeadScorer()

    scored = 0

    for pid in prospect_ids:

        try:

            res = (
                sb.table(
                    "prospects"
                )
                .select("*")
                .eq(
                    "id",
                    pid,
                )
                .single()
                .execute()
            )

            prospect = res.data

            overall, reason, breakdown = (
                scorer.score(
                    prospect,
                    scoring_rules,
                )
            )

            sb.table(
                "prospects"
            ).update(
                {
                    "intent_score": overall,
                    "score_reason": reason,
                    "status": "scored",
                    "metadata": {
                        **(
                            prospect.get(
                                "metadata"
                            )
                            or {}
                        ),
                        "score_breakdown": (
                            breakdown
                        ),
                    },
                    "tags": list(
                        set(
                            (
                                prospect.get(
                                    "tags"
                                )
                                or []
                            )
                            + [
                                breakdown.get(
                                    "recommended_service",
                                    "other",
                                )
                            ]
                        )
                    ),
                }
            ).eq(
                "id",
                pid,
            ).execute()

            scored += 1

        except Exception as e:

            logger.warning(
                f"Score failed {pid}: {e}"
            )

    return {
        "status": "completed",
        "scored": scored,
    }


# ============================================================
# GENERATE ASSET
# ============================================================

@celery_app.task(
    bind=True,
    name="generate_asset",
)
def generate_asset_task(
    self,
    prospect_id: str,
    asset_type: str,
    topic: str,
    branding: Dict[str, Any] = None,
):
    sb = get_supabase()

    branding = branding or {
        "company_name": "RuffNeck Services"
    }

    res = (
        sb.table(
            "prospects"
        )
        .select("*")
        .eq(
            "id",
            prospect_id,
        )
        .single()
        .execute()
    )

    prospect = res.data

    if asset_type == "ebook":

        filepath = create_ebook_pdf(
            topic,
            branding,
            prospect,
        )

    elif asset_type == "slides":

        filepath = create_slides_pptx(
            topic,
            branding,
            prospect,
        )

    else:

        raise ValueError(
            f"Unknown asset_type: {asset_type}"
        )

    file_url = f"file://{filepath}"

    (
        sb.table(
            "assets"
        )
        .insert(
            {
                "prospect_id": prospect_id,
                "asset_type": asset_type,
                "topic": topic,
                "title": (
                    f"{topic} for "
                    f"{prospect.get('username')}"
                ),
                "file_url": file_url,
                "branding": branding,
            }
        )
        .execute()
    )

    return {
        "status": "completed",
        "file_url": file_url,
        "local_path": filepath,
    }


# ============================================================
# SEND OUTREACH
# ============================================================

@celery_app.task(
    bind=True,
    name="send_outreach",
)
def send_outreach_task(
    self,
    prospect_ids: List[str],
    channel: str = "email",
    topic: str = "digital services",
    service: str = "website",
    send_real: bool = False,
):
    sb = get_supabase()

    writer = Copywriter()
    sender = FreeEmailSender()

    results = []

    for pid in prospect_ids:

        try:

            res = (
                sb.table(
                    "prospects"
                )
                .select("*")
                .eq(
                    "id",
                    pid,
                )
                .single()
                .execute()
            )

            prospect = res.data

            if prospect.get(
                "unsubscribed"
            ):
                continue

            sequence = []

            if channel == "email":

                sequence = build_sequence(
                    prospect,
                    service=service,
                )

                primary = sequence[0]

                copy = {
                    "subject": primary[
                        "subject"
                    ],
                    "body": primary[
                        "body"
                    ],
                }

            else:

                copy = writer.generate_outreach(
                    prospect,
                    channel=channel,
                    topic=topic,
                )

            log_status = "queued"

            if (
                send_real
                and channel == "email"
                and prospect.get(
                    "email"
                )
                and sender.is_configured()
            ):

                send_result = sender.send(
                    to_email=prospect[
                        "email"
                    ],
                    subject=copy[
                        "subject"
                    ],
                    body_html=copy[
                        "body"
                    ].replace(
                        "\n",
                        "<br>",
                    ),
                    body_text=copy[
                        "body"
                    ],
                )

                log_status = send_result.get(
                    "status",
                    "failed",
                )

            (
                sb.table(
                    "outreach_logs"
                )
                .insert(
                    {
                        "prospect_id": pid,
                        "channel": channel,
                        "subject_line": copy.get(
                            "subject"
                        ),
                        "message_text": copy.get(
                            "body"
                        ),
                        "status": log_status,
                    }
                )
                .execute()
            )

            if log_status in (
                "sent",
                "queued",
            ):

                (
                    sb.table(
                        "prospects"
                    )
                    .update(
                        {
                            "last_contacted_at": "now()",
                            "status": "contacted",
                        }
                    )
                    .eq(
                        "id",
                        pid,
                    )
                    .execute()
                )

            results.append(
                {
                    "prospect_id": pid,
                    "status": log_status,
                    "preview": (
                        copy.get(
                            "body"
                        )
                        or ""
                    )[:120],
                    "sequence_length": (
                        len(sequence)
                        if channel
                        == "email"
                        else 1
                    ),
                }
            )

        except Exception as e:

            logger.warning(
                f"Outreach {pid}: {e}"
            )

            results.append(
                {
                    "prospect_id": pid,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return {
        "status": "completed",
        "results": results,
    }


# ============================================================
# DAILY DISCOVERY
# ============================================================

@celery_app.task(
    bind=True,
    name="run_daily_discovery",
)
def run_daily_discovery_task(
    self,
    location: str = "",
    services: List[str] = None,
    workspace_id: str = None,
):
    """
    One-click daily discovery:

    - Service intent searches
    - LinkedIn intent
    - Job boards
    - Optional local Maps

    Discovery never runs email enrichment.
    """

    services = services or [
        "website",
        "digital_marketing",
        "ai_solution",
        "graphics",
        "cv_resume",
        "excel",
        "hiring_services",
        "buying_intent",
    ]

    results = {}

    sb = get_supabase()

    # ========================================================
    # 1. SERVICE INTENT
    # ========================================================

    for svc in services:

        try:

            extra = (
                [location]
                if location
                else []
            )

            leads = discover_service_leads(
                svc,
                extra,
                max_results=12,
                location=location or "Nigeria",
            )

            inserted = 0
            duplicates = 0

            for c in leads:

                try:

                    engagement = (
                        c.engagement
                        or {}
                    )

                    row = {
                        "platform": (
                            c.platform
                            or "google"
                        ),
                        "username": (
                            c.username
                            or "web"
                        ),
                        "display_name": (
                            c.display_name
                        ),
                        "profile_url": (
                            c.profile_url
                        ),
                        "comment_text": (
                            c.comment_text
                        ),
                        "post_url": (
                            c.post_url
                        ),
                        "bio_text": (
                            c.bio_text
                        ),
                        "data_source": (
                            "daily_discovery"
                        ),
                        "workspace_id": (
                            workspace_id
                        ),
                        "tags": [
                            svc,
                            "daily",
                        ],
                        "metadata": {
                            "query_service": svc,
                            "location": location,
                            "discovery": True,
                            "enrichment_status": "not_run",
                            "root_domain": engagement.get(
                                "root_domain"
                            ),
                            "page_type": engagement.get(
                                "page_type"
                            ),
                            "search_score": engagement.get(
                                "score"
                            ),
                            "original_issuer": engagement.get(
                                "original_issuer"
                            ),
                            "source_url": engagement.get(
                                "source_url"
                            ),
                            "source_domain": engagement.get(
                                "source_domain"
                            ),
                        },
                    }

                    if _prospect_exists(
                        sb,
                        row,
                        workspace_id=workspace_id,
                    ):

                        duplicates += 1
                        continue

                    # IMPORTANT:
                    # No _prepare_enrichment() here.
                    # Discovery must not generate guessed emails.

                    (
                        sb.table(
                            "prospects"
                        )
                        .insert(row)
                        .execute()
                    )

                    inserted += 1

                except Exception as e:

                    logger.warning(
                        "Daily service insert skip: "
                        f"{e}"
                    )

            results[
                f"service_{svc}"
            ] = {
                "inserted": inserted,
                "duplicates": duplicates,
            }

        except Exception as e:

            results[
                f"service_{svc}"
            ] = f"error: {e}"

    # ========================================================
    # 2. LINKEDIN BROAD INTENT
    # ========================================================

    try:

        li_leads = scrape_platform(
            "linkedin",
            (
                "need website OR "
                "digital marketing OR "
                "AI OR designer "
                f"{location}"
            ),
            max_results=15,
        )

        inserted = 0
        duplicates = 0

        for c in li_leads:

            try:

                # LinkedIn scraper results are dictionaries.
                # Use dictionary access here instead of
                # object attributes such as c.profile_url.

                row = {
                    "platform": "linkedin",
                    "username": c.get(
                        "username"
                    ),
                    "display_name": c.get(
                        "display_name"
                    ),
                    "profile_url": c.get(
                        "profile_url"
                    ),
                    "comment_text": c.get(
                        "comment_text"
                    ),
                    "post_url": c.get(
                        "post_url"
                    ),
                    "bio_text": c.get(
                        "bio_text"
                    ),
                    "data_source": (
                        "daily_discovery"
                    ),
                    "workspace_id": (
                        workspace_id
                    ),
                    "tags": [
                        "linkedin",
                        "daily",
                    ],
                    "metadata": {
                        "engagement": (
                            c.get(
                                "engagement"
                            )
                            or {}
                        ),
                        "discovery": True,
                        "enrichment_status": "not_run",
                    },
                }

                if _prospect_exists(
                    sb,
                    row,
                    workspace_id=workspace_id,
                ):

                    duplicates += 1
                    continue

                # No enrichment during discovery.
                (
                    sb.table(
                        "prospects"
                    )
                    .insert(row)
                    .execute()
                )

                inserted += 1

            except Exception as e:

                logger.warning(
                    "Daily LinkedIn insert skip: "
                    f"{e}"
                )

        results["linkedin"] = {
            "inserted": inserted,
            "duplicates": duplicates,
        }

    except Exception as e:

        results["linkedin"] = (
            f"error: {e}"
        )

    # ========================================================
    # 3. JOB BOARDS
    # ========================================================

    try:

        job_leads = scrape_platform(
            "jobs",
            "all",
            keywords=[
                # Digital / marketing demand
                "marketing",
                "digital marketing",
                "social media",
                "social media manager",
                "content creator",
                "content writer",
                "seo",
                "advertising",

                # Web / software demand
                "developer",
                "web developer",
                "software developer",
                "software engineer",
                "frontend",
                "backend",
                "full stack",
                "wordpress",

                # Design / creative demand
                "designer",
                "graphic designer",
                "ui designer",
                "ux designer",
                "ui/ux",
                "video editor",

                # Data / AI demand
                "data",
                "data analyst",
                "data entry",
                "excel",
                "power bi",
                "business intelligence",
                "artificial intelligence",
                "ai specialist",
                "machine learning",

                # Administrative / virtual support demand
                "virtual assistant",
                "administrative assistant",
                "admin assistant",
                "operations assistant",
                "customer support",
                "office assistant",
                "project assistant",
            ],
            max_results=20,
        )

        inserted = 0
        duplicates = 0

        for c in job_leads:

            try:

                row = {
                    "platform": "jobs",
                    "username": c.username,
                    "display_name": (
                        c.display_name
                    ),
                    "profile_url": (
                        c.profile_url
                    ),
                    "comment_text": (
                        c.comment_text
                    ),
                    "post_url": (
                        c.post_url
                    ),
                    "bio_text": (
                        c.bio_text
                    ),
                    "data_source": (
                        "daily_discovery"
                    ),
                    "workspace_id": (
                        workspace_id
                    ),
                    "tags": [
                        "jobs",
                        "daily",
                    ],
                    "metadata": {
                        "engagement": (
                            c.engagement
                            or {}
                        ),
                        "discovery": True,
                        "enrichment_status": "not_run",
                    },
                }

                if _prospect_exists(
                    sb,
                    row,
                    workspace_id=workspace_id,
                ):

                    duplicates += 1
                    continue

                # No enrichment during discovery.
                (
                    sb.table(
                        "prospects"
                    )
                    .insert(row)
                    .execute()
                )

                inserted += 1

            except Exception as e:

                logger.warning(
                    "Daily job insert skip: "
                    f"{e}"
                )

        results["jobs"] = {
            "inserted": inserted,
            "duplicates": duplicates,
        }

    except Exception as e:

        results["jobs"] = (
            f"error: {e}"
        )

    # ========================================================
    # 4. MAPS
    # ========================================================

    if location:

        try:

            map_leads = scrape_platform(
                "maps",
                location,
                keywords=[
                    "no_website"
                ],
                max_results=10,
            )

            inserted = 0
            duplicates = 0

            for c in map_leads:

                try:

                    row = {
                        "platform": "maps",
                        "username": c.username,
                        "display_name": (
                            c.display_name
                        ),
                        "profile_url": (
                            c.profile_url
                        ),
                        "comment_text": (
                            c.comment_text
                        ),
                        "post_url": (
                            c.post_url
                        ),
                        "bio_text": (
                            c.bio_text
                        ),
                        "data_source": (
                            "daily_discovery"
                        ),
                        "workspace_id": (
                            workspace_id
                        ),
                        "tags": [
                            "maps",
                            "daily",
                            "local",
                        ],
                        "metadata": {
                            **(
                                c.engagement
                                or {}
                            ),
                            "discovery": True,
                            "enrichment_status": "not_run",
                        },
                    }

                    if _prospect_exists(
                        sb,
                        row,
                        workspace_id=workspace_id,
                    ):

                        duplicates += 1
                        continue

                    # No enrichment during discovery.
                    (
                        sb.table(
                            "prospects"
                        )
                        .insert(row)
                        .execute()
                    )

                    inserted += 1

                except Exception as e:

                    logger.warning(
                        "Daily Maps insert skip: "
                        f"{e}"
                    )

            results["maps"] = {
                "inserted": inserted,
                "duplicates": duplicates,
            }

        except Exception as e:

            results["maps"] = (
                f"error: {e}"
            )

    return {
        "status": "completed",
        "results": results,
        "location": location,
    }


# ============================================================
# AUTO ENRICH NEW PROSPECTS
# ============================================================

@celery_app.task(
    bind=True,
    name="auto_enrich_new_prospects",
)
def auto_enrich_new_prospects_task(
    self,
    limit: int = 40,
):
    """
    Automatically find prospects that still need
    enrichment and run the waterfall.
    """

    sb = get_supabase()

    res = (
        sb.table(
            "prospects"
        )
        .select(
            "id, username, display_name, "
            "comment_text, bio_text, profile_url, "
            "post_url, email, phone, website, "
            "metadata, status"
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(200)
        .execute()
    )

    candidates = []

    for row in (
        res.data or []
    ):

        meta = (
            row.get(
                "metadata"
            )
            or {}
        )

        status = (
            meta.get(
                "enrichment_status"
            )
            or "none"
        )

        if (
            row.get("email")
            and status
            in (
                "email_found",
                "email_guessed",
            )
        ):

            continue

        if status in (
            "none",
            "not_run",
            "domain_found",
            "patterns_generated",
            None,
            "",
        ):

            candidates.append(
                row
            )

        if len(
            candidates
        ) >= limit:

            break

    enriched = 0

    for prospect in candidates:

        try:

            data = enrich_prospect(
                prospect
            )

            meta = {
                **(
                    prospect.get(
                        "metadata"
                    )
                    or {}
                )
            }

            meta[
                "email_source"
            ] = data.get(
                "email_source"
            )

            meta[
                "email_candidates"
            ] = data.get(
                "email_candidates",
                [],
            )

            meta[
                "phone_source"
            ] = data.get(
                "phone_source"
            )

            meta[
                "phone_candidates"
            ] = data.get(
                "phone_candidates",
                [],
            )

            meta[
                "phone_confidence"
            ] = data.get(
                "phone_confidence",
                0,
            )

            meta[
                "enrichment_status"
            ] = data.get(
                "enrichment_status",
                "none",
            )

            if data.get(
                "company_domain"
            ):

                meta[
                    "company_domain"
                ] = data[
                    "company_domain"
                ]

            update = {
                "metadata": meta
            }

            email = (
                data.get(
                    "email"
                )
                or ""
            ).strip()

            if data.get(
                "email_source"
            ) == "pattern_guess":

                update[
                    "email"
                ] = None

                update[
                    "email_confidence"
                ] = 0

            elif (
                email
                and not _is_fake_linkedin_email(
                    email
                )
            ):

                update[
                    "email"
                ] = email

                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )

                if prospect.get(
                    "status"
                ) in (
                    "new",
                    "scored",
                ):

                    update[
                        "status"
                    ] = "enriched"

            phone = (
                data.get(
                    "phone"
                )
                or ""
            ).strip()

            update[
                "phone"
            ] = phone or None

            if phone:
                if prospect.get(
                    "status"
                ) in (
                    "new",
                    "scored",
                ):

                    update[
                        "status"
                    ] = "enriched"
            (
                sb.table(
                    "prospects"
                )
                .update(update)
                .eq(
                    "id",
                    prospect["id"],
                )
                .execute()
            )

            if (
                email
                or phone
                or data.get(
                    "company_domain"
                )
            ):

                enriched += 1

        except Exception as e:

            logger.warning(
                "Auto-enrich failed "
                f"for {prospect.get('id')}: {e}"
            )

    return {
        "status": "completed",
        "candidates_checked": len(
            candidates
        ),
        "enriched": enriched,
    }


# ============================================================
# PROCESS DUE SEQUENCES
# ============================================================

@celery_app.task(
    bind=True,
    name="process_due_sequences",
)
def process_due_sequences_task(
    self,
):
    """
    Process sequence steps that are due.

    Skips / pauses enrollments marked as replied.
    """

    from datetime import (
        datetime,
        timezone,
    )

    sb = get_supabase()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    res = (
        sb.table(
            "sequence_enrollments"
        )
        .select(
            "*, sequences(*), "
            "prospects("
            "id, email, display_name, "
            "username, status, metadata"
            ")"
        )
        .eq(
            "status",
            "active",
        )
        .lte(
            "next_send_at",
            now,
        )
        .limit(50)
        .execute()
    )

    processed = 0

    for enroll in (
        res.data or []
    ):

        try:

            prospect = (
                enroll.get(
                    "prospects"
                )
                or {}
            )

            if (
                prospect.get(
                    "status"
                )
                == "replied"
            ):

                (
                    sb.table(
                        "sequence_enrollments"
                    )
                    .update(
                        {
                            "status": "replied"
                        }
                    )
                    .eq(
                        "id",
                        enroll["id"],
                    )
                    .execute()
                )

                continue

            steps_res = (
                sb.table(
                    "sequence_steps"
                )
                .select("*")
                .eq(
                    "sequence_id",
                    enroll[
                        "sequence_id"
                    ],
                )
                .order(
                    "step_order"
                )
                .execute()
            )

            steps = (
                steps_res.data
                or []
            )

            step_idx = (
                enroll.get(
                    "current_step"
                )
                or 0
            )

            if step_idx >= len(
                steps
            ):

                (
                    sb.table(
                        "sequence_enrollments"
                    )
                    .update(
                        {
                            "status": "completed"
                        }
                    )
                    .eq(
                        "id",
                        enroll["id"],
                    )
                    .execute()
                )

                continue

            step = steps[
                step_idx
            ]

            from .email_campaigns import (
                FreeEmailSender,
            )

            sender = FreeEmailSender()

            to_email = prospect.get(
                "email"
            )

            if not to_email:

                logger.info(
                    "Skipping enrollment "
                    f"{enroll.get('id')} "
                    "Ã¢â‚¬â€œ no email on prospect"
                )

                (
                    sb.table(
                        "sequence_enrollments"
                    )
                    .update(
                        {
                            "status": "paused"
                        }
                    )
                    .eq(
                        "id",
                        enroll["id"],
                    )
                    .execute()
                )

                continue

            meta = (
                prospect.get(
                    "metadata"
                )
                or {}
            )

            if meta.get(
                "email_status"
            ) in (
                "invalid_syntax",
                "disposable",
                "no_mx",
                "undeliverable",
                "risky",
            ):

                logger.info(
                    f"Skipping {to_email} "
                    "Ã¢â‚¬â€œ marked invalid"
                )

                (
                    sb.table(
                        "sequence_enrollments"
                    )
                    .update(
                        {
                            "status": "paused"
                        }
                    )
                    .eq(
                        "id",
                        enroll["id"],
                    )
                    .execute()
                )

                continue

            from .suppression import (
                is_suppressed,
            )

            if is_suppressed(
                sb,
                to_email,
            ):

                logger.info(
                    f"Skipping {to_email} "
                    "Ã¢â‚¬â€œ suppressed/unsubscribed"
                )

                (
                    sb.table(
                        "sequence_enrollments"
                    )
                    .update(
                        {
                            "status": "paused"
                        }
                    )
                    .eq(
                        "id",
                        enroll["id"],
                    )
                    .execute()
                )

                continue

            name = (
                prospect.get(
                    "display_name"
                )
                or prospect.get(
                    "username"
                )
                or "there"
            )

            ctx = {
                "name": name,
                "service": (
                    meta.get(
                        "recommended_service"
                    )
                    or "digital services"
                ),
                "context": (
                    prospect.get(
                        "comment_text"
                    )
                    or ""
                )[:100],
                "company": (
                    meta.get(
                        "company_domain"
                    )
                    or ""
                ),
            }

            subject = (
                step.get(
                    "subject_template"
                )
                or "Quick note"
            )

            body = (
                step.get(
                    "body_template"
                )
                or ""
            )

            for k, v in ctx.items():

                subject = subject.replace(
                    "{{" + k + "}}",
                    str(v),
                )

                body = body.replace(
                    "{{" + k + "}}",
                    str(v),
                )

            unsub_footer = (
                "\n\n---\n"
                "Reply STOP or UNSUBSCRIBE "
                "to opt out of future emails."
            )

            body_with_footer = (
                body
                + unsub_footer
            )

            body_html = (
                body_with_footer
                .replace(
                    "\n",
                    "<br>",
                )
            )

            send_result = sender.send(
                to_email,
                subject,
                body_html,
                body_text=body_with_footer,
            )

            logger.info(
                f"Sequence step {step_idx} "
                f"to {to_email}: "
                f"{send_result.get('status')}"
            )

            if (
                send_result.get(
                    "status"
                )
                == "failed"
            ):

                continue

            try:

                from .activity import (
                    log_activity,
                )

                log_activity(
                    sb,
                    prospect.get(
                        "id"
                    ),
                    "emailed",
                    (
                        "Sequence email sent "
                        f"(step {step_idx + 1})"
                    ),
                    body=subject,
                    metadata={
                        "to": to_email,
                        "step": step_idx,
                    },
                )

            except Exception:
                pass

            next_idx = (
                step_idx + 1
            )

            next_delay = 0

            if next_idx < len(
                steps
            ):

                next_delay = (
                    steps[
                        next_idx
                    ].get(
                        "delay_days"
                    )
                    or 1
                )

            from datetime import (
                timedelta,
            )

            next_send = (
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    days=next_delay
                )
            ).isoformat()

            (
                sb.table(
                    "sequence_enrollments"
                )
                .update(
                    {
                        "current_step": next_idx,
                        "last_sent_at": now,
                        "next_send_at": next_send,
                        "status": (
                            "completed"
                            if next_idx
                            >= len(steps)
                            else "active"
                        ),
                    }
                )
                .eq(
                    "id",
                    enroll["id"],
                )
                .execute()
            )

            if prospect.get(
                "status"
            ) in (
                "new",
                "scored",
                "enriched",
            ):

                (
                    sb.table(
                        "prospects"
                    )
                    .update(
                        {
                            "status": "contacted"
                        }
                    )
                    .eq(
                        "id",
                        prospect.get(
                            "id"
                        ),
                    )
                    .execute()
                )

            processed += 1

        except Exception as e:

            logger.warning(
                f"Sequence process error: {e}"
            )

    return {
        "status": "done",
        "processed": processed,
    }


# ============================================================
# CHECK REPLIES
# ============================================================

@celery_app.task(
    bind=True,
    name="check_replies",
)
def check_replies_task(
    self,
    since_hours: int = 48,
):
    """
    Match recent Gmail replies to prospects.

    On match:
    - log reply
    - detect basic intent
    - update prospect status
    - pause sequences
    - create activity
    - notify on positive replies
    """

    from .reply_detection import (
        GmailReplyDetector,
    )

    from .activity import (
        log_activity,
    )

    detector = GmailReplyDetector()

    if not detector.is_configured():

        return {
            "status": "skipped",
            "reason": (
                "IMAP/SMTP not configured"
            ),
        }

    sb = get_supabase()

    messages = (
        detector.fetch_recent_replies(
            since_hours=since_hours,
            max_messages=50,
        )
    )

    matched = 0
    details = []

    for msg in messages:

        from_email = (
            msg.get(
                "from_email"
            )
            or ""
        ).lower()

        if not from_email:
            continue

        try:

            res = (
                sb.table(
                    "prospects"
                )
                .select(
                    "id, email, status, "
                    "workspace_id, display_name"
                )
                .eq(
                    "email",
                    from_email,
                )
                .limit(1)
                .execute()
            )

            rows = (
                res.data
                or []
            )

            if not rows:
                continue

            prospect = rows[0]

            pid = prospect[
                "id"
            ]

            body = (
                msg.get(
                    "body"
                )
                or ""
            ).lower()

            positive = any(
                w in body
                for w in [
                    "interested",
                    "yes",
                    "sure",
                    "sounds good",
                    "pricing",
                    "how much",
                    "let's",
                    "available",
                ]
            )

            negative = any(
                w in body
                for w in [
                    "not interested",
                    "no thanks",
                    "unsubscribe",
                    "remove me",
                    "stop",
                ]
            )

            intent = (
                "positive"
                if positive
                else (
                    "negative"
                    if negative
                    else (
                        "question"
                        if "?" in body
                        else "neutral"
                    )
                )
            )

            (
                sb.table(
                    "replies"
                )
                .insert(
                    {
                        "prospect_id": pid,
                        "channel": "email",
                        "direction": "inbound",
                        "subject": msg.get(
                            "subject"
                        ),
                        "body": msg.get(
                            "body"
                        ),
                        "metadata": {
                            "detected_intent": intent,
                            "auto": True,
                            "message_id": msg.get(
                                "message_id"
                            ),
                        },
                    }
                )
                .execute()
            )

            from .suppression import (
                body_requests_unsubscribe,
                add_suppression,
            )

            if (
                body_requests_unsubscribe(
                    msg.get(
                        "body"
                    )
                    or ""
                )
                or (
                    intent == "negative"
                    and (
                        "unsub" in body
                        or body.strip() == "stop"
                    )
                )
            ):

                add_suppression(
                    sb,
                    from_email,
                    reason="unsubscribe",
                    source="auto_reply",
                )

                new_status = "lost"

            else:

                new_status = (
                    "meeting"
                    if intent == "positive"
                    else "replied"
                )

            (
                sb.table(
                    "prospects"
                )
                .update(
                    {
                        "status": new_status
                    }
                )
                .eq(
                    "id",
                    pid,
                )
                .execute()
            )

            (
                sb.table(
                    "sequence_enrollments"
                )
                .update(
                    {
                        "status": "replied"
                    }
                )
                .eq(
                    "prospect_id",
                    pid,
                )
                .eq(
                    "status",
                    "active",
                )
                .execute()
            )

            log_activity(
                sb,
                pid,
                "replied",
                (
                    "Auto-detected reply "
                    f"({intent})"
                ),
                body=(
                    msg.get(
                        "subject"
                    )
                    or ""
                )
                + "\n"
                + (
                    msg.get(
                        "body"
                    )
                    or ""
                )[:400],
                metadata={
                    "intent": intent,
                    "from": from_email,
                },
                workspace_id=prospect.get(
                    "workspace_id"
                ),
            )

            if intent == "positive":

                try:

                    from .notifications import (
                        notify,
                    )

                    notify(
                        sb,
                        "positive_reply",
                        f"Positive reply from {prospect.get('display_name') or from_email}",
                        body=(
                            msg.get(
                                "subject"
                            )
                            or ""
                        )[:120],
                        prospect_id=pid,
                        workspace_id=prospect.get(
                            "workspace_id"
                        ),
                    )

                except Exception:
                    pass

            matched += 1

            details.append(
                {
                    "prospect_id": pid,
                    "email": from_email,
                    "intent": intent,
                    "status": new_status,
                }
            )

        except Exception as e:

            logger.warning(
                f"Reply match error for "
                f"{from_email}: {e}"
            )

    return {
        "status": "done",
        "messages_scanned": len(
            messages
        ),
        "matched": matched,
        "details": details,
    }


# ============================================================
# HIGH SCORE NOTIFICATION
# ============================================================

def _maybe_notify_high_score(
    sb,
    prospect_id,
    score,
    name,
    workspace_id=None,
):
    """
    Send a notification when a prospect reaches
    a high intent score.
    """

    try:

        if (
            score is not None
            and int(score) >= 75
        ):

            from .notifications import (
                notify,
            )

            notify(
                sb,
                "high_score_lead",
                (
                    f"High-intent lead: "
                    f"{name or prospect_id}"
                ),
                body=(
                    f"Intent score {score}"
                ),
                prospect_id=prospect_id,
                workspace_id=workspace_id,
                metadata={
                    "score": score
                },
            )

    except Exception:
        pass









