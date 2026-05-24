"""Maintenance work order generator (Automation 3).

A work order is produced when:
  - Agent 5 detects anomalies in a post-run report, OR
  - The safety gate flags an overdue calibration.

The recommended action is grounded in the maintenance RAG corpus (so the work
order itself carries a citation when one is available). The work order is then
routed via the Airtable client (real Airtable or local queue) AND emails the
purple Email-3 template to the lab manager + facilities team — so the demo
sees the same automation surface a production install would.
"""

from __future__ import annotations

import logging

from vein.db.database import (
    create_work_order,
    get_instrument,
    get_instrument_usage_hours,
)
from vein.rag.indexer import query_corpus
from vein.services.airtable import push_work_order_record
from vein.services.email import send_work_order_email

logger = logging.getLogger("vein.work_order")


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

    return record
