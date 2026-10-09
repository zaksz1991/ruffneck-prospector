"""Simple in-app notifications."""
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def notify(
    sb,
    type: str,
    title: str,
    body: str = "",
    prospect_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user_email: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        sb.table("notifications").insert({
            "type": type,
            "title": title,
            "body": body or "",
            "prospect_id": prospect_id,
            "workspace_id": workspace_id,
            "user_email": user_email,
            "metadata": metadata or {},
            "read": False,
        }).execute()
    except Exception:
        logger.exception(
            "Notification insert failed "
            f"type={type!r} title={title!r} "
            f"prospect_id={prospect_id!r} "
            f"workspace_id={workspace_id!r} "
            f"user_email={user_email!r}"
        )


def list_notifications(sb, limit: int = 30, unread_only: bool = False) -> List[Dict[str, Any]]:
    try:
        q = sb.table("notifications").select("*").order("created_at", desc=True).limit(limit)
        if unread_only:
            q = q.eq("read", False)
        res = q.execute()
        return res.data or []
    except Exception as e:
        logger.warning(f"list_notifications: {e}")
        return []


def mark_read(sb, notification_ids: List[str] = None, all: bool = False) -> int:
    try:
        if all:
            sb.table("notifications").update({"read": True}).eq("read", False).execute()
            return -1
        n = 0
        for nid in (notification_ids or []):
            sb.table("notifications").update({"read": True}).eq("id", nid).execute()
            n += 1
        return n
    except Exception as e:
        logger.warning(f"mark_read: {e}")
        return 0
