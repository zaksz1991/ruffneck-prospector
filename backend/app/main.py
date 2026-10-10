"""
RuffNeck Prospector API
Free multi-platform prospecting + AI scoring + enrichment + outreach
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

import io
import os
import re

from .rate_limit import check_rate_limit
from .pipeline import (
    PIPELINE_STAGES,
    deduplicate_prospects,
    whatsapp_link,
    extract_phone,
)

from .tasks import (
    celery_app,
    scrape_prospects_task,
    score_prospects_task,
    generate_asset_task,
    send_outreach_task,
    discover_service_leads_task,
    enrich_prospects_task,
    run_daily_discovery_task,
    auto_enrich_new_prospects_task,
)

from supabase import create_client


load_dotenv()


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="RuffNeck Prospector API",
    description=(
        "Free multi-platform prospecting "
        "(LinkedIn, Jobs, Maps, social) + "
        "AI scoring + email campaigns"
    ),
    version="1.5.1",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SUPABASE
# ============================================================

def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = (
        os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
    )

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY are required"
        )

    return create_client(url, key)


# ============================================================
# WORKSPACES
# ============================================================

@app.get("/api/workspaces")
def list_workspaces(request: Request):
    """Return active workspaces accessible to the authenticated user."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please sign in again.",
        )

    try:
        sb = get_supabase()
        auth_result = sb.auth.get_user(token.strip())
        user = getattr(auth_result, "user", None)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Your session is invalid or expired. Please sign in again.",
            )

        user_id = str(user.id)
        email = (getattr(user, "email", None) or "").strip().lower()

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Your session could not be verified. Please sign in again.",
        )

    try:
        workspace_ids = set()

        # Include workspaces where this user has an active membership.
        memberships = (
            sb.table("workspace_members")
            .select("workspace_id")
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

        for row in (memberships.data or []):
            if row.get("workspace_id"):
                workspace_ids.add(str(row["workspace_id"]))

        # Support active memberships created by email invitation.
        if email:
            email_memberships = (
                sb.table("workspace_members")
                .select("workspace_id")
                .eq("email", email)
                .eq("status", "active")
                .execute()
            )

            for row in (email_memberships.data or []):
                if row.get("workspace_id"):
                    workspace_ids.add(str(row["workspace_id"]))

        # Include workspaces owned by this user, even if an older
        # database record has no corresponding membership row.
        owned = (
            sb.table("workspaces")
            .select("id")
            .eq("owner_id", user_id)
            .execute()
        )

        for row in (owned.data or []):
            if row.get("id"):
                workspace_ids.add(str(row["id"]))

        if not workspace_ids:
            return {"workspaces": []}

        result = (
            sb.table("workspaces")
            .select("id,name,slug")
            .in_("id", sorted(workspace_ids))
            .order("name")
            .execute()
        )

        return {
            "workspaces": [
                {
                    "id": str(row["id"]),
                    "name": str(row.get("name") or "Untitled workspace"),
                    "slug": row.get("slug"),
                }
                for row in (result.data or [])
            ]
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to load workspaces. Please try again later.",
        )

# ============================================================
# HELPERS
# ============================================================

def _is_fake_linkedin_email(email: str) -> bool:
    if not email:
        return False

    email = email.strip().lower()

    blocked = {
        "linkedin.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "facebook.com",
        "tiktok.com",
        "youtube.com",
        "reddit.com",
        "google.com",
        "duckduckgo.com",
    }

    if "@" not in email:
        return True

    domain = email.rsplit("@", 1)[1]

    return domain in blocked or domain.endswith(".linkedin.com")


def _safe_limit(
    value: int,
    default: int = 40,
    maximum: int = 200,
) -> int:
    try:
        value = int(value)
    except Exception:
        return default

    return max(1, min(value, maximum))


def _prospect_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return row or {}


# ============================================================
# REQUEST MODELS
# ============================================================

class ScrapeRequest(BaseModel):
    workspace_id: Optional[str] = None
    platform: str = Field(
        ...,
        examples=[
            "linkedin",
            "jobs",
            "maps",
            "instagram",
            "reddit",
            "google",
        ],
    )
    target_url: str
    keywords: List[str] = []
    max_results: int = Field(30, ge=1, le=80)


class DiscoverRequest(BaseModel):
    service: str = Field(
        ...,
        examples=[
            "website",
            "digital_marketing",
            "ai_solution",
            "graphics",
            "cv_resume",
            "excel",
        ],
    )
    extra_keywords: List[str] = []
    max_results: int = Field(20, ge=1, le=40)


class ScoreRequest(BaseModel):
    prospect_ids: List[str]
    scoring_rules: Dict[str, Any] = {}


class EnrichRequest(BaseModel):
    prospect_ids: List[str]


class GenerateAssetRequest(BaseModel):
    asset_type: str = "email"
    prospect_id: Optional[str] = None
    prompt: Optional[str] = None
    tone: Optional[str] = "professional"
    language: Optional[str] = "English"


class OutreachRequest(BaseModel):
    prospect_ids: List[str] = []
    subject: Optional[str] = None
    message: Optional[str] = None
    channel: str = "email"


class PipelineMoveRequest(BaseModel):
    prospect_id: str
    stage: str


class ReplyLogRequest(BaseModel):
    prospect_id: str
    channel: str = "email"
    direction: str = "inbound"
    body: str
    subject: Optional[str] = None


class NotificationReadRequest(BaseModel):
    notification_ids: List[str] = []
    all: bool = False


class LinkedInProfileRequest(BaseModel):
    profile_url: str


class AutoEnrichRequest(BaseModel):
    prospect_ids: Optional[List[str]] = None
    limit: int = Field(40, ge=1, le=200)


# ============================================================
# ROOT / HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "name": "RuffNeck Prospector",
        "version": "0.1.0",
        "env": os.getenv("ENV", "dev"),
        "platforms": [
            "linkedin",
            "jobs",
            "maps",
            "google",
            "instagram",
            "twitter",
            "reddit",
            "youtube",
            "tiktok",
            "facebook",
        ],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "1.3.0",
        "free_stack": True,
    }


