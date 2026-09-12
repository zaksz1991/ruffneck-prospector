"""
Free / low-cost email verification.
Methods:
1. Syntax check
2. Disposable domain blocklist (common ones)
3. MX record check (DNS)
4. Optional: free-tier APIs (Hunter verify, etc.) if key present
"""
from typing import Dict, Any, Optional
import os
import re
import logging
import smtplib
import dns.resolver

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Common disposable / throwaway domains (partial list)
DISPOSABLE = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "temp-mail.org",
    "10minutemail.com", "yopmail.com", "throwaway.email", "trashmail.com",
    "getnada.com", "maildrop.cc", "fakeinbox.com", "sharklasers.com",
}


def syntax_ok(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()))


def is_disposable(email: str) -> bool:
    try:
        domain = email.split("@")[1].lower()
        return domain in DISPOSABLE
    except Exception:
        return False


def has_mx(email: str) -> bool:
    try:
        domain = email.split("@")[1]
        records = dns.resolver.resolve(domain, "MX")
        return len(records) > 0
    except Exception:
        return False


def hunter_verify(email: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Hunter.io Email Verifier (free tier has limited credits)."""
    if not api_key:
        return None
    try:
        import requests
        resp = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": api_key},
            timeout=12,
        )
        if resp.status_code != 200:
            return None
        data = resp.json().get("data") or {}
        return {
            "result": data.get("result"),  # deliverable, undeliverable, risky...
            "score": data.get("score"),
            "source": "hunter",
        }
    except Exception as e:
        logger.debug(f"Hunter verify failed: {e}")
        return None


def verify_email(email: str) -> Dict[str, Any]:
    """
    Returns:
      valid: bool
      status: ok | invalid_syntax | disposable | no_mx | risky | unknown
      confidence: 0-100
      details: dict
    """
    email = (email or "").strip().lower()
    result = {
        "email": email,
        "valid": False,
        "status": "unknown",
        "confidence": 0,
        "details": {},
    }

    if not syntax_ok(email):
        result["status"] = "invalid_syntax"
        return result

    if is_disposable(email):
        result["status"] = "disposable"
        result["details"]["reason"] = "disposable domain"
        return result

    mx_ok = has_mx(email)
    result["details"]["mx"] = mx_ok
    if not mx_ok:
        result["status"] = "no_mx"
        result["confidence"] = 10
        return result

    # Optional Hunter
    hunter_key = os.getenv("HUNTER_API_KEY")
    hunter = hunter_verify(email, hunter_key) if hunter_key else None
    if hunter:
        result["details"]["hunter"] = hunter
        res = (hunter.get("result") or "").lower()
        if res == "deliverable":
            result.update({"valid": True, "status": "ok", "confidence": min(95, (hunter.get("score") or 80))})
            return result
        if res == "undeliverable":
            result.update({"valid": False, "status": "undeliverable", "confidence": 90})
            return result
        if res == "risky":
            result.update({"valid": True, "status": "risky", "confidence": 50})
            return result

    # Local pass: syntax + MX
    result.update({
        "valid": True,
        "status": "ok",
        "confidence": 65,  # moderate without external verifier
    })
    return result
