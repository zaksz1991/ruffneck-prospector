"""
Free AI content helper for ebooks / implementation guides.
Uses Groq free tier if GROQ_API_KEY set; otherwise structured templates.
"""
from typing import List, Dict, Any, Optional
import os
import json
import logging
import re

logger = logging.getLogger(__name__)


def _groq_chat(prompt: str, max_tokens: int = 2500) -> Optional[str]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "messages": [
                    {"role": "system", "content": "You are an expert business consultant and non-fiction author. Write clear, actionable, professional content. Use plain text with markdown-style ## headings and numbered steps. No fluff."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning(f"Groq error {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Groq failed: {e}")
        return None


def generate_ebook_chapters(title: str, subtitle: str = "", audience: str = "professionals", chapters: int = 6) -> List[Dict[str, str]]:
    prompt = f"""Write a practical digital ebook outline and full chapter content.

Title: {title}
Subtitle: {subtitle or 'A practical guide'}
Audience: {audience}
Chapters: {chapters}

For each chapter provide:
## Chapter N: Title
Then 3-5 short paragraphs and a "Action steps:" list with 3-5 concrete bullets.

Cover introduction briefly before chapter 1. End with a short conclusion chapter.
Keep total under 3000 words. Be specific and actionable."""

    text = _groq_chat(prompt)
    if text:
        return _parse_chapters(text, title)

    # Template fallback
    return _template_ebook(title, subtitle, audience, chapters)


def generate_implementation_guide(
    business_name: str,
    industry: str,
    goals: str,
    current_situation: str,
    services_offered: str,
    notes: str = "",
) -> List[Dict[str, str]]:
    prompt = f"""Create a step-by-step implementation guide for this business after a consultation.

Business name: {business_name}
Industry: {industry}
Goals: {goals}
Current situation: {current_situation}
Services we will deliver: {services_offered}
Consultation notes: {notes}

Structure:
## 1. Executive Summary
## 2. Current State Assessment
## 3. Recommended Solution
## 4. Step-by-Step Implementation Plan (phases with weeks, owners, deliverables)
## 5. Tools & Resources (prefer free/low-cost)
## 6. KPIs & Success Metrics
## 7. Timeline Overview
## 8. Next Actions (this week)

Be concrete. Number every action. No vague advice."""

    text = _groq_chat(prompt, max_tokens=3000)
    if text:
        return _parse_chapters(text, f"Implementation Guide – {business_name}")

    return _template_implementation(business_name, industry, goals, current_situation, services_offered, notes)


def _parse_chapters(text: str, fallback_title: str) -> List[Dict[str, str]]:
    parts = re.split(r"\n(?=##\s+)", text.strip())
    chapters = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n")
        title = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        if body or title:
            chapters.append({"title": title or fallback_title, "body": body})
    if not chapters:
        chapters = [{"title": fallback_title, "body": text}]
    return chapters


def _template_ebook(title: str, subtitle: str, audience: str, n: int) -> List[Dict[str, str]]:
    chapters = [
        {
            "title": "Introduction",
            "body": f"Welcome to <b>{title}</b>.{' ' + subtitle if subtitle else ''} "
            f"This guide is written for {audience}. "
            "Each chapter ends with action steps you can apply the same day.",
        },
        {
            "title": "Chapter 1: Clarify the Outcome",
            "body": "Define the single most important result you want in the next 90 days. "
            "Write it in one sentence that a stranger would understand.<br/><br/>"
            "<b>Action steps:</b><br/>"
            "1. Write your 90-day outcome.<br/>"
            "2. List three obstacles blocking it.<br/>"
            "3. Choose one obstacle to tackle this week.",
        },
        {
            "title": "Chapter 2: Understand Your Audience",
            "body": "Describe who benefits most from your offer: role, pain, and where they spend time online.<br/><br/>"
            "<b>Action steps:</b><br/>"
            "1. Draft a one-paragraph ideal customer profile.<br/>"
            "2. List five phrases they use when describing the problem.<br/>"
            "3. Pick one channel where they already gather.",
        },
        {
            "title": "Chapter 3: Shape the Offer",
            "body": "Package your solution as a clear offer with scope, timeline, and proof.<br/><br/>"
            "<b>Action steps:</b><br/>"
            "1. Write offer in the format: I help [who] achieve [result] without [pain].<br/>"
            "2. Define what's included and what's not.<br/>"
            "3. Add one proof point (result, testimonial, or case metric).",
        },
        {
            "title": "Chapter 4: Build a Simple System",
            "body": "You need a repeatable path from attention → trust → conversation → delivery.<br/><br/>"
            "<b>Action steps:</b><br/>"
            "1. Map your 4-stage funnel on one page.<br/>"
            "2. Identify the weakest stage.<br/>"
            "3. Improve only that stage for 14 days.",
        },
        {
            "title": "Chapter 5: Execute Weekly",
            "body": "Consistency beats intensity. Block focused work and measure weekly.<br/><br/>"
            "<b>Action steps:</b><br/>"
            "1. Schedule three 90-minute focus blocks this week.<br/>"
            "2. Pick one leading metric to track.<br/>"
            "3. Review every Friday for 20 minutes.",
        },
        {
            "title": "Conclusion & Next Steps",
            "body": f"You now have a practical path from the ideas in <b>{title}</b> to execution. "
            "Start with Chapter 1's action steps today. "
            "Revisit this guide monthly and update your metrics.",
        },
    ]
    return chapters[: max(3, min(n + 1, len(chapters)))]


def _template_implementation(name, industry, goals, current, services, notes) -> List[Dict[str, str]]:
    return [
        {
            "title": "1. Executive Summary",
            "body": f"This implementation guide is for <b>{name}</b> ({industry or 'business'}).<br/>"
            f"<b>Goals:</b> {goals or 'Improve digital presence and customer acquisition.'}<br/>"
            f"<b>Services in scope:</b> {services or 'Digital marketing, website, and automation support.'}",
        },
        {
            "title": "2. Current State Assessment",
            "body": f"{current or 'Current digital assets and processes need structure and clearer conversion paths.'}<br/><br/>"
            f"{('Notes: ' + notes) if notes else ''}",
        },
        {
            "title": "3. Recommended Solution",
            "body": f"Deliver <b>{services or 'agreed services'}</b> in phased sprints so {name} sees progress every week "
            "without disrupting daily operations.",
        },
        {
            "title": "4. Step-by-Step Implementation Plan",
            "body": "<b>Phase 1 – Foundation (Week 1–2)</b><br/>"
            "1. Kickoff call and asset inventory.<br/>"
            "2. Finalize positioning and offer messaging.<br/>"
            "3. Set up tracking (Analytics, pixels, CRM/pipeline).<br/><br/>"
            "<b>Phase 2 – Build (Week 3–5)</b><br/>"
            "1. Implement core deliverables (site, creatives, automations).<br/>"
            "2. Internal review and revisions.<br/>"
            "3. Soft launch to a small audience segment.<br/><br/>"
            "<b>Phase 3 – Launch & Optimize (Week 6–8)</b><br/>"
            "1. Full launch.<br/>"
            "2. Weekly metrics review.<br/>"
            "3. Iterate on highest-leverage funnel stage.",
        },
        {
            "title": "5. Tools & Resources (free / low-cost)",
            "body": "1. Google Analytics + Search Console<br/>"
            "2. Canva (creatives)<br/>"
            "3. Free CRM or RuffNeck pipeline for leads<br/>"
            "4. Gmail + documented sequences<br/>"
            "5. Notion/Google Docs for SOPs",
        },
        {
            "title": "6. KPIs & Success Metrics",
            "body": "1. Leads per week<br/>"
            "2. Reply / conversion rate<br/>"
            "3. Website enquiries or booked calls<br/>"
            "4. Revenue influenced by the new system<br/>"
            "5. Time saved on manual follow-up",
        },
        {
            "title": "7. Timeline Overview",
            "body": "Weeks 1–2: Foundation · Weeks 3–5: Build · Weeks 6–8: Launch & optimize · Ongoing: monthly review",
        },
        {
            "title": "8. Next Actions (This Week)",
            "body": f"1. Confirm scope and success metrics with {name}.<br/>"
            "2. Collect brand assets, access, and example customers.<br/>"
            "3. Schedule weekly check-in.<br/>"
            "4. Begin Phase 1 inventory checklist.",
        },
    ]
