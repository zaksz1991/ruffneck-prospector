"""
Full waterfall email enrichment + company domain discovery.

Order:
1. Extract publicly visible emails
2. Discover a real company domain
3. Generate email patterns only for a real company domain
4. Hunter.io
5. Apollo.io
6. Verify discovered email

Social/platform domains are NEVER treated as company domains.
"""

from typing import Dict, Any, Optional, List
import re
import os
import logging
import requests
from urllib.parse import quote_plus, urlparse, parse_qs

from .email_verify import verify_email

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Domains that must NEVER be treated as company domains.
SOCIAL_DOMAINS = {
    "linkedin.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "youtube.com",
    "google.com",
    "maps.google.com",
    "youtu.be",
    "reddit.com",
    "github.com",
    "medium.com",
    "duckduckgo.com",
    "threads.net",
}

# Domains that must NEVER be accepted as prospect emails.
BLOCKED_EMAIL_DOMAINS = SOCIAL_DOMAINS | {
    "example.com",
    "example.org",
    "example.net",
}


def normalize_domain(domain: str) -> Optional[str]:
    """Return a clean domain or None if it is unusable."""
    if not domain:
        return None

    domain = domain.strip().lower()
    domain = domain.split("@")[-1]
    domain = domain.split("/")[0]
    domain = domain.split(":")[0]
    domain = domain.removeprefix("www.")

    if not domain or "." not in domain:
        return None

    if domain in BLOCKED_EMAIL_DOMAINS:
        return None

    if any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in BLOCKED_EMAIL_DOMAINS
    ):
        return None

    return domain


def is_valid_company_domain(domain: str) -> bool:
    """Return True only for plausible non-social company domains."""
    normalized = normalize_domain(domain)

    if not normalized:
        return False

    if normalized in SOCIAL_DOMAINS:
        return False

    if any(
        normalized == social or normalized.endswith("." + social)
        for social in SOCIAL_DOMAINS
    ):
        return False

    return True


def is_valid_email(email: str) -> bool:
    """Reject platform/social/example emails."""
    if not email:
        return False

    email = email.strip().lower()

    if not EMAIL_RE.fullmatch(email):
        return False

    domain = email.rsplit("@", 1)[-1]

    return is_valid_company_domain(domain)


def extract_emails_from_text(text: str) -> List[str]:
    if not text:
        return []

    emails = EMAIL_RE.findall(text)

    valid = []

    for email in emails:
        email = email.lower().strip()

        if is_valid_email(email):
            valid.append(email)

    return list(dict.fromkeys(valid))


def guess_email_patterns(name: str, domain: str) -> List[str]:
    """Generate possible business emails only for a valid company domain."""
    if not name or not domain:
        return []

    domain = normalize_domain(domain)

    if not domain or not is_valid_company_domain(domain):
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

    return [
        email
        for email in candidates
        if email and is_valid_email(email)
    ]


def unwrap_url(url: str) -> str:
    """Unwrap DuckDuckGo redirect URLs."""
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        if "duckduckgo.com" in parsed.netloc:
            params = parse_qs(parsed.query)
            destination = params.get("uddg", [None])[0]

            if destination:
                return destination

        if url.startswith("//"):
            return "https:" + url

    except Exception:
        pass

    return url


def discover_company_domain(
    prospect: Dict[str, Any]
) -> Optional[str]:
    """
    Try to find a real company domain from available fields.
    """

    # ---------------------------------------------------------
    # 1. Direct website/profile/post URLs
    # ---------------------------------------------------------
    for url_field in (
        "website",
        "profile_url",
        "post_url",
    ):
        url = prospect.get(url_field) or ""

        if not url:
            continue

        url = unwrap_url(url)

        if "://" not in url:
            continue

        try:
            host = urlparse(url).netloc.lower()
            host = host.removeprefix("www.")

            if is_valid_company_domain(host):
                return host

        except Exception:
            pass

    # ---------------------------------------------------------
    # 2. Look for domains in visible text
    # ---------------------------------------------------------
    text = " ".join(
        filter(
            None,
            [
                prospect.get("bio_text"),
                prospect.get("comment_text"),
                prospect.get("display_name"),
            ],
        )
    )

    domain_match = re.search(
        r"\b([a-z0-9][-a-z0-9]*\."
        r"(?:com|co|io|net|org|ai|app|dev|biz))\b",
        text.lower(),
    )

    if domain_match:
        domain = normalize_domain(
            domain_match.group(1)
        )

        if domain and is_valid_company_domain(domain):
            return domain

    # ---------------------------------------------------------
    # 3. DuckDuckGo company-domain discovery
    # ---------------------------------------------------------
    name = (
        prospect.get("display_name")
        or prospect.get("username")
        or ""
    )

    if name and len(name) > 3:
        try:
            q = f'"{name}" official website OR company'

            url = (
                "https://html.duckduckgo.com/html/?q="
                + quote_plus(q)
            )

            resp = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=10,
            )

            if resp.status_code == 200:

                for match in re.finditer(
                    r"https?://(?:www\.)?"
                    r"([a-z0-9][-a-z0-9]*\."
                    r"(?:com|co|io|net|org|ai|app|dev|biz))",
                    resp.text.lower(),
                ):
                    domain = normalize_domain(
                        match.group(1)
                    )

                    if (
                        domain
                        and is_valid_company_domain(domain)
                    ):
                        return domain

        except Exception as e:
            logger.debug(
                f"Domain discovery failed: {e}"
            )

    return None