# ============================================================
# CELERY TASK STATUS
# ============================================================

@app.get("/api/tasks/{task_id}")
def task_status(task_id: str):
    """
    Return the current Celery task status.

    The frontend polls this endpoint until the task reaches
    SUCCESS or FAILURE.
    """

    try:
        result = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": result.status,
        }

        if result.successful():
            response["result"] = result.result

        elif result.failed():
            response["error"] = str(result.result)

        elif result.status == "REVOKED":
            response["error"] = "Task was revoked"

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# SERVICES
# ============================================================

@app.get("/api/services")
def services():
    return {
        "services": [
            "website",
            "software_app",
            "digital_marketing",
            "social_media_management",
            "graphics",
            "content_creation",
            "events_creative",
            "ai_solution",
            "ai_automation",
            "ai_data_annotation",
            "ai_content_writing",
            "ai_video_creation",
            "ai_training",
            "it_support",
            "computer_setup",
            "microsoft_office",
            "network_support",
            "web_hosting",
            "ecommerce",
            "data_management",
            "excel",
            "data_entry",
            "transcription",
            "virtual_assistant",
            "business_operations",
            "customer_support",
            "logistics_warehousing",
            "cv_resume",
            "coaching_consulting",
            "education_training",
            "health_wellness",
            "herbal_islamic_medicine",
            "home_services",
            "finance_legal",
            "sales_lead_generation",
            "b2b_suppliers",
            "hiring_services",
            "local_services",
            "buying_intent",
            "used_items",
            "any_product_service",
            "custom",
        ],
        "platforms": [
            "linkedin",
            "jobs",
            "maps",
            "google",
            "instagram",
            "twitter",
            "reddit",
            "youtube",
            "tiktok",
            "facebook",
        ],
    }


# ============================================================
# PROSPECT SEARCH
# ============================================================

