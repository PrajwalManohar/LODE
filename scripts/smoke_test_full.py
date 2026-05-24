"""Full E2E smoke test — intake, clarify, safety gate, confirm, post-run, governance."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vein.bootstrap import bootstrap
from vein.agents.graph import run_intake_graph, run_confirm_graph, run_postrun_graph
from vein.agents.safety import evaluate_safety_gate
from vein.db.database import get_agent_decisions, get_group_utilization, get_work_orders
from vein.models.experiment import PostRunReport


def main():
    print("[1] bootstrap")
    print("   ", bootstrap(reindex=False))

    print("[2] intake turn 1 (uncoated steel)")
    msg1 = (
        "I'm running hydrogen permeation tests on martensitic steel specimens. "
        "I need to characterize fracture surface morphology. Samples are 5mm x 5mm uncoated. "
        "Results by Thursday."
    )
    r1 = run_intake_graph(msg1, [], None)
    print(f"    reply: {r1.message[:90]}...")
    print(f"    needs_clarification={r1.needs_clarification} session={r1.session_id}")

    print("[3] intake turn 2 (yes coating)")
    history = [
        {"role": "user", "content": msg1},
        {"role": "assistant", "content": r1.message},
    ]
    r2 = run_intake_graph("Yes please include the coating prep time", history, r1.context, session_id=r1.session_id)
    print(f"    recs={len(r2.recommendations)} slots={len(r2.booking_options)} cites={len(r2.citations)}")
    print(f"    top: {r2.recommendations[0].instrument_name} score={r2.recommendations[0].fit_score}")
    print(f"    safety_gate.passed={r2.safety_gate.passed if r2.safety_gate else None} reasons={r2.safety_gate.reasons if r2.safety_gate else []}")

    print("[4] confirm (researcher TRAINED, in 'GeoChem-Lab' group)")
    ctx = r2.context
    ctx.researcher_name = "Test Researcher"
    ctx.researcher_email = "test@mines.edu"
    ctx.research_group = "GeoChem-Lab"
    ctx.trained_instruments = ["SEM-Operator", "XRD-Safety-101"]
    r3 = run_confirm_graph(ctx, r2.booking_options[0], r2.recommendations[0], session_id=r2.session_id)
    print(f"    {r3.message}")
    assert r3.sop_path and Path(r3.sop_path).exists(), "SOP missing"
    print(f"    sop:        {Path(r3.sop_path).name}")
    print(f"    airtable:   {r3.automations['airtable_booking']}")
    print(f"    email:      transport={r3.automations['email']['transport']} sent={r3.automations['email']['sent']}")
    print(f"    work_order: {r3.automations.get('work_order')}")

    print("[5] post-run with anomaly (triggers Agent 5 + work order)")
    report = PostRunReport(
        booking_id=1, ran_as_planned=False,
        actual_parameters="15 kV, EDS, sample charging observed",
        anomalies="Detector saturation on consecutive scans",
        data_quality_rating=2, notes="needed coating thickness check",
        researcher_name="Test Researcher",
    )
    r4 = run_postrun_graph(report, session_id=r2.session_id)
    print(f"    {r4['message']}  maintenance_alert={r4['maintenance_alert']}")
    print(f"    work_order={r4.get('work_order')}")

    print("[6] refusal: hazmat HF acid")
    hazmsg = "I need ICP-MS on a sample digested in hydrofluoric acid"
    rh = run_intake_graph(hazmsg, [], None)
    print(f"    hazmat={rh.context.hazardous_materials if rh.context else None} review_required={rh.context.hazmat_review_required if rh.context else None}")
    print(f"    gate.passed={rh.safety_gate.passed if rh.safety_gate else 'n/a'} reasons={(rh.safety_gate.reasons if rh.safety_gate else [])[:2]}")

    print("[7] audit log")
    decisions = get_agent_decisions(session_id=r2.session_id, limit=20)
    print(f"    {len(decisions)} agent decisions for session {r2.session_id}")
    for d in decisions[:6]:
        print(f"      • {d['agent']:18s} -> {d['outcome']:8s} conf={d['confidence']:3d}  {d['output_summary'][:60]}")

    print("[8] equity / utilization")
    eq = get_group_utilization(weeks=8)
    for row in eq[:5]:
        print(f"    {row['group']:20s} {row['hours']:6.1f}h  {row['pct']:5.1f}%")

    print("[9] work orders")
    for wo in get_work_orders()[:5]:
        print(f"    #{wo['id']} {wo['instrument_id']:14s} {wo['severity']:8s} {wo['issue'][:60]}")

    print("[10] airtable + email queues on disk")
    for p in ["data/airtable_queue/LODE_Bookings.jsonl",
              "data/airtable_queue/LODE_WorkOrders.jsonl",
              "data/email_outbox/outbox.jsonl"]:
        path = ROOT / p
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        print(f"    {p}: {len(lines)} record(s)")

    print("\nFULL E2E + GOVERNANCE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
