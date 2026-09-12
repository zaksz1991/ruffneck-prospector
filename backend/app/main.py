"""
RuffNeck Prospector API v1.4
100% Free • LinkedIn + Jobs + Maps + Email enrichment + multi-platform
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import re
from dotenv import load_dotenv
from fastapi import Request
from .rate_limit import check_rate_limit
from .pipeline import PIPELINE_STAGES, deduplicate_prospects, whatsapp_link, extract_phone

load_dotenv()

from .tasks import (
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

app = FastAPI(
    title="RuffNeck Prospector API",
    description="Free multi-platform prospecting (LinkedIn, Jobs, Maps, social) + AI scoring + email campaigns",
    version="1.5.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.method != "OPTIONS":
        try:
            check_rate_limit(request)
        except HTTPException as e:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    return await call_next(request)


def get_sb():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


class ScrapeRequest(BaseModel):
    workspace_id: Optional[str] = None
    platform: str = Field(..., examples=["linkedin", "jobs", "maps", "instagram", "reddit", "google"])
    target_url: str
    keywords: List[str] = []
    max_results: int = Field(30, ge=1, le=80)


class DiscoverRequest(BaseModel):
    service: str = Field(..., examples=["website", "digital_marketing", "ai_solution", "graphics", "cv_resume", "excel"])
    extra_keywords: List[str] = []
    max_results: int = Field(20, ge=1, le=40)


class ScoreRequest(BaseModel):
    prospect_ids: List[str]
    scoring_rules: Optional[Dict[str, Any]] = None


class EnrichRequest(BaseModel):
    prospect_ids: List[str]


class OutreachRequest(BaseModel):
    prospect_ids: List[str]
    channel: str = "email"
    topic: str = "digital services"
    service: str = "website"
    send_real: bool = False


class AssetRequest(BaseModel):
    prospect_id: str
    asset_type: str = Field(..., examples=["ebook", "slides"])
    topic: str
    branding: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.3.0", "free_stack": True}


@app.post("/api/prospects/search")
def search_prospects(data: ScrapeRequest):
    task = scrape_prospects_task.delay(
        platform=data.platform.lower(),
        target_url=data.target_url,
        keywords=data.keywords,
        max_results=data.max_results,
    )
    return {"task_id": task.id, "status": "scraping_started", "platform": data.platform}


@app.post("/api/discover/leads")
def discover_leads(data: DiscoverRequest):
    task = discover_service_leads_task.delay(
        service=data.service,
        extra_keywords=data.extra_keywords,
        max_results=data.max_results,
    )
    return {"task_id": task.id, "status": "discovery_started", "service": data.service}


@app.post("/api/prospects/score")
def score_prospects(data: ScoreRequest):
    task = score_prospects_task.delay(data.prospect_ids, data.scoring_rules)
    return {"task_id": task.id, "status": "scoring_started"}


@app.post("/api/prospects/enrich")
def enrich_prospects(data: EnrichRequest):
    """Free email enrichment (regex + pattern guessing)."""
    task = enrich_prospects_task.delay(data.prospect_ids)
    return {"task_id": task.id, "status": "enrichment_started"}


@app.post("/api/outreach/send")
def send_outreach(data: OutreachRequest):
    task = send_outreach_task.delay(
        prospect_ids=data.prospect_ids,
        channel=data.channel,
        topic=data.topic,
        service=data.service,
        send_real=data.send_real,
    )
    return {"task_id": task.id, "status": "outreach_queued"}


@app.post("/api/generate/asset")
def generate_asset(data: AssetRequest):
    task = generate_asset_task.delay(
        prospect_id=data.prospect_id,
        asset_type=data.asset_type,
        topic=data.topic,
        branding=data.branding or {},
    )
    return {"task_id": task.id, "status": "generation_started"}


@app.get("/api/prospects")
def list_prospects(
    platform: Optional[str] = None,
    min_score: Optional[int] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    sb = get_sb()
    q = sb.table("prospects").select("*").order("created_at", desc=True).range(offset, offset + limit - 1)
    if platform:
        q = q.eq("platform", platform)
    if min_score is not None:
        q = q.gte("intent_score", min_score)
    if status:
        q = q.eq("status", status)
    if tag:
        q = q.contains("tags", [tag])
    if workspace_id:
        q = q.eq("workspace_id", workspace_id)
    res = q.execute()
    return {"data": res.data, "count": len(res.data)}




@app.post("/api/prospects/auto-enrich")
def auto_enrich_prospects(limit: int = 40):
    """
    Automatically enrich prospects that still lack email / enrichment.
    Runs as a background Celery task.
    """
    task = auto_enrich_new_prospects_task.delay(limit=limit)
    return {"task_id": task.id, "status": "auto_enrich_started", "limit": limit}


@app.get("/api/prospects/export")
def export_prospects_excel(
    platform: Optional[str] = None,
    min_score: Optional[int] = 0,
    workspace_id: Optional[str] = None,
    limit: int = 500,
):
    """Export prospects to Excel (.xlsx). Filters match the list endpoint."""
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from .tasks import get_supabase

    sb = get_supabase()
    q = sb.table("prospects").select("*").order("created_at", desc=True).limit(limit)
    if platform:
        q = q.eq("platform", platform)
    if min_score:
        q = q.gte("intent_score", min_score)
    if workspace_id:
        q = q.eq("workspace_id", workspace_id)
    res = q.execute()
    rows = res.data or []

    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"

    headers = [
        "id", "platform", "username", "display_name", "comment_text", "profile_url",
        "email", "email_confidence", "company_domain", "location", "intent_score",
        "recommended_service", "enrichment_status", "email_source", "status",
        "follower_count", "tags", "created_at",
    ]

    header_fill = PatternFill("solid", fgColor="1E3A5F")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h.replace("_", " ").title())
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin

    for r_idx, row in enumerate(rows, 2):
        meta = row.get("metadata") or {}
        values = [
            row.get("id"),
            row.get("platform"),
            row.get("username"),
            row.get("display_name"),
            row.get("comment_text"),
            row.get("profile_url"),
            row.get("email"),
            row.get("email_confidence"),
            meta.get("company_domain"),
            meta.get("location") or row.get("bio_text"),
            row.get("intent_score"),
            meta.get("recommended_service") or (meta.get("score_breakdown") or {}).get("recommended_service"),
            meta.get("enrichment_status"),
            meta.get("email_source"),
            row.get("status"),
            row.get("follower_count"),
            ", ".join(row.get("tags") or []) if isinstance(row.get("tags"), list) else row.get("tags"),
            row.get("created_at"),
        ]
        for c_idx, val in enumerate(values, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val if val is not None else "")
            cell.border = thin

    # Reasonable column widths
    for col in ws.columns:
        max_len = 12
        col_letter = col[0].column_letter
        for cell in col:
            try:
                max_len = max(max_len, min(len(str(cell.value or "")), 45))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = max_len + 2

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = "RuffNeck_Leads_Export.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/prospects/{prospect_id}")
def get_prospect(prospect_id: str):
    sb = get_sb()
    res = sb.table("prospects").select("*").eq("id", prospect_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Prospect not found")
    return res.data


@app.get("/api/services")
def list_services():
    return {
        "services": [
            {"key": "digital_marketing", "label": "Digital Marketing / SEO / Social"},
            {"key": "website", "label": "Website / Web Development"},
            {"key": "ai_solution", "label": "AI Solutions / Automation / Chatbots"},
            {"key": "graphics", "label": "Graphics Design / Logo / Branding"},
            {"key": "cv_resume", "label": "CV / Resume / Cover Letter Writing"},
            {"key": "excel", "label": "Excel / Data Cleaning / Spreadsheets"},
        ]
    }



class LinkedInProfileRequest(BaseModel):
    profile_url: str
    enrich: bool = True


@app.post("/api/linkedin/profile")
def scrape_linkedin_profile(data: LinkedInProfileRequest):
    """
    Scrape a single public LinkedIn profile (free, Playwright).
    Optionally run waterfall enrichment afterwards.
    """
    from .scrapers.linkedin import LinkedInScraper
    from .enrichment import enrich_prospect
    from .tasks import get_supabase

    scraper = LinkedInScraper()
    profile = scraper.scrape_profile(data.profile_url)
    if not profile:
        raise HTTPException(404, "Could not scrape profile (private, blocked, or Playwright issue)")

    # Convert and optionally save
    result = scraper._profile_to_comment_result(profile, data.profile_url)
    row = {
        "platform": "linkedin",
        "username": result.username,
        "display_name": result.display_name,
        "profile_url": result.profile_url,
        "comment_text": result.comment_text,
        "bio_text": result.bio_text,
        "follower_count": result.follower_count or 0,
        "data_source": "linkedin_profile",
        "metadata": result.engagement or {},
    }

    if data.enrich:
        enrich = enrich_prospect(row)
        if enrich.get("email"):
            row["email"] = enrich["email"]
            row["email_confidence"] = enrich.get("email_confidence", 0)
        if enrich.get("company_domain"):
            row["metadata"]["company_domain"] = enrich["company_domain"]
        row["metadata"]["enrichment_status"] = enrich.get("enrichment_status")
        row["metadata"]["email_source"] = enrich.get("email_source")

    # Save to DB
    try:
        sb = get_supabase()
        inserted = sb.table("prospects").insert(row).execute()
        row["id"] = inserted.data[0]["id"] if inserted.data else None
    except Exception as e:
        row["save_error"] = str(e)

    return {"status": "ok", "profile": profile, "prospect": row}


# ---------- Pipeline & Replies ----------
class StageUpdate(BaseModel):
    prospect_ids: List[str]
    stage: str

class ReplyCreate(BaseModel):
    prospect_id: str
    channel: str = "email"
    direction: str = "inbound"
    subject: Optional[str] = None
    body: Optional[str] = None

@app.post("/api/pipeline/move")
def move_pipeline_stage(data: StageUpdate):
    if data.stage not in PIPELINE_STAGES:
        raise HTTPException(400, f"Invalid stage. Use one of: {PIPELINE_STAGES}")
    from .tasks import get_supabase
    sb = get_supabase()
    for pid in data.prospect_ids:
        sb.table("prospects").update({"status": data.stage}).eq("id", pid).execute()
    return {"status": "updated", "stage": data.stage, "count": len(data.prospect_ids)}

@app.post("/api/replies")
def log_reply(data: ReplyCreate):
    """
    Log a reply. Inbound replies automatically:
    - Move prospect to "replied"
    - Pause any active sequences
    - Store simple intent detection (positive / neutral / negative / question)
    """
    from .tasks import get_supabase
    sb = get_supabase()

    body = (data.body or "").lower()
    # Simple reply sentiment / intent detection
    positive = any(w in body for w in ["interested", "yes", "sure", "let's", "sounds good", "available", "pricing", "how much", "send me"])
    negative = any(w in body for w in ["not interested", "no thanks", "unsubscribe", "remove me", "stop"])
    question = "?" in body

    intent = "neutral"
    if positive:
        intent = "positive"
    elif negative:
        intent = "negative"
    elif question:
        intent = "question"

    row = {
        "prospect_id": data.prospect_id,
        "channel": data.channel,
        "direction": data.direction,
        "subject": data.subject,
        "body": data.body,
        "metadata": {"detected_intent": intent},
    }
    sb.table("replies").insert(row).execute()

    if data.direction == "inbound":
        from .suppression import body_requests_unsubscribe, add_suppression
        from .tasks import get_supabase as _gs
        # Load email for suppression
        new_status = "replied"
        if intent == "positive":
            new_status = "meeting"
        if body_requests_unsubscribe(data.body or ""):
            new_status = "lost"
            try:
                prow = sb.table("prospects").select("email").eq("id", data.prospect_id).single().execute()
                if prow.data and prow.data.get("email"):
                    add_suppression(sb, prow.data["email"], reason="unsubscribe", source="manual_reply")
            except Exception:
                pass
        sb.table("prospects").update({"status": new_status}).eq("id", data.prospect_id).execute()
        sb.table("sequence_enrollments").update({"status": "replied"}).eq("prospect_id", data.prospect_id).eq("status", "active").execute()

    try:
        from .activity import log_activity
        log_activity(sb, data.prospect_id, "replied", f"Reply logged ({intent})", body=data.body or "", metadata={"intent": intent, "channel": data.channel})
    except Exception:
        pass
    return {"status": "reply_logged", "detected_intent": intent}

@app.get("/api/pipeline")
def get_pipeline(workspace_id: Optional[str] = None):
    """Return prospects grouped by pipeline stage for Kanban."""
    from .tasks import get_supabase
    sb = get_supabase()
    q = sb.table("prospects").select(
        "id, platform, username, display_name, email, intent_score, status, metadata, profile_url, comment_text, workspace_id, assigned_to"
    ).order("intent_score", desc=True).limit(300)
    if workspace_id:
        q = q.eq("workspace_id", workspace_id)
    res = q.execute()
    board = {stage: [] for stage in PIPELINE_STAGES}
    for p in (res.data or []):
        stage = p.get("status") if p.get("status") in PIPELINE_STAGES else "new"
        board[stage].append(p)
    return {"stages": PIPELINE_STAGES, "board": board, "workspace_id": workspace_id}

# ---------- Sequences ----------
class EnrollRequest(BaseModel):
    sequence_id: str
    prospect_ids: List[str]

@app.post("/api/sequences/enroll")
def enroll_in_sequence(data: EnrollRequest):
    from .tasks import get_supabase
    from datetime import datetime, timedelta
    sb = get_supabase()
    enrolled = 0
    for pid in data.prospect_ids:
        try:
            sb.table("sequence_enrollments").upsert({
                "sequence_id": data.sequence_id,
                "prospect_id": pid,
                "current_step": 0,
                "status": "active",
                "next_send_at": datetime.utcnow().isoformat(),
            }).execute()
            enrolled += 1
        except Exception:
            pass
    return {"status": "enrolled", "count": enrolled}

@app.post("/api/sequences/process")
def process_sequences():
    """Process due sequence steps (call via cron or manually). Auto-pauses on reply."""
    from .tasks import process_due_sequences_task
    task = process_due_sequences_task.delay()
    return {"task_id": task.id, "status": "processing_started"}

# ---------- Deduplication ----------
@app.post("/api/prospects/deduplicate")
def run_deduplication():
    from .tasks import get_supabase
    sb = get_supabase()
    res = sb.table("prospects").select("*").limit(1000).execute()
    original = res.data or []
    unique = deduplicate_prospects(original)
    # For safety we only report; actual deletion can be manual
    return {
        "original_count": len(original),
        "unique_count": len(unique),
        "duplicates_found": len(original) - len(unique),
        "message": "Review complete. Use with care before deleting."
    }

# ---------- Analytics ----------
@app.get("/api/analytics")
def get_analytics(workspace_id: Optional[str] = None):
    from .tasks import get_supabase
    sb = get_supabase()
    q = sb.table("prospects").select("id, platform, status, intent_score, email, metadata, created_at, workspace_id").limit(2000)
    if workspace_id:
        q = q.eq("workspace_id", workspace_id)
    res = q.execute()
    rows = res.data or []
    total = len(rows)
    with_email = sum(1 for r in rows if r.get("email"))
    high_intent = sum(1 for r in rows if (r.get("intent_score") or 0) >= 70)
    by_platform = {}
    by_status = {}
    for r in rows:
        plat = r.get("platform") or "unknown"
        by_platform[plat] = by_platform.get(plat, 0) + 1
        st = r.get("status") or "new"
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "total_prospects": total,
        "with_email": with_email,
        "email_rate": round(with_email / total * 100, 1) if total else 0,
        "high_intent": high_intent,
        "by_platform": by_platform,
        "by_status": by_status,
        "replied": by_status.get("replied", 0),
        "won": by_status.get("won", 0),
    }

# ---------- WhatsApp helper ----------
@app.get("/api/prospects/{prospect_id}/whatsapp")
def get_whatsapp_link(prospect_id: str, message: str = "Hi, I came across your business and would love to help with your online presence."):
    from .tasks import get_supabase
    sb = get_supabase()
    res = sb.table("prospects").select("*").eq("id", prospect_id).single().execute()
    p = res.data
    if not p:
        raise HTTPException(404, "Prospect not found")
    # Try phone from metadata or text
    phone = (p.get("metadata") or {}).get("phone") or extract_phone(p.get("comment_text") or "") or extract_phone(p.get("bio_text") or "")
    link = whatsapp_link(phone, message) if phone else None
    return {"phone": phone, "whatsapp_link": link, "has_phone": bool(phone)}



@app.get("/api/sequences")
def list_sequences():
    from .tasks import get_supabase
    sb = get_supabase()
    res = sb.table("sequences").select("*, sequence_steps(count)").order("created_at", desc=True).execute()
    return {"sequences": res.data or []}

@app.get("/api/sequences/{sequence_id}")
def get_sequence(sequence_id: str):
    from .tasks import get_supabase
    sb = get_supabase()
    seq = sb.table("sequences").select("*").eq("id", sequence_id).single().execute()
    steps = sb.table("sequence_steps").select("*").eq("sequence_id", sequence_id).order("step_order").execute()
    return {"sequence": seq.data, "steps": steps.data or []}

@app.get("/api/sequences/{sequence_id}/enrollments")
def list_enrollments(sequence_id: str):
    from .tasks import get_supabase
    sb = get_supabase()
    res = (
        sb.table("sequence_enrollments")
        .select("*, prospects(id, username, display_name, email, status, intent_score)")
        .eq("sequence_id", sequence_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return {"enrollments": res.data or []}


@app.post("/api/email/verify")
def verify_email_endpoint(email: str):
    from .email_verify import verify_email
    return verify_email(email)

@app.post("/api/prospects/verify-emails")
def verify_prospect_emails(prospect_ids: list[str] = None):
    """Batch verify emails on prospects and store results in metadata."""
    from .tasks import get_supabase
    from .email_verify import verify_email
    from pydantic import BaseModel
    # Accept body
    return {"message": "POST JSON {\"prospect_ids\": [...]}"}

class VerifyBatch(BaseModel):
    prospect_ids: list[str]

@app.post("/api/prospects/verify-batch")
def verify_batch(data: VerifyBatch):
    from .tasks import get_supabase
    from .email_verify import verify_email
    sb = get_supabase()
    results = []
    for pid in data.prospect_ids[:50]:
        try:
            row = sb.table("prospects").select("id, email, metadata").eq("id", pid).single().execute()
            p = row.data
            if not p or not p.get("email"):
                results.append({"id": pid, "status": "no_email"})
                continue
            v = verify_email(p["email"])
            meta = {**(p.get("metadata") or {}), "email_valid": v.get("valid"), "email_status": v.get("status"), "email_verify_confidence": v.get("confidence")}
            update = {"metadata": meta}
            if not v.get("valid"):
                update["email_confidence"] = min(p.get("email_confidence") or 0, 20)
            sb.table("prospects").update(update).eq("id", pid).execute()
            results.append({"id": pid, "email": p["email"], **v})
        except Exception as e:
            results.append({"id": pid, "error": str(e)})
    return {"verified": results}


# ---------- Auth (Supabase) ----------
class AuthSignup(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class AuthLogin(BaseModel):
    email: str
    password: str

@app.post("/api/auth/signup")
def auth_signup(data: AuthSignup):
    """Create user via Supabase Auth."""
    from .tasks import get_supabase
    sb = get_supabase()
    try:
        res = sb.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {"data": {"full_name": data.full_name or ""}},
        })
        user = res.user
        session = res.session
        return {
            "user": {"id": user.id if user else None, "email": data.email},
            "access_token": session.access_token if session else None,
            "refresh_token": session.refresh_token if session else None,
        }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/auth/login")
def auth_login(data: AuthLogin):
    """Login via Supabase Auth."""
    from .tasks import get_supabase
    sb = get_supabase()
    try:
        res = sb.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password,
        })
        user = res.user
        session = res.session
        return {
            "user": {"id": user.id if user else None, "email": data.email},
            "access_token": session.access_token if session else None,
            "refresh_token": session.refresh_token if session else None,
        }
    except Exception as e:
        raise HTTPException(401, "Invalid email or password")

@app.get("/api/auth/me")
def auth_me(authorization: Optional[str] = None):
    """Return current user from Bearer token (best-effort)."""
    from .tasks import get_supabase
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.replace("Bearer ", "").strip()
    sb = get_supabase()
    try:
        user = sb.auth.get_user(token)
        return {"user": {"id": user.user.id, "email": user.user.email}}
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


class ProductDemandRequest(BaseModel):
    product_or_service: str  # e.g. "solar panels", "wedding photographer", "accounting software"
    location: str = ""
    max_results: int = 25
    workspace_id: Optional[str] = None


@app.post("/api/discover/product-demand")
def discover_product_demand_api(data: ProductDemandRequest):
    """
    Find people online who need ANY product or service.
    Uses free search intent queries (looking for / need / recommend / where can I buy).
    """
    from .tasks import discover_service_leads_task
    # Reuse service discovery with custom mode
    task = discover_service_leads_task.delay(
        service="custom",
        extra_keywords=[data.product_or_service] + ([data.location] if data.location else []),
        max_results=data.max_results,
    )
    return {
        "task_id": task.id,
        "status": "product_demand_search_started",
        "product_or_service": data.product_or_service,
        "location": data.location,
    }


class CompetitorDiscoverRequest(BaseModel):
    seed: str  # company name or website domain
    location: str = ""
    category: str = ""  # e.g. "digital agency", "plumber"
    max_results: int = 25
    workspace_id: Optional[str] = None


@app.post("/api/discover/competitors")
def discover_competitors_api(data: CompetitorDiscoverRequest):
    """
    Free competitor / lookalike discovery from a seed company or domain.
    Uses related:, alternatives to, competitors of, and optional Maps category.
    """
    from .tasks import scrape_prospects_task
    keywords = []
    if data.location:
        keywords.append(data.location)
    if data.category:
        keywords.append(data.category)
    task = scrape_prospects_task.delay(
        platform="competitors",
        target_url=data.seed,
        keywords=keywords,
        max_results=data.max_results,
        workspace_id=getattr(data, "workspace_id", None),
    )
    return {
        "task_id": task.id,
        "status": "competitor_discovery_started",
        "seed": data.seed,
        "location": data.location,
        "category": data.category,
    }


# ---------- Activity Timeline & Auto Reply Detection ----------
@app.get("/api/prospects/{prospect_id}/activities")
def get_prospect_activities(prospect_id: str, limit: int = 50):
    from .tasks import get_supabase
    from .activity import list_activities
    sb = get_supabase()
    return {"activities": list_activities(sb, prospect_id, limit=limit)}


@app.post("/api/replies/check")
def check_replies_now(since_hours: int = 48):
    """
    Poll Gmail IMAP for recent replies and match to prospects by email.
    Auto-logs reply, moves stage, pauses sequences, writes activity.
    Requires SMTP_USER + SMTP_PASS (Gmail App Password) or IMAP_*.
    """
    from .tasks import check_replies_task
    task = check_replies_task.delay(since_hours=since_hours)
    return {"task_id": task.id, "status": "reply_check_started", "since_hours": since_hours}


@app.get("/api/replies/status")
def reply_detection_status():
    from .reply_detection import GmailReplyDetector
    d = GmailReplyDetector()
    return {
        "configured": d.is_configured(),
        "hint": "Set SMTP_USER + SMTP_PASS (Gmail App Password) for IMAP reply detection",
    }


# ---------- Suppressions / Unsubscribe ----------
class SuppressionAdd(BaseModel):
    email: str
    reason: str = "unsubscribe"
    source: str = "manual"


@app.get("/api/suppressions")
def get_suppressions(limit: int = 200):
    from .tasks import get_supabase
    from .suppression import list_suppressions
    sb = get_supabase()
    return {"suppressions": list_suppressions(sb, limit=limit)}


@app.post("/api/suppressions")
def add_suppression_api(data: SuppressionAdd):
    from .tasks import get_supabase
    from .suppression import add_suppression
    sb = get_supabase()
    ok = add_suppression(sb, data.email, reason=data.reason, source=data.source)
    return {"status": "added" if ok else "failed", "email": data.email}


@app.delete("/api/suppressions/{email}")
def remove_suppression(email: str):
    from .tasks import get_supabase
    sb = get_supabase()
    sb.table("suppressions").delete().eq("email", email.lower().strip()).execute()
    return {"status": "removed", "email": email}


class AssignLead(BaseModel):
    prospect_ids: List[str]
    assigned_to: str  # email or name of team member


@app.post("/api/prospects/assign")
def assign_leads(data: AssignLead):
    """Assign one or more prospects to a team member (email or label)."""
    from .tasks import get_supabase
    from .activity import log_activity
    sb = get_supabase()
    updated = 0
    for pid in data.prospect_ids:
        try:
            sb.table("prospects").update({"assigned_to": data.assigned_to.strip()}).eq("id", pid).execute()
            log_activity(sb, pid, "note", f"Assigned to {data.assigned_to}", metadata={"assigned_to": data.assigned_to})
            updated += 1
        except Exception:
            pass
    return {"status": "assigned", "count": updated, "assigned_to": data.assigned_to}


# ---------- Notifications & Tech detect ----------
@app.get("/api/notifications")
def get_notifications(limit: int = 30, unread_only: bool = False):
    from .tasks import get_supabase
    from .notifications import list_notifications
    sb = get_supabase()
    items = list_notifications(sb, limit=limit, unread_only=unread_only)
    unread = sum(1 for n in items if not n.get("read"))
    return {"notifications": items, "unread": unread}


class MarkRead(BaseModel):
    ids: List[str] = []
    all: bool = False


@app.post("/api/notifications/read")
def mark_notifications_read(data: MarkRead):
    from .tasks import get_supabase
    from .notifications import mark_read
    sb = get_supabase()
    n = mark_read(sb, notification_ids=data.ids, all=data.all)
    return {"status": "ok", "updated": n}


@app.post("/api/tech/detect")
def tech_detect_api(url: str):
    from .tech_detect import detect_tech
    return detect_tech(url)


@app.post("/api/prospects/{prospect_id}/detect-tech")
def prospect_detect_tech(prospect_id: str):
    """Detect tech for a prospect website (profile_url or metadata domain) and store on metadata."""
    from .tasks import get_supabase
    from .tech_detect import detect_tech
    from .activity import log_activity
    sb = get_supabase()
    res = sb.table("prospects").select("*").eq("id", prospect_id).single().execute()
    p = res.data
    if not p:
        raise HTTPException(404, "Prospect not found")
    meta = p.get("metadata") or {}
    url = p.get("profile_url") or meta.get("website") or meta.get("company_domain")
    if url and not str(url).startswith("http") and "." in str(url):
        url = "https://" + str(url)
    if not url:
        raise HTTPException(400, "No website URL on prospect")
    result = detect_tech(str(url))
    meta["tech"] = result
    sb.table("prospects").update({"metadata": meta}).eq("id", prospect_id).execute()
    log_activity(sb, prospect_id, "note", "Tech detection", body=str(result.get("technologies") or result.get("error")), metadata=result)
    return result


# ---------- Branded Ebook & Implementation Guide ----------
class EbookRequest(BaseModel):
    title: str
    subtitle: str = ""
    audience: str = "business owners and professionals"
    company_name: str = "RuffNeck"
    accent_color: str = "#1e3a5f"
    chapters: int = 6
    footer: str = ""


class ImplementationGuideRequest(BaseModel):
    business_name: str
    industry: str = ""
    goals: str = ""
    current_situation: str = ""
    services: str = ""
    notes: str = ""
    company_name: str = "RuffNeck Consulting"
    accent_color: str = "#0f766e"
    title: str = ""
    subtitle: str = ""
    prospect_id: Optional[str] = None


@app.post("/api/generate/ebook")
def generate_ebook_now(data: EbookRequest):
    """Generate a full branded ebook PDF from a title, save to asset library, return download."""
    from .generators import create_ebook_pdf
    from .tasks import get_supabase
    from fastapi.responses import FileResponse
    import os, shutil, uuid as _uuid
    branding = {
        "company_name": data.company_name,
        "accent_color": data.accent_color,
        "subtitle": data.subtitle or "A practical guide",
        "audience": data.audience,
        "chapters": data.chapters,
        "footer": data.footer,
        "mode": "full",
    }
    path = create_ebook_pdf(topic=data.title, branding=branding, prospect={})
    storage = os.path.join(os.path.dirname(__file__), "..", "storage", "assets")
    os.makedirs(storage, exist_ok=True)
    fname = f"ebook_{_uuid.uuid4().hex[:10]}.pdf"
    dest = os.path.join(storage, fname)
    try:
        shutil.copy2(path, dest)
    except Exception:
        dest = path
        fname = os.path.basename(path)
    asset_id = None
    try:
        sb = get_supabase()
        ins = sb.table("assets").insert({
            "asset_type": "ebook",
            "title": data.title,
            "file_path": dest,
            "file_name": fname,
            "branding": branding,
            "metadata": {"subtitle": data.subtitle, "audience": data.audience},
        }).execute()
        asset_id = (ins.data or [{}])[0].get("id")
    except Exception:
        pass
    headers = {"X-Asset-Id": str(asset_id or "")}
    return FileResponse(
        dest,
        media_type="application/pdf",
        filename=f"{data.title[:40].replace(' ', '_')}.pdf",
        headers=headers,
    )


@app.post("/api/generate/implementation-guide")
def generate_implementation_guide_now(data: ImplementationGuideRequest):
    """After consultation: business details → step-by-step implementation PDF + asset library."""
    from .generators import create_implementation_guide_pdf
    from .tasks import get_supabase
    from .activity import log_activity
    from fastapi.responses import FileResponse
    import os, shutil, uuid as _uuid
    business = {
        "business_name": data.business_name,
        "industry": data.industry,
        "goals": data.goals,
        "current_situation": data.current_situation,
        "services": data.services,
        "notes": data.notes,
        "title": data.title,
        "subtitle": data.subtitle,
    }
    branding = {
        "company_name": data.company_name,
        "accent_color": data.accent_color,
    }
    path = create_implementation_guide_pdf(business=business, branding=branding)
    storage = os.path.join(os.path.dirname(__file__), "..", "storage", "assets")
    os.makedirs(storage, exist_ok=True)
    fname = f"guide_{_uuid.uuid4().hex[:10]}.pdf"
    dest = os.path.join(storage, fname)
    try:
        shutil.copy2(path, dest)
    except Exception:
        dest = path
        fname = os.path.basename(path)
    prospect_id = getattr(data, "prospect_id", None)
    asset_id = None
    try:
        sb = get_supabase()
        row = {
            "asset_type": "implementation_guide",
            "title": data.title or f"Implementation Guide: {data.business_name}",
            "file_path": dest,
            "file_name": fname,
            "branding": branding,
            "metadata": business,
        }
        if prospect_id:
            row["prospect_id"] = prospect_id
        ins = sb.table("assets").insert(row).execute()
        asset_id = (ins.data or [{}])[0].get("id")
        if prospect_id:
            log_activity(sb, prospect_id, "note", "Implementation guide generated", body=row["title"], metadata={"asset_id": asset_id})
    except Exception:
        pass
    safe = data.business_name[:30].replace(" ", "_") or "guide"
    return FileResponse(
        dest,
        media_type="application/pdf",
        filename=f"Implementation_{safe}.pdf",
        headers={"X-Asset-Id": str(asset_id or "")},
    )


@app.get("/api/assets")
def list_assets(limit: int = 50, asset_type: Optional[str] = None, prospect_id: Optional[str] = None):
    from .tasks import get_supabase
    sb = get_supabase()
    q = sb.table("assets").select("id, prospect_id, workspace_id, asset_type, title, file_name, metadata, created_at").order("created_at", desc=True).limit(limit)
    if asset_type:
        q = q.eq("asset_type", asset_type)
    if prospect_id:
        q = q.eq("prospect_id", prospect_id)
    res = q.execute()
    return {"assets": res.data or []}


@app.get("/api/assets/{asset_id}/download")
def download_asset(asset_id: str):
    from .tasks import get_supabase
    from fastapi.responses import FileResponse
    import os
    sb = get_supabase()
    res = sb.table("assets").select("*").eq("id", asset_id).single().execute()
    row = res.data
    if not row:
        raise HTTPException(404, "Asset not found")
    path = row.get("file_path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "File missing on server")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=row.get("file_name") or "asset.pdf",
    )


class SendAssetEmail(BaseModel):
    to_email: Optional[str] = None  # default: prospect email
    subject: Optional[str] = None
    message: Optional[str] = None


@app.post("/api/assets/{asset_id}/send")
def send_asset_email(asset_id: str, data: SendAssetEmail = None):
    """Email a saved PDF asset to the prospect or a custom address (Gmail SMTP)."""
    from .tasks import get_supabase
    from .email_campaigns import FreeEmailSender
    from .suppression import is_suppressed
    from .activity import log_activity
    import os

    data = data or SendAssetEmail()
    sb = get_supabase()
    res = sb.table("assets").select("*").eq("id", asset_id).single().execute()
    asset = res.data
    if not asset:
        raise HTTPException(404, "Asset not found")
    path = asset.get("file_path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "PDF file missing on server")

    to_email = (data.to_email or "").strip().lower()
    prospect = None
    if not to_email and asset.get("prospect_id"):
        pr = sb.table("prospects").select("*").eq("id", asset["prospect_id"]).single().execute()
        prospect = pr.data
        to_email = (prospect or {}).get("email") or ""
    if not to_email:
        raise HTTPException(400, "No recipient email. Pass to_email or link asset to a prospect with email.")

    if is_suppressed(sb, to_email):
        raise HTTPException(400, f"{to_email} is on the suppression list")

    title = asset.get("title") or "Your document"
    name = (prospect or {}).get("display_name") or (prospect or {}).get("username") or "there"
    subject = data.subject or f"Your document: {title}"
    body = data.message or (
        f"Hi {name},\n\n"
        f"Please find attached: {title}.\n\n"
        f"Let me know if you have any questions.\n\n"
        f"Best regards"
    )
    body = body.replace("\\n", "\n")
    html = body.replace("\n", "<br>")

    sender = FreeEmailSender()
    result = sender.send_with_attachment(
        to_email=to_email,
        subject=subject,
        body_text=body,
        body_html=html,
        attachment_path=path,
        attachment_name=asset.get("file_name") or "document.pdf",
    )
    if result.get("status") == "sent" and asset.get("prospect_id"):
        try:
            log_activity(
                sb,
                asset["prospect_id"],
                "emailed",
                f"Sent PDF: {title}",
                body=f"To {to_email}",
                metadata={"asset_id": asset_id, "to": to_email},
            )
            # mark contacted if still new
            st = (prospect or {}).get("status")
            if st in (None, "new", "scored", "enriched"):
                sb.table("prospects").update({"status": "contacted"}).eq("id", asset["prospect_id"]).execute()
        except Exception:
            pass
    return result


@app.post("/api/demo/seed")
def seed_demo_data(clear_existing_demo: bool = True):
    """
    Load sample prospects into the pipeline for first-run demos.
    Safe: only touches rows tagged data_source=demo_seed when clearing.
    """
    from .tasks import get_supabase
    from .seed_demo import demo_prospects
    sb = get_supabase()
    removed = 0
    if clear_existing_demo:
        try:
            # delete prior demo rows
            existing = sb.table("prospects").select("id").eq("data_source", "demo_seed").limit(200).execute()
            for row in (existing.data or []):
                sb.table("prospects").delete().eq("id", row["id"]).execute()
                removed += 1
        except Exception:
            pass
    inserted = 0
    errors = []
    for row in demo_prospects():
        try:
            sb.table("prospects").insert(row).execute()
            inserted += 1
        except Exception as e:
            errors.append(str(e)[:120])
    return {
        "status": "ok",
        "inserted": inserted,
        "removed_old_demo": removed,
        "errors": errors[:5],
        "message": "Open Pipeline or Prospects to explore the sample leads.",
    }


@app.delete("/api/demo/seed")
def clear_demo_data():
    """Remove all demo_seed prospects."""
    from .tasks import get_supabase
    sb = get_supabase()
    removed = 0
    try:
        existing = sb.table("prospects").select("id").eq("data_source", "demo_seed").limit(200).execute()
        for row in (existing.data or []):
            sb.table("prospects").delete().eq("id", row["id"]).execute()
            removed += 1
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"status": "cleared", "removed": removed}


class WebsiteAuditRequest(BaseModel):
    url: Optional[str] = None
    prospect_id: Optional[str] = None
    business_name: str = ""
    company_name: str = "RuffNeck"
    accent_color: str = "#1e3a5f"


@app.post("/api/generate/website-audit")
def generate_website_audit(data: WebsiteAuditRequest):
    """Run tech detect (if needed) and return a branded website audit PDF; save to assets."""
    from .tasks import get_supabase
    from .tech_detect import detect_tech
    from .generators import create_website_audit_pdf
    from .activity import log_activity
    from fastapi.responses import FileResponse
    import os, shutil, uuid as _uuid

    sb = get_supabase()
    prospect = None
    url = (data.url or "").strip()
    name = data.business_name
    tech = {}

    if data.prospect_id:
        res = sb.table("prospects").select("*").eq("id", data.prospect_id).single().execute()
        prospect = res.data
        if not prospect:
            raise HTTPException(404, "Prospect not found")
        meta = prospect.get("metadata") or {}
        if not url:
            url = prospect.get("profile_url") or meta.get("website") or meta.get("company_domain") or ""
            if url and not str(url).startswith("http") and "." in str(url):
                url = "https://" + str(url)
        name = name or prospect.get("display_name") or prospect.get("username") or ""
        if meta.get("tech") and meta["tech"].get("ok"):
            tech = meta["tech"]

    if not url:
        raise HTTPException(400, "url or prospect_id with a website is required")
    if not tech:
        tech = detect_tech(url)
        if prospect:
            meta = prospect.get("metadata") or {}
            meta["tech"] = tech
            sb.table("prospects").update({"metadata": meta}).eq("id", prospect["id"]).execute()

    path = create_website_audit_pdf(
        url=str(tech.get("url") or url),
        tech=tech,
        business_name=name,
        branding={"company_name": data.company_name, "accent_color": data.accent_color},
    )
    storage = os.path.join(os.path.dirname(__file__), "..", "storage", "assets")
    os.makedirs(storage, exist_ok=True)
    fname = f"audit_{_uuid.uuid4().hex[:10]}.pdf"
    dest = os.path.join(storage, fname)
    try:
        shutil.copy2(path, dest)
    except Exception:
        dest = path
        fname = os.path.basename(path)
    asset_id = None
    try:
        row = {
            "asset_type": "website_audit",
            "title": f"Website Audit – {name or url}",
            "file_path": dest,
            "file_name": fname,
            "branding": {"company_name": data.company_name},
            "metadata": {"url": url, "tech": tech},
        }
        if data.prospect_id:
            row["prospect_id"] = data.prospect_id
        ins = sb.table("assets").insert(row).execute()
        asset_id = (ins.data or [{}])[0].get("id")
        if data.prospect_id:
            log_activity(sb, data.prospect_id, "note", "Website audit generated", body=url, metadata={"asset_id": asset_id})
    except Exception:
        pass

    safe = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "audit")[:30])
    return FileResponse(
        dest,
        media_type="application/pdf",
        filename=f"Website_Audit_{safe}.pdf",
        headers={"X-Asset-Id": str(asset_id or "")},
    )

@app.get("/")
def root():
    return {
        "name": "RuffNeck Prospector",
        "version": "1.3.0",
        "free": True,
        "platforms": [
            "linkedin", "jobs", "maps", "google",
            "instagram", "twitter", "reddit", "youtube", "tiktok", "facebook"
        ],
        "docs": "/docs",
    }


@app.post("/api/sequences/seed-default")
def seed_default_sequence():
    """Create a ready-to-use 3-step sequence if none exists."""
    from .tasks import get_supabase
    sb = get_supabase()
    existing = sb.table("sequences").select("id").limit(1).execute()
    if existing.data:
        return {"status": "already_exists", "id": existing.data[0]["id"]}

    seq = sb.table("sequences").insert({
        "name": "Default Service Outreach",
        "description": "3-step sequence with auto-pause on reply",
        "is_active": True,
    }).execute()
    seq_id = seq.data[0]["id"]

    steps = [
        {
            "sequence_id": seq_id,
            "step_order": 0,
            "delay_days": 0,
            "channel": "email",
            "subject_template": "Quick idea for {{name}}",
            "body_template": "Hi {{name}},\n\nI came across your note about {{context}} and thought I could help with {{service}}.\n\nWould you be open to a quick chat?\n\nBest regards",
        },
        {
            "sequence_id": seq_id,
            "step_order": 1,
            "delay_days": 3,
            "channel": "email",
            "subject_template": "Following up – {{service}}",
            "body_template": "Hi {{name}},\n\nJust floating this again in case it got buried.\n\nHappy to share a couple of relevant examples if useful.\n\nCheers",
        },
        {
            "sequence_id": seq_id,
            "step_order": 2,
            "delay_days": 5,
            "channel": "email",
            "subject_template": "Closing the loop",
            "body_template": "Hi {{name}},\n\nI'll close the loop for now. If timing becomes better later, just reply.\n\nAll the best",
        },
    ]
    for s in steps:
        sb.table("sequence_steps").insert(s).execute()

    return {"status": "created", "sequence_id": seq_id}


# ---------- Team / Workspace ----------
class WorkspaceCreate(BaseModel):
    name: str
    owner_email: Optional[str] = None

class InviteMember(BaseModel):
    workspace_id: str
    email: str
    role: str = "member"

@app.post("/api/workspaces")
def create_workspace(data: WorkspaceCreate):
    from .tasks import get_supabase
    import re
    sb = get_supabase()
    slug = re.sub(r"[^a-z0-9]+", "-", data.name.lower()).strip("-")[:40]
    row = {
        "name": data.name,
        "slug": slug,
    }
    res = sb.table("workspaces").insert(row).execute()
    ws = res.data[0] if res.data else None
    if ws and data.owner_email:
        sb.table("workspace_members").insert({
            "workspace_id": ws["id"],
            "email": data.owner_email,
            "role": "owner",
            "status": "active",
        }).execute()
    return {"workspace": ws}

@app.get("/api/workspaces")
def list_workspaces():
    from .tasks import get_supabase
    sb = get_supabase()
    res = sb.table("workspaces").select("*, workspace_members(count)").order("created_at", desc=True).limit(50).execute()
    return {"workspaces": res.data or []}

@app.post("/api/workspaces/invite")
def invite_member(data: InviteMember):
    from .tasks import get_supabase
    sb = get_supabase()
    # Upsert invite
    sb.table("workspace_members").upsert({
        "workspace_id": data.workspace_id,
        "email": data.email.lower().strip(),
        "role": data.role,
        "status": "invited",
    }).execute()
    return {"status": "invited", "email": data.email}

@app.get("/api/workspaces/{workspace_id}/members")
def list_members(workspace_id: str):
    from .tasks import get_supabase
    sb = get_supabase()
    res = sb.table("workspace_members").select("*").eq("workspace_id", workspace_id).execute()
    return {"members": res.data or []}

class AssignProspects(BaseModel):
    prospect_ids: List[str]

@app.post("/api/workspaces/{workspace_id}/assign-prospects")
def assign_prospects_to_workspace(workspace_id: str, data: AssignProspects):
    """Assign existing prospects to a workspace so the whole team sees them in the pipeline."""
    from .tasks import get_supabase
    sb = get_supabase()
    updated = 0
    for pid in data.prospect_ids:
        try:
            sb.table("prospects").update({"workspace_id": workspace_id}).eq("id", pid).execute()
            updated += 1
        except Exception:
            pass
    return {"status": "assigned", "count": updated, "workspace_id": workspace_id}
