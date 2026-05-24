"""Hard-coded refusal rules and the human-in-the-loop safety gate.

These rules are architectural — they are enforced inside the LangGraph and
cannot be bypassed from the UI. Spec source: LODE design doc §"Governance
Framework" and §"Five-Agent Architecture / safety gate".
"""

from __future__ import annotations

import re
from typing import Iterable

from vein.db.database import get_instrument, get_instrument_usage_hours
from vein.models.experiment import ExperimentContext, InstrumentFit, SafetyGateResult

HAZMAT_KEYWORDS: tuple[str, ...] = (
    "hydrofluoric", "hf acid", "hf ", "perchloric",
    "radioactive", "uranium", "thorium", "plutonium",
    "beryllium", "mercury", "cyanide", "arsenic",
    "pyrophoric", "nanoparticle", "asbestos",
    "concentrated nitric", "aqua regia", "chromium vi", "hexavalent chromium",
    "explosive", "lithium metal", "white phosphorus",
)

CONFIDENCE_FLOOR = 80  # per spec: "Fit Scorer's confidence falls below 80%"


def detect_hazardous_materials(*texts: str) -> list[str]:
    blob = " ".join(t.lower() for t in texts if t)
    hits: list[str] = []
    for kw in HAZMAT_KEYWORDS:
        if kw in blob and kw not in hits:
            hits.append(kw)
    # detect concentrated acid/base patterns
    if re.search(r"\b(conc\.?|concentrated)\s+(h2so4|hcl|hno3|naoh|koh)\b", blob):
        hits.append("concentrated acid/base")
    return hits


def evaluate_safety_gate(
    ctx: ExperimentContext,
    top: InstrumentFit | None,
) -> SafetyGateResult:
    """Decides whether to advance to Agent 4 or escalate to a human reviewer.

    Refusal triggers per spec:
      - Researcher lacks documented training for the selected instrument
      - Instrument has an active maintenance flag or overdue calibration
      - Experiment description contains hazardous-material keywords
      - Fit Scorer's confidence falls below 80%
    """
    reasons: list[str] = []

    if top is None:
        return SafetyGateResult(passed=False, requires_review=True, reasons=["No instrument recommendation available."])

    # 1. Training
    inst = get_instrument(top.instrument_id) or {}
    required = (inst.get("required_training") or "").strip()
    if required and required not in (ctx.trained_instruments or []):
        reasons.append(
            f"Researcher lacks documented training for {top.instrument_name} (required: {required})."
        )

    # 2. Maintenance state + calibration overdue
    if inst.get("status") == "maintenance":
        reasons.append(f"{top.instrument_name} is under active maintenance.")
    interval = inst.get("calibration_interval_hours") or 0
    if interval:
        used = get_instrument_usage_hours(top.instrument_id)
        if used >= interval:
            reasons.append(
                f"Calibration overdue: {used:.1f}h logged vs {interval}h interval."
            )

    # 3. Hazmat
    if ctx.hazmat_review_required or ctx.hazardous_materials:
        reasons.append(
            f"Hazardous materials detected ({', '.join(ctx.hazardous_materials) or 'flagged'}) — EH&S review required."
        )

    # 4. Confidence
    confidence = top.confidence or top.fit_score
    if confidence < CONFIDENCE_FLOOR:
        reasons.append(
            f"Fit confidence {confidence}/100 below {CONFIDENCE_FLOOR}% threshold."
        )

    passed = not reasons
    return SafetyGateResult(passed=passed, requires_review=not passed, reasons=reasons)


def annotate_hazmat(ctx: ExperimentContext, *extra_texts: str) -> ExperimentContext:
    """Mutates ctx in place: populates hazardous_materials + hazmat_review_required."""
    hits = detect_hazardous_materials(
        ctx.material_type, ctx.analysis_goal, ctx.notes, ctx.surface_condition,
        ctx.coating_status, *extra_texts,
    )
    if hits:
        ctx.hazardous_materials = hits
        ctx.hazmat_review_required = True
    return ctx
