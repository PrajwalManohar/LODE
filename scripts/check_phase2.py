"""Phase 2 integration check: exercises the Postgres + pgvector data layer
end-to-end against the live Supabase project and asserts the legacy dict shapes.

Run:  .\.venv\Scripts\python.exe scripts\check_phase2.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vein.bootstrap import bootstrap
from vein.db import database as db


def main() -> int:
    print("== bootstrap (seed + pgvector index) ==")
    res = bootstrap(reindex=True)
    print("  ", res)

    print("== instruments ==")
    insts = db.get_instruments()
    print(f"   count={len(insts)} first={insts[0]['name'] if insts else None}")
    assert len(insts) == 5, "expected 5 seeded instruments"

    print("== RAG query (pgvector) ==")
    from vein.rag.indexer import query_corpus
    hits = query_corpus("hydrogen embrittlement steel fracture SEM", n_results=3, instrument_id="sem-jeol")
    for h in hits:
        print(f"   [{h['distance']:.3f}] {h['source']} §{h['section']} :: {h['text'][:60]}...")
    assert hits and "text" in hits[0] and hits[0]["text"], "expected RAG hits with text"

    print("== create + read booking (shape check) ==")
    start = datetime.now() + timedelta(days=1)
    bid = db.create_booking(
        instrument_id="sem-jeol",
        researcher_name="Phase2 Tester",
        researcher_email="tester@mines.edu",
        start_time=start,
        end_time=start + timedelta(hours=2),
        experiment_context={"research_group": "QA-Lab", "material_type": "steel"},
        sop_path=None,
    )
    bk = [b for b in db.get_bookings() if b["id"] == bid][0]
    print(f"   id={bid} start_time={bk['start_time']!r} ctx_type={type(bk['experiment_context']).__name__}")
    assert isinstance(bk["start_time"], str), "start_time must be ISO string"
    assert isinstance(bk["experiment_context"], str), "experiment_context must be JSON string"
    datetime.fromisoformat(bk["start_time"])  # must parse like the old layer

    print("== agent decision (json-string columns) ==")
    did = db.log_agent_decision(
        session_id="phase2-sess",
        agent="Context",
        input_summary="probe",
        output_summary="ok",
        reasoning="because",
        confidence=88,
        rag_chunks=[{"source": "JEOL JSM-IT800 Manual", "section": "3.2", "page": "42"}],
        citations=[{"source": "JEOL JSM-IT800 Manual", "section": "3.2", "page": "42", "excerpt": "..."}],
        outcome="advance",
    )
    dec = db.get_agent_decisions(session_id="phase2-sess", limit=1)[0]
    print(f"   id={did} rag_chunks_json_type={type(dec['rag_chunks_json']).__name__}")
    assert isinstance(dec["rag_chunks_json"], str) and dec["rag_chunks_json"].startswith("["), "rag_chunks_json must be JSON string"
    assert isinstance(dec["citations_json"], str), "citations_json must be JSON string"

    print("== work order + governance aggregates ==")
    wid = db.create_work_order("sem-jeol", "QA probe", "low", 1.0, 400.0, "none", "phase2")
    wos = db.get_work_orders()
    eq = db.get_group_utilization(weeks=8)
    util = db.get_utilization()
    hrs = db.get_instrument_usage_hours("sem-jeol")
    print(f"   work_orders={len(wos)} equity_groups={len(eq)} util_rows={len(util)} sem_hours={hrs:.2f}")
    assert any(w["id"] == wid for w in wos)

    print("\nPHASE 2 DATA LAYER OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
