"""Hit the live API end-to-end exercising every governance feature."""
import sys
from pathlib import Path
import httpx
import json

BASE = "http://127.0.0.1:8000/api"


def main():
    print("== status ==")
    s = httpx.get(f"{BASE}/status").json()
    print(s)

    print("\n== Scenario A: hazmat refusal (HF acid + ICP-MS) ==")
    r = httpx.post(f"{BASE}/chat/intake", json={
        "message": "I want ICP-MS on samples digested in concentrated hydrofluoric acid",
        "history": [], "context": None,
    }).json()
    print(" hazmat detected:", r.get("context", {}).get("hazardous_materials"))
    print(" review required:", r.get("context", {}).get("hazmat_review_required"))

    print("\n== Scenario B: full success path ==")
    msg1 = "Hydrogen permeation tests on martensitic steel; fracture surface morphology; 5mm x 5mm uncoated; need by Thursday"
    r1 = httpx.post(f"{BASE}/chat/intake", json={
        "message": msg1, "history": [],
        "context": {
            "material_type": "", "analysis_goal": "", "sample_dimensions": "",
            "surface_condition": "", "coating_status": "", "urgency": "medium",
            "researcher_name": "Dr. Test", "researcher_email": "test@mines.edu",
            "research_group": "MetEng-Lab", "trained_instruments": ["SEM-Operator"],
            "notes": "", "is_complete": False,
        },
    }).json()
    sid = r1["session_id"]
    print(f" turn1 needs_clarify={r1['needs_clarification']} session={sid}")
    print(f" turn1 reply: {r1['message'][:80]}...")

    r2 = httpx.post(f"{BASE}/chat/intake", json={
        "message": "yes please include the coating prep time",
        "history": [{"role": "user", "content": msg1},
                    {"role": "assistant", "content": r1["message"]}],
        "context": r1["context"],
        "session_id": sid,
    }).json()
    print(f" turn2 recs={len(r2['recommendations'])} slots={len(r2['booking_options'])}")
    print(f" turn2 top: {r2['recommendations'][0]['instrument_name']} score={r2['recommendations'][0]['fit_score']}")
    print(f" turn2 safety_gate: passed={r2['safety_gate']['passed']} reasons={r2['safety_gate']['reasons']}")

    print(" confirming...")
    confirm = httpx.post(f"{BASE}/chat/confirm", json={
        "context": r2["context"],
        "option": r2["booking_options"][0],
        "recommendation": r2["recommendations"][0],
        "session_id": sid,
    }).json()
    print(f" confirm: {confirm['message']}")
    print(f" automations.airtable: {confirm['automations']['airtable_booking']['id']} → {confirm['automations']['airtable_booking']['destination']}")
    print(f" automations.email:    transport={confirm['automations']['email']['transport']}")
    print(f" SOP url: {BASE}/files/sops/{Path(confirm['sop_path']).name}")

    print("\n== Scenario C: post-run with anomaly → work order ==")
    pr = httpx.post(f"{BASE}/postrun", json={
        "booking_id": 1, "ran_as_planned": False,
        "actual_parameters": "15 kV", "anomalies": "Filament failure during scan",
        "data_quality_rating": 1, "notes": "", "researcher_name": "Dr. Test",
        "session_id": sid,
    }).json()
    print(f" {pr['message']}")
    if pr.get("work_order"):
        print(f" work_order #{pr['work_order']['id']} severity={pr['work_order']['severity']}")

    print("\n== Audit log for session ==")
    decisions = httpx.get(f"{BASE}/admin/audit", params={"session_id": sid, "limit": 20}).json()
    for d in decisions:
        print(f"  {d['agent']:18s} → {d['outcome']:8s} conf={d['confidence']:3d}  {d['output_summary'][:50]}")

    print("\n== Work orders ==")
    for w in httpx.get(f"{BASE}/admin/work-orders").json():
        print(f"  #{w['id']} {w['instrument_id']} {w['severity']} — {w['issue'][:60]}")

    print("\n== Equity ==")
    eq = httpx.get(f"{BASE}/admin/equity", params={"weeks": 8}).json()
    for g in eq["groups"]:
        print(f"  {g['group']:20s} {g['hours']:6.1f}h  {g['pct']:5.1f}%")
    print(f"  flagged: {[g['group'] for g in eq['flagged']]}")

    print("\nLIVE API E2E OK")


if __name__ == "__main__":
    main()
