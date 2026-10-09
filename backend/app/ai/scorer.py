import os
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq

logger = logging.getLogger(__name__)


class LeadScorer:
    SERVICE_CHOICES = [
        "AI services",
        "Virtual Assistance",
        "Graphic Design",
        "Transcription",
        "Data Entry",
        "Excel Data Analysis",
        "AI Technical Content Writing",
        "AI Training",
        "Digital Marketing",
        "Social Media Management",
        "CV & Cover Letter",
        "Microsoft Office Training",
        "AI Data Evaluation",
        "Website Development",
        "Consultancy",
        "other",
    ]

    INTENT_TERMS = {
        "looking for": 25,
        "looking to": 20,
        "need help": 25,
        "need support": 25,
        "we need": 25,
        "seeking": 20,
        "hire": 20,
        "hiring": 15,
        "outsource": 25,
        "outsourcing": 25,
        "request a quote": 30,
        "request quote": 30,
        "rfq": 30,
        "procurement": 25,
        "vendor": 15,
        "supplier": 15,
        "tender": 25,
        "quotation": 25,
        "services required": 30,
    }

    JOB_TERMS = [
        "job vacancy",
        "job opening",
        "vacancy",
        "career",
        "careers",
        "apply now",
        "job description",
        "salary",
        "remote job",
    ]

    COMPETITOR_TERMS = [
        "digital marketing agency",
        "marketing agency",
        "social media agency",
        "branding agency",
        "graphic design agency",
        "graphic designer",
        "web design agency",
        "web development agency",
        "web developer",
        "website designer",
        "resume writer",
        "cv writer",
        "recruitment agency",
        "staffing agency",
        "virtual assistant service",
        "freelancer",
    ]

    def __init__(self, model: Optional[str] = None):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")

        self.model = model or os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b",
        )
        self.client = Groq(api_key=self.api_key)

    def _prospect_text(self, prospect: Dict[str, Any]) -> str:
        parts = []

        for key in [
            "display_name",
            "username",
            "name",
            "company_name",
            "title",
            "bio_text",
            "description",
            "comment_text",
            "post_caption",
            "profile_url",
            "website",
            "email",
            "location",
            "platform",
        ]:
            value = prospect.get(key)
            if value:
                parts.append(str(value))

        metadata = prospect.get("metadata") or {}
        if isinstance(metadata, dict):
            for key in [
                "query_service",
                "page_type",
                "location",
                "root_domain",
                "company_domain",
                "discovery",
            ]:
                value = metadata.get(key)
                if value:
                    parts.append(str(value))

        tags = prospect.get("tags") or []
        if isinstance(tags, list):
            parts.extend(str(x) for x in tags)

        return " ".join(parts).lower()

    def _service_fit(self, prospect: Dict[str, Any], text: str):
        metadata = prospect.get("metadata") or {}
        query = str(metadata.get("query_service") or "").lower()

        query_map = {
            "ai_solution": "AI services",
            "digital_marketing": "Digital Marketing",
            "social_media": "Social Media Management",
            "graphics": "Graphic Design",
            "cv_resume": "CV & Cover Letter",
            "excel": "Excel Data Analysis",
            "data_entry": "Data Entry",
            "website": "Website Development",
            "hiring_services": "Virtual Assistance",
            "virtual_assistance": "Virtual Assistance",
            "transcription": "Transcription",
            "ai_training": "AI Training",
            "consulting": "Consultancy",
        }

        for key, service in query_map.items():
            if key in query:
                return service, 55

        checks = [
            (["outsourcing", "business support", "administrative support"], "Virtual Assistance", 50),
            (["artificial intelligence", "machine learning", "automation"], "AI services", 50),
            (["digital marketing", "social media marketing", "seo"], "Digital Marketing", 50),
            (["graphic design", "branding"], "Graphic Design", 45),
            (["data entry", "data processing"], "Data Entry", 50),
            (["excel", "spreadsheet", "data analysis", "power bi"], "Excel Data Analysis", 50),
            (["resume", "cv writing", "cover letter"], "CV & Cover Letter", 45),
            (["website", "web development", "web design"], "Website Development", 45),
            (["transcription"], "Transcription", 45),
            (["training", "workshop", "capacity building"], "AI Training", 35),
            (["consulting", "consultancy"], "Consultancy", 40),
        ]

        for terms, service, fit in checks:
            if any(term in text for term in terms):
                return service, fit

        return "other", 10

    def _deterministic_score(self, prospect: Dict[str, Any]):
        text = self._prospect_text(prospect)
        metadata = prospect.get("metadata") or {}

        if not isinstance(metadata, dict):
            metadata = {}

        service, fit = self._service_fit(prospect, text)

        intent = sum(
            points
            for term, points in self.INTENT_TERMS.items()
            if term in text
        )
        intent = min(100, intent)

        evidence = 0

        if prospect.get("display_name"):
            evidence += 15
        if prospect.get("profile_url"):
            evidence += 10
        if metadata.get("root_domain") or metadata.get("company_domain"):
            evidence += 10
        if metadata.get("page_type") == "homepage":
            evidence += 10
        if prospect.get("email"):
            evidence += 5

        platform = str(prospect.get("platform") or "").lower()
        page_type = str(metadata.get("page_type") or "").lower()

        is_job = (
            platform == "jobs"
            or "job" in page_type
            or any(term in text for term in self.JOB_TERMS)
        )

        is_competitor = any(
            term in text
            for term in self.COMPETITOR_TERMS
        )

        # Buying-intent records describe organizations looking to
        # purchase services; vendor language inside an RFP should
        # not classify the buyer as a competitor.
        if str(metadata.get("query_service") or "").lower() == "buying_intent":
            is_competitor = False

        score = int(
            fit * 0.45
            + evidence * 0.20
            + intent * 0.35
        )

        if intent >= 40:
            score = max(score, 75)
        elif intent >= 25:
            score = max(score, 60)
        elif intent >= 10 and fit >= 40:
            score = max(score, 50)
        elif fit >= 45 and evidence >= 30:
            score = max(score, 40)

        if is_competitor and intent < 20:
            score = min(score, 35)

        if is_job:
            score = min(score, 15)

        tags = []

        if service != "other":
            tags.append(service.lower())
        if intent > 0:
            tags.append("commercial-intent")
        if is_competitor:
            tags.append("competitor")
        if is_job:
            tags.append("job-result")
        if page_type == "homepage":
            tags.append("homepage")
        if "outsourcing" in text:
            tags.append("outsourcing")
        if "business support" in text:
            tags.append("business-support")

        return max(0, min(100, score)), intent, service, tags

    def score(
        self,
        prospect: Dict[str, Any],
        scoring_rules: Optional[Dict[str, Any]] = None,
    ):
        deterministic_score, deterministic_intent, deterministic_service, deterministic_tags = (
            self._deterministic_score(prospect)
        )

        prompt = f"""
Score this B2B sales prospect for RuffNeck Entertainment.

RuffNeck services:
AI services, Virtual Assistance, Graphic Design, Transcription,
Data Entry, Excel Data Analysis, AI Technical Content Writing,
AI Training, Digital Marketing, Social Media Management,
CV & Cover Letter, Microsoft Office Training, AI Data Evaluation,
Website Development, Consultancy.

Prospect:
{json.dumps(prospect, ensure_ascii=False, default=str)}

Deterministic evidence:
score={deterministic_score}
intent={deterministic_intent}
service={deterministic_service}

Do not invent buying intent.
A company homepage with relevant service fit is still a valid prospect.
Zero social engagement does not mean zero business relevance.
Jobs and obvious service providers should score low.

Return ONLY JSON:
{{
  "overall": 0,
  "reason": "",
  "breakdown": {{
    "engagement_score": 0,
    "intent_score": 0,
    "recommended_service": "other",
    "tags": []
  }}
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON for B2B lead scoring.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = json.loads(
                response.choices[0].message.content or "{}"
            )

            llm_score = int(
                max(
                    0,
                    min(100, result.get("overall", 0)),
                )
            )

            breakdown = result.get("breakdown") or {}

            llm_engagement = int(
                max(
                    0,
                    min(
                        100,
                        breakdown.get("engagement_score", 0),
                    ),
                )
            )

            llm_intent = int(
                max(
                    0,
                    min(
                        100,
                        breakdown.get("intent_score", 0),
                    ),
                )
            )

            service = str(
                breakdown.get(
                    "recommended_service",
                    deterministic_service,
                )
            )

            if service not in self.SERVICE_CHOICES:
                service = deterministic_service

            llm_tags = breakdown.get("tags") or []
            if not isinstance(llm_tags, list):
                llm_tags = []

            tags = []

            for tag in deterministic_tags + [
                str(x) for x in llm_tags[:10]
            ]:
                if (
                    str(prospect.get("metadata", {}).get("query_service") or "").lower()
                    == "buying_intent"
                    and str(tag).lower() == "competitor"
                ):
                    continue
                if tag not in tags:
                    tags.append(tag)

            overall = max(
                llm_score,
                deterministic_score,
            )

            intent_score = max(
                llm_intent,
                deterministic_intent,
            )

            engagement_score = max(
                llm_engagement,
                deterministic_score,
            )

            reason = str(
                result.get("reason", "")
            )[:500]

            if deterministic_intent:
                reason = (
                    f"{reason} "
                    f"Commercial evidence detected; "
                    f"deterministic intent={deterministic_intent}."
                )[:500]

            return (
                overall,
                reason,
                {
                    "engagement_score": engagement_score,
                    "intent_score": intent_score,
                    "recommended_service": service,
                    "tags": tags[:10],
                },
            )

        except Exception as exc:
            logger.error("AI scoring failed: %s", exc)

            return (
                deterministic_score,
                (
                    "Deterministic scoring used because "
                    f"AI scoring failed: {exc}"
                )[:500],
                {
                    "engagement_score": deterministic_score,
                    "intent_score": deterministic_intent,
                    "recommended_service": deterministic_service,
                    "tags": deterministic_tags[:10],
                },
            )



