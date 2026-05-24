"""Email delivery for LODE — branded HTML templates (see email_templates.py).

Transport preference: Resend → SendGrid → SMTP → local outbox (demo). Every send
records an automation_event in Supabase for the live admin feed, and honors
EMAIL_OVERRIDE (route all mail to one inbox for Resend test mode).

Senders, one per email.docx scenario:
  - send_sop_email            Email 1 · booking confirmation + SOP (navy)
  - send_hitl_email           Email 2 · HITL approval request (brown)
  - send_work_order_email     Email 3 · maintenance work order (purple)
  - send_monthly_report_email Email 4 · monthly utilization report (green)
"""

from __future__ import annotations

import base64
import json
import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import httpx

from vein.config import DATA_DIR, settings
from vein.models.experiment import ExperimentContext
from vein.services import email_templates as T

logger = logging.getLogger("vein.email")

OUTBOX_DIR = DATA_DIR / "email_outbox"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# An attachment is (filename, bytes, mime_type).
Attachment = tuple[str, bytes, str]


def _outbox_record(record: dict) -> str:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    rid = f"mail_{uuid.uuid4().hex[:10]}"
    record["id"] = rid
    record["created_at"] = datetime.now().isoformat()
    with (OUTBOX_DIR / "outbox.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return rid


def read_outbox(limit: int = 50) -> list[dict]:
    path = OUTBOX_DIR / "outbox.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


# --------------------------------------------------------------------------
# Transports
# --------------------------------------------------------------------------
def _via_resend(to_list, subject, text, html, attachments: list[Attachment]) -> bool:
    payload: dict = {"from": settings.resend_from, "to": to_list, "subject": subject}
    if text:
        payload["text"] = text
    if html:
        payload["html"] = html
    if attachments:
        payload["attachments"] = [{"filename": f, "content": _b64(b)} for f, b, _ in attachments]
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        if resp.status_code in (200, 201):
            return True
        logger.warning("Resend failed %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resend error: %s", exc)
    return False


def _via_sendgrid(to_list, subject, text, html, attachments: list[Attachment]) -> bool:
    content = []
    if text:
        content.append({"type": "text/plain", "value": text})
    if html:
        content.append({"type": "text/html", "value": html})
    payload: dict = {
        "personalizations": [{"to": [{"email": e} for e in to_list]}],
        "from": {"email": settings.lab_email_from},
        "subject": subject,
        "content": content or [{"type": "text/plain", "value": " "}],
    }
    if attachments:
        payload["attachments"] = [
            {"content": _b64(b), "type": m, "filename": f, "disposition": "attachment"}
            for f, b, m in attachments
        ]
    try:
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        if resp.status_code in (200, 202):
            return True
        logger.warning("SendGrid failed %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:  # noqa: BLE001
        logger.warning("SendGrid error: %s", exc)
    return False


def _via_smtp(to_list, subject, text, html, attachments: list[Attachment]) -> bool:
    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = settings.lab_email_from
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text or " ", "plain"))
        if html:
            alt.attach(MIMEText(html, "html"))
        msg.attach(alt)
        for f, b, m in attachments:
            if m == DOCX_MIME:
                part = MIMEApplication(b, _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document")
            else:
                maintype, _, subtype = m.partition("/")
                part = MIMEBase(maintype or "application", subtype or "octet-stream")
                part.set_payload(b)
                from email import encoders
                encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=f)
            msg.attach(part)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.lab_email_from, to_list, msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMTP error: %s", exc)
    return False


