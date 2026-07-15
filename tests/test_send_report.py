"""
Tests for scheduled/send_report.py's pure formatting logic. Nothing here sends
real email - send_email() itself (the SMTP I/O) is intentionally not covered
by unit tests since it's a thin, well-understood stdlib call; what's worth
testing is that we build the right subject/body/attachments from results.
"""

from scheduled.send_report import build_success_report

TEMPLATE = {
    "subject": "booking data",
    "greeting": "მოგესალმებით,",
    "intro": "გიგზავნით მონაცემებს:",
    "closing": "პატივისცემით,\nსანდრო AI",
}


def _url(checkin: str, checkout: str) -> str:
    return f"https://www.booking.com/searchresults.html?ss=Georgia&checkin={checkin}&checkout={checkout}"


def test_all_succeeded_lists_a_bullet_per_search():
    results = [
        {"success": True, "url": _url("2026-07-15", "2026-07-16"), "output_file": "july.xlsx"},
        {"success": True, "url": _url("2026-08-15", "2026-08-16"), "output_file": "aug.xlsx"},
        {"success": True, "url": _url("2026-09-15", "2026-09-16"), "output_file": "sep.xlsx"},
    ]

    report = build_success_report(results, template=TEMPLATE)

    assert report["subject"] == "booking data"
    assert "მოგესალმებით," in report["body"]
    assert "გიგზავნით მონაცემებს:" in report["body"]
    assert "* 15-16 July, hotels" in report["body"]
    assert "* 15-16 August, hotels" in report["body"]
    assert "* 15-16 September, hotels" in report["body"]
    assert "პატივისცემით,\nსანდრო AI" in report["body"]
    assert report["attachments"] == ["july.xlsx", "aug.xlsx", "sep.xlsx"]


def test_bullet_order_matches_result_order():
    results = [
        {"success": True, "url": _url("2026-09-15", "2026-09-16"), "output_file": "sep.xlsx"},
        {"success": True, "url": _url("2026-07-15", "2026-07-16"), "output_file": "july.xlsx"},
    ]

    report = build_success_report(results, template=TEMPLATE)
    body = report["body"]

    assert body.index("September") < body.index("July")


def test_partial_failure_only_attaches_successful_files_and_notes_failure():
    results = [
        {"success": True, "url": _url("2026-07-15", "2026-07-16"), "output_file": "july.xlsx"},
        {"success": False, "url": _url("2026-08-15", "2026-08-16"), "error": "timeout"},
    ]

    report = build_success_report(results, template=TEMPLATE)

    assert report["attachments"] == ["july.xlsx"]
    assert "* 15-16 July, hotels" in report["body"]
    assert "1 of 2 searches failed" in report["body"]
    assert "timeout" in report["body"]


def test_no_closing_is_omitted_cleanly():
    template = {"subject": "booking data", "greeting": "Hi,", "intro": "Data:", "closing": ""}
    results = [{"success": True, "url": _url("2026-07-15", "2026-07-16"), "output_file": "a.xlsx"}]

    report = build_success_report(results, template=template)

    assert report["body"].strip().endswith("15-16 July, hotels")
