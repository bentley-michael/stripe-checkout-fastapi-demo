# app/utils/send_email.py
import os, base64, logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition, Email
)

log = logging.getLogger(__name__)

SENDGRID_API_KEY  = os.getenv("SENDGRID_API_KEY", "")
EMAIL_SENDER      = os.getenv("EMAIL_SENDER", "contact@content365.xyz")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "Nathan Bentley")
REPLY_TO          = os.getenv("REPLY_TO", "")
EMAIL_CC          = [s.strip() for s in os.getenv("EMAIL_CC","").split(",") if s.strip()]
EMAIL_BCC         = [s.strip() for s in os.getenv("EMAIL_BCC","").split(",") if s.strip()]

def _write_outbox_copy(to_email: str, subject: str, text: str, pdf_bytes: bytes, filename: str) -> str:
    out = Path("outbox"); out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_to = "".join(c for c in (to_email or "unknown") if c.isalnum() or c in ("@", ".", "_", "-"))
    pdf_path = out / f"{stamp}_{safe_to}_{filename or 'report.pdf'}"
    note_path = out / f"{stamp}_{safe_to}_note.txt"
    pdf_path.write_bytes(pdf_bytes or b"")
    note_path.write_text(
        f"TO: {to_email}\nFROM: {EMAIL_SENDER} ({EMAIL_SENDER_NAME})\n"
        f"CC: {', '.join(EMAIL_CC) or '-'}\nBCC: {', '.join(EMAIL_BCC) or '-'}\n"
        f"SUBJECT: {subject}\n\n{text}\n",
        encoding="utf-8"
    )
    return f"dev-outbox:{pdf_path.as_posix()}"

def send_pdf_email(to_email: str, subject: str, text: str, pdf_bytes: bytes, filename: str) -> Optional[str]:
    if not SENDGRID_API_KEY or not EMAIL_SENDER:
        log.warning("SENDGRID not configured; writing to ./outbox")
        return _write_outbox_copy(to_email, subject, text, pdf_bytes, filename)

    try:
        message = Mail(
            from_email=Email(EMAIL_SENDER, EMAIL_SENDER_NAME),
            to_emails=[to_email],
            subject=subject,
            plain_text_content=text,
            html_content=f"<p>{text}</p><p>Report attached.</p>",
        )
        if REPLY_TO:
            message.reply_to = Email(REPLY_TO)

        # CC/BCC if provided
        for addr in EMAIL_CC:
            try: message.add_cc(Email(addr))
            except Exception: pass
        for addr in EMAIL_BCC:
            try: message.add_bcc(Email(addr))
            except Exception: pass

        encoded = base64.b64encode(pdf_bytes or b"").decode("utf-8")
        attachment = Attachment(
            FileContent(encoded),
            FileName(filename or "report.pdf"),
            FileType("application/pdf"),
            Disposition("attachment"),
        )
        try: message.add_attachment(attachment)
        except Exception: message.attachment = attachment

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        resp = sg.send(message)
        log.info("SendGrid response: %s", resp.status_code)
        return "202 Accepted" if resp.status_code in (200, 202) else f"status {resp.status_code}"
    except Exception as e:
        log.warning("SendGrid send failed, using ./outbox: %s", e)
        return _write_outbox_copy(to_email, subject, text, pdf_bytes, filename)
