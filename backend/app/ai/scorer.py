"""
Advanced free AI Lead Scorer (Groq free tier).
Scores intent + influence + niche fit + engagement potential.
"""
from typing import Dict, Any, Tuple
import json
import os
import logging
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LeadScorer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required (free at console.groq.com)")
        self.client = Groq(api_key=self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def score(self, prospect: Dict[str, Any], rules: Dict[str, Any] | None = None) -> Tuple[int, str, Dict[str, Any]]:
        """
        Returns (overall_score 0-100, reason, breakdown_dict)
        """
        rules = rules or self._default_rules()

        prompt = f"""You are an elite B2B / service lead qualification engine.
Score this prospect comprehensively for offering digital services
(digital marketing, websites, AI solutions, graphics design, CV/resume writing, Excel data cleaning).

PROSPECT:
- Platform: {prospect.get('platform')}
- Username / Source: {prospect.get('username')} / {prospect.get('display_name')}
- Comment / Snippet: "{(prospect.get('comment_text') or '')[:600]}"
- Bio: "{(prospect.get('bio_text') or '')[:300]}"
- Followers / Influence proxy: {prospect.get('follower_count', 0)}
- Verified: {prospect.get('is_verified', False)}
- Engagement data: {json.dumps(prospect.get('metadata', {}).get('engagement', {}))}

SCORING DIMENSIONS (return all):
1. intent_score (0-100): How clearly they express need / buying intent for services.
2. influence_score (0-100): Follower count, verification, engagement quality, platform authority.
3. niche_fit (0-100): How well their need matches digital marketing / web / AI / design / CV / Excel services.
4. engagement_potential (0-100): Likelihood they will reply or convert from outreach.

Also return a short overall reason.

Return ONLY valid JSON:
{{
  "intent_score": <int>,
  "influence_score": <int>,
  "niche_fit": <int>,
  "engagement_potential": <int>,
  "overall_score": <int 0-100 weighted>,
  "reason": "<one concise sentence>",
  "recommended_service": "<one of: digital_marketing, website, ai_solution, graphics, cv_resume, excel, other>"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            overall = max(0, min(100, int(data.get("overall_score") or data.get("intent_score", 0))))
            reason = str(data.get("reason", ""))[:300]
            breakdown = {
                "intent": data.get("intent_score", overall),
                "influence": data.get("influence_score", 0),
                "niche_fit": data.get("niche_fit", 0),
                "engagement_potential": data.get("engagement_potential", 0),
                "recommended_service": data.get("recommended_service", "other"),
            }
            return overall, reason, breakdown
        except Exception as e:
            logger.error(f"AI scoring failed: {e}")
            return self._heuristic(prospect, rules)

    def _default_rules(self) -> Dict:
        return {
            "high_intent": [
                "need", "looking for", "hire", "anyone know", "recommend", "budget",
                "price", "cost", "help with", "struggling", "want a", "seeking"
            ],
            "service_keywords": {
                "digital_marketing": ["marketing", "seo", "social media", "ads", "content"],
                "website": ["website", "web developer", "landing page", "shopify", "wordpress"],
                "ai_solution": ["ai", "chatgpt", "automation", "chatbot", "machine learning"],
                "graphics": ["logo", "design", "branding", "flyer", "graphics"],
                "cv_resume": ["resume", "cv", "cover letter", "job application"],
                "excel": ["excel", "spreadsheet", "data cleaning", "pivot", "vba"],
            },
        }

    def _heuristic(self, prospect: Dict[str, Any], rules: Dict) -> Tuple[int, str, Dict]:
        text = ((prospect.get("comment_text") or "") + " " + (prospect.get("bio_text") or "")).lower()
        score = 25
        for s in rules.get("high_intent", []):
            if s in text:
                score += 10
        followers = prospect.get("follower_count") or 0
        influence = min(100, int(followers / 50) if followers else 10)
        if prospect.get("is_verified"):
            influence = min(100, influence + 25)

        niche = 20
        rec = "other"
        for svc, kws in rules.get("service_keywords", {}).items():
            hits = sum(1 for k in kws if k in text)
            if hits > 0:
                niche = min(100, 30 + hits * 20)
                rec = svc
                break

        overall = int(score * 0.5 + influence * 0.2 + niche * 0.3)

        # Enrichment boosts
        if prospect.get("email"):
            overall += 12
        if prospect.get("company_domain") or (prospect.get("metadata") or {}).get("company_domain"):
            overall += 8
        if (prospect.get("email_confidence") or 0) >= 70:
            overall += 5

        overall = max(0, min(100, overall))
        return overall, "Heuristic multi-signal score (AI unavailable)", {
            "intent": score,
            "influence": influence,
            "niche_fit": niche,
            "engagement_potential": 40,
            "recommended_service": rec,
            "enrichment_boost": bool(prospect.get("email") or prospect.get("company_domain")),
        }
