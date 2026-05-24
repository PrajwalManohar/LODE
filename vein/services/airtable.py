"""Airtable automation.

If AIRTABLE_API_KEY + AIRTABLE_BASE_ID are configured we POST to the real REST
API. Otherwise we append records to a local JSONL queue under
data/airtable_queue/ so the prototype demonstrates the full workflow without
external credentials. Either way returns a record id.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from vein.config import DATA_DIR, settings

logger = logging.getLogger("vein.airtable")

QUEUE_DIR = DATA_DIR / "airtable_queue"


def _queue_path(table: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    return QUEUE_DIR / f"{table}.jsonl"


def _write_local(table: str, fields: dict) -> str:
    rid = f"loc_{uuid.uuid4().hex[:10]}"
    record = {"id": rid, "table": table, "fields": fields, "created_at": datetime.now().isoformat()}
    with _queue_path(table).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    logger.info("Airtable [local-queue:%s] %s", table, rid)
    return rid


def _post_airtable(table: str, fields: dict) -> Optional[str]:
    url = f"https://api.airtable.com/v0/{settings.airtable_base_id}/{table}"
    headers = {
        "Authorization": f"Bearer {settings.airtable_api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.post(url, headers=headers, json={"fields": fields}, timeout=10)
        if resp.status_code >= 300:
            logger.warning("Airtable POST failed %s: %s", resp.status_code, resp.text[:200])
            return None
        return resp.json().get("id")
    except Exception as exc:
        logger.warning("Airtable error: %s", exc)
        return None


def push_record(table: str, fields: dict) -> dict:
    """Route to Airtable when configured, else the local JSONL queue. Either way
    an automation_event is recorded in Supabase for the live admin feed."""
    use_remote = bool(settings.airtable_api_key and settings.airtable_base_id)
    rid = None
    destination = "local-queue"
    if use_remote:
        rid = _post_airtable(table, fields)
        if rid:
            destination = "airtable"
    if not rid:
        rid = _write_local(table, fields)

    try:
        from vein.db.database import record_automation_event

        kind = {"LODE_Bookings": "booking_sync", "LODE_WorkOrders": "work_order"}.get(table, "sync")
        record_automation_event(
            kind=kind,
            status="sent" if destination == "airtable" else "queued",
            target=table,
            detail=str(fields.get("Researcher") or fields.get("Issue") or table)[:120],
            payload={"destination": destination, "record_id": rid},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("automation_event (%s) not recorded: %s", table, exc)

    return {"id": rid, "destination": destination, "table": table}


def read_queue(table: str, limit: int = 50) -> list[dict]:
    path = _queue_path(table)
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


def push_booking_record(
    booking_id: int,
    researcher: str,
    instrument_name: str,
    instrument_id: str,
    start_time: datetime,
    end_time: datetime,
    experiment_type: str,
    material_type: str,
    fit_score: int,
    sop_status: str,
    rationale: str,
    research_group: str = "",
) -> dict:
    fields = {
        "Booking ID": booking_id,
        "Researcher": researcher,
        "Research Group": research_group,
        "Instrument": instrument_name,
        "Instrument ID": instrument_id,
        "Start": start_time.isoformat() if isinstance(start_time, datetime) else str(start_time),
        "End": end_time.isoformat() if isinstance(end_time, datetime) else str(end_time),
        "Experiment Type": experiment_type,
        "Material": material_type,
        "Fit Score": fit_score,
        "SOP Status": sop_status,
        "Agent Rationale": rationale[:1000],
    }
    return push_record("LODE_Bookings", fields)


def push_work_order_record(work_order: dict) -> dict:
    fields = {
        "Work Order ID": work_order.get("id"),
        "Instrument": work_order.get("instrument_id"),
        "Issue": work_order.get("issue"),
        "Severity": work_order.get("severity"),
        "Usage Hours": work_order.get("usage_hours"),
        "Calibration Interval (hr)": work_order.get("calibration_interval_hours"),
        "Recommended Action": work_order.get("recommended_action"),
        "Source": work_order.get("source"),
        "Status": work_order.get("status", "open"),
    }
    return push_record("LODE_WorkOrders", fields)
