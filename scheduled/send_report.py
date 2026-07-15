#!/usr/bin/env python3
"""
Emails the results of a scheduled batch run, or an alert if the pre-run test
gate failed. Provider-agnostic SMTP (works with Gmail, Google Workspace,
Microsoft 365, or any other SMTP-over-SSL provider) - credentials come from
environment variables, nothing sensitive lives in the repo. The subject/
greeting/signature text comes from scheduled/email_template.json, which is
NOT sensitive and can be edited directly.

Required env vars:
    SMTP_HOST         - e.g. smtp.gmail.com, smtp.office365.com
    SMTP_PORT         - defaults to 465 (SMTP over SSL)
    SMTP_USERNAME     - the account to send from / authenticate as
    SMTP_PASSWORD     - that account's password or app password
    REPORT_RECIPIENT  - comma-separated recipient address(es)

CLI usage:
    uv run python scheduled/send_report.py success scheduled_results.json
    uv run python scheduled/send_report.py alert "pytest failed, see workflow logs"
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.url_parser import extract_booking_params  # noqa: E402

XLSX_MIME = ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "email_template.json")

# Hardcoded (not locale-dependent) so month names in the email are always English
# regardless of what locale the machine running this happens to have configured.
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def load_template(path: str = TEMPLATE_PATH) -> Dict[str, str]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _smtp_config():
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    recipients = [r.strip() for r in os.environ["REPORT_RECIPIENT"].split(",") if r.strip()]
    if not recipients:
        raise ValueError("REPORT_RECIPIENT is set but contains no addresses")
    return host, port, username, password, recipients


def send_email(subject: str, body: str, attachments: Optional[Sequence[str]] = None) -> None:
    host, port, username, password, recipients = _smtp_config()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    for path in attachments or []:
        with open(path, "rb") as f:
            data = f.read()
        maintype, subtype = XLSX_MIME
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=os.path.basename(path))

    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(username, password)
        smtp.send_message(msg)


def _format_bullet(url: str) -> str:
    """"* 15-16 July, hotels" - built from the search's own checkin/checkout, so
    this always reflects whichever 3 months actually ran, not a hardcoded date."""
    params = extract_booking_params(url)
    checkin = datetime.strptime(params["check_in"], "%Y-%m-%d").date()
    checkout = datetime.strptime(params["check_out"], "%Y-%m-%d").date()
    month_name = MONTH_NAMES[checkin.month - 1]
    return f"* {checkin.day}-{checkout.day} {month_name}, hotels"


def build_success_report(results: List[Dict[str, Any]], template: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Pure function (no I/O) so the formatting logic can be tested without sending mail."""
    template = template if template is not None else load_template()
    succeeded_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]

    bullets = [_format_bullet(r["url"]) for r in succeeded_results]
    attachments = [r["output_file"] for r in succeeded_results]

    body_parts = [template["greeting"], "", template["intro"], "", *bullets]

    if failed_results:
        body_parts += [
            "",
            f"Note: {len(failed_results)} of {len(results)} searches failed and have no attachment:",
        ]
        for r in failed_results:
            body_parts.append(f"  - {r['url']} ({r['error']})")

    if template.get("closing"):
        body_parts += ["", template["closing"]]

    return {"subject": template["subject"], "body": "\n".join(body_parts), "attachments": attachments}


def send_success_report(results: List[Dict[str, Any]]) -> None:
    report = build_success_report(results)
    send_email(report["subject"], report["body"], report["attachments"])


def send_test_failure_alert(details: str) -> None:
    template = load_template()
    subject = f"{template['subject']} - FAILED (tests did not pass, scrape skipped)"
    body = (
        f"{template['greeting']}\n\n"
        "The pre-run test suite failed, so no scraping was attempted this month.\n"
        "This usually means booking.com changed its page markup and the selectors\n"
        "need updating - see tests/test_live_smoke.py and tests/refresh_fixtures.py "
        "in the repo.\n\n"
        f"{details}"
    )
    send_email(subject, body)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: send_report.py success <results.json> | alert <details>")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "success":
        results_path = sys.argv[2] if len(sys.argv) > 2 else "scheduled_results.json"
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f)
        send_success_report(results)
    elif mode == "alert":
        details = sys.argv[2] if len(sys.argv) > 2 else "(no details provided)"
        send_test_failure_alert(details)
    else:
        print(f"Unknown mode: {mode!r} (expected 'success' or 'alert')")
        sys.exit(1)


if __name__ == "__main__":
    main()
