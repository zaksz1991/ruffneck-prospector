"""
Free automatic reply detection via Gmail IMAP.
Uses App Password (same as SMTP). No paid APIs.
"""
from typing import List, Dict, Any, Optional
import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta, timezone
import logging
import re

logger = logging.getLogger(__name__)


def _decode_header_value(val) -> str:
    if not val:
        return ""
    parts = decode_header(val)
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            out.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(text)
    return " ".join(out)


def _extract_email(addr: str) -> str:
    if not addr:
        return ""
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", addr)
    return (m.group(0) if m else addr).lower().strip()


class GmailReplyDetector:
    def __init__(self):
        self.user = os.getenv("SMTP_USER") or os.getenv("IMAP_USER")
        self.password = os.getenv("SMTP_PASS") or os.getenv("IMAP_PASS")
        self.host = os.getenv("IMAP_HOST", "imap.gmail.com")
        self.port = int(os.getenv("IMAP_PORT", "993"))

    def is_configured(self) -> bool:
        return bool(self.user and self.password)

    def fetch_recent_replies(self, since_hours: int = 48, max_messages: int = 40) -> List[Dict[str, Any]]:
        """
        Fetch recent INBOX messages that look like replies (In-Reply-To / Re: subject).
        Returns list of {from_email, subject, body, message_id, date}.
        """
        if not self.is_configured():
            return []

        results = []
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port)
            mail.login(self.user, self.password)
            mail.select("INBOX")

            since_date = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%d-%b-%Y")
            # Search recent mail
            status, data = mail.search(None, f'(SINCE {since_date})')
            if status != "OK" or not data or not data[0]:
                mail.logout()
                return []

            ids = data[0].split()
            # Newest first
            ids = list(reversed(ids))[-max_messages:]

            for mid in ids:
                try:
                    st, msg_data = mail.fetch(mid, "(RFC822)")
                    if st != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    subject = _decode_header_value(msg.get("Subject", ""))
                    from_addr = _extract_email(_decode_header_value(msg.get("From", "")))
                    in_reply_to = msg.get("In-Reply-To", "") or ""
                    references = msg.get("References", "") or ""

                    # Prefer messages that look like replies
                    is_reply = bool(in_reply_to or references) or subject.lower().startswith("re:")
                    if not is_reply and not from_addr:
                        continue

                    body = self._get_body(msg)
                    results.append({
                        "from_email": from_addr,
                        "subject": subject,
                        "body": body[:2000],
                        "message_id": msg.get("Message-ID", ""),
                        "in_reply_to": in_reply_to,
                        "date": msg.get("Date", ""),
                        "is_reply": is_reply,
                    })
                except Exception as e:
                    logger.debug(f"Skip message: {e}")

            mail.logout()
        except Exception as e:
            logger.error(f"IMAP fetch failed: {e}")
            return []

        return results

    def _get_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition") or "")
                if ctype == "text/plain" and "attachment" not in disp:
                    try:
                        payload = part.get_payload(decode=True)
                        body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                        break
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                body = str(msg.get_payload())
        return body or ""
