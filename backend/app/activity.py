"""Prospect activity timeline helpers."""
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def log_activity(
    sb,
    prospect_id: str,
    activity_type: str,
    title: str,
    body: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    workspace_id: Optional[str] = None,
) -> None:
    try:
        row = {
            "prospect_id": prospect_id,
            "activity_type": activity_type,
            "title": title,
            "body": body or "",
            "metadata": metadata or {},
        }
        if workspace_id:
            row["workspace_id"] = workspace_id
        sb.table("prospect_activities").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")


def list_activities(sb, prospect_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        res = (
            sb.table("prospect_activities")
            .select("*")
            .eq("prospect_id", prospect_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning(f"list_activities failed: {e}")
        return []
