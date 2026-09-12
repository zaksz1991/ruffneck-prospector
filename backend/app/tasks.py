"""
Celery tasks – 100% free stack (LinkedIn + jobs + maps + enrichment).
"""
from celery import Celery
import os
import logging
from typing import List, Dict, Any
from supabase import create_client
from .scrapers import scrape_platform, discover_service_leads
from .ai.scorer import LeadScorer
from .ai.copywriter import Copywriter
from .generators import create_ebook_pdf, create_slides_pptx
from .email_campaigns import FreeEmailSender, build_sequence
from .enrichment import enrich_prospect

logger = logging.getLogger(__name__)

celery_app = Celery(
    "ruffneck",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
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
)


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY required")
    return create_client(url, key)


@celery_app.task(bind=True, name="scrape_prospects")
def scrape_prospects_task(self, platform: str, target_url: str, keywords: List[str] = None, max_results: int = 40, workspace_id: str = None):
    keywords = keywords or []
    sb = get_supabase()
    try:
        self.update_state(state="PROGRESS", meta={"status": "scraping", "platform": platform})
        comments = scrape_platform(platform, target_url, keywords=keywords, max_results=max_results)
        inserted = 0
        for c in comments:
            try:
                row = {
                    "platform": c.platform,
                    "username": c.username,
                    "display_name": c.display_name,
                    "profile_url": c.profile_url,
                    "comment_text": c.comment_text,
                    "comment_url": c.comment_url,
                    "post_url": c.post_url or target_url,
                    "post_caption": c.post_caption,
                    "follower_count": c.follower_count or 0,
                    "bio_text": c.bio_text,
                    "is_verified": c.is_verified,
                    "data_source": f"{c.platform}_public",
                    "workspace_id": workspace_id,
                    "tags": ["competitor", "lookalike"] if c.platform == "competitors" else [],
                    "metadata": {"engagement": c.engagement or {}, "seed": (c.engagement or {}).get("seed")},
                }
                # Free enrichment
                enrich = enrich_prospect(row)
                if enrich.get("email"):
                    row["email"] = enrich["email"]
                    row["email_confidence"] = enrich.get("email_confidence", 0)
                if enrich.get("company_domain"):
                    row["metadata"] = row.get("metadata") or {}
                    row["metadata"]["company_domain"] = enrich["company_domain"]
                row["metadata"] = row.get("metadata") or {}
                row["metadata"]["email_source"] = enrich.get("email_source")
                row["metadata"]["email_candidates"] = enrich.get("email_candidates", [])
                row["metadata"]["enrichment_status"] = enrich.get("enrichment_status", "none")

                ins = sb.table("prospects").insert(row).execute()
                inserted += 1
                # Tech detect for site-based leads
                try:
                    pid = (ins.data or [{}])[0].get("id")
                    url = row.get("profile_url") or (row.get("metadata") or {}).get("company_domain")
                    if pid and url and row.get("platform") in ("maps", "google", "competitors", "google_maps"):
                        from .tech_detect import detect_tech
                        tech = detect_tech(str(url))
                        if tech.get("ok"):
                            meta = row.get("metadata") or {}
                            meta["tech"] = tech
                            sb.table("prospects").update({"metadata": meta}).eq("id", pid).execute()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Insert skip: {e}")
        return {"status": "completed", "scraped": len(comments), "inserted": inserted, "platform": platform}
    except Exception as e:
        logger.exception("Scrape failed")
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="discover_service_leads")
def discover_service_leads_task(self, service: str, extra_keywords: List[str] = None, max_results: int = 25):
    sb = get_supabase()
    try:
        leads = discover_service_leads(service, extra_keywords or [], max_results=max_results)
        inserted = 0
        for c in leads:
            try:
                row = {
                    "platform": c.platform or "google",
                    "username": c.username or "web",
                    "display_name": c.display_name,
                    "profile_url": c.profile_url,
                    "comment_text": c.comment_text,
                    "post_url": c.post_url,
                    "bio_text": c.bio_text,
                    "data_source": "google_intent_search",
                    "tags": [service],
                    "metadata": {"query_service": service},
                }
                enrich = enrich_prospect(row)
                if enrich.get("email"):
                    row["email"] = enrich["email"]
                    row["email_confidence"] = enrich.get("email_confidence", 0)
                sb.table("prospects").insert(row).execute()
                inserted += 1
            except Exception as e:
                logger.warning(f"Discover insert skip: {e}")
        return {"status": "completed", "found": len(leads), "inserted": inserted, "service": service}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="enrich_prospects")
