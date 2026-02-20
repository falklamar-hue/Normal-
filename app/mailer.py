from __future__ import annotations

import smtplib
from email.message import EmailMessage


class Mailer:
    def __init__(self, db) -> None:
        self.db = db

    def smtp_settings(self) -> dict:
        return {
            "host": self.db.get_setting("smtp_host", ""),
            "port": int(self.db.get_setting("smtp_port", "465") or 465),
            "user": self.db.get_setting("smtp_user", ""),
            "password": self.db.get_setting("smtp_password", ""),
            "from_email": self.db.get_setting("smtp_from", ""),
        }

    def send_html(self, to_email: str, subject: str, html: str) -> None:
        cfg = self.smtp_settings()
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg["from_email"] or cfg["user"]
        msg["To"] = to_email
        msg.set_content("Rapporten finnes i HTML-format.")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=20) as smtp:
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
