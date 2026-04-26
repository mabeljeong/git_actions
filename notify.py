"""Email notifications via Gmail SMTP.

Reads credentials from env vars (injected by GitHub Secrets in CI):
  - EMAIL_SENDER        Gmail address sending the alert
  - EMAIL_APP_PASSWORD  16-char Gmail app password
  - EMAIL_RECIPIENT     Where to send alerts (defaults to EMAIL_SENDER)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable

from scrapers.base import Job

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class MissingCredentialsError(RuntimeError):
    pass


def _get_creds() -> tuple[str, str, str]:
    sender = os.environ.get("EMAIL_SENDER", "").strip()
    password = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
    recipient = os.environ.get("EMAIL_RECIPIENT", "").strip() or sender
    if not sender or not password:
        raise MissingCredentialsError(
            "EMAIL_SENDER and EMAIL_APP_PASSWORD env vars must be set."
        )
    return sender, password, recipient


def _format_body(new_jobs: list[Job]) -> tuple[str, str]:
    lines_text = [f"{len(new_jobs)} new Product Data Scientist role(s) found:\n"]
    rows_html = []
    by_company: dict[str, list[Job]] = {}
    for job in new_jobs:
        by_company.setdefault(job.company, []).append(job)

    for company, jobs in by_company.items():
        lines_text.append(f"== {company} ({len(jobs)}) ==")
        for j in jobs:
            lines_text.append(f"- {j.title}")
            lines_text.append(f"  Location: {j.location or 'N/A'}")
            if j.company_size:
                lines_text.append(f"  Company size: {j.company_size}")
            lines_text.append(f"  URL: {j.url}")
            lines_text.append("")
        rows_html.append(f"<h3>{company} ({len(jobs)})</h3><ul>")
        for j in jobs:
            rows_html.append(
                f'<li><a href="{j.url}">{j.title}</a>'
                f'<br><small>{j.location or "N/A"}'
                f'{" | Company size: " + j.company_size if j.company_size else ""}'
                "</small></li>"
            )
        rows_html.append("</ul>")

    text = "\n".join(lines_text)
    html = (
        "<html><body>"
        f"<p><b>{len(new_jobs)} new Product Data Scientist role(s) found.</b></p>"
        + "".join(rows_html)
        + "</body></html>"
    )
    return text, html


def send_new_jobs_email(new_jobs: Iterable[Job]) -> None:
    new_jobs = list(new_jobs)
    if not new_jobs:
        return

    sender, password, recipient = _get_creds()

    msg = EmailMessage()
    msg["Subject"] = f"[Job Alert] {len(new_jobs)} new Product Data Scientist role(s)"
    msg["From"] = sender
    msg["To"] = recipient

    text, html = _format_body(new_jobs)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
        server.login(sender, password)
        server.send_message(msg)

    print(f"[notify] Emailed {len(new_jobs)} new job(s) to {recipient}")