def enrich_prospects_task(self, prospect_ids: List[str]):
    """Run free email enrichment on existing prospects."""
    sb = get_supabase()
    enriched = 0
    for pid in prospect_ids:
        try:
            res = sb.table("prospects").select("*").eq("id", pid).single().execute()
            prospect = res.data
            data = enrich_prospect(prospect)
            meta = {**(prospect.get("metadata") or {})}
            meta["email_source"] = data.get("email_source")
            meta["email_candidates"] = data.get("email_candidates", [])
            meta["enrichment_status"] = data.get("enrichment_status", "none")
            if data.get("company_domain"):
                meta["company_domain"] = data["company_domain"]
            update = {
                "metadata": meta,
                "status": "enriched" if prospect.get("status") in ("new", "scored") else prospect.get("status"),
            }
            if data.get("email"):
                update["email"] = data["email"]
                update["email_confidence"] = data.get("email_confidence", 0)
            sb.table("prospects").update(update).eq("id", pid).execute()
            if data.get("email") or data.get("company_domain"):
                enriched += 1
        except Exception as e:
            logger.warning(f"Enrich failed {pid}: {e}")
    return {"status": "completed", "enriched": enriched}


@celery_app.task(bind=True, name="score_prospects")
def score_prospects_task(self, prospect_ids: List[str], scoring_rules: Dict[str, Any] = None):
    sb = get_supabase()
    scorer = LeadScorer()
    scored = 0
    for pid in prospect_ids:
        try:
            res = sb.table("prospects").select("*").eq("id", pid).single().execute()
            prospect = res.data
            overall, reason, breakdown = scorer.score(prospect, scoring_rules)
            sb.table("prospects").update({
                "intent_score": overall,
                "score_reason": reason,
                "status": "scored",
                "metadata": {**(prospect.get("metadata") or {}), "score_breakdown": breakdown},
                "tags": list(set((prospect.get("tags") or []) + [breakdown.get("recommended_service", "other")])),
            }).eq("id", pid).execute()
            scored += 1
        except Exception as e:
            logger.warning(f"Score failed {pid}: {e}")
    return {"status": "completed", "scored": scored}


@celery_app.task(bind=True, name="generate_asset")
def generate_asset_task(self, prospect_id: str, asset_type: str, topic: str, branding: Dict[str, Any] = None):
    sb = get_supabase()
    branding = branding or {"company_name": "RuffNeck Services"}
    res = sb.table("prospects").select("*").eq("id", prospect_id).single().execute()
    prospect = res.data
    if asset_type == "ebook":
        filepath = create_ebook_pdf(topic, branding, prospect)
    elif asset_type == "slides":
        filepath = create_slides_pptx(topic, branding, prospect)
    else:
        raise ValueError(f"Unknown asset_type: {asset_type}")
    file_url = f"file://{filepath}"
    sb.table("assets").insert({
        "prospect_id": prospect_id,
        "asset_type": asset_type,
        "topic": topic,
        "title": f"{topic} for {prospect.get('username')}",
        "file_url": file_url,
        "branding": branding,
    }).execute()
    return {"status": "completed", "file_url": file_url, "local_path": filepath}


