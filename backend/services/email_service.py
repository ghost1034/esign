"""SMTP delivery. Success is recorded only after the SMTP server accepts mail."""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from core.runtime import is_local, require_cloud_value

logger = logging.getLogger(__name__)

class EmailService:
    def send_email(self, to_email, subject, body_text, reply_to=None):
        return self.send_html_email(to_email, subject, None, body_text, reply_to=reply_to)

    def send_html_email(self, to_email, subject, html_body, text_body, reply_to=None, inline_images=None, attachments=None):
        message = EmailMessage()
        message["To"] = to_email
        message["From"] = os.getenv("SMTP_FROM") or ("esign <noreply@localhost>" if is_local() else require_cloud_value("SMTP_FROM"))
        message["Subject"] = subject
        if reply_to: message["Reply-To"] = reply_to
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")
            for cid, content, mime_type, filename in inline_images or []:
                main, sub = mime_type.split("/", 1)
                message.get_payload()[-1].add_related(content, maintype=main, subtype=sub, cid=f"<{cid}>", filename=filename)
        for filename, content, mime_type in attachments or []:
            main, sub = mime_type.split("/", 1)
            message.add_attachment(content, maintype=main, subtype=sub, filename=filename)
        try:
            mode = os.getenv("SMTP_SECURITY", "none" if is_local() else "starttls")
            if mode not in {"none", "ssl", "starttls"} or (not is_local() and mode == "none"):
                raise ValueError("Production SMTP requires ssl or starttls")
            host = os.getenv("SMTP_HOST") or ("127.0.0.1" if is_local() else require_cloud_value("SMTP_HOST"))
            factory = smtplib.SMTP_SSL if mode == "ssl" else smtplib.SMTP
            with factory(host, int(os.getenv("SMTP_PORT", "1025" if is_local() else "587")), timeout=30) as smtp:
                if mode == "starttls": smtp.starttls(context=ssl.create_default_context())
                if os.getenv("SMTP_USERNAME"): smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
                refused = smtp.send_message(message)
                return not refused
        except Exception:
            logger.exception("SMTP delivery failed")
            return False

email_service = EmailService()