@app.post("/api/prospects/search")
def search_prospects(
    data: ScrapeRequest,
    request: Request,
):
    try:
        check_rate_limit(request)
    except Exception:
        pass

    task = scrape_prospects_task.delay(
        platform=data.platform.lower(),
        target_url=data.target_url,
        keywords=data.keywords,
        max_results=data.max_results,
    )

    return {
        "task_id": task.id,
        "status": "scraping_started",
        "platform": data.platform,
    }


# ============================================================
# SERVICE LEAD DISCOVERY
# ============================================================

@app.post("/api/discover/leads")
def discover_leads(data: DiscoverRequest):
    task = discover_service_leads_task.delay(
        service=data.service,
        extra_keywords=data.extra_keywords,
        max_results=data.max_results,
    )

    return {
        "task_id": task.id,
        "status": "discovery_started",
        "service": data.service,
    }


# ============================================================
# AI SCORING
# ============================================================

@app.post("/api/prospects/score")
def score_prospects(data: ScoreRequest):
    if not data.prospect_ids:
        raise HTTPException(
            status_code=400,
            detail="prospect_ids cannot be empty",
        )

    task = score_prospects_task.delay(
        prospect_ids=data.prospect_ids,
        scoring_rules=data.scoring_rules,
    )

    return {
        "task_id": task.id,
        "status": "scoring_started",
        "count": len(data.prospect_ids),
    }


# ============================================================
# SPECIFIC ENRICHMENT
# ============================================================

@app.post("/api/prospects/enrich")
def enrich_prospects(data: EnrichRequest):
    if not data.prospect_ids:
        raise HTTPException(
            status_code=400,
            detail="prospect_ids cannot be empty",
        )

    task = enrich_prospects_task.delay(
        prospect_ids=data.prospect_ids
    )

    return {
        "task_id": task.id,
        "status": "enrichment_started",
        "count": len(data.prospect_ids),
    }


# ============================================================
# AUTOMATIC / SPECIFIC ENRICHMENT
# ============================================================

@app.post("/api/prospects/auto-enrich")
def auto_enrich_prospects(
    limit: int = 40,
    prospect_ids: Optional[List[str]] = None,
):
    """
    Enrich specific prospects when prospect_ids are supplied.

    Otherwise automatically enrich prospects that still need
    enrichment.
    """

    if prospect_ids:
        task = enrich_prospects_task.delay(
            prospect_ids=prospect_ids
        )

        return {
            "task_id": task.id,
            "status": "enrichment_started",
            "mode": "specific_prospects",
            "prospect_ids": prospect_ids,
            "count": len(prospect_ids),
        }

    limit = _safe_limit(limit)

    task = auto_enrich_new_prospects_task.delay(
        limit=limit
    )

    return {
        "task_id": task.id,
        "status": "auto_enrich_started",
        "mode": "automatic",
        "limit": limit,
    }


# ============================================================
# ASSET GENERATION
# ============================================================

@app.post("/api/generate/asset")
def generate_asset(data: GenerateAssetRequest):
    task = generate_asset_task.delay(
        asset_type=data.asset_type,
        prospect_id=data.prospect_id,
        prompt=data.prompt,
        tone=data.tone,
        language=data.language,
    )

    return {
        "task_id": task.id,
        "status": "generation_started",
        "asset_type": data.asset_type,
    }


# ============================================================
# OUTREACH
# ============================================================

@app.post("/api/outreach/send")
def send_outreach(data: OutreachRequest):
    task = send_outreach_task.delay(
        prospect_ids=data.prospect_ids,
        subject=data.subject,
        message=data.message,
        channel=data.channel,
    )

    return {
        "task_id": task.id,
        "status": "outreach_started",
        "count": len(data.prospect_ids),
        "channel": data.channel,
    }


# ============================================================
# LIST PROSPECTS
# ============================================================