@celery_app.task(bind=True, name="send_outreach")
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
            res = sb.table("prospects").select("*").eq("id", pid).single().execute()
            prospect = res.data
            if prospect.get("unsubscribed"):
                continue

            sequence = []
            if channel == "email":
                sequence = build_sequence(prospect, service=service)
                primary = sequence[0]
                copy = {"subject": primary["subject"], "body": primary["body"]}
            else:
                copy = writer.generate_outreach(prospect, channel=channel, topic=topic)

            log_status = "queued"
            if send_real and channel == "email" and prospect.get("email") and sender.is_configured():
                send_result = sender.send(
                    to_email=prospect["email"],
                    subject=copy["subject"],
                    body_html=copy["body"].replace("\n", "<br>"),
                    body_text=copy["body"],
                )
                log_status = send_result.get("status", "failed")

            sb.table("outreach_logs").insert({
                "prospect_id": pid,
                "channel": channel,
                "subject_line": copy.get("subject"),
                "message_text": copy.get("body"),
                "status": log_status,
            }).execute()

            if log_status in ("sent", "queued"):
                sb.table("prospects").update({
                    "last_contacted_at": "now()",
                    "status": "contacted",
                }).eq("id", pid).execute()

            results.append({
                "prospect_id": pid,
                "status": log_status,
                "preview": (copy.get("body") or "")[:120],
                "sequence_length": len(sequence) if channel == "email" else 1,
            })
        except Exception as e:
            logger.warning(f"Outreach {pid}: {e}")
            results.append({"prospect_id": pid, "status": "failed", "error": str(e)})

    return {"status": "completed", "results": results}


@celery_app.task(bind=True, name="run_daily_discovery")
def run_daily_discovery_task(self, location: str = "", services: List[str] = None, workspace_id: str = None):
    """
    One-click daily discovery:
    - Service intent searches for the main services
    - LinkedIn intent
    - Job boards (all)
    - Optional local Maps if location provided
    """
    services = services or ["website", "digital_marketing", "ai_solution", "graphics", "cv_resume", "excel", "hiring_services", "buying_intent"]
    results = {}
    sb = get_supabase()

    # 1. Service intent discoveries
    for svc in services:
        try:
            extra = [location] if location else []
            leads = discover_service_leads(svc, extra, max_results=12)
            inserted = 0
            for c in leads:
                try:
                    row = {
                        "platform": c.platform or "google",
                        "username": c.username or "web",
                        "display_name": c.display_name,
                        "profile_url": c.profile_url,
                        "comment_text": c.comment_text,
                        "post_url": c.post_url,
                        "bio_text": c.bio_text,
                        "data_source": "daily_discovery",
                        "workspace_id": workspace_id,
                        "tags": [svc, "daily"],
                        "metadata": {"query_service": svc, "location": location},
                    }
                    enrich = enrich_prospect(row)
                    if enrich.get("email"):
                        row["email"] = enrich["email"]
                        row["email_confidence"] = enrich.get("email_confidence", 0)
                    sb.table("prospects").insert(row).execute()
                    inserted += 1
                except Exception:
                    pass
            results[f"service_{svc}"] = inserted
        except Exception as e:
            results[f"service_{svc}"] = f"error: {e}"

    # 2. LinkedIn broad intent
    try:
        from .scrapers import scrape_platform
        li_leads = scrape_platform("linkedin", f"need website OR digital marketing OR AI OR designer {location}", max_results=15)
        inserted = 0
        for c in li_leads:
            try:
                row = {
                    "platform": "linkedin",
                    "username": c.username,
                    "display_name": c.display_name,
                    "profile_url": c.profile_url,
                    "comment_text": c.comment_text,
                    "post_url": c.post_url,
                    "data_source": "daily_discovery",
                    "tags": ["linkedin", "daily"],
                }
                sb.table("prospects").insert(row).execute()
                inserted += 1
            except Exception:
                pass
        results["linkedin"] = inserted
    except Exception as e:
        results["linkedin"] = f"error: {e}"

    # 3. Job boards
    try:
        job_leads = scrape_platform("jobs", "all", keywords=["marketing", "developer", "designer", "data"], max_results=20)
        inserted = 0
        for c in job_leads:
            try:
                row = {
                    "platform": "jobs",
                    "username": c.username,
                    "display_name": c.display_name,
                    "profile_url": c.profile_url,
                    "comment_text": c.comment_text,
                    "post_url": c.post_url,
                    "bio_text": c.bio_text,
                    "data_source": "daily_discovery",
                    "tags": ["jobs", "daily"],
                }
                sb.table("prospects").insert(row).execute()
                inserted += 1
            except Exception:
                pass
        results["jobs"] = inserted
    except Exception as e:
        results["jobs"] = f"error: {e}"

    # 4. Optional Maps if location given
    if location:
        try:
            map_leads = scrape_platform("maps", location, keywords=["no_website"], max_results=10)
            inserted = 0
            for c in map_leads:
                try:
                    row = {
                        "platform": "maps",
                        "username": c.username,
                        "display_name": c.display_name,
                        "comment_text": c.comment_text,
                        "data_source": "daily_discovery",
                        "tags": ["maps", "daily", "local"],
                        "metadata": c.engagement or {},
                    }
                    sb.table("prospects").insert(row).execute()
                    inserted += 1
                except Exception:
                    pass
            results["maps"] = inserted
        except Exception as e:
            results["maps"] = f"error: {e}"

    return {"status": "completed", "results": results, "location": location}


