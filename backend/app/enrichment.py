"""
Full waterfall email enrichment + company domain discovery.
Order: local (regex + patterns) → Hunter.io free → Apollo.io free.
All optional — works with zero API keys using pure local methods.
"""
from typing import Dict, Any, Optional, List
import re
import os
import logging
import requests
from urllib.parse import quote_plus, urlparse
from .email_verify import verify_email

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Domains we never treat as company domains
SOCIAL_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "instagram.com", "facebook.com",
    "tiktok.com", "youtube.com", "google.com", "maps.google.com", "youtu.be",
    "reddit.com", "github.com", "medium.com"
}


def extract_emails_from_text(text: str) -> List[str]:
    if not text:
        return []
    return list(set(EMAIL_RE.findall(text)))


def guess_email_patterns(name: str, domain: str) -> List[str]:
    if not name or not domain:
        return []
    parts = re.sub(r"[^a-z\s]", "", name.lower()).split()
    if not parts:
        return []
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    candidates = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}" if last else None,
        f"{first[0]}{last}@{domain}" if last else None,
        f"{first}{last}@{domain}" if last else None,
        f"{last}@{domain}" if last else None,
        f"{first}_{last}@{domain}" if last else None,
    ]
    return [c for c in candidates if c]


def discover_company_domain(prospect: Dict[str, Any]) -> Optional[str]:
    """
    Try to find a real company domain from available fields.
    """
    # 1. Direct from profile/post URL if it looks like a company site
    for url_field in ("profile_url", "post_url", "website"):
        url = prospect.get(url_field) or ""
        if not url or "://" not in url:
            continue
        try:
            host = urlparse(url).netloc.lower().replace("www.", "")
            if host and not any(s in host for s in SOCIAL_DOMAINS):
                return host
        except Exception:
            pass

    # 2. Look for domain-like strings in bio / comment
    text = " ".join(filter(None, [
        prospect.get("bio_text"),
        prospect.get("comment_text"),
        prospect.get("display_name"),
    ]))
    # Simple heuristic: something.com / .co / .io etc.
    domain_match = re.search(r"\b([a-z0-9][-a-z0-9]*\.(?:com|co|io|net|org|ai|app|dev|biz))\b", text.lower())
    if domain_match:
        return domain_match.group(1)

    # 3. Lightweight Google/DuckDuckGo hint (very rate-limited)
    name = prospect.get("display_name") or prospect.get("username") or ""
    if name and len(name) > 3:
        try:
            q = f'"{name}" official website OR company'
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                # Very crude: first non-social .com in results
                for m in re.finditer(r"https?://(?:www\.)?([a-z0-9][-a-z0-9]*\.(?:com|co|io|net|org))", resp.text.lower()):
                    host = m.group(1)
                    if not any(s in host for s in SOCIAL_DOMAINS):
                        return host
        except Exception as e:
            logger.debug(f"Domain discovery Google failed: {e}")

    return None


def hunter_find_email(name: str, domain: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Hunter.io Email Finder (free tier: ~25–50 searches/month)."""
    if not api_key or not name or not domain:
        return None
    try:
        parts = name.strip().split()
        first = parts[0] if parts else ""
        last = parts[-1] if len(parts) > 1 else ""
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "domain": domain,
                "first_name": first,
                "last_name": last,
                "api_key": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json().get("data") or {}
        email = data.get("email")
        if email:
            return {
                "email": email,
                "confidence": data.get("score") or 70,
                "source": "hunter",
                "position": data.get("position"),
            }
    except Exception as e:
        logger.debug(f"Hunter failed: {e}")
    return None


def apollo_find_email(name: str, domain: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Apollo.io people match / enrichment (free tier available).
    Note: Apollo API shape can change; this is a best-effort free-tier call.
    """
    if not api_key or not name or not domain:
        return None
    try:
        # Apollo people/match or search endpoint (simplified)
        resp = requests.post(
            "https://api.apollo.io/v1/people/match",
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "X-Api-Key": api_key,
            },
            json={
                "name": name,
                "organization_name": domain.split(".")[0],
                "domain": domain,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json().get("person") or {}
        email = data.get("email")
        if email:
            return {
                "email": email,
                "confidence": 75,
                "source": "apollo",
                "title": data.get("title"),
            }
    except Exception as e:
        logger.debug(f"Apollo failed: {e}")
    return None


def enrich_prospect(prospect: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full waterfall enrichment.
    Returns dict with:
      email, email_confidence, email_source, email_candidates,
      company_domain, enrichment_status
    """
    result = {
        "email": None,
        "email_confidence": 0,
        "email_source": None,
        "email_candidates": [],
        "company_domain": None,
        "enrichment_status": "none",
    }

    # ---------- 1. Company domain discovery ----------
    domain = discover_company_domain(prospect)
    if domain:
        result["company_domain"] = domain
        result["enrichment_status"] = "domain_found"

    # ---------- 2. Local email extraction ----------
    text = " ".join(filter(None, [
        prospect.get("comment_text"),
        prospect.get("bio_text"),
        prospect.get("display_name"),
        prospect.get("email"),  # already present?
    ]))
    found = extract_emails_from_text(text)
    if found:
        result.update({
            "email": found[0],
            "email_confidence": 90,
            "email_source": "extracted_from_text",
            "email_candidates": found,
            "enrichment_status": "email_found",
        })
        return result

    name = prospect.get("display_name") or prospect.get("username") or ""
    hunter_key = os.getenv("HUNTER_API_KEY")
    apollo_key = os.getenv("APOLLO_API_KEY")

    # ---------- 3. Pattern guessing (local) ----------
    if domain and name:
        guesses = guess_email_patterns(name, domain)
        if guesses:
            result["email_candidates"] = guesses
            # We don't set email yet — lower confidence; wait for better sources
            result["enrichment_status"] = "patterns_generated"

    # ---------- 4. Hunter.io free ----------
    if domain and name and hunter_key:
        hunter = hunter_find_email(name, domain, hunter_key)
        if hunter:
            result.update({
                "email": hunter["email"],
                "email_confidence": hunter.get("confidence", 70),
                "email_source": "hunter",
                "enrichment_status": "email_found",
            })
            return result

    # ---------- 5. Apollo.io free ----------
    if domain and name and apollo_key:
        apollo = apollo_find_email(name, domain, apollo_key)
        if apollo:
            result.update({
                "email": apollo["email"],
                "email_confidence": apollo.get("confidence", 70),
                "email_source": "apollo",
                "enrichment_status": "email_found",
            })
            return result

    # ---------- 6. Fall back to best pattern guess ----------
    if result.get("email_candidates"):
        result.update({
            "email": result["email_candidates"][0],
            "email_confidence": 35,
            "email_source": "pattern_guess",
            "enrichment_status": "email_guessed",
        })

    
    # Verify email if we have one
    if result.get("email"):
        try:
            v = verify_email(result["email"])
            result["email_valid"] = v.get("valid")
            result["email_status"] = v.get("status")
            result["email_verify_confidence"] = v.get("confidence")
            # Downgrade confidence if verification fails
            if not v.get("valid"):
                result["email_confidence"] = min(result.get("email_confidence") or 0, 20)
            elif v.get("status") == "risky":
                result["email_confidence"] = min(result.get("email_confidence") or 50, 55)
        except Exception:
            pass

    return result
