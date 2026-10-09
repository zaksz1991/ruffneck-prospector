"""
Pipeline stages, reply tracking, deduplication, WhatsApp helpers.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import hashlib
import re

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["new", "contacted", "replied", "meeting", "won", "lost"]

def normalize_key(prospect: Dict[str, Any]) -> str:
    """Create a deduplication key from available identity signals."""
    email = (prospect.get("email") or "").lower().strip()
    if email:
        return f"email:{email}"
    username = (prospect.get("username") or "").lower().strip()
    platform = (prospect.get("platform") or "").lower()
    profile = (prospect.get("profile_url") or "").lower().strip()
    if profile:
        return f"url:{profile}"
    if username and platform:
        return f"{platform}:{username}"
    name = (prospect.get("display_name") or "").lower().strip()
    domain = (prospect.get("metadata") or {}).get("company_domain") or ""
    return f"name:{name}|{domain}"


def deduplicate_prospects(prospects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the highest-scored / most enriched version of each unique lead."""
    seen = {}
    for p in prospects:
        key = normalize_key(p)
        existing = seen.get(key)
        if not existing:
            seen[key] = p
            continue
        # Prefer one with email, then higher score
        score_new = p.get("intent_score") or 0
        score_old = existing.get("intent_score") or 0
        has_email_new = bool(p.get("email"))
        has_email_old = bool(existing.get("email"))
        if (has_email_new and not has_email_old) or (has_email_new == has_email_old and score_new > score_old):
            seen[key] = p
    return list(seen.values())


def whatsapp_link(phone: str, message: str = "") -> Optional[str]:
    """Generate a WhatsApp deep link (wa.me)."""
    if not phone:
        return None
    # Keep digits only, assume international if starts with +
    digits = re.sub(r"[^\d+]", "", phone)
    digits = digits.lstrip("+")
    if len(digits) < 8:
        return None
    base = f"https://wa.me/{digits}"
    if message:
        from urllib.parse import quote
        return f"{base}?text={quote(message)}"
    return base


def extract_phone(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
    return m.group(1).strip() if m else None