@celery_app.task(bind=True, name="auto_enrich_new_prospects")
def auto_enrich_new_prospects_task(self, limit: int = 40):
    """
    Automatically find prospects that still need enrichment
    (no email / enrichment_status = none) and run the waterfall on them.
    Can be triggered manually or scheduled with Celery Beat.
    """
    sb = get_supabase()
    # Fetch recent prospects that look unenriched
    res = (
        sb.table("prospects")
        .select("id, username, display_name, comment_text, bio_text, profile_url, post_url, email, metadata, status")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    candidates = []
    for row in (res.data or []):
        meta = row.get("metadata") or {}
        status = meta.get("enrichment_status") or "none"
        if row.get("email") and status in ("email_found", "email_guessed"):
            continue  # already enriched
        if status in ("none", "domain_found", "patterns_generated", None, ""):
            candidates.append(row)
        if len(candidates) >= limit:
            break

    enriched = 0
    for prospect in candidates:
        try:
            data = enrich_prospect(prospect)
            meta = {**(prospect.get("metadata") or {})}
            meta["email_source"] = data.get("email_source")
            meta["email_candidates"] = data.get("email_candidates", [])
            meta["enrichment_status"] = data.get("enrichment_status", "none")
            if data.get("company_domain"):
                meta["company_domain"] = data["company_domain"]

            update = {"metadata": meta}
            if data.get("email"):
                update["email"] = data["email"]
                update["email_confidence"] = data.get("email_confidence", 0)
                if prospect.get("status") in ("new", "scored"):
                    update["status"] = "enriched"

            sb.table("prospects").update(update).eq("id", prospect["id"]).execute()
            if data.get("email") or data.get("company_domain"):
                enriched += 1
        except Exception as e:
            logger.warning(f"Auto-enrich failed for {prospect.get('id')}: {e}")

    return {
        "status": "completed",
        "candidates_checked": len(candidates),
        "enriched": enriched,
    }


@celery_app.task(bind=True, name="process_due_sequences")
def process_due_sequences_task(self):
    """
    Process sequence steps that are due.
    Skips / pauses enrollments marked as replied.
    """
    from datetime import datetime, timezone
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    # Active enrollments that are due
    res = (
        sb.table("sequence_enrollments")
        .select("*, sequences(*), prospects(id, email, display_name, username, status)")
        .eq("status", "active")
        .lte("next_send_at", now)
        .limit(50)
        .execute()
    )
    processed = 0
    for enroll in (res.data or []):
        try:
            prospect = enroll.get("prospects") or {}
            if prospect.get("status") == "replied":
                sb.table("sequence_enrollments").update({"status": "replied"}).eq("id", enroll["id"]).execute()
                continue

            # Load steps
            steps_res = sb.table("sequence_steps").select("*").eq("sequence_id", enroll["sequence_id"]).order("step_order").execute()
            steps = steps_res.data or []
            step_idx = enroll.get("current_step") or 0
            if step_idx >= len(steps):
                sb.table("sequence_enrollments").update({"status": "completed"}).eq("id", enroll["id"]).execute()
                continue

            step = steps[step_idx]
            # --- Actual email sending via free Gmail SMTP ---
            from .email_campaigns import FreeEmailSender
            sender = FreeEmailSender()

            to_email = prospect.get("email")
            if not to_email:
                logger.info(f"Skipping enrollment {enroll.get('id')} – no email on prospect")
                sb.table("sequence_enrollments").update({"status": "paused"}).eq("id", enroll["id"]).execute()
                continue

            # Skip if previously marked invalid
            meta = prospect.get("metadata") or {}
            if meta.get("email_valid") is False or meta.get("email_status") in ("invalid_syntax", "disposable", "no_mx", "undeliverable"):
                logger.info(f"Skipping {to_email} – marked invalid")
                sb.table("sequence_enrollments").update({"status": "paused"}).eq("id", enroll["id"]).execute()
                continue

            # Skip suppressed / unsubscribed emails
            from .suppression import is_suppressed
            if is_suppressed(sb, to_email):
                logger.info(f"Skipping {to_email} – suppressed/unsubscribed")
                sb.table("sequence_enrollments").update({"status": "paused"}).eq("id", enroll["id"]).execute()
                continue

            # Simple template rendering
            name = prospect.get("display_name") or prospect.get("username") or "there"
            ctx = {
                "name": name,
                "service": (prospect.get("metadata") or {}).get("recommended_service") or "digital services",
                "context": (prospect.get("comment_text") or "")[:100],
                "company": (prospect.get("metadata") or {}).get("company_domain") or "",
            }
            subject = step.get("subject_template") or "Quick note"
            body = step.get("body_template") or ""
            for k, v in ctx.items():
                subject = subject.replace("{{" + k + "}}", str(v))
                body = body.replace("{{" + k + "}}", str(v))

            unsub_footer = "\n\n---\nReply STOP or UNSUBSCRIBE to opt out of future emails."
            body_with_footer = body + unsub_footer
            body_html = body_with_footer.replace("\n", "<br>")
            send_result = sender.send(to_email, subject, body_html, body_text=body_with_footer)
            logger.info(f"Sequence step {step_idx} to {to_email}: {send_result.get('status')}")

            if send_result.get("status") == "failed":
                continue  # do not advance on hard failure

            try:
                from .activity import log_activity
                log_activity(
                    sb,
                    prospect.get("id"),
                    "emailed",
                    f"Sequence email sent (step {step_idx + 1})",
                    body=subject,
                    metadata={"to": to_email, "step": step_idx},
                )
            except Exception:
                pass

            # Advance
            next_idx = step_idx + 1
            next_delay = 0
            if next_idx < len(steps):
                next_delay = steps[next_idx].get("delay_days") or 1
            from datetime import timedelta
            next_send = (datetime.now(timezone.utc) + timedelta(days=next_delay)).isoformat()
            sb.table("sequence_enrollments").update({
                "current_step": next_idx,
                "last_sent_at": now,
                "next_send_at": next_send,
                "status": "completed" if next_idx >= len(steps) else "active",
            }).eq("id", enroll["id"]).execute()

            # Mark prospect contacted
            if prospect.get("status") in ("new", "scored", "enriched"):
                sb.table("prospects").update({"status": "contacted"}).eq("id", prospect["id"]).execute()

            processed += 1
        except Exception as e:
            logger.warning(f"Sequence process error: {e}")

    return {"status": "done", "processed": processed}


@celery_app.task(bind=True, name="check_replies")
def check_replies_task(self, since_hours: int = 48):
    """
    Match recent Gmail replies to prospects by from_email.
    On match: log reply, stage=replied (or meeting if positive), pause sequences, activity log.
    """
    from .reply_detection import GmailReplyDetector
    from .activity import log_activity
    from .pipeline import PIPELINE_STAGES

    detector = GmailReplyDetector()
    if not detector.is_configured():
        return {"status": "skipped", "reason": "IMAP/SMTP not configured"}

    sb = get_supabase()
    messages = detector.fetch_recent_replies(since_hours=since_hours, max_messages=50)
    matched = 0
    details = []

    for msg in messages:
        from_email = (msg.get("from_email") or "").lower()
        if not from_email:
            continue
        try:
            res = sb.table("prospects").select("id, email, status, workspace_id, display_name").eq("email", from_email).limit(1).execute()
            rows = res.data or []
            if not rows:
                continue
            prospect = rows[0]
            pid = prospect["id"]

            # Detect simple intent
            body = (msg.get("body") or "").lower()
            positive = any(w in body for w in ["interested", "yes", "sure", "sounds good", "pricing", "how much", "let's", "available"])
            negative = any(w in body for w in ["not interested", "no thanks", "unsubscribe", "remove me", "stop"])
            intent = "positive" if positive else ("negative" if negative else ("question" if "?" in body else "neutral"))

            # Insert reply
            sb.table("replies").insert({
                "prospect_id": pid,
                "channel": "email",
                "direction": "inbound",
                "subject": msg.get("subject"),
                "body": msg.get("body"),
                "metadata": {"detected_intent": intent, "auto": True, "message_id": msg.get("message_id")},
            }).execute()

            from .suppression import body_requests_unsubscribe, add_suppression
            if body_requests_unsubscribe(msg.get("body") or "") or intent == "negative" and "unsub" in body:
                add_suppression(sb, from_email, reason="unsubscribe", source="auto_reply")
                new_status = "lost"
            else:
                new_status = "meeting" if intent == "positive" else "replied"

            sb.table("prospects").update({"status": new_status}).eq("id", pid).execute()

            # Pause sequences
            sb.table("sequence_enrollments").update({"status": "replied"}).eq(
                "prospect_id", pid
            ).eq("status", "active").execute()

            log_activity(
                sb,
                pid,
                "replied",
                f"Auto-detected reply ({intent})",
                body=(msg.get("subject") or "") + "\n" + (msg.get("body") or "")[:400],
                metadata={"intent": intent, "from": from_email},
                workspace_id=prospect.get("workspace_id"),
            )
            if intent == "positive":
                try:
                    from .notifications import notify
                    notify(
                        sb,
                        "positive_reply",
                        f"Positive reply from {prospect.get('display_name') or from_email}",
                        body=(msg.get("subject") or "")[:120],
                        prospect_id=pid,
                        workspace_id=prospect.get("workspace_id"),
                    )
                except Exception:
                    pass
            matched += 1
            details.append({"prospect_id": pid, "email": from_email, "intent": intent, "status": new_status})
        except Exception as e:
            logger.warning(f"Reply match error for {from_email}: {e}")

    return {"status": "done", "messages_scanned": len(messages), "matched": matched, "details": details}


def _maybe_notify_high_score(sb, prospect_id, score, name, workspace_id=None):
    try:
        if score is not None and int(score) >= 75:
            from .notifications import notify
            notify(
                sb,
                "high_score_lead",
                f"High-intent lead: {name or prospect_id}",
                body=f"Intent score {score}",
                prospect_id=prospect_id,
                workspace_id=workspace_id,
                metadata={"score": score},
            )
    except Exception:
        pass
