"""
AI Outreach Copywriter - Groq free tier.
Generates short, personalized, compliant messages.
"""
from typing import Dict, Any
import os
import logging
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class Copywriter:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required")
        self.client = Groq(api_key=self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_outreach(
        self,
        prospect: Dict[str, Any],
        channel: str = "email",
        topic: str = "AI career tips",
        sender_name: str = "Alex from RuffNeck",
        extra_instructions: str = "",
    ) -> Dict[str, str]:
        """
        Returns {"subject": "...", "body": "..."}
        Always includes unsubscribe language for email.
        """
        comment = (prospect.get("comment_text") or "")[:280]
        bio = (prospect.get("bio_text") or "")[:200]
        username = prospect.get("username") or "there"
        platform = prospect.get("platform") or "social"

        system = (
            "You write concise, human, high-converting outreach that never sounds spammy. "
            "Reference the exact comment. Offer clear value. Keep under 90 words for email, 40 for DM."
        )

        prompt = f"""Write a personalized {channel} message.

PROSPECT:
- Username: {username}
- Platform: {platform}
- Their comment: "{comment}"
- Bio: "{bio}"

OFFER: Free mini-guide / 1-pager about "{topic}"
SENDER: {sender_name}

REQUIREMENTS:
- Reference their specific comment naturally
- Soft CTA (reply "yes" / "send it")
- For email: include subject line + body with unsubscribe note at bottom
- No hype, no fake urgency
- Sound like a real person
{extra_instructions}

Return ONLY JSON:
{{
  "subject": "<subject or empty string for DM>",
  "body": "<full message body>"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            import json
            data = json.loads(response.choices[0].message.content)
            return {
                "subject": data.get("subject") or f"Quick resource for you, {username}",
                "body": data.get("body") or self._fallback_body(username, comment, topic, sender_name, channel),
            }
        except Exception as e:
            logger.error(f"Copy generation failed: {e}")
            return {
                "subject": f"Resource based on your comment",
                "body": self._fallback_body(username, comment, topic, sender_name, channel),
            }

    def _fallback_body(self, username, comment, topic, sender, channel):
        snippet = (comment[:80] + "...") if len(comment) > 80 else comment
        if channel == "dm":
            return (
                f"Hey {username} — saw your comment: \"{snippet}\".\n\n"
                f"I made a free short guide on {topic}. Want me to send it?"
            )
        return (
            f"Hi {username},\n\n"
            f"I noticed your comment: \"{snippet}\"\n\n"
            f"I put together a free mini-guide on {topic} that might help.\n\n"
            f"Happy to send it over — just reply \"yes\".\n\n"
            f"Best,\n{sender}\n\n"
            f"---\nReply STOP to unsubscribe."
        )