def hunter_find_email(
    name: str,
    domain: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:

    if not api_key or not name or not domain:
        return None

    domain = normalize_domain(domain)

    if not domain or not is_valid_company_domain(domain):
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

        if email and is_valid_email(email):
            return {
                "email": email,
                "confidence": data.get("score") or 70,
                "source": "hunter",
                "position": data.get("position"),
            }

    except Exception as e:
        logger.debug(
            f"Hunter failed: {e}"
        )

    return None


def apollo_find_email(
    name: str,
    domain: str,
    api_key: str,
) -> Optional[Dict[str, Any]]:

    if not api_key or not name or not domain:
        return None

    domain = normalize_domain(domain)

    if not domain or not is_valid_company_domain(domain):
        return None

    try:
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

        if email and is_valid_email(email):
            return {
                "email": email,
                "confidence": 75,
                "source": "apollo",
                "title": data.get("title"),
            }

    except Exception as e:
        logger.debug(
            f"Apollo failed: {e}"
        )

    return None



# ============================================================
# PHONE ENRICHMENT
# ============================================================

# Nigerian mobile formats:
#   0803 123 4567
#   0803-123-4567
#   +234 803 123 4567
#   +234-803-123-4567
#   234 803 123 4567
_NG_PHONE_RE = re.compile(
    r"(?<!\d)(?:"
    r"(?:\+234|234)[\s().-]?"
    r"(?:70|71|80|81|90|91)"
    r"[\s().-]?\d"
    r"[\s().-]?\d{3}"
    r"[\s.-]?\d{4}"
    r"|"
    r"0(?:70|71|80|81|90|91)"
    r"[\s().-]?\d"
    r"[\s().-]?\d{3}"
    r"[\s.-]?\d{4}"
    r")(?!\d)"
)

_PLUS_PHONE_RE = re.compile(
    r"(?<!\d)\+\d[\d\s().-]{7,18}\d(?!\d)"
)


def _normalise_phone(
    value: str,
) -> Optional[str]:
    raw = (value or "").strip()

    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)

    ng_prefixes = {
        "70",
        "71",
        "80",
        "81",
        "90",
        "91",
    }

    # Nigerian local format:
    # 08031234567 -> +2348031234567
    if (
        len(digits) == 11
        and digits.startswith("0")
        and digits[1:3] in ng_prefixes
    ):
        return "+234" + digits[1:]

    # Nigerian international format:
    # 2348031234567 -> +2348031234567
    if (
        len(digits) == 13
        and digits.startswith("234")
        and digits[3:5] in ng_prefixes
    ):
        return "+" + digits

    # Nigerian international format with an extra national 0:
    # +23408031234567 -> +2348031234567
    if (
        raw.startswith("+")
        and len(digits) == 14
        and digits.startswith("2340")
        and digits[4:6] in ng_prefixes
    ):
        return "+234" + digits[4:]

    # Generic international format.
    # Must be explicitly prefixed with + and cannot begin with 0.
    if (
        raw.startswith("+")
        and 10 <= len(digits) <= 15
        and digits[0] != "0"
    ):
        return "+" + digits

    return None

def extract_phone_candidates(
    text: str,
) -> list[str]:
    if not text:
        return []

    candidates = []

    for match in _NG_PHONE_RE.findall(text):
        normalized = _normalise_phone(match)

        if (
            normalized
            and normalized not in candidates
        ):
            candidates.append(normalized)

    for match in _PLUS_PHONE_RE.findall(text):
        normalized = _normalise_phone(match)

        if (
            normalized
            and normalized not in candidates
        ):
            candidates.append(normalized)

    return candidates


