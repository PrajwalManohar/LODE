"""Seed a *live-feeling* activity layer on top of the demo users.

`seed_demo_users.py` creates the 10 personas + 3 bookings each. This script
adds the "it's alive right now" layer a presenter wants on demo day: a dense
spread of bookings across the demo week (multiple per day, varied instruments
and locations), fresh run logs, one open work order, one pending HITL request,
and a handful of recent automation events — so the dashboards, governance queue,
and activity feeds all render with current-looking data.

Everything it writes is tagged with a version marker so it is fully
idempotent and reversible:

    python scripts/seed_demo_activity.py            # add the activity layer
    python scripts/seed_demo_activity.py --wipe     # remove ONLY this layer
    python scripts/seed_demo_activity.py --wipe --seed   # reset + reseed

The marker is ``demo_activity = "v1"`` in booking experiment_context, the token
``[demo-activity-v1]`` inside run-log parameters, and ``DEMO-ACT-v1`` inside the
target/source of HITL / work-order / automation rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vein.db.database import get_conn, init_db  # noqa: E402

MARKER = "v1"
TOKEN = "[demo-activity-v1]"
TAG = "DEMO-ACT-v1"

# Anchor the activity to the demo week. The presentation is Friday 2026-06-05;
# we spread bookings Wed→Sun so whichever day the app is opened there is recent
# and upcoming activity on screen.
DEMO_DATE = date(2026, 6, 5)


def _profiles_by_email() -> dict[str, dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, email, full_name, research_group, trained_instruments "
            "FROM profiles WHERE email LIKE %s",
            ("%@demo.mines.edu",),
        ).fetchall()
    return {r["email"]: r for r in rows}


# (email, instrument_id, day_offset_from_demo_date, start_hour, duration_h, status, goal)
# day offsets: -2=Wed, -1=Thu, 0=Fri(demo day), +1=Sat, +2=Sun
ACTIVITY_BOOKINGS = [
    ("lfischer@demo.mines.edu",  "sem-jeol",    -2,  9, 2, "confirmed", "fracture surface morphology"),
    ("achen@demo.mines.edu",     "tem-talos",   -2, 13, 3, "confirmed", "dislocation microstructure"),
    ("panand@demo.mines.edu",    "icp-ms",      -1, 10, 2, "confirmed", "trace metal quantification"),
    ("rmartinez@demo.mines.edu", "xrd-empyrean",-1, 14, 2, "cancelled", "phase analysis"),
    # Demo day (Friday) — a full slate so "Today's bookings" is busy.
    ("mthompson@demo.mines.edu", "sem-jeol",     0,  8, 2, "confirmed", "grain boundary decohesion imaging"),
    ("spatel@demo.mines.edu",    "xrd-d8",       0, 10, 2, "confirmed", "martensite phase fraction"),
    ("jokonkwo@demo.mines.edu",  "icp-ms",       0, 11, 3, "confirmed", "mine drainage trace elements"),
    ("schen@demo.mines.edu",     "xps-kratos",   0, 13, 2, "confirmed", "oxidation-state binding energy"),
    ("knakamura@demo.mines.edu", "rock-mech",    0, 14, 2, "confirmed", "uniaxial compressive strength"),
    ("lfischer@demo.mines.edu",  "fib-helios",   0, 16, 2, "confirmed", "cross-section lamella prep"),
    # Weekend tail — upcoming.
    ("mrivera@demo.mines.edu",   "raman-witec",  1, 10, 2, "confirmed", "graphitic Raman signature"),
    ("achen@demo.mines.edu",     "sem-jeol",     2, 11, 2, "confirmed", "fracture surface morphology"),
]

# Recent completed runs (dated relative to DEMO_DATE) → "recent runs" + activity.
# (email, instrument_id, day_offset, material, params, outcome, quality)
ACTIVITY_RUNS = [
    ("lfischer@demo.mines.edu",  "sem-jeol", -2, "martensitic steel",
     "15 kV, EDS mapping, carbon coated", "Fracture facets + secondary cracks imaged", 5),
    ("panand@demo.mines.edu",    "icp-ms",   -1, "mine drainage water",
     "43 elements, 1:100 dilution", "Cu/Zn/As above detection; QC within 5%", 4),
    ("spatel@demo.mines.edu",    "xrd-d8",   -1, "high-strength steel",
     "2theta 30-100, Co Kalpha", "Retained austenite 6.2% quantified", 4),
    ("schen@demo.mines.edu",     "xps-kratos", 0, "oxidized Ni alloy",
     "Al Kalpha, survey + O1s/Ni2p high-res", "NiO/Ni2O3 mix resolved", 5),
    ("knakamura@demo.mines.edu", "rock-mech",  0, "sandstone core",
     "axial load to failure, 0.5 mm/min", "UCS 64 MPa; brittle failure", 4),
]


# Per-persona HITL requests in every lifecycle state, so "My Requests" is
# populated for whichever demo persona you sign in as. Each carries a full,
# replayable payload (context + recommendation + option) so an *approved*
# request's "Confirm booking" button actually works.
# (email, instr_id, instr_name, goal, status, fit, grade, alert_title, reason)
ACTIVITY_HITL = [
    ("mthompson@demo.mines.edu", "sem-jeol", "JEOL JSM-IT800 SEM-EDS", "grain boundary decohesion imaging",
     "pending", 92, "A", "Hazardous materials detected",
     "Hazmat keyword detected (hydrofluoric acid etch) — EH&S review required."),
    ("mthompson@demo.mines.edu", "sem-jeol", "JEOL JSM-IT800 SEM-EDS", "fracture surface morphology",
     "approved", 92, "A", "Manual review approved",
     "Supervisor approved — confirm your slot to finalize the booking."),
    ("lfischer@demo.mines.edu", "fib-helios", "FEI Helios NanoLab 600i FIB-SEM", "cross-section lamella prep",
     "completed", 90, "A", "Booking completed", "Approved after review and booked."),
    ("panand@demo.mines.edu", "icp-ms", "Agilent 7900 ICP-MS", "trace metal quantification",
     "denied", 88, "A", "Hazardous materials detected",
     "HF digestion not approved for the requested hood; resubmit via EH&S."),
    ("spatel@demo.mines.edu", "xrd-d8", "Bruker D8 Advance XRD", "martensite phase fraction",
     "pending", 78, "B+", "Fit Scorer confidence below 80%",
     "Fit confidence 78/100 below 80% threshold — human sign-off required."),
    ("jokonkwo@demo.mines.edu", "icp-ms", "Agilent 7900 ICP-MS", "mine drainage trace elements",
     "approved", 88, "A", "Manual review approved",
     "Supervisor approved — confirm your slot to finalize the booking."),
    ("achen@demo.mines.edu", "tem-talos", "FEI Talos F200X (S)TEM", "dislocation microstructure",
     "pending", 85, "A", "Training certification missing", "TEM-Operator certification not on file."),
    ("mrivera@demo.mines.edu", "xrd-d8", "Bruker D8 Advance XRD", "phase identification",
     "denied", 78, "B+", "Fit Scorer confidence below 80%", "Fit confidence 78/100 below 80% threshold."),
]

# Open/in-progress work orders on instruments personas have upcoming bookings
# on, so "Maintenance affecting my bookings" populates.
# (instr_id, issue, severity, usage_hours, interval, action, status)
AFFECTING_WO = [
    ("sem-jeol", "Aperture contamination causing astigmatism at high magnification",
     "warning", 430.0, 400.0, "Clean apertures and re-align column", "open"),
    ("xrd-d8", "Goniometer zero offset drift detected during QC scan",
     "warning", 380.0, 500.0, "Re-run zero calibration before next session", "in_progress"),
]


def _dt(day_offset: int, hour: int, minute: int = 0) -> datetime:
    d = DEMO_DATE + timedelta(days=day_offset)
    return datetime.combine(d, time(hour=hour, minute=minute))


def _hitl_payload(p, instr_id, instr_name, goal, status, fit, grade, alert_title, reason, idx):
    start = _dt(0, 15)
    end = start + timedelta(hours=2)
    prep = start - timedelta(minutes=45)
    code = f"HITL-{instr_id[:3].upper()}{1000 + idx}"
    ctx = _ctx(p, instr_id, goal)
    ctx["analysis_goal"] = goal
    rec = {
        "instrument_id": instr_id, "instrument_name": instr_name,
        "fit_score": int(fit), "grade": grade, "rationale": reason,
        "citations": [], "requires_training": False,
        "prep_time_minutes": 45, "run_duration_minutes": 120, "confidence": int(fit),
    }
    opt = {
        "instrument_id": instr_id, "instrument_name": instr_name,
        "start_time": start.isoformat(), "end_time": end.isoformat(),
        "prep_start": prep.isoformat(), "rank": 1, "score": float(fit), "notes": "Demo slot",
    }
    payload = {
        "booking_code": code, "session_id": f"sess_demo_{status}_{idx}",
        "researcher_name": p["full_name"], "researcher_email": p["email"],
        "research_group": p["research_group"], "instrument_id": instr_id,
        "instrument_name": instr_name, "experiment": goal,
        "fit_score": int(fit), "grade": grade, "confidence": int(fit),
        "when": f"{start:%A, %b %d, %Y · %I:%M %p}–{end:%I:%M %p}",
        "alert_title": alert_title, "alert_text": reason, "reasons": [reason],
        "context": ctx, "recommendation": rec, "option": opt,
    }
    return code, payload


def _ctx(p: dict[str, Any], instr: str, goal: str) -> dict[str, Any]:
    return {
        "researcher_name": p["full_name"],
        "researcher_email": p["email"],
        "research_group": p["research_group"],
        "trained_instruments": p["trained_instruments"] or [],
        "material_type": "sample",
        "analysis_goal": goal,
        "urgency": "medium",
        "is_complete": True,
        "hazardous_materials": [],
        "hazmat_review_required": False,
        "demo_activity": MARKER,
    }


def already_seeded(conn) -> bool:
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM bookings "
        "WHERE experiment_context @> %s::jsonb",
        (json.dumps({"demo_activity": MARKER}),),
    ).fetchone()["n"]
    return bool(n)


def wipe(conn) -> dict[str, int]:
    removed = {}
    removed["bookings"] = len(conn.execute(
        "DELETE FROM bookings WHERE experiment_context @> %s::jsonb RETURNING id",
        (json.dumps({"demo_activity": MARKER}),),
    ).fetchall())
    removed["run_logs"] = len(conn.execute(
        "DELETE FROM run_logs WHERE parameters LIKE %s RETURNING id", (f"%{TOKEN}%",),
    ).fetchall())
    removed["work_orders"] = len(conn.execute(
        "DELETE FROM work_orders WHERE source = %s RETURNING id", (TAG,),
    ).fetchall())
    removed["automation_events"] = len(conn.execute(
        "DELETE FROM automation_events WHERE target LIKE %s RETURNING id", (f"%{TAG}%",),
    ).fetchall())
    return removed


def seed(conn) -> dict[str, int]:
    profiles = _profiles_by_email()
    counts = {"bookings": 0, "run_logs": 0, "work_orders": 0, "hitl": 0, "automations": 0}

    # --- Bookings spread across the demo week ---
    for email, instr, off, hour, dur, status, goal in ACTIVITY_BOOKINGS:
        p = profiles.get(email)
        if not p:
            continue
        start = _dt(off, hour)
        end = start + timedelta(hours=dur)
        # created_at staggered so the activity feed reads "submitted N ago".
        created = start - timedelta(days=3, hours=hour)
        conn.execute(
            """INSERT INTO bookings
               (instrument_id, user_id, researcher_name, researcher_email,
                start_time, end_time, status, experiment_context, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (instr, p["id"], p["full_name"], email, start, end, status,
             json.dumps(_ctx(p, instr, goal)), created),
        )
        counts["bookings"] += 1

    # --- Recent run logs ---
    for email, instr, off, material, params, outcome, quality in ACTIVITY_RUNS:
        p = profiles.get(email)
        name = p["full_name"] if p else email
        conn.execute(
            """INSERT INTO run_logs (instrument_id, researcher_name, material_type,
               parameters, outcome, quality_rating, run_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (instr, name, material, f"{params} {TOKEN}", outcome, quality, _dt(off, 12)),
        )
        counts["run_logs"] += 1

    # --- One fresh OPEN work order so "maintenance" shows an active alert ---
    conn.execute(
        """INSERT INTO work_orders (instrument_id, issue, severity, usage_hours,
           calibration_interval_hours, recommended_action, status, created_at, source)
           VALUES (%s,%s,%s,%s,%s,%s,'open',%s,%s)""",
        ("tube-furnace",
         "Setpoint drift +18°C at 1100°C observed on consecutive runs",
         "critical", 612.0, 600.0,
         "Recalibrate control thermocouple; block bookings until verified",
         _dt(-1, 16), TAG),
    )
    counts["work_orders"] += 1

    # --- One fresh PENDING HITL request (hazmat) so the queue looks active ---
    p = profiles.get("panand@demo.mines.edu")
    if p:
        payload = {
            "action": "new_booking",
            "researcher_email": p["email"],
            "researcher_name": p["full_name"],
            "instrument_name": "Agilent 7900 ICP-MS",
            "instrument_id": "icp-ms",
            "experiment": "Trace metals in HF-digested drainage water",
            "booking_code": f"{TAG}-HITL",
            "when": _dt(0, 15).strftime("%a, %b %d · %I:%M %p"),
            "reasons": ["Hazardous materials detected: hydrofluoric acid — EH&S review required."],
        }
        conn.execute(
            """INSERT INTO automation_events (kind, status, target, detail, payload, created_at)
               VALUES ('hitl_request','pending',%s,%s,%s::jsonb,%s)""",
            (f"{TAG}-HITL", "Hazmat review required — pending EH&S sign-off",
             json.dumps(payload), _dt(0, 8)),
        )
        counts["hitl"] += 1

    # --- Per-persona HITL requests in every state (so My Requests populates) ---
    for idx, (email, instr_id, instr_name, goal, status, fit, grade, alert_title, reason) in enumerate(ACTIVITY_HITL):
        p = profiles.get(email)
        if not p:
            continue
        code, payload = _hitl_payload(p, instr_id, instr_name, goal, status, fit, grade, alert_title, reason, idx)
        created = _dt(0, 8) - timedelta(hours=idx + 1)
        conn.execute(
            """INSERT INTO automation_events (kind, status, target, detail, payload, created_at)
               VALUES ('hitl_request', %s, %s, %s, %s::jsonb, %s)""",
            (status, f"{TAG}-HITL-{idx}", f"{code} — {alert_title}", json.dumps(payload), created),
        )
        counts["hitl"] += 1

    # --- Work orders on instruments personas have upcoming bookings on ---
    for instr_id, issue, sev, uh, cih, action, status in AFFECTING_WO:
        conn.execute(
            """INSERT INTO work_orders (instrument_id, issue, severity, usage_hours,
               calibration_interval_hours, recommended_action, status, created_at, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (instr_id, issue, sev, uh, cih, action, status, _dt(-1, 10), TAG),
        )
        counts["work_orders"] += 1

    # --- A few recent automation events for a lively feed ---
    feed = [
        ("email", "sent", "Booking confirmed: VEIN — JEOL SEM-EDS", _dt(0, 8, 5)),
        ("booking_sync", "queued", "Airtable push: SEM-EDS session", _dt(0, 8, 6)),
        ("email", "sent", "SOP generated + emailed: ICP-MS drainage run", _dt(0, 11, 2)),
        ("email", "sent", "Maintenance alert: tube furnace setpoint drift", _dt(-1, 16, 3)),
    ]
    for kind, status, detail, created in feed:
        conn.execute(
            """INSERT INTO automation_events (kind, status, target, detail, payload, created_at)
               VALUES (%s,%s,%s,%s,'{}'::jsonb,%s)""",
            (kind, status, f"{TAG}", detail, created),
        )
        counts["automations"] += 1

    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wipe", action="store_true", help="Remove the v1 activity layer")
    ap.add_argument("--seed", action="store_true", help="Force (re)seed even after --wipe")
    args = ap.parse_args()

    init_db()
    with get_conn() as conn:
        if args.wipe:
            r = wipe(conn)
            print(f"[wipe] removed {r}")
            if not args.seed:
                return 0
        if already_seeded(conn) and not args.seed:
            print("[skip] activity layer already present — use --wipe --seed to reset.")
            return 0
        c = seed(conn)
        print(f"[seed] inserted {c}")
    print("[done] demo activity layer is live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
