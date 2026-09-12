"""Email suppression / unsubscribe list (free, local)."""
from typing import Optional, List, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_suppressed(sb, email: str) -> bool:
    email = normalize_email(email)
    if not email:
        return True
    try:
        res = sb.table("suppressions").select("id").eq("email", email).limit(1).execute()
        return bool(res.data)
    except Exception as e:
        logger.warning(f"suppression check failed: {e}")
        return False


def add_suppression(sb, email: str, reason: str = "unsubscribe", source: str = "manual") -> bool:
    email = normalize_email(email)
    if not email:
        return False
    try:
        sb.table("suppressions").upsert({
            "email": email,
            "reason": reason,
            "source": source,
        }).execute()
        return True
    except Exception as e:
        logger.warning(f"add_suppression failed: {e}")
        return False


def list_suppressions(sb, limit: int = 200) -> List[Dict[str, Any]]:
    try:
        res = sb.table("suppressions").select("*").order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


UNSUBSCRIBE_KEYWORDS = [
    "unsubscribe", "remove me", "stop emailing", "opt out", "opt-out",
    "don't contact", "do not contact", "take me off", "stop sending",
]


def body_requests_unsubscribe(body: str) -> bool:
    b = (body or "").lower()
    return any(k in b for k in UNSUBSCRIBE_KEYWORDS)
