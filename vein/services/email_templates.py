"""Branded HTML email templates for LODE (match email.docx designs).

Four email types, each with a colored header band, label/value tables, tinted
alert callouts, and a footer — built with table-based, inline-CSS HTML so they
render consistently across email clients (Gmail, Outlook, Apple Mail).

Builders (all return a complete HTML document string):
  - booking_confirmation_html  (navy)   — Email 1
  - hitl_approval_html         (brown)  — Email 2
  - work_order_html            (purple) — Email 3
  - monthly_report_html        (green)  — Email 4
"""

from __future__ import annotations

from html import escape
from typing import Optional

# Palette
NAVY = "#21314f"
GOLD = "#c79a3e"
BROWN = "#7a3d0c"
PURPLE = "#4c3d99"
GREEN = "#14543a"
INK = "#1f2937"
GRAY = "#6b7280"
LIGHT = "#f4f5f7"
BORDER = "#e5e7eb"
CITE = "#3b6fb5"

DASH_URL = "http://127.0.0.1:5173"
SUBTITLE = "Lab Operations &amp; Data Engine · Colorado School of Mines"


def _e(s) -> str:
    return escape(str(s if s is not None else ""))


def _document(inner: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px 0;background:#eef0f3;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:{INK};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:#ffffff;border:1px solid {BORDER};border-radius:10px;overflow:hidden;">
      {inner}
    </table>
  </td></tr></table>
</body></html>"""


def _header(bg: str, pill_label: str = "", wordmark_color: str = "#ffffff", subtitle: str = SUBTITLE) -> str:
    pill = ""
    if pill_label:
        pill = (
            f'<td align="right" valign="middle"><span style="background:rgba(255,255,255,0.18);'
            f'color:#ffffff;font-size:12px;font-weight:600;padding:6px 12px;border-radius:999px;'
            f'white-space:nowrap;">{_e(pill_label)}</span></td>'
        )
    return f"""
    <tr><td style="background:{bg};padding:22px 28px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td valign="middle">
          <div style="color:{wordmark_color};font-size:22px;font-weight:800;letter-spacing:0.5px;line-height:1;">LODE</div>
          <div style="color:rgba(255,255,255,0.72);font-size:11px;margin-top:5px;">{subtitle}</div>
        </td>
        {pill}
      </tr></table>
    </td></tr>"""


def _body_open() -> str:
    return '<tr><td style="padding:26px 28px;">'


def _body_close() -> str:
    return "</td></tr>"


def _greeting(name: str, intro: str) -> str:
    return (
        f'<p style="font-size:15px;margin:0 0 14px;">Hi {_e(name)},</p>'
        f'<p style="font-size:14px;line-height:1.6;color:#374151;margin:0 0 20px;">{intro}</p>'
    )


def _kv_table(rows: list[tuple[str, str]], striped: bool = True) -> str:
    out = [f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
           f'style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;margin:0 0 20px;">']
    for i, (k, v) in enumerate(rows):
        bg = "#fafbfc" if (striped and i % 2 == 0) else "#ffffff"
        out.append(
            f'<tr style="background:{bg};">'
            f'<td style="padding:11px 14px;font-size:13px;color:{GRAY};width:38%;border-bottom:1px solid {BORDER};">{_e(k)}</td>'
            f'<td style="padding:11px 14px;font-size:13px;color:{INK};font-weight:600;border-bottom:1px solid {BORDER};">{v}</td>'
            f'</tr>'
        )
    out.append("</table>")
    return "".join(out)


def _alert(title: str, text: str, *, bg: str, border: str, color: str, icon: str = "&#9888;") -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">'
        f'<tr><td style="background:{bg};border:1px solid {border};border-left:4px solid {border};border-radius:8px;padding:14px 16px;">'
        f'<div style="font-size:13px;font-weight:700;color:{color};margin-bottom:5px;">{icon} {_e(title)}</div>'
        f'<div style="font-size:13px;line-height:1.55;color:{color};">{text}</div>'
        f'</td></tr></table>'
    )


def _section_label(text: str) -> str:
    return (f'<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:{GRAY};'
            f'text-transform:uppercase;margin:0 0 12px;">{_e(text)}</div>')


def _checklist(steps: list[dict]) -> str:
    """steps: [{text, citation}] — numbered badges + inline blue italic citation."""
    rows = []
    for i, s in enumerate(steps, 1):
        cite = (f' <span style="color:{CITE};font-style:italic;font-size:12px;">[{_e(s.get("citation"))}]</span>'
                if s.get("citation") else "")
        rows.append(
            f'<tr>'
            f'<td valign="top" style="width:26px;padding:0 10px 14px 0;">'
            f'<div style="width:22px;height:22px;border-radius:50%;background:{NAVY};color:#fff;'
            f'font-size:12px;font-weight:700;text-align:center;line-height:22px;">{i}</div></td>'
            f'<td valign="top" style="padding:0 0 14px;font-size:13px;line-height:1.5;color:#374151;">{_e(s.get("text"))}{cite}</td>'
            f'</tr>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{LIGHT};border:1px solid {BORDER};border-radius:8px;padding:16px;margin:0 0 20px;">'
        f'<tr><td>{_section_label("SOP preview — pre-session checklist")}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
        f'</td></tr></table>'
    )


def _bullets(items: list[str], *, bg: str, border: str, color: str, label: str) -> str:
    lis = "".join(
        f'<tr><td valign="top" style="width:14px;color:{border};padding:0 8px 9px 0;font-size:13px;">&bull;</td>'
        f'<td valign="top" style="padding:0 0 9px;font-size:13px;line-height:1.5;color:{color};">{it}</td></tr>'
        for it in items
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{bg};border:1px solid {border};border-radius:8px;padding:16px;margin:0 0 20px;">'
        f'<tr><td>{_section_label(label)}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{lis}</table></td></tr></table>'
    )


def _attachments(files: list[tuple[str, str]]) -> str:
    """files: [(icon, name)]"""
    chips = []
    for icon, name in files:
        chips.append(
            f'<span style="display:inline-block;border:1px solid {BORDER};border-radius:8px;'
            f'padding:8px 12px;font-size:12px;color:{INK};margin:0 8px 8px 0;background:#fff;">'
            f'{icon}&nbsp; {_e(name)}</span>'
        )
    return f'<div style="margin:0 0 18px;">{"".join(chips)}</div>'


def _button(label: str, url: str, bg: str, color: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 8px;">'
        f'<tr><td align="center" style="background:{bg};border-radius:8px;">'
        f'<a href="{_e(url)}" style="display:block;padding:14px;font-size:14px;font-weight:700;'
        f'color:{color};text-decoration:none;">{_e(label)}</a></td></tr></table>'
    )


def _two_buttons(b1: tuple[str, str], b2: tuple[str, str]) -> str:
    (l1, u1), (l2, u2) = b1, b2
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 8px;"><tr>'
        f'<td width="50%" style="padding-right:6px;"><a href="{_e(u1)}" style="display:block;text-align:center;'
        f'border:1px solid {BORDER};border-radius:8px;padding:12px;font-size:14px;font-weight:600;color:{INK};text-decoration:none;">&#10003; {_e(l1)}</a></td>'
        f'<td width="50%" style="padding-left:6px;"><a href="{_e(u2)}" style="display:block;text-align:center;'
        f'border:1px solid {BORDER};border-radius:8px;padding:12px;font-size:14px;font-weight:600;color:{INK};text-decoration:none;">&#10005; {_e(l2)}</a></td>'
        f'</tr></table>'
    )


def _footer(note: str) -> str:
    return (
        f'<tr><td style="padding:18px 28px 26px;border-top:1px solid {BORDER};">'
        f'<p style="text-align:center;font-size:11px;line-height:1.7;color:{GRAY};margin:0;">'
        f'LODE — Lab Operations &amp; Data Engine<br>'
        f'Colorado School of Mines · Shared Instrumentation Facility<br>{_e(note)}</p>'
        f'</td></tr>'
    )


def _progress_bar(value: float, limit: float, color: str = "#dc2626") -> str:
    pct = min(100, int((value / limit) * 100)) if limit else 0
    return (
        f'<div style="font-size:12px;color:{GRAY};margin:0 0 6px;">Usage since last calibration '
        f'<span style="float:right;font-weight:700;color:{color};">{value:.0f}h / {limit:.0f}h limit</span></div>'
        f'<div style="background:{BORDER};border-radius:999px;height:8px;overflow:hidden;margin:0 0 4px;">'
        f'<div style="background:{color};height:8px;width:{pct}%;border-radius:999px;"></div></div>'
        f'<div style="font-size:11px;color:{color};margin:0 0 18px;">{pct}% of calibration interval — overdue</div>'
    )


# --------------------------------------------------------------------------
# Email 1 — Booking confirmation + SOP (navy)
# --------------------------------------------------------------------------
def _references_block(references: list[dict]) -> str:
    """Render RAG references as a labeled list. Each link deep-links into the
    `/knowledge` page with source/section/page query params so clicking the
    citation opens the actual cited chunk, not just a generic admin page."""
    if not references:
        return ""
    from urllib.parse import urlencode

    lis = []
    for i, r in enumerate(references[:8], 1):
        params = {}
        if r.get("source"):  params["source"]  = r["source"]
        if r.get("section"): params["section"] = r["section"]
        if r.get("page"):    params["page"]    = r["page"]
        url = f"{DASH_URL}/knowledge?" + urlencode(params)
        label_parts = []
        if r.get("source"):  label_parts.append(r["source"])
        if r.get("section"): label_parts.append(r["section"])
        if r.get("page"):    label_parts.append(f"p.{r['page']}")
        label = _e(" — ".join(label_parts) or r.get("label") or r.get("source", ""))
        lis.append(
            f'<tr><td valign="top" style="width:22px;color:{CITE};padding:0 6px 8px 0;font-size:12px;font-weight:700;">[{i}]</td>'
            f'<td valign="top" style="padding:0 0 8px;font-size:12px;line-height:1.5;color:#374151;">'
            f'<a href="{_e(url)}" style="color:{CITE};text-decoration:none;">{label}</a>'
            f' <span style="color:#9ca3af;">→ open in knowledge base</span></td></tr>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#f7fafc;border:1px solid {BORDER};border-radius:8px;padding:16px;margin:0 0 20px;">'
        f'<tr><td>{_section_label("RAG references — grounding sources for this SOP")}'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(lis)}</table>'
        f'</td></tr></table>'
    )


def booking_confirmation_html(
    *, researcher: str, booking_code: str, instrument: str, location: str,
    when: str, experiment: str, fit_score: int, grade: str, approved_by: str,
    checklist: list[dict], sop_filename: str, ics_filename: str,
    intro: str = "", prep_tip: str = "", references: list[dict] | None = None,
) -> str:
    rows = [
        ("Booking ID", _e(booking_code)),
        ("Instrument", f"{_e(instrument)} — {_e(location)}"),
        ("Date &amp; time", _e(when)),
        ("Experiment", _e(experiment)),
        ("Fit score", f"{fit_score} / 100 (Grade {_e(grade)})"),
        ("Approved by", _e(approved_by)),
    ]
    intro_html = _e(intro) if intro else (
        "Your lab session has been confirmed. A customized Standard Operating Procedure has been "
        "generated for your experiment and is attached to this email. Please review it before your session."
    )
    prep_block = ""
    if prep_tip:
        prep_block = _alert(
            "Prep tip", _e(prep_tip),
            bg="#f0f9ff", border="#0284c7", color="#075985", icon="&#128161;",
        )
    inner = (
        _header(NAVY, wordmark_color=GOLD)
        + _body_open()
        + _greeting(researcher, intro_html)
        + _kv_table(rows)
        + prep_block
        + _checklist(checklist)
        + _references_block(references or [])
        + _attachments([("&#128196;", sop_filename), ("&#128197;", ics_filename)])
        + _button("View booking in LODE dashboard", f"{DASH_URL}/bookings", NAVY, GOLD)
        + _body_close()
        + _footer("This is an automated message. Do not reply to this email.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 2 — HITL approval request (brown)
# --------------------------------------------------------------------------
def hitl_approval_html(
    *, manager: str, booking_code: str, researcher: str, instrument: str, location: str,
    when: str, experiment: str, fit_score: int, grade: str, confidence: int,
    training_status: str, alert_title: str, alert_text: str, reasoning: list[str],
    approve_url: str, deny_url: str, intro: str = "",
) -> str:
    rows = [
        ("Booking ID", _e(booking_code)),
        ("Researcher", _e(researcher)),
        ("Instrument", f"{_e(instrument)} — {_e(location)}"),
        ("Requested slot", _e(when)),
        ("Experiment", _e(experiment)),
        ("Fit score", f"{fit_score} / 100 (Grade {_e(grade)}) &nbsp;<span style='color:{BROWN};font-weight:600;'>Conf. {confidence}%</span>"),
        ("Training status", _e(training_status)),
    ]
    intro_html = _e(intro) if intro else (
        "A booking request has been flagged by the LODE safety gate and requires your manual review "
        "before it can be confirmed. Please approve or deny using the buttons below."
    )
    inner = (
        _header(BROWN, pill_label="⚠ Action required")
        + _body_open()
        + _greeting(manager, intro_html)
        + _alert(alert_title, alert_text, bg="#fdf6e3", border="#e0b34d", color="#7a4a0c")
        + _kv_table(rows, striped=False)
        + _bullets(reasoning, bg=LIGHT, border="#c98a3c", color="#374151",
                   label="Agent reasoning chain — why this was escalated")
        + _two_buttons(("Approve booking", approve_url), ("Deny booking", deny_url))
        + f'<p style="text-align:center;font-size:12px;color:{GRAY};margin:6px 0 0;">These action links expire in 48 hours. After expiry, the booking will be automatically cancelled.</p>'
        + _body_close()
        + _footer("This is an automated message. Reply to this email to contact the researcher directly.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 3 — Maintenance work order (purple)
# --------------------------------------------------------------------------
def work_order_html(
    *, work_order_code: str, instrument: str, location: str, usage_hours: float,
    interval_hours: float, last_calibrated: str, issue_type: str, severity: str,
    triggered_by: str, anomaly: str, actions: list[str], wo_filename: str,
) -> str:
    rows = [
        ("Issue type", _e(issue_type)),
        ("Severity", _e(severity)),
        ("Last calibration", _e(last_calibrated)),
        ("Triggered by", _e(triggered_by)),
        ("Anomaly noted", _e(anomaly)),
        ("Instrument status", "Bookings blocked pending maintenance clearance"),
    ]
    wo_card = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{LIGHT};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin:0 0 16px;">'
        f'<tr><td><div style="font-size:11px;color:{GRAY};">Work order {_e(work_order_code)}</div>'
        f'<div style="font-size:15px;font-weight:700;color:{INK};margin-top:2px;">{_e(instrument)}</div>'
        f'<div style="font-size:12px;color:{GRAY};margin-top:2px;">&#128205; {_e(location)}</div></td></tr></table>'
    )
    inner = (
        _header(PURPLE, pill_label="\U0001f527 Maintenance work order")
        + _body_open()
        + _greeting(
            "Dr. Morse and Facilities Team",
            "LODE's Post-Run Analyzer (Agent 5) has generated a maintenance work order following a recent "
            "session. The instrument usage hours have exceeded the recommended calibration interval. Immediate "
            "scheduling of maintenance is recommended.",
        )
        + wo_card
        + _progress_bar(usage_hours, interval_hours)
        + _kv_table(rows, striped=False)
        + _bullets(actions, bg="#f1effb", border=PURPLE, color="#374151",
                   label="Recommended actions — sourced from RAG corpus")
        + _attachments([("&#128196;", wo_filename)])
        + _button("Open work order in LODE dashboard", f"{DASH_URL}/governance", PURPLE, "#ffffff")
        + _body_close()
        + _footer("Bookings for this instrument are blocked until the work order is marked resolved.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 4 — Monthly utilization report (green)
# --------------------------------------------------------------------------
def _kpi_cards(cards: list[tuple[str, str, bool]]) -> str:
    """cards: [(value, label, is_alert)]"""
    tds = []
    for value, label, alert in cards:
        col = "#dc2626" if alert else INK
        tds.append(
            f'<td width="25%" style="padding:4px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {BORDER};border-radius:8px;"><tr><td style="padding:14px 8px;text-align:center;">'
            f'<div style="font-size:24px;font-weight:800;color:{col};line-height:1;">{value}</div>'
            f'<div style="font-size:11px;color:{GRAY};margin-top:6px;">{_e(label)}</div></td></tr></table></td>'
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 22px;"><tr>{"".join(tds)}</tr></table>'


def _util_bars(items: list[tuple[str, int]]) -> str:
    rows = []
    for name, pct in items:
        high = pct >= 80
        color = "#b91c1c" if high else GREEN
        rows.append(
            f'<tr><td style="width:34%;font-size:13px;color:{INK};padding:6px 8px 6px 0;">{_e(name)}</td>'
            f'<td style="padding:6px 0;"><div style="background:{BORDER};border-radius:999px;height:8px;overflow:hidden;">'
            f'<div style="background:{color};height:8px;width:{min(100,pct)}%;border-radius:999px;"></div></div></td>'
            f'<td style="width:46px;text-align:right;font-size:13px;font-weight:700;color:{color};padding:6px 0 6px 8px;">{pct}%</td></tr>'
        )
    return (f'{_section_label("Instrument utilization")}'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">{"".join(rows)}</table>')


# --------------------------------------------------------------------------
# Email 5 — User notification: HITL pending review (amber)
# --------------------------------------------------------------------------
AMBER = "#b45309"


def user_hitl_pending_html(
    *, researcher: str, booking_code: str, instrument: str, when: str, experiment: str,
    reasons: list[str], alert_title: str, requests_url: str,
) -> str:
    rows = [
        ("Request ID", _e(booking_code)),
        ("Instrument", _e(instrument)),
        ("Requested slot", _e(when)),
        ("Experiment", _e(experiment)),
        ("Status", '<span style="color:#b45309;font-weight:700;">Awaiting supervisor review</span>'),
    ]
    inner = (
        _header(AMBER, pill_label="⏳ Under review")
        + _body_open()
        + _greeting(
            researcher,
            "Your booking request has been received but requires supervisor approval before it can be "
            "confirmed. We have notified your lab manager and you will receive another email when a "
            "decision is made — typically within one business day.",
        )
        + _alert(alert_title, "; ".join(reasons) or "Manual review required.",
                 bg="#fdf6e3", border="#e0b34d", color="#7a4a0c")
        + _kv_table(rows, striped=False)
        + _bullets(reasons, bg=LIGHT, border=AMBER, color="#374151",
                   label="Why this booking requires review")
        + _button("Track this request in LODE", requests_url, AMBER, "#ffffff")
        + _body_close()
        + _footer("You will be emailed as soon as your supervisor reviews this request.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 6 — User notification: HITL approved (green)
# --------------------------------------------------------------------------
def user_hitl_approved_html(
    *, researcher: str, booking_code: str, instrument: str, when: str, experiment: str,
    approver_note: str, complete_url: str, requests_url: str,
) -> str:
    rows = [
        ("Request ID", _e(booking_code)),
        ("Instrument", _e(instrument)),
        ("Approved slot", _e(when)),
        ("Experiment", _e(experiment)),
        ("Status", '<span style="color:#15803d;font-weight:700;">Approved &mdash; ready to confirm</span>'),
    ]
    note_block = ""
    if approver_note:
        note_block = _alert("Note from your supervisor", _e(approver_note),
                            bg="#ecfdf5", border="#10b981", color="#065f46", icon="&#10003;")
    inner = (
        _header(GREEN, pill_label="✓ Approved")
        + _body_open()
        + _greeting(
            researcher,
            "Good news — your supervisor has approved your booking. Click the button below to confirm "
            "the slot. LODE will generate your customized SOP and email you a calendar invite.",
        )
        + _kv_table(rows, striped=False)
        + note_block
        + _button("Confirm booking now", complete_url, GREEN, "#ffffff")
        + f'<p style="text-align:center;font-size:12px;color:{GRAY};margin:8px 0 0;">Or open the My Requests page: <a href="{_e(requests_url)}" style="color:{CITE};">{_e(requests_url)}</a></p>'
        + _body_close()
        + _footer("This approval expires in 48 hours. After expiry the slot is released back to the pool.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 7 — User notification: HITL denied (red)
# --------------------------------------------------------------------------
def user_hitl_denied_html(
    *, researcher: str, booking_code: str, instrument: str, when: str, experiment: str,
    reasons: list[str], approver_note: str, requests_url: str, intake_url: str,
) -> str:
    rows = [
        ("Request ID", _e(booking_code)),
        ("Instrument", _e(instrument)),
        ("Requested slot", _e(when)),
        ("Experiment", _e(experiment)),
        ("Status", '<span style="color:#b91c1c;font-weight:700;">Denied by supervisor</span>'),
    ]
    note_block = ""
    if approver_note:
        note_block = _alert("Note from your supervisor", _e(approver_note),
                            bg="#fef2f2", border="#dc2626", color="#7f1d1d", icon="&#10005;")
    inner = (
        _header("#9f1239", pill_label="✕ Denied")
        + _body_open()
        + _greeting(
            researcher,
            "Your supervisor has reviewed and denied this booking request. Please review the reasons "
            "below and update your experiment plan or training records before resubmitting.",
        )
        + _kv_table(rows, striped=False)
        + note_block
        + _bullets(reasons, bg=LIGHT, border="#dc2626", color="#374151",
                   label="Why this request was denied")
        + _two_buttons(
            ("View request", requests_url),
            ("Start a new booking", intake_url),
        )
        + _body_close()
        + _footer("Contact your lab manager if you have questions about this decision.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 7a — Admin notification: booking change requested (brown, action required)
# Fires when a researcher asks to reschedule or cancel an existing booking.
# Mirrors hitl_approval_html so the approve/deny buttons drive the SAME
# /governance?hitl=<id>&action=… flow the new-booking requests use.
# --------------------------------------------------------------------------
def booking_change_request_html(
    *, manager: str, action: str, booking_code: str, researcher: str,
    instrument: str, from_when: str, to_when: str, reason: str,
    approve_url: str, deny_url: str,
) -> str:
    is_cancel = action == "cancel"
    title = "Cancellation request" if is_cancel else "Reschedule request"
    rows = [
        ("Request ID", _e(booking_code)),
        ("Researcher", _e(researcher)),
        ("Instrument", _e(instrument)),
        ("Current slot", _e(from_when)),
    ]
    if not is_cancel:
        rows.append(("Requested new slot", _e(to_when)))
    rows.append(("Action", f'<span style="color:{AMBER};font-weight:700;">{_e(title)}</span>'))
    reason_block = ""
    if reason:
        reason_block = _alert("Researcher's reason", _e(reason),
                              bg="#fffbeb", border="#f59e0b", color="#92400e")
    verb = "cancel" if is_cancel else "reschedule"
    inner = (
        _header(BROWN, pill_label="● Action required")
        + _body_open()
        + _greeting(
            manager,
            f"{_e(researcher)} has requested to {verb} an existing booking. Approve to apply the change "
            "immediately, or deny to keep the booking unchanged. The researcher is emailed either way.",
        )
        + _kv_table(rows, striped=False)
        + reason_block
        + _two_buttons(("Approve change", approve_url), ("Deny change", deny_url))
        + _body_close()
        + _footer("Raised from the researcher's My schedule page. This change has not been applied yet.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 7b — User notification: booking change applied (reschedule=green, cancel=crimson)
# Sent after an admin APPROVES a change request. The change is already applied,
# so there is no "confirm" CTA — the email just states the outcome.
# --------------------------------------------------------------------------
def booking_change_applied_html(
    *, researcher: str, action: str, booking_code: str, instrument: str,
    when: str, approver_note: str, requests_url: str,
) -> str:
    is_cancel = action == "cancel"
    if is_cancel:
        color, pill = "#9f1239", "✕ Cancelled"
        status = '<span style="color:#b91c1c;font-weight:700;">Cancelled &mdash; slot released</span>'
        when_label = "Released slot"
        lede = ("Your supervisor approved your cancellation request. The booking below has been removed "
                "from the schedule and the slot released back to the pool — no further action is needed.")
        note_bg, note_border, note_color, icon = "#fef2f2", "#dc2626", "#7f1d1d", "&#10005;"
    else:
        color, pill = GREEN, "✓ Rescheduled"
        status = '<span style="color:#15803d;font-weight:700;">Confirmed &mdash; new time</span>'
        when_label = "New confirmed slot"
        lede = ("Your supervisor approved your reschedule request. Your booking is now confirmed for the "
                "new time below — no further action is needed.")
        note_bg, note_border, note_color, icon = "#ecfdf5", "#10b981", "#065f46", "&#10003;"
    rows = [
        ("Request ID", _e(booking_code)),
        ("Instrument", _e(instrument)),
        (when_label, _e(when)),
        ("Status", status),
    ]
    note_block = ""
    if approver_note:
        note_block = _alert("Note from your supervisor", _e(approver_note),
                            bg=note_bg, border=note_border, color=note_color, icon=icon)
    inner = (
        _header(color, pill_label=pill)
        + _body_open()
        + _greeting(researcher, lede)
        + _kv_table(rows, striped=False)
        + note_block
        + _button("Open My schedule", requests_url, color, "#ffffff")
        + _body_close()
        + _footer("This change has already been applied. Contact your lab manager with any questions.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 8 — User notification: maintenance affecting your booking (purple)
# --------------------------------------------------------------------------
def user_maintenance_alert_html(
    *, researcher: str, work_order_code: str, instrument: str, severity: str,
    issue: str, affected_when: str, requests_url: str,
) -> str:
    rows = [
        ("Work order", _e(work_order_code)),
        ("Instrument", _e(instrument)),
        ("Severity", _e(severity)),
        ("Your affected slot", _e(affected_when)),
        ("Status", '<span style="color:#7c3aed;font-weight:700;">Under maintenance</span>'),
    ]
    sev_color = "#dc2626" if severity.lower() == "critical" else "#7c3aed"
    inner = (
        _header(PURPLE, pill_label="\U0001f527 Maintenance")
        + _body_open()
        + _greeting(
            researcher,
            "An instrument you have a booking on has been flagged for maintenance. Your session may be "
            "delayed or rescheduled depending on the work required. We will email you again as soon as "
            "the work order status changes.",
        )
        + _alert("Affected instrument", _e(issue),
                 bg="#f1effb", border=sev_color, color="#4c1d95")
        + _kv_table(rows, striped=False)
        + _button("Track this work order", requests_url, PURPLE, "#ffffff")
        + _body_close()
        + _footer("No action is required from you right now. Bookings on this instrument are paused.")
    )
    return _document(inner)


# --------------------------------------------------------------------------
# Email 9 — User notification: maintenance resolved (green)
# --------------------------------------------------------------------------
def user_maintenance_resolved_html(
    *, researcher: str, work_order_code: str, instrument: str, affected_when: str,
    requests_url: str,
) -> str:
    rows = [
        ("Work order", _e(work_order_code)),
        ("Instrument", _e(instrument)),
        ("Your slot", _e(affected_when)),
        ("Status", '<span style="color:#15803d;font-weight:700;">Resolved &mdash; instrument back online</span>'),
    ]
    inner = (
        _header(GREEN, pill_label="✓ Resolved")
        + _body_open()
        + _greeting(
            researcher,
            "The maintenance work order affecting your booking has been resolved. Your session can "
            "proceed as scheduled. If you need to reschedule, open My Requests in LODE.",
        )
        + _kv_table(rows, striped=False)
        + _button("Open My Requests", requests_url, GREEN, "#ffffff")
        + _body_close()
        + _footer("Thank you for your patience while the instrument was offline.")
    )
    return _document(inner)


def monthly_report_html(
    *, recipients_greeting: str, period: str, total_bookings: int, sops_generated: int,
    avg_fit: str, open_work_orders: int, utilization: list[tuple[str, int]],
    insights: list[str], action_title: str, action_text: str, pdf_filename: str,
) -> str:
    inner = (
        _header(GREEN, pill_label=period, subtitle="Monthly utilization report · Shared Instrumentation Facility")
        + _body_open()
        + _greeting(
            recipients_greeting,
            f"Here is your automated monthly summary from LODE for {_e(period)}. Full details and charts are "
            "available in the attached PDF report.",
        )
        + _kpi_cards([
            (str(total_bookings), "Total bookings", False),
            (str(sops_generated), "SOPs generated", False),
            (f'{avg_fit}<span style="font-size:13px;color:{GRAY};">/100</span>', "Avg fit score", False),
            (str(open_work_orders), "Open work orders", open_work_orders > 0),
        ])
        + _util_bars(utilization)
        + _bullets(insights, bg="#eaf3ee", border=GREEN, color="#374151", label="LODE insights — generated by Agent 4")
        + (_alert(action_title, action_text, bg="#fdeeea", border="#e07a52", color="#9a3412") if action_title else "")
        + _attachments([("&#128196;", pdf_filename)])
        + _button("View live dashboard in LODE", f"{DASH_URL}/governance", GREEN, "#ffffff")
        + _body_close()
        + _footer("Delivered on the 1st of each month at 7:00 AM. Manage preferences in LODE settings.")
    )
    return _document(inner)
