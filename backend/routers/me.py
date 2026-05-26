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

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from vein.agents.graph import run_confirm_graph
from vein.db.database import (
    get_automation_event,
    get_automation_events,
    get_bookings,
    get_work_orders,
    update_automation_event_status,
)
from vein.models.experiment import BookingOption, ExperimentContext, InstrumentFit

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
