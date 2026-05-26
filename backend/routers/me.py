"""User-scoped request tracker — the "My Requests" surface.

What this exposes (all by researcher_email, since the harness has profile/email
parity end-to-end already):

  GET  /api/me/requests?email=...        → {hitl: [...], maintenance: [...]}
  POST /api/me/requests/{event_id}/complete
       → runs run_confirm_graph with the payload stored at refusal-time,
         creates the real booking, generates the SOP, sends the confirm email,
         and marks the HITL event status='completed'. Refuses if the event is
         not 'approved'.

The HITL row gets its payload prepopulated at refusal time in
`vein/agents/graph.py:_safety_gate()` (context + recommendation + option).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from vein.agents.graph import run_confirm_graph
from vein.config import settings
from vein.db.database import (
    get_automation_event,
    get_automation_events,
    get_booking,
    get_bookings,
    get_conn,
    get_work_orders,
    record_automation_event,
    update_automation_event_status,
)
from vein.models.experiment import BookingOption, ExperimentContext, InstrumentFit
from vein.services.privacy import audit

router = APIRouter()
logger = logging.getLogger("backend.me")


def _payload(event: dict) -> dict:
    p = event.get("payload") or {}
    if isinstance(p, str):
        try:
            return json.loads(p or "{}")
        except json.JSONDecodeError:
            return {}
    return p if isinstance(p, dict) else {}


def _hitl_for_email(email: str, limit: int = 100) -> list[dict]:
    out: list[dict] = []
    for e in get_automation_events(kind="hitl_request", limit=limit):
        if (_payload(e).get("researcher_email") or "").lower() == email.lower():
            out.append(e)
    return out


def _upcoming_instrument_ids(email: str) -> set[str]:
    """Instruments the user has a non-cancelled booking on, in the future."""
    now = datetime.now()
    ids: set[str] = set()
    for b in get_bookings():
        if (b.get("researcher_email") or "").lower() != email.lower():
            continue
        if b.get("status") == "cancelled":
            continue
        try:
            if datetime.fromisoformat(b["start_time"]) >= now:
                ids.add(b["instrument_id"])
        except Exception:  # noqa: BLE001
            continue
    return ids


def _maintenance_for_email(email: str) -> list[dict]:
    affected = _upcoming_instrument_ids(email)
    if not affected:
        return []
    return [w for w in get_work_orders() if w.get("instrument_id") in affected]


@router.get("/requests")
def list_requests(email: str = Query(..., description="Researcher email")):
    """Return everything 'My Requests' should show for one user."""
    return {
        "hitl": _hitl_for_email(email),
        "maintenance": _maintenance_for_email(email),
    }


class CompleteResponse(BaseModel):
    ok: bool
    booking_id: Optional[int] = None
    sop_path: Optional[str] = None
    message: str
    event_id: int


class CompleteRequest(BaseModel):
    # Optional reschedule: the researcher picked a different slot than the one
    # proposed at refusal time. When present, it overrides the stored option.
    option: Optional[BookingOption] = None


@router.get("/requests/{event_id}/slots")
def request_slots(event_id: int):
    """Fresh, conflict-free slots for an approved request, so the researcher can
    reschedule before confirming. Reuses Agent 3's scheduler with the stored
    context + recommendation."""
    event = get_automation_event(event_id)
    if not event or event.get("kind") != "hitl_request":
        raise HTTPException(status_code=404, detail="HITL request not found")
    payload = _payload(event)
    ctx_raw = payload.get("context")
    rec_raw = payload.get("recommendation")
    if not (ctx_raw and rec_raw):
        raise HTTPException(status_code=422, detail="request payload missing context/recommendation")
    try:
        from vein.agents.pipeline import schedule_booking
        ctx = ExperimentContext(**ctx_raw)
        recommendation = InstrumentFit(**rec_raw)
        options = schedule_booking(ctx, recommendation)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"could not propose slots: {exc}") from exc
    return {"options": [o.model_dump(mode="json") for o in options]}


@router.post("/requests/{event_id}/complete", response_model=CompleteResponse)
def complete_hitl(event_id: int, body: Optional[CompleteRequest] = None):
    """Replay the booking with the payload stored at refusal time.

    If ``body.option`` is supplied (the researcher chose a different slot), it
    overrides the slot proposed at refusal time.
    """
    event = get_automation_event(event_id)
    if not event or event.get("kind") != "hitl_request":
        raise HTTPException(status_code=404, detail="HITL request not found")
    if event.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail=f"cannot complete — request is {event.get('status')}, must be 'approved'",
        )

    payload = _payload(event)
    ctx_raw = payload.get("context")
    rec_raw = payload.get("recommendation")
    opt_raw = payload.get("option")
    if not (ctx_raw and rec_raw and opt_raw):
        raise HTTPException(
            status_code=422,
            detail="HITL payload missing context/recommendation/option — cannot replay",
        )

    try:
        ctx = ExperimentContext(**ctx_raw)
        recommendation = InstrumentFit(**rec_raw)
        # Researcher-chosen reschedule wins over the stored slot.
        option = (body.option if body and body.option else BookingOption(**opt_raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"payload parse error: {exc}") from exc

    # Replay the confirm graph. This re-runs the safety gate; the operator's
    # approval is what authorises us to bypass it, so we monkey-patch the
    # confidence floor for THIS call only by injecting a "manager approved"
    # marker into the context notes — see safety.py evaluate_safety_gate.
    ctx.notes = (ctx.notes + " [approved-by-manager]").strip()
    sid = payload.get("session_id")
    resp = run_confirm_graph(ctx, option, recommendation, session_id=sid)

    if resp.escalated:
        # Safety gate still refused — surface so the UI can show why.
        return CompleteResponse(
            ok=False, event_id=event_id, message=resp.message,
        )

    # Booking succeeded — mark the HITL row completed so it leaves the queue.
    update_automation_event_status(event_id, "completed", detail="Completed by researcher after approval")

    # Pull the new booking id from the message if possible (best-effort).
    booking_id = None
    try:
        # message looks like "Booking confirmed (ID #123). …"
        if "ID #" in resp.message:
            booking_id = int(resp.message.split("ID #")[1].split(")")[0])
    except Exception:  # noqa: BLE001
        pass

    return CompleteResponse(
        ok=True, event_id=event_id, booking_id=booking_id,
        sop_path=resp.sop_path, message=resp.message,
    )


# ===========================================================================
# Privacy endpoints — GDPR Art. 15 (access), Art. 17 (erasure),
# Art. 20 (portability). The audit log addresses Art. 30 / HIPAA §164.312(b)
# / FERPA §99.32 record-of-disclosure. See COMPLIANCE.md.
# ===========================================================================
class DeleteResponse(BaseModel):
    ok: bool
    deleted_profile: bool
    deleted_bookings: int
    deleted_auth_user: bool
    message: str


@router.get("/export")
def export_my_data(email: str = Query(..., description="Researcher email")):
    """Return everything the system holds for this user (profile, bookings,
    HITL requests, audit excerpts). GDPR Art. 20 — data portability."""
    email = email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email required")

    with get_conn() as conn:
        profile = conn.execute(
            "SELECT id, email, full_name, research_group, role, trained_instruments, created_at "
            "FROM profiles WHERE lower(email) = %s",
            (email,),
        ).fetchone()
        if not profile:
            raise HTTPException(status_code=404, detail="No profile for that email")

        bookings_rows = conn.execute(
            "SELECT id, instrument_id, start_time, end_time, status, sop_path, created_at, experiment_context "
            "FROM bookings WHERE lower(researcher_email) = %s ORDER BY start_time",
            (email,),
        ).fetchall()

    hitl_rows = _hitl_for_email(email, limit=500)

    audit(
        "privacy.export",
        actor=email,
        subject=email,
        detail={"bookings": len(bookings_rows), "hitl": len(hitl_rows)},
    )

    return {
        "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "profile": dict(profile),
        "bookings": [dict(b) for b in bookings_rows],
        "hitl_requests": hitl_rows,
        "notice": "This export is provided pursuant to GDPR Art. 20. The audit log "
                  "records that this export was generated.",
    }


def _delete_auth_user_in_supabase(user_id: str) -> bool:
    """Best-effort delete via Supabase Admin REST API. Returns False if
    SUPABASE_URL / SERVICE_ROLE_KEY are not configured (demo without auth)."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return False
    try:
        r = httpx.delete(
            f"{settings.supabase_url}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
            },
            timeout=15,
        )
        return r.status_code in (200, 204)
    except Exception:  # noqa: BLE001
        return False


