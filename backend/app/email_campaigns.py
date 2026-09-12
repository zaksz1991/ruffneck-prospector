"""
Free email campaigns module.
Primary sender: Gmail SMTP with App Password (500 emails/day personal free).
Alternative: any SMTP (self-hosted Postal, docker-mailserver, etc.).
No paid ESPs required.
"""
from typing import List, Dict, Any, Optional
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)


class FreeEmailSender:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")  # full Gmail address
        self.smtp_pass = os.getenv("SMTP_PASS")  # App Password, not regular password
        self.from_name = os.getenv("FROM_NAME", "RuffNeck Services")
        self.from_email = os.getenv("FROM_EMAIL") or self.smtp_user

    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_pass)

    def send(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "skipped",
                "reason": "SMTP not configured. Set SMTP_USER + SMTP_PASS (Gmail App Password).",
            }

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            return {"status": "sent", "to": to_email}
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return {"status": "failed", "error": str(e)}



    def send_with_attachment(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        attachment_path: str,
        attachment_name: str = None,
        body_html: str = None,
    ):
        """Send email with a file attachment (e.g. PDF guide)."""
        if not self.is_configured():
            return {
                "status": "skipped",
                "reason": "SMTP not configured. Set SMTP_USER + SMTP_PASS (Gmail App Password).",
            }
        import os
        from email.mime.base import MIMEBase
        from email import encoders

        if not attachment_path or not os.path.isfile(attachment_path):
            return {"status": "failed", "error": "Attachment file not found"}

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text or "", "plain"))
        if body_html:
            alt.attach(MIMEText(body_html, "html"))
        msg.attach(alt)

        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        name = attachment_name or os.path.basename(attachment_path)
        part.add_header("Content-Disposition", f'attachment; filename="{name}"')
        msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=45) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            return {"status": "sent", "to": to_email, "attachment": name}
        except Exception as e:
            logger.error(f"SMTP attach send failed: {e}")
            return {"status": "failed", "error": str(e)}


def build_sequence(
    prospect: Dict[str, Any],
    service: str,
    sender_name: str = "Alex",
) -> List[Dict[str, str]]:
    """Generate a 3-email free sequence tailored to the service + prospect."""
    username = prospect.get("username") or "there"
    comment = (prospect.get("comment_text") or "")[:120]
    service_label = service.replace("_", " ").title()

    emails = [
        {
            "day": 0,
            "subject": f"Quick idea for your {service_label.lower()} needs",
            "body": f"""Hi {username},

I noticed your comment: "{comment}"

I help people and businesses with {service_label.lower()}. 
I put together a short free resource that addresses exactly what you mentioned.

Would you like me to send it over? Just reply "yes".

Best,
{sender_name}

---
Reply STOP to unsubscribe.""",
        },
        {
            "day": 3,
            "subject": f"Following up – free {service_label} tip",
            "body": f"""Hi {username},

Just checking in. Last time I offered a free resource related to {service_label.lower()}.

If the timing isn't right, no worries at all. 
If it is, reply and I'll send it immediately (no strings).

{sender_name}

---
Reply STOP to unsubscribe.""",
        },
        {
            "day": 7,
            "subject": f"Last note – {service_label}",
            "body": f"""Hi {username},

I'll close the loop here. If you ever need help with {service_label.lower()}, 
I'm happy to share the free guide or a quick checklist.

Wishing you the best,
{sender_name}

---
Reply STOP to unsubscribe.""",
        },
    ]
    return emails