def extract_public_website_phones(
    domain: Optional[str],
) -> list[str]:
    if not domain:
        return []

    value = str(domain).strip()

    if not value:
        return []

    url = (
        value
        if value.startswith(
            ("http://", "https://")
        )
        else "https://" + value
    )

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "RuffNeck-Prospector/1.0"
                )
            },
            timeout=8,
            allow_redirects=True,
        )

        if response.status_code >= 400:
            return []

        html = (
            response.text or ""
        )[:300000]

        candidates = []

        tel_values = re.findall(
            r'href\s*=\s*["\']tel:([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )

        for value in tel_values:
            normalized = _normalise_phone(value)

            if (
                normalized
                and normalized not in candidates
            ):
                candidates.append(normalized)

        if candidates:
            return candidates

        visible = re.sub(
            r"<[^>]+>",
            " ",
            html,
        )

        return extract_phone_candidates(
            visible
        )

    except Exception as e:
        logger.debug(
            f"Website phone extraction failed: {e}"
        )
        return []


def enrich_prospect(
    prospect: Dict[str, Any]
) -> Dict[str, Any]:

    result = {
        "email": None,
        "email_confidence": 0,
        "email_source": None,
        "email_candidates": [],
        "phone": None,
        "phone_confidence": 0,
        "phone_source": None,
        "phone_candidates": [],
        "company_domain": None,
        "enrichment_status": "none",
    }

    # ---------------------------------------------------------
    # 1. Company domain
    # ---------------------------------------------------------
    domain = discover_company_domain(prospect)

    if domain:
        result["company_domain"] = domain
        result["enrichment_status"] = "domain_found"

    # ---------------------------------------------------------
    # 2. Extract only genuinely valid public emails
    # ---------------------------------------------------------
    text = " ".join(
        filter(
            None,
            [
                prospect.get("comment_text"),
                prospect.get("bio_text"),
                prospect.get("display_name"),
            ],
        )
    )

    found = extract_emails_from_text(text)

    # ---------------------------------------------------------
    # 2b. Public phone enrichment
    # ---------------------------------------------------------
    existing_phone = (
        prospect.get("phone") or ""
    ).strip()

    phone_candidates = extract_phone_candidates(
        text
    )

    if existing_phone:
        normalized_existing = _normalise_phone(
            existing_phone
        )

        if normalized_existing:
            phone_candidates = [
                normalized_existing,
                *[
                    phone
                    for phone in phone_candidates
                    if phone != normalized_existing
                ],
            ]

            result["phone_source"] = "existing"

    # Website fallback. Prefer an already discovered company
    # domain; otherwise use the prospect's public website.
    website_domain = (
        result.get("company_domain")
        or prospect.get("website")
    )

    if (
        not phone_candidates
        and website_domain
    ):
        phone_candidates = (
            extract_public_website_phones(
                website_domain
            )
        )

        if phone_candidates:
            result["phone_source"] = "website"

    if phone_candidates:
        result["phone"] = phone_candidates[0]
        result["phone_candidates"] = phone_candidates

        if result.get("phone_source") == "existing":
            result["phone_confidence"] = 95

        elif result.get("phone_source") == "website":
            result["phone_confidence"] = 85

        else:
            result["phone_confidence"] = 90
            result["phone_source"] = "extracted_from_text"

    if found:
        result.update(
            {
                "email": found[0],
                "email_confidence": 90,
                "email_source": "extracted_from_text",
                "email_candidates": found,
                "enrichment_status": "email_found",
            }
        )
        return result

    name = (
        prospect.get("display_name")
        or prospect.get("username")
        or ""
    )

    hunter_key = os.getenv("HUNTER_API_KEY")
    apollo_key = os.getenv("APOLLO_API_KEY")

    # ---------------------------------------------------------
    # 3. Pattern generation
    # ---------------------------------------------------------
    if domain and name:
        guesses = guess_email_patterns(
            name,
            domain,
        )

        if guesses:
            result["email_candidates"] = guesses
            result["enrichment_status"] = (
                "patterns_generated"
            )

    # ---------------------------------------------------------
    # 4. Hunter
    # ---------------------------------------------------------
    if domain and name and hunter_key:
        hunter = hunter_find_email(
            name,
            domain,
            hunter_key,
        )

        if hunter:
            result.update(
                {
                    "email": hunter["email"],
                    "email_confidence": hunter.get(
                        "confidence",
                        70,
                    ),
                    "email_source": "hunter",
                    "enrichment_status": "email_found",
                }
            )
            return result

    # ---------------------------------------------------------
    # 5. Apollo
    # ---------------------------------------------------------
    if domain and name and apollo_key:
        apollo = apollo_find_email(
            name,
            domain,
            apollo_key,
        )

        if apollo:
            result.update(
                {
                    "email": apollo["email"],
                    "email_confidence": apollo.get(
                        "confidence",
                        70,
                    ),
                    "email_source": "apollo",
                    "enrichment_status": "email_found",
                }
            )
            return result

    # ---------------------------------------------------------
    # 6. Pattern fallback
    # ---------------------------------------------------------
    if result.get("email_candidates"):
        result.update(
            {
                "email": None,
                "email_confidence": 0,
                "email_source": "pattern_guess",
                "enrichment_status": "email_guessed",
            }
        )

    # ---------------------------------------------------------
    # 7. Verify email
    # ---------------------------------------------------------
    if result.get("email"):
        try:
            v = verify_email(
                result["email"]
            )

            result["email_valid"] = v.get(
                "valid"
            )
            result["email_status"] = v.get(
                "status"
            )
            result["email_verify_confidence"] = (
                v.get("confidence")
            )

            status = v.get("status")

            if status == "risky":
                # Risky is not verified, but the address may still
                # be plausible. Keep a moderate confidence ceiling.
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 50,
                    55,
                )

            elif status == "unknown":
                # Syntax + MX confirms only the domain, not the
                # specific mailbox. Preserve source confidence.
                pass

            elif not v.get("valid"):
                # Definitive negative verification results should
                # strongly reduce the email confidence.
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 0,
                    20,
                )

        except Exception:
            pass

    return result