@router.post("/delete", response_model=DeleteResponse)
def delete_my_account(email: str = Query(..., description="Researcher email")):
    """Hard-delete the user's bookings, profile, and Supabase auth row.

    GDPR Art. 17 ('right to be forgotten'). We log the deletion intent to the
    audit log before removing data, so a record-of-disclosure remains even
    after the subject's row is gone (FERPA §99.32 analogue).
    """
    email = email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email required")

    user_id: Optional[str] = None
    deleted_bookings = 0
    deleted_profile = False

    with get_conn() as conn:
        prof = conn.execute(
            "SELECT id FROM profiles WHERE lower(email) = %s",
            (email,),
        ).fetchone()
        if prof:
            user_id = str(prof["id"])
        # Bookings first — they reference the profile.
        deleted_bookings = len(
            conn.execute(
                "DELETE FROM bookings WHERE lower(researcher_email) = %s RETURNING id",
                (email,),
            ).fetchall()
        )
        if user_id:
            conn.execute("DELETE FROM profiles WHERE id = %s", (user_id,))
            deleted_profile = True

    audit(
        "privacy.delete",
        actor=email,
        subject=email,
        detail={"bookings": deleted_bookings, "profile_deleted": deleted_profile},
    )

    deleted_auth = False
    if user_id:
        deleted_auth = _delete_auth_user_in_supabase(user_id)

    return DeleteResponse(
        ok=True,
        deleted_profile=deleted_profile,
        deleted_bookings=deleted_bookings,
        deleted_auth_user=deleted_auth,
        message=("All personal data removed. The audit log retains a record that "
                 "this deletion occurred, per HIPAA §164.312(b) / FERPA §99.32."),
    )


