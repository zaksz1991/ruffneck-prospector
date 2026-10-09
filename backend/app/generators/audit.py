"""Branded website audit PDF from tech_detect results."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.colors import HexColor, white
from typing import Dict, Any, List, Optional
import os
import tempfile
import uuid
import re


def _safe(text: str) -> str:
    if not text:
        return ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", "<br/>")
    return text


def create_website_audit_pdf(
    url: str,
    tech: Dict[str, Any],
    business_name: str = "",
    branding: Optional[Dict[str, Any]] = None,
    output_dir: str = None,
) -> str:
    branding = branding or {}
    company = branding.get("company_name") or "RuffNeck"
    accent = branding.get("accent_color") or "#1e3a5f"
    name = business_name or tech.get("title") or url

    output_dir = output_dir or tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"audit_{uuid.uuid4().hex[:10]}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", parent=styles["Heading1"], fontSize=22, textColor=HexColor(accent), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], fontSize=13, textColor=HexColor(accent), spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=6))
    styles.add(ParagraphStyle(name="Muted", parent=styles["Normal"], fontSize=9, textColor=HexColor("#666666"), alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="Bullet", parent=styles["Normal"], fontSize=10.5, leading=14, leftIndent=10, spaceAfter=3))

    techs: List[str] = tech.get("technologies") or []
    outdated: List[str] = tech.get("outdated_signals") or []
    pitch = tech.get("pitch_hint") or ""
    https = tech.get("https")
    status = tech.get("status_code")
    ok = tech.get("ok", False)

    # Simple score 0-100
    score = 70
    if not ok:
        score = 25
    else:
        if https is False:
            score -= 20
        if "no_mobile_viewport" in outdated:
            score -= 15
        if "old_jquery" in outdated:
            score -= 10
        if not techs:
            score -= 5
        if any(x in " ".join(techs).lower() for x in ("wix", "godaddy", "squarespace")):
            score -= 5
        score = max(15, min(95, score))

    story = []
    story.append(Paragraph("Website Audit Report", styles["H1"]))
    story.append(Paragraph(_safe(name), styles["Muted"]))
    story.append(Paragraph(_safe(url), styles["Muted"]))
    story.append(Paragraph(_safe(f"Prepared by {company}"), styles["Muted"]))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(accent), spaceAfter=8))

    story.append(Paragraph("1. Snapshot", styles["H2"]))
    rows = [
        ["Overall digital health", f"{score}/100"],
        ["HTTPS", "Yes" if https else "No / unknown"],
        ["HTTP status", str(status or "n/a")],
        ["Technologies detected", ", ".join(techs) if techs else "None clearly detected"],
        ["Risk signals", ", ".join(outdated) if outdated else "None flagged"],
    ]
    table = Table(rows, colWidths=[65*mm, 105*mm])
    table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(table)

    story.append(Paragraph("2. Findings", styles["H2"]))
    if not ok:
        story.append(Paragraph(_safe(f"Could not fully analyze the site: {tech.get('error') or 'unreachable or blocked'}."), styles["Body"]))
    else:
        story.append(Paragraph(_safe(pitch or "See recommendations below."), styles["Body"]))
        if https is False:
            story.append(Paragraph("• Site may not force HTTPS — hurts trust and SEO.", styles["Bullet"]))
        if "no_mobile_viewport" in outdated:
            story.append(Paragraph("• Missing mobile viewport — poor phone experience likely.", styles["Bullet"]))
        if "old_jquery" in outdated:
            story.append(Paragraph("• Outdated JavaScript libraries detected — security/performance risk.", styles["Bullet"]))
        if any(x in " ".join(techs).lower() for x in ("wix", "squarespace", "godaddy")):
            story.append(Paragraph("• Builder platform limits customization, speed, and SEO control as you grow.", styles["Bullet"]))
        if "WordPress" in techs:
            story.append(Paragraph("• WordPress site — ensure updates, backups, and lightweight theme/plugins.", styles["Bullet"]))

    story.append(Paragraph("3. Recommended next steps", styles["H2"]))
    steps = [
        "Confirm primary goal (leads, bookings, sales) and measure current baseline.",
        "Fix trust basics: HTTPS, mobile layout, clear contact/booking path.",
        "Improve homepage message: who you serve, what you offer, what to do next.",
        "Add or refine Google Business Profile and consistent NAP details (local).",
        "Set up simple analytics and a weekly review of enquiries.",
        "Plan a 30-day content or outreach sprint aligned to your offer.",
    ]
    for i, s in enumerate(steps, 1):
        story.append(Paragraph(_safe(f"{i}. {s}"), styles["Bullet"]))

    story.append(Paragraph("4. How we can help", styles["H2"]))
    story.append(Paragraph(
        _safe(
            f"{company} can implement the highest-impact items: website refresh, local SEO, "
            "conversion-focused pages, and a simple lead follow-up system. "
            "Reply to this report to prioritize a focused 2-week sprint."
        ),
        styles["Body"],
    ))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc"), spaceBefore=6, spaceAfter=6))
    story.append(Paragraph(
        _safe(f"© {company}. Automated technical signals — validate critical findings manually. Not a penetration test."),
        styles["Muted"],
    ))

    doc.build(story)
    return path
