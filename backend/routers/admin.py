from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vein.db.database import (
    find_hitl_by_session,
    get_agent_decisions,
    get_automation_event,
    get_automation_events,
    get_group_utilization,
    get_rag_stats,
    get_run_logs,
    get_work_orders,
    update_automation_event_status,
    update_work_order_status,
)
from vein.rag.indexer import index_corpus

router = APIRouter()

VALID_WO_STATUS = {"open", "in_progress", "closed"}


class WorkOrderStatus(BaseModel):
    status: str


class HitlDecision(BaseModel):
    note: str | None = None


@router.get("/rag")
def rag_status():
    return get_rag_stats()


@router.post("/rag/reindex")
def reindex():
    result = index_corpus(force=True)
    stats = get_rag_stats()
    return {**result, **stats}


@router.get("/runs")
def runs():
    return get_run_logs(100)


@router.get("/audit")
def audit(limit: int = 50, session_id: str | None = None):
    return get_agent_decisions(session_id=session_id, limit=limit)


@router.get("/equity")
def equity(weeks: int = 4):
    rows = get_group_utilization(weeks=weeks)
    # Flag concentration: any group >40% of total weekly hours
    flagged = [r for r in rows if r["pct"] > 40]
    return {"window_weeks": weeks, "groups": rows, "flagged": flagged}


@router.get("/work-orders")
def work_orders(status: str | None = None):
    return get_work_orders(status=status)


@router.post("/work-orders/{work_order_id}/status")
def set_work_order_status(work_order_id: int, body: WorkOrderStatus):
    if body.status not in VALID_WO_STATUS:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_WO_STATUS)}")
    row = update_work_order_status(work_order_id, body.status)
    if not row:
        raise HTTPException(status_code=404, detail="work order not found")
    return row


@router.get("/automations")
def automations(kind: str | None = None, limit: int = 50):
    """Live automation audit feed (email / booking_sync / work_order)."""
    return get_automation_events(kind=kind, limit=limit)


@router.get("/automations/airtable")
def airtable_queue(table: str = "LODE_Bookings", limit: int = 50):
    return get_automation_events(kind="booking_sync", limit=limit)


@router.get("/automations/email")
def email_outbox(limit: int = 50):
    return get_automation_events(kind="email", limit=limit)


# ---------- HITL approve / deny ----------
@router.get("/hitl")
def list_hitl(status: str | None = None, limit: int = 50):
    """All HITL requests (kind=hitl_request) for the Governance UI."""
    events = get_automation_events(kind="hitl_request", limit=limit)
    if status:
        events = [e for e in events if e.get("status") == status]
    return events


def _resolve_hitl(event_id: int | None, session_id: str | None) -> dict:
    if event_id:
        event = get_automation_event(event_id)
    elif session_id:
        event = find_hitl_by_session(session_id)
    else:
        raise HTTPException(status_code=422, detail="event_id or session_id required")
    if not event:
        raise HTTPException(status_code=404, detail="HITL request not found")
    if event.get("kind") != "hitl_request":
        raise HTTPException(status_code=409, detail="not a HITL request")
    return event


@router.post("/hitl/{event_id}/approve")
def approve_hitl(event_id: int, body: HitlDecision | None = None):
    event = _resolve_hitl(event_id, None)
    if event.get("status") in ("approved", "denied"):
        raise HTTPException(status_code=409, detail=f"already {event['status']}")
    note = (body.note if body else None) or "Approved via dashboard"
    row = update_automation_event_status(event_id, "approved", detail=note)
    return {"ok": True, "event": row}


@router.post("/hitl/{event_id}/deny")
def deny_hitl(event_id: int, body: HitlDecision | None = None):
    event = _resolve_hitl(event_id, None)
    if event.get("status") in ("approved", "denied"):
        raise HTTPException(status_code=409, detail=f"already {event['status']}")
    note = (body.note if body else None) or "Denied via dashboard"
    row = update_automation_event_status(event_id, "denied", detail=note)
    return {"ok": True, "event": row}


# ---------- Manual monthly report trigger ----------
@router.post("/reports/monthly/send")
def send_monthly_report(to: str | None = None):
    """Fire Email 4 (monthly utilization report) on demand."""
    from datetime import timedelta

    from vein.config import local_now, settings
    from vein.services.email import send_monthly_report_email

    prev_month = local_now().replace(day=1) - timedelta(days=1)
    period = prev_month.strftime("%B %Y")

    # Aggregate the prior month's real data so the demo shows actual numbers.
    from vein.db.database import get_bookings, get_instruments, get_work_orders as _gwo

    bookings = [
        b for b in get_bookings()
        if b.get("start_time", "")[:7] == prev_month.strftime("%Y-%m")
    ]
    sops_generated = sum(1 for b in bookings if b.get("sop_path"))
    open_wos = len([w for w in _gwo() if w.get("status") == "open"])

    # Per-instrument utilization for the period (rough % of 160 hr/month).
    util = []
    for inst in get_instruments():
        h = 0.0
        for b in bookings:
            if b["instrument_id"] == inst["id"] and b.get("status") != "cancelled":
                from datetime import datetime as _dt
                try:
                    bt = _dt.fromisoformat(b["start_time"])
                    et = _dt.fromisoformat(b["end_time"])
                    h += (et - bt).total_seconds() / 3600
                except Exception:  # noqa: BLE001
                    pass
        pct = min(100, round((h / 160.0) * 100))
        util.append((inst["name"], pct))

    insights = [
        f"{len(bookings)} bookings completed in {period}; {sops_generated} SOPs auto-generated.",
        "Equity flag at /governance — any group over 40% is highlighted in amber.",
        "Open work orders: " + str(open_wos) + ". Address before next calibration cycle.",
    ]
    if to:
        orig_chair = settings.lab_email_chair
        orig_tech = settings.lab_email_tech
        settings.lab_email_chair = to
        settings.lab_email_tech = to
    try:
        result = send_monthly_report_email(
            period=period,
            total_bookings=len(bookings),
            sops_generated=sops_generated,
            avg_fit="—",
            open_work_orders=open_wos,
            utilization=util,
            insights=insights,
            action_title="",
            action_text="",
        )
    finally:
        if to:
            settings.lab_email_chair = orig_chair
            settings.lab_email_tech = orig_tech
    return {"ok": True, "result": result, "period": period}