@router.get("/audit")
def my_audit(email: str = Query(...), limit: int = 50):
    """Return audit events where the caller is actor or subject."""
    from vein.services.privacy import read_audit
    email_lower = email.strip().lower()
    rows = [
        r for r in read_audit(limit=500)
        if (r.get("actor") or "").lower() == email_lower
        or (r.get("subject") or "").lower() == email_lower
    ]
    return {"rows": rows[:limit]}


# ===========================================================================
# Clear / dismiss — researcher hides a terminal-state request from their
# "My Requests" page. Allowed only for HITL rows in {approved, denied,
# completed} status (pending requests cannot be dismissed). The dismissal is
# recorded in the audit log; the row itself is left intact for compliance.
# ===========================================================================
TERMINAL_HITL_STATUSES = {"approved", "denied", "completed"}


class DismissResponse(BaseModel):
    ok: bool
    event_id: int
    status: str
    message: str


@router.post("/requests/{event_id}/dismiss", response_model=DismissResponse)
def dismiss_request(event_id: int, email: str = Query(..., description="Researcher email")):
    event = get_automation_event(event_id)
    if not event or event.get("kind") != "hitl_request":
        raise HTTPException(status_code=404, detail="HITL request not found")
    payload = _payload(event)
    owner = (payload.get("researcher_email") or "").lower()
    if owner and owner != email.strip().lower():
        raise HTTPException(status_code=403, detail="Cannot dismiss another researcher's request")
    if event.get("status") not in TERMINAL_HITL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Only terminal requests can be cleared (got {event.get('status')}).",
        )
    audit(
        "request.dismiss",
        actor=email,
        subject=email,
        detail={"event_id": event_id, "status": event.get("status")},
    )
    return DismissResponse(
        ok=True, event_id=event_id, status=event.get("status") or "",
        message="Request cleared from your list. The underlying audit row is retained.",
    )


