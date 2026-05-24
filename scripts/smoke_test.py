"""Quick smoke test — run: python scripts/smoke_test.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vein.bootstrap import bootstrap
from vein.agents.graph import run_intake_graph


def main():
    print("1. Bootstrap...")
    result = bootstrap(reindex=True)
    print("  ", result)

    print("2. Intake graph (hydrogen embrittlement demo)...")
    msg = (
        "I'm running hydrogen permeation tests on martensitic steel specimens. "
        "I need to characterize fracture surface morphology. Samples are 5mm x 5mm uncoated. "
        "I need results by Thursday."
    )
    resp = run_intake_graph(msg, [], None)
    print("  Message:", resp.message[:120], "...")
    print("  Recommendations:", len(resp.recommendations))
    if resp.recommendations:
        top = resp.recommendations[0]
        print(f"  Top: {top.instrument_name} score={top.fit_score} grade={top.grade}")
    print("  Booking options:", len(resp.booking_options))
    print("  Citations:", len(resp.citations))
    print("\nSmoke test OK")


if __name__ == "__main__":
    main()
