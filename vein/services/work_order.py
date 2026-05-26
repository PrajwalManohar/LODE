"""Maintenance work order generator (Automation 3).

A work order is produced when:
  - Agent 5 detects anomalies in a post-run report, OR
  - The safety gate flags an overdue calibration.

The recommended action is grounded in the maintenance RAG corpus (so the work
order itself carries a citation when one is available). The work order is then
routed via the Airtable client (real Airtable or local queue) AND emails the
purple Email-3 template to the lab manager + facilities team — so the demo
sees the same automation surface a production install would.

Additionally, every user with an upcoming booking on the affected instrument
is emailed when (a) the work order opens and (b) it closes. The list of
affected users + their slot is stored in the work order's audit row so the
"My Requests" page can surface the same data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from vein.db.database import (
    create_work_order,
    get_bookings,
    get_instrument,
    get_instrument_usage_hours,
    record_automation_event,
)
from vein.rag.indexer import query_corpus
from vein.services.airtable import push_work_order_record
from vein.services.email import (
    send_user_maintenance_alert_email,
    send_user_maintenance_resolved_email,
    send_work_order_email,
)

logger = logging.getLogger("vein.work_order")


def _affected_bookings(instrument_id: str, lookahead_days: int = 14) -> list[dict]:
    """Upcoming, non-cancelled bookings on this instrument for the next N days."""
    now = datetime.now()
    horizon = now + timedelta(days=lookahead_days)
    out: list[dict] = []
    for b in get_bookings(instrument_id):
        if b.get("status") == "cancelled":
            continue
        try:
            bt = datetime.fromisoformat(b["start_time"])
        except Exception:  # noqa: BLE001
            continue
        if now <= bt <= horizon:
            out.append(b)
    return out


def _fmt_slot(b: dict) -> str:
    try:
        bt = datetime.fromisoformat(b["start_time"])
        et = datetime.fromisoformat(b["end_time"])
        return f"{bt:%a, %b %d · %I:%M %p}–{et:%I:%M %p}"
    except Exception:  # noqa: BLE001
        return str(b.get("start_time", "—"))


def notify_affected_users_created(record: dict) -> list[dict]:
    """Email every researcher with an upcoming booking on the affected instrument."""
    affected = _affected_bookings(record["instrument_id"])
    sent: list[dict] = []
    for b in affected:
        email = (b.get("researcher_email") or "").strip()
        if not email:
            continue
        try:
            result = send_user_maintenance_alert_email(
                researcher_email=email,
                researcher_name=b.get("researcher_name") or "",
                work_order_code=f"WO-{record['id']:03d}",
                instrument=record["instrument_name"],
                severity=record["severity"],
                issue=record["issue"],
                affected_when=_fmt_slot(b),
            )
            sent.append({
                "booking_id": b.get("id"),
                "email": email,
                "transport": result.get("transport"),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("user maintenance alert email failed for %s: %s", email, exc)
    return sent


def notify_affected_users_resolved(work_order_id: int, wo: dict) -> list[dict]:
    """Called when WO transitions to closed — emails the same set of users."""
    instrument_id = wo.get("instrument_id")
    if not instrument_id:
        return []
    inst = get_instrument(instrument_id) or {}
    affected = _affected_bookings(instrument_id, lookahead_days=30)
    sent: list[dict] = []
    for b in affected:
        email = (b.get("researcher_email") or "").strip()
        if not email:
            continue
        try:
            result = send_user_maintenance_resolved_email(
                researcher_email=email,
                researcher_name=b.get("researcher_name") or "",
                work_order_code=f"WO-{work_order_id:03d}",
                instrument=inst.get("name", instrument_id),
                affected_when=_fmt_slot(b),
            )
            sent.append({
                "booking_id": b.get("id"),
                "email": email,
                "transport": result.get("transport"),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("user maintenance resolved email failed for %s: %s", email, exc)
    if sent:
        record_automation_event(
            kind="work_order",
            status="closed",
            target=f"WO-{work_order_id:03d}",
            detail=f"Notified {len(sent)} researcher(s) that {inst.get('name', instrument_id)} is back online",
            payload={"notified": sent, "work_order_id": work_order_id},
        )
    return sent


def _recommend_action(instrument_id: str, issue: str) -> tuple[str, str]:
    """Returns (recommended_action, citation_str)."""
    chunks = query_corpus(
        f"{issue} {instrument_id} maintenance",
        n_results=2,
        instrument_id=instrument_id,
        corpus_type="maintenance",
    )
    if not chunks:
        chunks = query_corpus(f"{issue} {instrument_id} maintenance", n_results=2)
    if chunks:
        c = chunks[0]
        cite = f"[Source: {c['source']}" + (f", {c['section']}" if c.get("section") else "") + "]"
        return c["text"][:240], cite
    return "Schedule service inspection.", "[no RAG match]"


def generate_work_order(
    instrument_id: str,
    issue: str,
    severity: str = "warning",
    source: str = "agent",
) -> dict:
    inst = get_instrument(instrument_id) or {}
    usage = get_instrument_usage_hours(instrument_id)
    interval = float(inst.get("calibration_interval_hours") or 0)

    action, citation = _recommend_action(instrument_id, issue)

    wid = create_work_order(
        instrument_id=instrument_id,
        issue=issue,
        severity=severity,
        usage_hours=usage,
        calibration_interval_hours=interval,
        recommended_action=f"{action}\n{citation}",
        source=source,
    )

    record = {
        "id": wid,
        "instrument_id": instrument_id,
        "instrument_name": inst.get("name", instrument_id),
        "issue": issue,
        "severity": severity,
        "usage_hours": round(usage, 1),
        "calibration_interval_hours": interval,
        "recommended_action": action,
        "citation": citation,
        "source": source,
        "status": "open",
    }
    routing = push_work_order_record(record)
    record["routing"] = routing

    # Email 3 — purple work-order notification to lab manager + facilities.
    # Fire-and-log: a transport failure must not fail the booking confirm path.
    try:
        last_cal = inst.get("last_calibrated_at") or "Not on file"
        actions = [action]
        if citation and citation != "[no RAG match]":
            actions.append(citation)
        actions.append(
            "Block instrument bookings until ticket is marked resolved in LODE."
        )
        email_result = send_work_order_email(
            work_order_code=f"WO-{wid:03d}",
            instrument=inst.get("name", instrument_id),
            location=inst.get("location", "—"),
            usage_hours=round(usage, 1),
            interval_hours=interval,
            last_calibrated=str(last_cal),
            issue_type=issue,
            severity=severity.capitalize(),
            triggered_by=f"Agent · source={source}",
            anomaly=issue,
            actions=actions,
        )
        record["email"] = email_result
    except Exception as exc:  # noqa: BLE001
        logger.warning("work-order email dispatch failed: %s", exc)
        record["email"] = {"sent": False, "error": str(exc)}

    # User notifications — every researcher with an upcoming booking on the
    # affected instrument is told their session may be delayed. The list of
    # recipients is recorded as a `work_order` automation event so it shows up
    # on the live admin feed AND so My Requests can correlate WO → bookings.
    try:
        notified = notify_affected_users_created(record)
        record["affected_users"] = notified
        if notified:
            record_automation_event(
                kind="work_order",
                status="opened",
                target=f"WO-{wid:03d}",
                detail=f"Notified {len(notified)} researcher(s) of maintenance on {inst.get('name', instrument_id)}",
                payload={"notified": notified, "work_order_id": wid,
                         "instrument_id": instrument_id, "severity": severity},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("affected-user notifications failed: %s", exc)
        record["affected_users"] = []

    return record