@app.get("/api/prospects")
def get_prospects(
    limit: int = 50,
    offset: int = 0,
    platform: Optional[str] = None,
    status: Optional[str] = None,
):
    try:
        limit = _safe_limit(limit, 50, 200)
        offset = max(0, int(offset))

        sb = get_supabase()

        query = (
            sb.table("prospects")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if platform:
            query = query.eq("platform", platform)

        if status:
            query = query.eq("status", status)

        result = query.execute()

        return {
            "data": result.data or [],
            "count": len(result.data or []),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# PIPELINE BOARD
# ============================================================

@app.get("/api/pipeline")
def get_pipeline(
    workspace_id: Optional[str] = None,
):
    try:
        sb = get_supabase()

        query = (
            sb.table("prospects")
            .select("*")
            .order("created_at", desc=True)
            .limit(1000)
        )

        if workspace_id:
            query = query.eq(
                "workspace_id",
                workspace_id,
            )

        result = query.execute()
        rows = result.data or []

        board = {
            stage: []
            for stage in PIPELINE_STAGES
        }

        for prospect in rows:
            status = str(
                prospect.get("status") or "new"
            ).lower()

            if status in (
                "new",
                "enriched",
                "scored",
            ):
                metadata = prospect.get("metadata") or {}
                platform = str(
                    prospect.get("platform") or ""
                ).lower()

                tags = {
                    str(tag).strip().lower()
                    for tag in (prospect.get("tags") or [])
                }

                query_service = str(
                    metadata.get("query_service") or ""
                ).lower()

                page_type = str(
                    metadata.get("page_type") or ""
                ).lower()

                try:
                    score = float(
                        prospect.get("intent_score") or 0
                    )
                except (TypeError, ValueError):
                    score = 0.0

                is_competitor = "competitor" in tags
                is_job = platform == "jobs"

                is_buying_intent = (
                    query_service == "buying_intent"
                    or "buying_intent" in tags
                )

                is_sales_qualified = (
                    (
                        is_buying_intent
                        and (
                            page_type == "opportunity"
                            or score > 0
                        )
                    )
                    or score >= 70
                )

                is_qualifying = (
                    not is_competitor
                    and not is_job
                    and is_sales_qualified
                )

                if is_qualifying:
                    board["new"].append(prospect)

            elif status in PIPELINE_STAGES:
                board[status].append(prospect)

        return {
            "board": board,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================

@app.post("/api/replies/check")
def check_replies_endpoint(since_hours: int = 48):
    """Queue the Gmail reply-check worker."""
    from .tasks import check_replies_task

    hours = max(1, min(int(since_hours), 168))
    task = check_replies_task.delay(since_hours=hours)

    return {
        "status": "started",
        "task_id": task.id,
        "since_hours": hours,
    }



# ============================================================
# SEQUENCES
# ============================================================

class SequenceEnrollRequest(BaseModel):
    sequence_id: str
    prospect_ids: List[str]


@app.get("/api/sequences")
def list_sequences():
    sb = get_supabase()

    result = (
        sb.table("sequences")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "sequences": result.data or []
    }


@app.post("/api/sequences/seed-default")
def seed_default_sequence():
    sb = get_supabase()

    existing = (
        sb.table("sequences")
        .select("*")
        .eq("name", "Default 3-Step Outreach")
        .limit(1)
        .execute()
    )

    if existing.data:
        return {
            "status": "exists",
            "sequence": existing.data[0],
        }

    sequence_result = (
        sb.table("sequences")
        .insert({
            "name": "Default 3-Step Outreach",
            "description": "Three-step email outreach sequence.",
            "is_active": True,
        })
        .execute()
    )

    sequence = (sequence_result.data or [None])[0]

    if not sequence:
        raise HTTPException(
            status_code=500,
            detail="Failed to create default sequence",
        )

    steps = [
        {
            "sequence_id": sequence["id"],
            "step_order": 0,
            "channel": "email",
            "delay_days": 0,
            "subject_template": "Quick idea for your {{service}} needs",
            "body_template": (
                "Hi {{name}},\n\n"
                "I noticed your recent activity and wanted to share a quick idea "
                "related to {{service}}.\n\n"
                "Would you like me to send over a short free resource?\n\n"
                "Best,\n"
                "RuffNeck Entertainment"
            ),
        },
        {
            "sequence_id": sequence["id"],
            "step_order": 1,
            "channel": "email",
            "delay_days": 3,
            "subject_template": "Following up - {{service}}",
            "body_template": (
                "Hi {{name}},\n\n"
                "Just following up on my previous message about {{service}}.\n\n"
                "If the timing is right, I can send the resource and "
                "discuss the next step.\n\n"
                "Best,\n"
                "RuffNeck Entertainment"
            ),
        },
        {
            "sequence_id": sequence["id"],
            "step_order": 2,
            "channel": "email",
            "delay_days": 7,
            "subject_template": "Last note - {{service}}",
            "body_template": (
                "Hi {{name}},\n\n"
                "I'll close the loop here. If you need help with {{service}}, "
                "I'm happy to share the resource or answer any questions.\n\n"
                "Best,\n"
                "RuffNeck Entertainment"
            ),
        },
    ]

    steps_result = (
        sb.table("sequence_steps")
        .insert(steps)
        .execute()
    )

    return {
        "status": "created",
        "sequence": sequence,
        "steps": steps_result.data or [],
    }


@app.get("/api/sequences/{sequence_id}")
def get_sequence(sequence_id: str):
    sb = get_supabase()

    sequence_result = (
        sb.table("sequences")
        .select("*")
        .eq("id", sequence_id)
        .limit(1)
        .execute()
    )

    sequence_rows = sequence_result.data or []

    if not sequence_rows:
        raise HTTPException(
            status_code=404,
            detail="Sequence not found",
        )

    steps_result = (
        sb.table("sequence_steps")
        .select("*")
        .eq("sequence_id", sequence_id)
        .order("step_order")
        .execute()
    )

    return {
        "sequence": sequence_rows[0],
        "steps": steps_result.data or [],
    }


@app.get("/api/sequences/{sequence_id}/enrollments")
def get_sequence_enrollments(sequence_id: str):
    sb = get_supabase()

    sequence_result = (
        sb.table("sequences")
        .select("id")
        .eq("id", sequence_id)
        .limit(1)
        .execute()
    )

    if not (sequence_result.data or []):
        raise HTTPException(
            status_code=404,
            detail="Sequence not found",
        )

    result = (
        sb.table("sequence_enrollments")
        .select(
            "*, prospects("
            "id, email, display_name, username, status"
            ")"
        )
        .eq("sequence_id", sequence_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "enrollments": result.data or []
    }


@app.post("/api/sequences/enroll")
def enroll_in_sequence(data: SequenceEnrollRequest):
    sb = get_supabase()

    sequence_result = (
        sb.table("sequences")
        .select("id, name, is_active")
        .eq("id", data.sequence_id)
        .limit(1)
        .execute()
    )

    sequence_rows = sequence_result.data or []

    if not sequence_rows:
        raise HTTPException(
            status_code=404,
            detail="Sequence not found",
        )

    from datetime import datetime, timezone

    next_send_at = datetime.now(timezone.utc).isoformat()

    enrolled = []
    skipped = []

    for prospect_id in data.prospect_ids:

        prospect_result = (
            sb.table("prospects")
            .select("id")
            .eq("id", prospect_id)
            .limit(1)
            .execute()
        )

        if not (prospect_result.data or []):
            skipped.append({
                "prospect_id": prospect_id,
                "reason": "prospect_not_found",
            })
            continue

        existing = (
            sb.table("sequence_enrollments")
            .select("id, status")
            .eq("sequence_id", data.sequence_id)
            .eq("prospect_id", prospect_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            skipped.append({
                "prospect_id": prospect_id,
                "reason": "already_enrolled",
                "enrollment": existing.data[0],
            })
            continue

        enrollment_result = (
            sb.table("sequence_enrollments")
            .insert({
                "sequence_id": data.sequence_id,
                "prospect_id": prospect_id,
                "current_step": 0,
                "status": "active",
                "next_send_at": next_send_at,
            })
            .execute()
        )

        row = (enrollment_result.data or [None])[0]

        if row:
            enrolled.append(row)

    return {
        "status": "enrolled",
        "sequence_id": data.sequence_id,
        "enrolled": enrolled,
        "skipped": skipped,
        "count": len(enrolled),
    }


@app.post("/api/sequences/process")
def process_sequences():
    from .tasks import process_due_sequences_task

    task = process_due_sequences_task.delay()

    return {
        "status": "started",
        "task_id": task.id,
    }


# EXPORT
# ============================================================

@app.get("/api/prospects/export")
def export_prospects(
    limit: int = 200,
):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment

        limit = _safe_limit(limit, 200, 1000)

        sb = get_supabase()

        result = (
            sb.table("prospects")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        rows = result.data or []

        fields = [
            "id",
            "platform",
            "username",
            "display_name",
            "profile_url",
            "post_url",
            "email",
            "email_confidence",
            "location",
            "follower_count",
            "following_count",
            "post_count",
            "engagement_score",
            "intent_score",
            "score_reason",
            "status",
            "created_at",
        ]

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Prospects"

        # Header
        worksheet.append(fields)

        # Header formatting
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="D9EAF7",
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

        # Data
        for row in rows:
            worksheet.append(
                [row.get(field) for field in fields]
            )

        # Freeze the header
        worksheet.freeze_panes = "A2"

        # Enable Excel filtering
        if worksheet.max_row >= 1:
            worksheet.auto_filter.ref = worksheet.dimensions

        # Adjust column widths
        for column_cells in worksheet.columns:
            column_letter = column_cells[0].column_letter
            max_length = 0

            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(max_length, len(value))

            worksheet.column_dimensions[column_letter].width = min(
                max_length + 2,
                50,
            )

        # Make URLs clickable
        url_fields = {
            "profile_url",
            "post_url",
        }

        field_indexes = {
            field: index + 1
            for index, field in enumerate(fields)
        }

        for field in url_fields:
            column_index = field_indexes[field]

            for row_number in range(2, worksheet.max_row + 1):
                cell = worksheet.cell(
                    row=row_number,
                    column=column_index,
                )

                if cell.value:
                    cell.hyperlink = str(cell.value)
                    cell.style = "Hyperlink"

        # Write XLSX into memory
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": (
                    'attachment; filename="ruffneck_prospects.xlsx"'
                )
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}",
        )


# ============================================================
# SINGLE PROSPECT
# ============================================================

@app.get("/api/prospects/{prospect_id}")
def get_prospect(prospect_id: str):
    try:
        sb = get_supabase()

        result = (
            sb.table("prospects")
            .select("*")
            .eq("id", prospect_id)
            .single()
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Prospect not found",
            )

        return result.data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.get("/api/notifications")
def get_notifications(limit: int = 20):
    try:
        sb = get_supabase()

        from .notifications import list_notifications

        notifications = list_notifications(
            sb,
            limit=max(1, min(int(limit), 100)),
        )

        unread = sum(
            1
            for notification in notifications
            if not notification.get("read", False)
        )

        return {
            "notifications": notifications,
            "unread": unread,
            "count": len(notifications),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.post("/api/notifications/read")
def mark_notifications_read(data: NotificationReadRequest):
    try:
        sb = get_supabase()

        from .notifications import mark_read

        count = mark_read(
            sb,
            notification_ids=data.notification_ids,
            all=data.all,
        )

        return {
            "status": "updated",
            "count": count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# PROSPECT ACTIVITIES
# ============================================================

@app.get("/api/prospects/{prospect_id}/activities")
def get_prospect_activities(prospect_id: str, limit: int = 50):
    try:
        sb = get_supabase()

        prospect_result = (
            sb.table("prospects")
            .select("id")
            .eq("id", prospect_id)
            .limit(1)
            .execute()
        )

        if not (prospect_result.data or []):
            raise HTTPException(
                status_code=404,
                detail="Prospect not found",
            )

        from .activity import list_activities

        activities = list_activities(
            sb,
            prospect_id,
            limit=max(1, min(int(limit), 200)),
        )

        return {
            "activities": activities,
            "count": len(activities),
            "prospect_id": prospect_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# LINKEDIN PROFILE
# ============================================================

@app.post("/api/linkedin/profile")
def linkedin_profile(data: LinkedInProfileRequest):
    task = scrape_prospects_task.delay(
        platform="linkedin",
        target_url=data.profile_url,
        keywords=[],
        max_results=1,
    )

    return {
        "task_id": task.id,
        "status": "scraping_started",
        "platform": "linkedin",
        "profile_url": data.profile_url,
    }


# ============================================================
# LOG REPLY
# ============================================================

@app.post("/api/replies")
def log_reply(data: ReplyLogRequest):
    try:
        sb = get_supabase()

        prospect_result = (
            sb.table("prospects")
            .select("id, workspace_id, display_name, email")
            .eq("id", data.prospect_id)
            .limit(1)
            .execute()
        )

        prospect_rows = prospect_result.data or []

        if not prospect_rows:
            raise HTTPException(
                status_code=404,
                detail="Prospect not found",
            )

        prospect = prospect_rows[0]

        reply_result = (
            sb.table("replies")
            .insert(
                {
                    "prospect_id": data.prospect_id,
                    "channel": data.channel,
                    "direction": data.direction,
                    "subject": data.subject,
                    "body": data.body,
                    "metadata": {
                        "manual": True,
                    },
                }
            )
            .execute()
        )

        (
            sb.table("prospects")
            .update({"status": "replied"})
            .eq("id", data.prospect_id)
            .execute()
        )

        try:
            from .activity import log_activity

            log_activity(
                sb,
                data.prospect_id,
                "replied",
                "Manual reply logged",
                body=data.body[:400],
                metadata={
                    "channel": data.channel,
                    "manual": True,
                },
                workspace_id=prospect.get("workspace_id"),
            )
        except Exception:
            pass

        return {
            "status": "logged",
            "prospect_id": data.prospect_id,
            "stage": "replied",
            "reply": (reply_result.data or [None])[0],
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# PIPELINE
# ============================================================

@app.post("/api/pipeline/move")
def move_pipeline(data: PipelineMoveRequest):
    if data.stage not in PIPELINE_STAGES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid pipeline stage",
                "allowed_stages": PIPELINE_STAGES,
            },
        )

    try:
        sb = get_supabase()

        result = (
            sb.table("prospects")
            .update({"status": data.stage})
            .eq("id", data.prospect_id)
            .execute()
        )

        return {
            "status": "moved",
            "prospect_id": data.prospect_id,
            "stage": data.stage,
            "data": result.data or [],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# DAILY DISCOVERY
# ============================================================

class DailyDiscoveryRequest(BaseModel):
    location: str = ""
    services: Optional[List[str]] = None
    workspace_id: Optional[str] = None


@app.post("/api/discovery/daily")
def daily_discovery(
    data: Optional[DailyDiscoveryRequest] = None,
):
    data = data or DailyDiscoveryRequest()

    task = run_daily_discovery_task.delay(
        location=data.location,
        services=data.services,
        workspace_id=data.workspace_id,
    )

    return {
        "task_id": task.id,
        "status": "daily_discovery_started",
        "location": data.location,
        "services": data.services,
        "workspace_id": data.workspace_id,
    }


# ============================================================
# DEDUPLICATE
# ============================================================

@app.post("/api/prospects/deduplicate")
def deduplicate():
    try:
        sb = get_supabase()

        result = (
            sb.table("prospects")
            .select("*")
            .limit(1000)
            .execute()
        )

        rows = result.data or []

        cleaned = deduplicate_prospects(rows)

        return {
            "status": "completed",
            "before": len(rows),
            "after": len(cleaned),
            "removed": len(rows) - len(cleaned),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )