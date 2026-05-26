"""Postgres (Supabase) data layer.

Public function signatures are identical to the previous SQLite layer, and the
dicts returned are byte-compatible with the old ones: datetimes come back as ISO
strings and jsonb/array columns as JSON strings. That keeps routers, agents, and
the frontend unchanged after the cutover. The richer jsonb/timestamptz schema
lives in Postgres; all shimming is contained here.
"""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from vein.config import settings, ensure_dirs, LOCAL_TZ_NAME

_pool = None


def _configure_connection(conn) -> None:
    """Set the Postgres session timezone to the local one.

    Without this, Supabase defaults to UTC. The scheduler builds naive
    ``datetime.now()`` values (local wall-clock); Postgres would interpret
    those as UTC, so a 2 PM MT booking would be stored as 2 PM UTC and read
    back displayed as 2 PM — but it actually represented 8 AM local. Aligning
    the session TZ makes the naive round-trip preserve wall-clock time.
    """
    # SET TIME ZONE doesn't support parameter binding (it expects a literal),
    # so use the equivalent set_config() function which does. Commit so the
    # pool sees the connection back in IDLE state (configure callbacks must
    # not leave an open transaction).
    conn.execute("SELECT set_config('TimeZone', %s, false)", (LOCAL_TZ_NAME,))
    conn.commit()


def _get_pool():
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured; set it in .env")
        from psycopg_pool import ConnectionPool

        # The admin/analytics pages fan out ~8-10 parallel queries (bookings,
        # utilization, work-orders, automations, hitl, equity, audit) and
        # re-fire on 15s polling + realtime invalidations. max_size=5 let that
        # burst exhaust the pool and hit a 30s PoolTimeout (looks like the app
        # hanging). 12 comfortably covers the fan-out and stays well under
        # Supabase's transaction-pooler ceiling. timeout fails fast rather than
        # hanging a request for 30s if it ever does saturate.
        _pool = ConnectionPool(
            settings.database_url,
            min_size=2,
            max_size=12,
            timeout=10.0,
            kwargs={"row_factory": dict_row},
            configure=_configure_connection,
            open=False,
        )
        _pool.open()
    return _pool


@contextmanager
def get_conn():
    """Yield a pooled connection. Commits on clean exit, rolls back on error."""
    pool = _get_pool()
    with pool.connection() as conn:
        yield conn


def init_db() -> None:
    """Schema is provisioned by supabase/setup.sql. Ensure dirs + pool reachable."""
    ensure_dirs()
    _get_pool()


def row_to_dict(row: dict) -> dict[str, Any]:
    """Legacy SQLite dict shape: naive ISO strings for datetimes, JSON strings
    for jsonb/array values. Postgres returns timestamptz as tz-aware datetimes;
    we drop the offset so downstream code that builds naive datetimes (the
    scheduler's conflict checks, utilization math) can compare without hitting
    'offset-naive vs offset-aware' TypeErrors — matching the old SQLite layer."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = (v.replace(tzinfo=None) if v.tzinfo else v).isoformat()
        elif isinstance(v, (dict, list)):
            out[k] = json.dumps(v)
        else:
            out[k] = v
    return out


def get_instruments() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM instruments ORDER BY name").fetchall()
    return [row_to_dict(r) for r in rows]


def get_instrument(instrument_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM instruments WHERE id = %s", (instrument_id,)).fetchone()
    return row_to_dict(row) if row else None


def get_bookings(instrument_id: Optional[str] = None, email: Optional[str] = None) -> list[dict]:
    q = ("SELECT b.*, i.name as instrument_name, i.location as instrument_location "
         "FROM bookings b JOIN instruments i ON b.instrument_id = i.id")
    clauses: list[str] = []
    params: list = []
    if instrument_id:
        clauses.append("b.instrument_id = %s")
        params.append(instrument_id)
    if email:
        clauses.append("LOWER(b.researcher_email) = LOWER(%s)")
        params.append(email)
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY b.start_time"
    with get_conn() as conn:
        rows = conn.execute(q, tuple(params)).fetchall()
    return [row_to_dict(r) for r in rows]


def get_lab_day_bookings(email: str) -> list[dict]:
    """Today's bookings at every location where this user has any non-cancelled
    booking — so a researcher can see who else is in their lab today, without
    being able to see the whole facility's schedule.
    """
    mine = get_bookings(email=email)
    locations = {
        (b.get("instrument_location") or "").strip()
        for b in mine
        if b.get("status") != "cancelled" and (b.get("instrument_location") or "").strip()
    }
    if not locations:
        return []
    today = datetime.now().date()
    out: list[dict] = []
    for b in get_bookings():
        if b.get("status") == "cancelled":
            continue
        if (b.get("instrument_location") or "").strip() not in locations:
            continue
        try:
            if datetime.fromisoformat(b["start_time"]).date() == today:
                out.append(b)
        except Exception:  # noqa: BLE001
            continue
    return out


def get_admin_emails() -> list[str]:
    """Every profile with role='admin'. Used to fan out HITL approval requests
    to every admin instead of a single hard-coded address."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT email FROM profiles WHERE role = 'admin' AND email IS NOT NULL"
        ).fetchall()
    return [r["email"] for r in rows if r["email"]]


def _resolve_user_id_by_email(conn, email: str) -> Optional[str]:
    """Look up profiles.id (UUID) by email so realtime RLS can match the row
    back to the signed-in user. Returns None if no matching profile."""
    if not email:
        return None
    row = conn.execute(
        "SELECT id FROM profiles WHERE lower(email) = lower(%s) LIMIT 1", (email,),
    ).fetchone()
    return row["id"] if row else None


def create_booking(
    instrument_id: str,
    researcher_name: str,
    researcher_email: str,
    start_time: datetime,
    end_time: datetime,
    experiment_context: dict,
    sop_path: Optional[str] = None,
    user_id: Optional[str] = None,
) -> int:
    with get_conn() as conn:
        # If caller didn't supply user_id (the form path doesn't), look it up
        # from the email so Supabase realtime push routes the row to the
        # right authenticated session via the bookings_owner_read policy.
        if user_id is None:
            user_id = _resolve_user_id_by_email(conn, researcher_email)
        row = conn.execute(
            """INSERT INTO bookings (instrument_id, researcher_name, researcher_email,
               start_time, end_time, experiment_context, sop_path, user_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                instrument_id,
                researcher_name,
                researcher_email,
                start_time,
                end_time,
                Jsonb(experiment_context),
                sop_path,
                user_id,
            ),
        ).fetchone()
        return int(row["id"])


def get_run_logs(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM run_logs ORDER BY run_date DESC LIMIT %s", (limit,)
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def add_run_log(
    instrument_id: str,
    researcher_name: str,
    material_type: str,
    parameters: str,
    outcome: str,
    quality_rating: int,
    booking_id: Optional[int] = None,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO run_logs (instrument_id, researcher_name, material_type,
               parameters, outcome, quality_rating, run_date, booking_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                instrument_id,
                researcher_name,
                material_type,
                parameters,
                outcome,
                quality_rating,
                datetime.now(),
                booking_id,
            ),
        ).fetchone()
        return int(row["id"])


def add_maintenance_log(
    instrument_id: str,
    error_code: str,
    description: str,
    action_taken: str,
    severity: str,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO maintenance_logs (instrument_id, error_code, description,
               action_taken, severity, logged_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (instrument_id, error_code, description, action_taken, severity, datetime.now()),
        ).fetchone()
        return int(row["id"])


def get_maintenance_logs(instrument_id: Optional[str] = None) -> list[dict]:
    q = "SELECT * FROM maintenance_logs"
    params: tuple = ()
    if instrument_id:
        q += " WHERE instrument_id = %s"
        params = (instrument_id,)
    q += " ORDER BY logged_at DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]


def get_utilization() -> list[dict]:
    """Weekly utilization per instrument for heatmap."""
    instruments = get_instruments()
    bookings = get_bookings()
    now = datetime.now()
    weeks = []
    for w in range(4):
        start = now - timedelta(weeks=3 - w)
        weeks.append(start.strftime("%b %d"))

    result = []
    for inst in instruments:
        hours = [0.0] * 4
        for b in bookings:
            if b["instrument_id"] != inst["id"] or b["status"] == "cancelled":
                continue
            bt = datetime.fromisoformat(b["start_time"])
            et = datetime.fromisoformat(b["end_time"])
            duration = (et - bt).total_seconds() / 3600
            for i in range(4):
                week_start = now - timedelta(weeks=3 - i)
                week_end = week_start + timedelta(days=7)
                # compare naive vs aware safely by stripping tz
                bt_cmp = bt.replace(tzinfo=None)
                if week_start <= bt_cmp < week_end:
                    hours[i] += duration
        for i, label in enumerate(weeks):
            result.append({
                "instrument": inst["name"],
                "week": label,
                "hours": round(hours[i], 1),
                "instrument_id": inst["id"],
            })
    return result


def get_rag_stats() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rag_metadata ORDER BY indexed_at DESC").fetchall()
    docs = [row_to_dict(r) for r in rows]
    total_chunks = sum(d.get("chunk_count", 0) for d in docs)
    last_update = docs[0]["indexed_at"] if docs else None
    return {"documents": docs, "total_chunks": total_chunks, "last_update": last_update}


def log_agent_decision(
    session_id: str,
    agent: str,
    input_summary: str,
    output_summary: str,
    reasoning: str,
    confidence: int,
    rag_chunks: list[dict],
    citations: list[dict],
    outcome: str,
) -> int:
    trimmed = [{"source": c.get("source"), "section": c.get("section"), "page": c.get("page")} for c in rag_chunks][:8]
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO agent_decisions (session_id, agent, input_summary, output_summary,
               reasoning, confidence, rag_chunks, citations, outcome, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                session_id,
                agent,
                input_summary[:500],
                output_summary[:1000],
                reasoning[:2000],
                confidence,
                Jsonb(trimmed),
                Jsonb(citations[:8]),
                outcome,
                datetime.now(),
            ),
        ).fetchone()
        return int(row["id"])


def get_agent_decisions(session_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    # Alias jsonb columns back to the *_json names the frontend expects; row_to_dict
    # then serializes the jsonb values to JSON strings.
    q = """SELECT id, session_id, agent, input_summary, output_summary, reasoning,
                  confidence, rag_chunks AS rag_chunks_json, citations AS citations_json,
                  outcome, created_at
           FROM agent_decisions"""
    params: tuple = ()
    if session_id:
        q += " WHERE session_id = %s"
        params = (session_id,)
    q += " ORDER BY created_at DESC LIMIT %s"
    with get_conn() as conn:
        rows = conn.execute(q, params + (limit,)).fetchall()
    return [row_to_dict(r) for r in rows]


def create_work_order(
    instrument_id: str,
    issue: str,
    severity: str,
    usage_hours: float,
    calibration_interval_hours: float,
    recommended_action: str,
    source: str,
) -> int:
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO work_orders (instrument_id, issue, severity, usage_hours,
               calibration_interval_hours, recommended_action, status, created_at, source)
               VALUES (%s, %s, %s, %s, %s, %s, 'open', %s, %s) RETURNING id""",
            (
                instrument_id, issue, severity, usage_hours, calibration_interval_hours,
                recommended_action, datetime.now(), source,
            ),
        ).fetchone()
        return int(row["id"])


def update_work_order_status(work_order_id: int, status: str) -> Optional[dict]:
    """Move a ticket through open → in_progress → closed. Returns the row."""
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE work_orders SET status = %s WHERE id = %s RETURNING *",
            (status, work_order_id),
        ).fetchone()
    return row_to_dict(row) if row else None


def assign_work_order(work_order_id: int, team: str) -> Optional[dict]:
    """Route a work order to a responsible team (Lab Tech / Facilities / …)."""
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE work_orders SET assigned_team = %s WHERE id = %s RETURNING *",
            (team, work_order_id),
        ).fetchone()
    return row_to_dict(row) if row else None


def add_work_order_note(work_order_id: int, author: str, text: str) -> Optional[dict]:
    """Append a review comment to the work order's notes (jsonb array).

    Each note is ``{author, text, at}``. Uses jsonb concat so concurrent adds
    don't clobber each other.
    """
    note = {"author": author or "—", "text": text, "at": datetime.now().isoformat()}
    with get_conn() as conn:
        row = conn.execute(
            """UPDATE work_orders
               SET notes = COALESCE(notes, '[]'::jsonb) || %s::jsonb
               WHERE id = %s RETURNING *""",
            (Jsonb([note]), work_order_id),
        ).fetchone()
    return row_to_dict(row) if row else None


def record_automation_event(
    kind: str,
    status: str,
    target: str = "",
    detail: str = "",
    payload: Optional[dict] = None,
    error: Optional[str] = None,
) -> int:
    """Append an audit row for an automation attempt (email/booking_sync/work_order)."""
    with get_conn() as conn:
        row = conn.execute(
            """INSERT INTO automation_events (kind, status, target, detail, payload, error, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (kind, status, target, detail, Jsonb(payload or {}), error, datetime.now()),
        ).fetchone()
        return int(row["id"])


def get_automation_events(kind: Optional[str] = None, limit: int = 50) -> list[dict]:
    q = "SELECT * FROM automation_events"
    params: tuple = ()
    if kind:
        q += " WHERE kind = %s"
        params = (kind,)
    q += " ORDER BY created_at DESC LIMIT %s"
    with get_conn() as conn:
        rows = conn.execute(q, params + (limit,)).fetchall()
    return [row_to_dict(r) for r in rows]


def get_automation_event(event_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM automation_events WHERE id = %s", (event_id,)).fetchone()
    return row_to_dict(row) if row else None


def find_hitl_by_session(session_id: str) -> Optional[dict]:
    """Latest HITL request row for a session — used by approve/deny endpoints."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM automation_events
               WHERE kind = 'hitl_request' AND target = %s
               ORDER BY created_at DESC LIMIT 1""",
            (session_id,),
        ).fetchone()
    return row_to_dict(row) if row else None


def update_automation_event_status(
    event_id: int,
    status: str,
    *,
    detail: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[dict]:
    """Used by HITL approve/deny + cron triggers to mutate state in place."""
    sets = ["status = %s"]
    params: list = [status]
    if detail is not None:
        sets.append("detail = %s")
        params.append(detail)
    if error is not None:
        sets.append("error = %s")
        params.append(error)
    with get_conn() as conn:
        row = conn.execute(
            f"UPDATE automation_events SET {', '.join(sets)} WHERE id = %s RETURNING *",
            (*params, event_id),
        ).fetchone()
    return row_to_dict(row) if row else None


def get_work_orders(status: Optional[str] = None) -> list[dict]:
    q = "SELECT w.*, i.name as instrument_name FROM work_orders w LEFT JOIN instruments i ON w.instrument_id = i.id"
    params: tuple = ()
    if status:
        q += " WHERE w.status = %s"
        params = (status,)
    q += " ORDER BY w.created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
    return [row_to_dict(r) for r in rows]


def get_instrument_usage_hours(instrument_id: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0), 0) AS hrs
               FROM bookings WHERE instrument_id = %s AND status != 'cancelled'""",
            (instrument_id,),
        ).fetchone()
    return float(row["hrs"]) if row else 0.0


def get_group_utilization(weeks: int = 4) -> list[dict]:
    """Booking concentration by research group for equity monitoring."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT experiment_context, start_time, end_time
               FROM bookings WHERE status != 'cancelled'
               AND start_time >= now() - make_interval(days => %s)""",
            (weeks * 7,),
        ).fetchall()
    totals: dict[str, float] = {}
    for r in rows:
        ec = r["experiment_context"] or {}
        if isinstance(ec, str):
            try:
                ec = json.loads(ec or "{}")
            except json.JSONDecodeError:
                ec = {}
        grp = ec.get("research_group") or "Unassigned"
        hrs = (r["end_time"] - r["start_time"]).total_seconds() / 3600
        totals[grp] = totals.get(grp, 0) + hrs
    total = sum(totals.values()) or 1.0
    return sorted(
        [{"group": g, "hours": round(h, 1), "pct": round(h / total * 100, 1)} for g, h in totals.items()],
        key=lambda r: r["hours"],
        reverse=True,
    )


def upsert_rag_metadata(corpus_type: str, document_name: str, chunk_count: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO rag_metadata (corpus_type, document_name, chunk_count, indexed_at)
               VALUES (%s, %s, %s, %s)""",
            (corpus_type, document_name, chunk_count, datetime.now()),
        )
