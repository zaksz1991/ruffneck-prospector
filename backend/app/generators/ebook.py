"""
Branded PDF generator for:
- Digital ebooks (from a title)
- Post-consultation implementation guides (from business details)
Uses ReportLab (free). Content from Groq free tier or templates.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.colors import HexColor
from typing import Dict, Any, List, Optional
import os
import re
import tempfile
import uuid
from .content_ai import generate_ebook_chapters, generate_implementation_guide


def _safe(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # restore simple tags we use
    for tag in ("b", "br", "i"):
        text = text.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
        text = text.replace(f"&lt;{tag}/&gt;", f"<{tag}/>")
    text = text.replace("&lt;br/&gt;", "<br/>").replace("&lt;br /&gt;", "<br/>")
    # markdown-ish
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = text.replace("\n", "<br/>")
    return text


def _styles(accent: str):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Heading1"], fontSize=28,
        textColor=HexColor(accent), alignment=TA_CENTER, spaceAfter=14, leading=34,
    ))
    styles.add(ParagraphStyle(
        name="CoverSub", parent=styles["Normal"], fontSize=13,
        alignment=TA_CENTER, textColor=HexColor("#444444"), spaceAfter=8, leading=18,
    ))
    styles.add(ParagraphStyle(
        name="Brand", parent=styles["Normal"], fontSize=11,
        alignment=TA_CENTER, textColor=HexColor("#666666"), spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SectionHead", parent=styles["Heading2"], fontSize=14,
        textColor=HexColor(accent), spaceBefore=14, spaceAfter=8, leading=18,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextCustom", parent=styles["Normal"], fontSize=10.5,
        leading=15, spaceAfter=8, alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name="Footer", parent=styles["Normal"], fontSize=8,
        textColor=HexColor("#888888"), alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TOC", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=4,
    ))
    return styles


def _build_pdf(
    filepath: str,
    cover_title: str,
    cover_sub: str,
    company: str,
    accent: str,
    chapters: List[Dict[str, str]],
    footer_note: str = "",
) -> str:
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    styles = _styles(accent)
    story = []

    # Cover
    story.append(Spacer(1, 45 * mm))
    story.append(Paragraph(_safe(cover_title), styles["CoverTitle"]))
    if cover_sub:
        story.append(Paragraph(_safe(cover_sub), styles["CoverSub"]))
    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(width="40%", thickness=2, color=HexColor(accent), spaceBefore=4, spaceAfter=12, hAlign="CENTER"))
    story.append(Paragraph(_safe(f"by {company}"), styles["Brand"]))
    story.append(PageBreak())

    # TOC
    story.append(Paragraph("Contents", styles["SectionHead"]))
    for i, ch in enumerate(chapters, 1):
        story.append(Paragraph(_safe(f"{i}. {ch.get('title') or 'Section'}"), styles["TOC"]))
    story.append(PageBreak())

    # Chapters
    for ch in chapters:
        block = []
        block.append(Paragraph(_safe(ch.get("title") or "Section"), styles["SectionHead"]))
        body = ch.get("body") or ""
        # split paragraphs
        for para in re.split(r"(?:<br\s*/?>\s*){2,}|\n\n+", body):
            para = para.strip()
            if not para:
                continue
            block.append(Paragraph(_safe(para), styles["BodyTextCustom"]))
        block.append(Spacer(1, 4 * mm))
        story.append(KeepTogether(block))

    story.append(Spacer(1, 16 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#cccccc"), spaceBefore=8, spaceAfter=8))
    story.append(Paragraph(
        _safe(footer_note or f"© {company}. Generated with RuffNeck Prospector. For the recipient’s use."),
        styles["Footer"],
    ))

    doc.build(story)
    return filepath


def create_ebook_pdf(
    topic: str,
    branding: Dict[str, Any],
    prospect: Dict[str, Any] = None,
    output_dir: str = None,
) -> str:
    """Backward-compatible: mini or full ebook from topic/title."""
    prospect = prospect or {}
    branding = branding or {}
    company = branding.get("company_name") or branding.get("brand_name") or "RuffNeck"
    accent = branding.get("accent_color") or "#1e3a5f"
    subtitle = branding.get("subtitle") or f"Prepared for {prospect.get('display_name') or prospect.get('username') or 'you'}"
    audience = branding.get("audience") or "business owners and professionals"
    mode = branding.get("mode") or "full"  # full | mini

    output_dir = output_dir or tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)
    filename = f"ebook_{uuid.uuid4().hex[:10]}.pdf"
    filepath = os.path.join(output_dir, filename)

    if mode == "mini":
        chapters = [
            {"title": "Why This Matters", "body": f"You engaged with topics related to <b>{topic}</b>. Here are practical steps you can use immediately."},
            {"title": "3 Quick Wins", "body": "1. Clarify your core offer in one sentence.<br/>2. Identify the audience already talking about the problem.<br/>3. Publish one high-value answer to their top question."},
            {"title": "Next Step", "body": "Reply and tell us which win you want help with first."},
        ]
    else:
        chapters = generate_ebook_chapters(topic, subtitle=subtitle, audience=audience, chapters=int(branding.get("chapters") or 6))

    return _build_pdf(
        filepath, topic, subtitle, company, accent, chapters,
        footer_note=branding.get("footer") or f"© {company}. All rights reserved for the licensed recipient.",
    )


def create_implementation_guide_pdf(
    business: Dict[str, Any],
    branding: Dict[str, Any] = None,
    output_dir: str = None,
) -> str:
    """Full step-by-step implementation guide after consultation."""
    branding = branding or {}
    company = branding.get("company_name") or "RuffNeck Consulting"
    accent = branding.get("accent_color") or "#0f766e"
    name = business.get("business_name") or business.get("name") or "Client"

    chapters = generate_implementation_guide(
        business_name=name,
        industry=business.get("industry") or "",
        goals=business.get("goals") or "",
        current_situation=business.get("current_situation") or business.get("current") or "",
        services_offered=business.get("services") or business.get("services_offered") or "",
        notes=business.get("notes") or business.get("consultation_notes") or "",
    )

    output_dir = output_dir or tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"impl_guide_{uuid.uuid4().hex[:10]}.pdf")
    title = business.get("title") or f"Implementation Guide: {name}"
    subtitle = business.get("subtitle") or "Step-by-step plan from consultation to execution"

    return _build_pdf(filepath, title, subtitle, company, accent, chapters)
