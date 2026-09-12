"""
Free website technology detection from HTML + headers.
No paid APIs. Used to strengthen website-related pitches.
"""
from typing import Dict, Any, List, Optional
import re
import logging
import requests

logger = logging.getLogger(__name__)

SIGNATURES = [
    (r"wp-content|wordpress", "WordPress"),
    (r"Shopify\.|cdn\.shopify", "Shopify"),
    (r"wix\.com|static\.wix", "Wix"),
    (r"squarespace", "Squarespace"),
    (r"websitedesigner|godaddy", "GoDaddy Builder"),
    (r"jimdo", "Jimdo"),
    (r"webflow", "Webflow"),
    (r"drupal", "Drupal"),
    (r"joomla", "Joomla"),
    (r"react|__NEXT_DATA__|_next/", "React/Next.js"),
    (r"nuxt|__NUXT__", "Nuxt"),
    (r"angular", "Angular"),
    (r"vue\.js|vue\.min", "Vue"),
    (r"bootstrap", "Bootstrap"),
    (r"tailwind", "Tailwind"),
    (r"googleapis\.com/maps|maps\.google", "Google Maps embed"),
    (r"cloudflare", "Cloudflare"),
    (r"mailchimp|list-manage", "Mailchimp"),
    (r"googletagmanager|gtag\(|google-analytics", "Google Analytics"),
    (r"facebook\.net/en_US/fbevents|fbq\(", "Facebook Pixel"),
]


def detect_tech(url: str, timeout: int = 10) -> Dict[str, Any]:
    if not url:
        return {"ok": False, "error": "no url"}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RuffNeckProspector/1.9)"},
            allow_redirects=True,
        )
        html = resp.text[:500000].lower()
        headers = {k.lower(): v for k, v in resp.headers.items()}
        found: List[str] = []
        for pattern, name in SIGNATURES:
            if re.search(pattern, html, re.I) or re.search(pattern, str(headers), re.I):
                if name not in found:
                    found.append(name)

        generator = headers.get("x-generator") or headers.get("x-powered-by")
        if generator and generator not in found:
            found.append(generator[:60])

        # Simple quality heuristics
        has_https = url.startswith("https")
        has_viewport = "viewport" in html
        title_m = re.search(r"<title[^>]*>([^<]{0,120})", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        outdated_signals = []
        if "wordpress" in " ".join(found).lower() and re.search(r"wp-includes/js/jquery/jquery\.js\?ver=1\.", html):
            outdated_signals.append("old_jquery")
        if not has_viewport:
            outdated_signals.append("no_mobile_viewport")
        if not has_https:
            outdated_signals.append("no_https")

        return {
            "ok": True,
            "url": str(resp.url),
            "status_code": resp.status_code,
            "technologies": found,
            "title": title[:120],
            "https": has_https,
            "outdated_signals": outdated_signals,
            "pitch_hint": _pitch_hint(found, outdated_signals),
        }
    except Exception as e:
        logger.debug(f"tech detect failed for {url}: {e}")
        return {"ok": False, "error": str(e)[:200], "url": url}


def _pitch_hint(tech: List[str], outdated: List[str]) -> str:
    t = " ".join(tech).lower()
    if "wix" in t or "squarespace" in t or "godaddy" in t:
        return "Builder platform site – often limited SEO/customization; strong redesign opportunity."
    if "wordpress" in t and outdated:
        return "WordPress with outdated signals – maintenance or rebuild pitch."
    if "shopify" in t:
        return "Shopify store – upsells: speed, conversion, apps, creative."
    if not tech:
        return "Stack unclear or custom – audit offer works well."
    if outdated:
        return "Outdated technical signals – modernization pitch."
    return "Modern stack detected – pitch integration/AI/marketing rather than full rebuild."