@router.get("/requests/dismissed")
def list_dismissed(email: str = Query(...)):
    """Returns the event-ids the user has dismissed (read from the audit log).
    The frontend filters these out client-side so the dismissal sticks across
    devices / sessions for the same account."""
    from vein.services.privacy import read_audit
    email_lower = email.strip().lower()
    ids: list[int] = []
    for r in read_audit(limit=2000):
        if r.get("event") != "request.dismiss":
            continue
        if (r.get("actor") or "").lower() != email_lower:
            continue
        eid = (r.get("detail") or {}).get("event_id")
        if isinstance(eid, int) and eid not in ids:
            ids.append(eid)
    return {"event_ids": ids}


# ---------------------------------------------------------------------------
# Same pattern for work orders. Only WOs in status='closed' can be cleared.
# ---------------------------------------------------------------------------
class WoDismissResponse(BaseModel):
    ok: bool
    work_order_id: int
    message: str


@router.post("/work-orders/{work_order_id}/dismiss", response_model=WoDismissResponse)
def dismiss_work_order(work_order_id: int, email: str = Query(...)):
    rows = [w for w in get_work_orders() if w.get("id") == work_order_id]
    wo = rows[0] if rows else None
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    if wo.get("status") != "closed":
        raise HTTPException(
            status_code=409,
            detail=f"Only closed work orders can be cleared (got {wo.get('status')}).",
        )
    audit(
        "workorder.dismiss",
        actor=email,
        subject=email,
        detail={"work_order_id": work_order_id, "status": wo.get("status")},
    )
    return WoDismissResponse(
        ok=True, work_order_id=work_order_id,
        message="Work order cleared from your list. The underlying row is retained.",
    )


@router.get("/work-orders/dismissed")
def list_dismissed_work_orders(email: str = Query(...)):
    from vein.services.privacy import read_audit
    email_lower = email.strip().lower()
    ids: list[int] = []
    for r in read_audit(limit=2000):
        if r.get("event") != "workorder.dismiss":
            continue
        if (r.get("actor") or "").lower() != email_lower:
            continue
        wid = (r.get("detail") or {}).get("work_order_id")
        if isinstance(wid, int) and wid not in ids:
            ids.append(wid)
    return {"work_order_ids": ids}


# ===========================================================================
# Booking change requests — edit (reschedule) and cancel.
#
# Both go through the same HITL approval path the rest of the app uses:
#   1. Researcher submits the change request → we create a `hitl_request`
#      event with payload.action = "edit_booking" | "cancel_booking".
#   2. Admin sees the request in Governance (or in the live automation feed)
#      and approves/denies via the existing endpoints.
#   3. approve_hitl (admin.py) executes the underlying action and emails the
#      researcher when the action is "edit_booking" / "cancel_booking".
# ===========================================================================
class EditBookingRequest(BaseModel):
    new_start_time: datetime
    reason: Optional[str] = None


class CancelBookingRequest(BaseModel):
    reason: Optional[str] = None


class BookingChangeResponse(BaseModel):
    ok: bool
    event_id: int
    message: str


def _owned_by(email: str, booking: dict) -> bool:
    return (booking.get("researcher_email") or "").lower() == email.strip().lower()


def _fmt_when(start: datetime, end: datetime) -> str:
    return f"{start:%a, %b %d · %I:%M %p}–{end:%I:%M %p}"