# --------------------------------------------------------------------------
# Dispatcher
# --------------------------------------------------------------------------
def _dispatch(
    intended: list[str],
    subject: str,
    text: str,
    html: str,
    attachments: Optional[list[Attachment]] = None,
) -> dict:
    attachments = attachments or []
    intended = [e for e in intended if e]
    if not intended:
        intended = [settings.lab_email_tech] if settings.lab_email_tech else []

    # Demo override: route everything to one inbox (Resend test-mode limit).
    if settings.email_override:
        recipients = [settings.email_override]
        note = f"[Demo delivery] Routed to {settings.email_override}. Intended recipients: {', '.join(intended) or '—'}."
        text = f"{text}\n\n{note}"
        if html and "</body>" in html:
            banner = (f'<div style="text-align:center;font-size:11px;color:#9aa0a6;padding:6px 0 14px;">{note}</div>')
            html = html.replace("</body>", banner + "</body>")
    else:
        recipients = intended

    transport, sent = "local-outbox", False
    if settings.resend_api_key and recipients:
        if _via_resend(recipients, subject, text, html, attachments):
            transport, sent = "resend", True
    if not sent and settings.sendgrid_api_key and recipients:
        if _via_sendgrid(recipients, subject, text, html, attachments):
            transport, sent = "sendgrid", True
    if not sent and settings.smtp_host and recipients:
        if _via_smtp(recipients, subject, text, html, attachments):
            transport, sent = "smtp", True

    rid = _outbox_record({
        "to": recipients, "subject": subject, "body": text,
        "attachment": ", ".join(f for f, _, _ in attachments),
        "transport": transport, "delivered": sent,
    })

    try:
        from vein.db.database import record_automation_event

        record_automation_event(
            kind="email",
            status="sent" if sent else "queued",
            target=", ".join(recipients),
            detail=subject,
            payload={"transport": transport, "attachments": [f for f, _, _ in attachments], "intended": intended},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("automation_event (email) not recorded: %s", exc)

    return {"sent": sent, "transport": transport, "id": rid, "to": recipients}


def _read_attachment(path: Optional[Path], mime: str = DOCX_MIME) -> list[Attachment]:
    if path and path.exists():
        return [(path.name, path.read_bytes(), mime)]
    return []


# --------------------------------------------------------------------------
# Email 1 — Booking confirmation + SOP
# --------------------------------------------------------------------------
def send_sop_email(
    ctx: ExperimentContext,
    sop_path: Optional[str],
    session_summary: str = "",
    *,
    booking_code: str = "",
    instrument: str = "",
    location: str = "",
    when: str = "",
    fit_score: int = 0,
    grade: str = "",
    approved_by: str = "Auto-approved (fit ≥ threshold)",
    checklist: Optional[list[dict]] = None,
    ics_text: Optional[str] = None,
) -> dict:
    if not sop_path:
        return {"sent": False, "reason": "no SOP path"}
    path = Path(sop_path)
    instrument = instrument or (ctx.material_type or "Instrument")
    subject = f"LODE booking confirmed: {booking_code or ctx.material_type or 'session'} — {instrument}"

    html = T.booking_confirmation_html(
        researcher=ctx.researcher_name or "Researcher",
        booking_code=booking_code or "—",
        instrument=instrument,
        location=location or "—",
        when=when or session_summary,
        experiment=ctx.analysis_goal or ctx.material_type or "—",
        fit_score=fit_score,
        grade=grade or "—",
        approved_by=approved_by,
        checklist=checklist or [],
        sop_filename=path.name,
        ics_filename=f"LODE_Session_{booking_code or 'session'}.ics",
    )
    text = (
        f"Your lab session has been confirmed.\n\nBooking: {booking_code}\n"
        f"Instrument: {instrument} — {location}\nWhen: {when}\n"
        f"Fit: {fit_score}/100 (Grade {grade})\n\nThe customized SOP is attached."
    )

    attachments = _read_attachment(path)
    if ics_text:
        attachments.append((f"LODE_Session_{booking_code or 'session'}.ics", ics_text.encode("utf-8"), "text/calendar"))

    intended = [ctx.researcher_email, settings.lab_email_tech]
    return _dispatch(intended, subject, text, html, attachments)


# --------------------------------------------------------------------------
# Email 2 — HITL approval request
# --------------------------------------------------------------------------
def send_hitl_email(
    *,
    booking_code: str,
    researcher: str,
    instrument: str,
    location: str,
    when: str,
    experiment: str,
    fit_score: int,
    grade: str,
    confidence: int,
    training_status: str,
    alert_title: str,
    alert_text: str,
    reasoning: list[str],
    event_id: int | None = None,
) -> dict:
    manager_email = settings.lab_email_tech
    subject = f"Action required: LODE booking {booking_code} needs your review"
    # If we have a row id in the automation_events table, the link points at
    # /governance?hitl=<id>&action=approve|deny — the Governance page calls
    # the backend endpoint and flips the badge to "approved" or "denied".
    qkey = f"hitl={event_id}" if event_id else f"approve={booking_code}"
    approve = f"{T.DASH_URL}/governance?{qkey}&action=approve"
    deny = f"{T.DASH_URL}/governance?{qkey}&action=deny"
    html = T.hitl_approval_html(
        manager="Dr. Morse", booking_code=booking_code, researcher=researcher,
        instrument=instrument, location=location, when=when, experiment=experiment,
        fit_score=fit_score, grade=grade, confidence=confidence, training_status=training_status,
        alert_title=alert_title, alert_text=alert_text, reasoning=reasoning,
        approve_url=approve, deny_url=deny,
    )
    text = f"Booking {booking_code} flagged for review.\n{alert_title}: {alert_text}\nApprove: {approve}\nDeny: {deny}"
    return _dispatch([manager_email], subject, text, html, [])


# --------------------------------------------------------------------------
# Email 3 — Maintenance work order
# --------------------------------------------------------------------------
def send_work_order_email(
    *,
    work_order_code: str,
    instrument: str,
    location: str,
    usage_hours: float,
    interval_hours: float,
    last_calibrated: str,
    issue_type: str,
    severity: str,
    triggered_by: str,
    anomaly: str,
    actions: list[str],
) -> dict:
    recipients = [settings.lab_email_tech, settings.lab_email_facilities]
    subject = f"Maintenance required: {work_order_code} — {issue_type}"
    html = T.work_order_html(
        work_order_code=work_order_code, instrument=instrument, location=location,
        usage_hours=usage_hours, interval_hours=interval_hours, last_calibrated=last_calibrated,
        issue_type=issue_type, severity=severity, triggered_by=triggered_by, anomaly=anomaly,
        actions=actions, wo_filename=f"WorkOrder_{work_order_code}.docx",
    )
    text = f"{work_order_code} — {issue_type} on {instrument}. Severity {severity}. {anomaly}"
    return _dispatch(recipients, subject, text, html, [])


# --------------------------------------------------------------------------
# Email 4 — Monthly utilization report
# --------------------------------------------------------------------------
def send_monthly_report_email(
    *,
    period: str,
    total_bookings: int,
    sops_generated: int,
    avg_fit: str,
    open_work_orders: int,
    utilization: list[tuple[str, int]],
    insights: list[str],
    action_title: str = "",
    action_text: str = "",
) -> dict:
    recipients = [settings.lab_email_chair, settings.lab_email_tech]
    subject = f"LODE monthly report — {period} · Shared Instrumentation Facility"
    html = T.monthly_report_html(
        recipients_greeting="Dr. Williams and Dr. Morse", period=period,
        total_bookings=total_bookings, sops_generated=sops_generated, avg_fit=avg_fit,
        open_work_orders=open_work_orders, utilization=utilization, insights=insights,
        action_title=action_title, action_text=action_text,
        pdf_filename=f"LODE_Monthly_Report_{period.replace(' ', '_')}.pdf",
    )
    text = f"LODE monthly report — {period}. Bookings: {total_bookings}, SOPs: {sops_generated}, Avg fit: {avg_fit}, Open WOs: {open_work_orders}."
    return _dispatch(recipients, subject, text, html, [])


# Backwards-compatible alias.
def notify_sop_ready(ctx: ExperimentContext, sop_path: Optional[str]) -> bool:
    return send_sop_email(ctx, sop_path).get("sent", False)
