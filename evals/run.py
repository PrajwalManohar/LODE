"""Run the golden eval set and write a metrics report.

    python evals/run.py                  # run all three suites
    python evals/run.py --suite fit      # only the fit-score suite
    python evals/run.py --json results.json

Writes evals/REPORT.md by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running as `python evals/run.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.cases import fit_cases, parse_cases, safety_cases  # noqa: E402
from vein.agents.pipeline import score_instruments  # noqa: E402
from vein.agents.safety import detect_hazardous_materials, evaluate_safety_gate  # noqa: E402
from vein.models.experiment import ExperimentContext, InstrumentFit  # noqa: E402


# ---------------------------------------------------------------------------
# Suite runners — each returns (passed, total, fail_examples, extra_metrics).
# ---------------------------------------------------------------------------
def run_fit() -> dict:
    cases = fit_cases()
    passed = 0
    fails: list[dict] = []
    for c in cases:
        ctx = ExperimentContext(
            material_type=c["material_type"],
            analysis_goal=c["analysis_goal"],
            is_complete=True,
        )
        recs = score_instruments(ctx, rag_chunks=[])
        if recs and recs[0].instrument_id == c["expected_top"]:
            passed += 1
        elif len(fails) < 5:
            fails.append({
                "id": c["id"], "expected": c["expected_top"],
                "got": recs[0].instrument_id if recs else None,
                "goal": c["analysis_goal"],
            })
    return {
        "name": "fit",
        "total": len(cases),
        "passed": passed,
        "accuracy": passed / len(cases) if cases else 0,
        "metric": "top-1 instrument match",
        "fails": fails,
    }


def run_safety() -> dict:
    cases = safety_cases()
    tp = tn = fp = fn = 0
    fails: list[dict] = []

    for c in cases:
        ctx = ExperimentContext(
            material_type=c["material_type"],
            analysis_goal=c["analysis_goal"],
            trained_instruments=c["trained"],
            hazardous_materials=c["hazardous_materials"],
            hazmat_review_required=bool(c["hazardous_materials"]),
            is_complete=True,
        )
        fit = InstrumentFit(
            instrument_id=c["instrument_id"],
            instrument_name=c["instrument_id"],
            fit_score=c["fit_score"],
            grade="A",
            rationale="(eval)",
            confidence=c["fit_score"],
        )
        gate = evaluate_safety_gate(ctx, fit)

        # Convention: "positive" = gate REFUSED (correct refusal is TP).
        actual_refused = not gate.passed
        expected_refused = not c["expected_passed"]

        if expected_refused and actual_refused:
            tp += 1
        elif not expected_refused and not actual_refused:
            tn += 1
        elif not expected_refused and actual_refused:
            fp += 1
        else:  # expected_refused but passed → false negative (bad)
            fn += 1
            if len(fails) < 5:
                fails.append({
                    "id": c["id"], "expected_class": c["expected_reason_class"],
                    "reasons": gate.reasons,
                })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "name": "safety",
        "total": len(cases),
        "passed": tp + tn,
        "accuracy": (tp + tn) / len(cases) if cases else 0,
        "metric": "refusal precision/recall",
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "fails": fails,
    }


def run_parse() -> dict:
    cases = parse_cases()
    tp = fp = fn = 0
    fails: list[dict] = []

    for c in cases:
        got = detect_hazardous_materials(c["text"])
        # Compare as sets (order doesn't matter)
        expected = set(c["expected"])
        actual = set(got)
        tp += len(expected & actual)
        fp += len(actual - expected)
        fn += len(expected - actual)
        if expected != actual and len(fails) < 5:
            fails.append({"id": c["id"], "text": c["text"], "expected": list(expected), "got": list(actual)})

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    exact = sum(1 for c in cases if set(c["expected"]) == set(detect_hazardous_materials(c["text"])))
    return {
        "name": "parse",
        "total": len(cases),
        "passed": exact,
        "accuracy": exact / len(cases) if cases else 0,
        "metric": "exact-match hazmat list + token-level F1",
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fails": fails,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------
def render_markdown(results: list[dict], elapsed: float) -> str:
    lines = [
        "# LODE — Golden Eval Report",
        f"_Generated {datetime.utcnow().isoformat(timespec='seconds')}Z · {elapsed:.2f}s_",
        "",
        "## Headline metrics",
        "",
        "| Suite | Cases | Passed | Headline metric |",
        "|-------|-------|--------|-----------------|",
    ]
    for r in results:
        if r["name"] == "fit":
            headline = f"top-1 accuracy **{r['accuracy']*100:.1f}%**"
        elif r["name"] == "safety":
            headline = (f"acc **{r['accuracy']*100:.1f}%** · "
                        f"prec **{r['precision']*100:.1f}%** · "
                        f"recall **{r['recall']*100:.1f}%** · "
                        f"F1 **{r['f1']*100:.1f}%**")
        else:
            headline = (f"exact-match **{r['accuracy']*100:.1f}%** · "
                        f"token F1 **{r['f1']*100:.1f}%**")
        lines.append(f"| {r['name']} | {r['total']} | {r['passed']} | {headline} |")

    lines += ["", "## Failures (first 5 per suite)"]
    for r in results:
        lines.append(f"\n### {r['name']}")
        if not r["fails"]:
            lines.append("_All cases passed._")
            continue
        for f in r["fails"]:
            lines.append(f"- `{f['id']}` · " + json.dumps({k: v for k, v in f.items() if k != 'id'}, ensure_ascii=False))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["fit", "safety", "parse", "all"], default="all")
    ap.add_argument("--json", default=None, help="Also write raw JSON results to this path")
    ap.add_argument("--out", default="evals/REPORT.md")
    args = ap.parse_args()

    t0 = time.perf_counter()
    runners = {"fit": run_fit, "safety": run_safety, "parse": run_parse}
    targets = list(runners) if args.suite == "all" else [args.suite]
    results = [runners[t]() for t in targets]
    elapsed = time.perf_counter() - t0

    report = render_markdown(results, elapsed)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"\n[done] Raw results: {args.json}")
    print(f"\n[done] Report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