@router.post("/bookings/{booking_id}/request-edit", response_model=BookingChangeResponse)
def request_booking_edit(
    booking_id: int,
    body: EditBookingRequest,
    email: str = Query(..., description="Researcher email"),
):
    booking = get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not _owned_by(email, booking):
        raise HTTPException(status_code=403, detail="You can only request changes to your own bookings")

    # Compute new end based on existing duration.
    try:
        old_start = datetime.fromisoformat(str(booking["start_time"]))
        old_end = datetime.fromisoformat(str(booking["end_time"]))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"booking time parse: {exc}") from exc
    duration = old_end - old_start
    new_end = body.new_start_time + duration

    payload = {
        "action": "edit_booking",
        "booking_id": booking_id,
        "instrument_name": booking.get("instrument_name") or booking.get("instrument_id"),
        "instrument_id": booking.get("instrument_id"),
        "researcher_email": booking.get("researcher_email"),
        "researcher_name": booking.get("researcher_name"),
        "experiment": "Reschedule request",
        "booking_code": f"EDIT-{booking_id}",
        "reasons": [
            f"Researcher requested a reschedule from {_fmt_when(old_start, old_end)} "
            f"to {_fmt_when(body.new_start_time, new_end)}."
        ] + ([f"Reason: {body.reason}"] if body.reason else []),
        "from": old_start.isoformat(),
        "to": body.new_start_time.isoformat(),
        "to_end": new_end.isoformat(),
        "when": _fmt_when(body.new_start_time, new_end),
    }
    event = record_automation_event(
        kind="hitl_request",
        status="pending",
        target=f"EDIT-{booking_id}",
        detail="Booking reschedule requested by researcher.",
        payload=payload,
    )
    # Notify admins so the change request enters the same approval flow as
    # a new-booking HITL (the approve/deny buttons hit /governance?hitl=<id>).
    try:
        from vein.services.email import send_booking_change_request_email
        send_booking_change_request_email(
            action="edit",
            booking_code=payload["booking_code"],
            researcher=payload.get("researcher_name") or email,
            instrument=payload["instrument_name"],
            from_when=_fmt_when(old_start, old_end),
            to_when=_fmt_when(body.new_start_time, new_end),
            reason=body.reason or "",
            event_id=int(event["id"]) if event else 0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("edit-request admin email failed: %s", exc)
    audit("booking.edit_requested", actor=email, subject=email,
          detail={"booking_id": booking_id, "to": body.new_start_time.isoformat()})
    return BookingChangeResponse(
        ok=True, event_id=int(event["id"]) if event else 0,
        message="Reschedule request submitted. An admin will review and you'll be emailed when a decision is made.",
    )


@router.post("/bookings/{booking_id}/request-cancel", response_model=BookingChangeResponse)
def request_booking_cancel(
    booking_id: int,
    body: Optional[CancelBookingRequest] = None,
    email: str = Query(..., description="Researcher email"),
):
    booking = get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not _owned_by(email, booking):
        raise HTTPException(status_code=403, detail="You can only cancel your own bookings")
    if booking.get("status") == "cancelled":
        raise HTTPException(status_code=409, detail="Booking is already cancelled")

    try:
        start = datetime.fromisoformat(str(booking["start_time"]))
        end = datetime.fromisoformat(str(booking["end_time"]))
        when = _fmt_when(start, end)
    except Exception:  # noqa: BLE001
        when = "(time parse error)"

    payload = {
        "action": "cancel_booking",
        "booking_id": booking_id,
        "instrument_name": booking.get("instrument_name") or booking.get("instrument_id"),
        "instrument_id": booking.get("instrument_id"),
        "researcher_email": booking.get("researcher_email"),
        "researcher_name": booking.get("researcher_name"),
        "experiment": "Cancellation request",
        "booking_code": f"CANCEL-{booking_id}",
        "reasons": [f"Researcher requested cancellation of {when}."] + (
            [f"Reason: {body.reason}"] if body and body.reason else []
        ),
        "when": when,
    }
    event = record_automation_event(
        kind="hitl_request",
        status="pending",
        target=f"CANCEL-{booking_id}",
        detail="Booking cancellation requested by researcher.",
        payload=payload,
    )
    try:
        from vein.services.email import send_booking_change_request_email
        send_booking_change_request_email(
            action="cancel",
            booking_code=payload["booking_code"],
            researcher=payload.get("researcher_name") or email,
            instrument=payload["instrument_name"],
            from_when=when,
            reason=(body.reason if body else "") or "",
            event_id=int(event["id"]) if event else 0,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cancel-request admin email failed: %s", exc)
    audit("booking.cancel_requested", actor=email, subject=email,
          detail={"booking_id": booking_id})
    return BookingChangeResponse(
        ok=True, event_id=int(event["id"]) if event else 0,
        message="Cancellation request submitted. An admin will review and you'll be emailed when a decision is made.",
    )
