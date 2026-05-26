"""LLM-driven email copy for LODE.

Generates short, contextual intro paragraphs and prep guidance for each email
type so the body reads less like a template and more like a personalized
message. Falls back to deterministic copy when no LLM is configured.
"""

from __future__ import annotations

import logging
from typing import Optional

from vein.agents.llm import has_llm, invoke_json
from vein.models.experiment import ExperimentContext, InstrumentFit

logger = logging.getLogger("vein.email_ai")


# ---------------------------------------------------------------------------
# Booking confirmation
# ---------------------------------------------------------------------------
_BOOKING_SYSTEM = """You write short, friendly email copy for LODE, the Colorado School of Mines
Shared Instrumentation Facility booking system. The reader is a researcher
who just had their lab session confirmed. Be specific to their experiment
(material, goal, deadline). Write in active voice, two sentences maximum.

Return JSON ONLY:
{
  "intro": "<2 sentences customized to the experiment>",
  "prep_tip": "<one actionable prep tip (≤ 25 words) grounded in the SOP>"
}"""


def booking_intro(
    ctx: ExperimentContext,
    fit: InstrumentFit,
    when: str,
) -> dict:
    """Return {intro, prep_tip} strings for the booking confirmation email."""
    fallback = {
        "intro": (
            f"Your {fit.instrument_name} session for "
            f"{ctx.analysis_goal or 'your experiment'} on {ctx.material_type or 'your sample'} "
            f"has been confirmed for {when}. The attached SOP has been customized to your "
            f"sample and includes the recommended operating parameters."
        ),
        "prep_tip": (
            f"Arrive ~45 minutes before your slot so you have time for the "
            f"{fit.instrument_name} warm-up cycle and any sample prep noted in the SOP."
        ),
    }
    if not has_llm():
        return fallback

    user = (
        f"Researcher: {ctx.researcher_name or '—'} ({ctx.research_group or '—'})\n"
        f"Instrument: {fit.instrument_name}\n"
        f"Material: {ctx.material_type or '—'}\n"
        f"Analysis goal: {ctx.analysis_goal or '—'}\n"
        f"Sample form: {ctx.sample_dimensions or '—'}\n"
        f"Coating / prep: {ctx.coating_status or '—'}\n"
        f"Deadline / urgency: {ctx.deadline or ctx.urgency}\n"
        f"Booking window: {when}\n"
        f"Fit rationale: {fit.rationale}\n"
    )
    try:
        data = invoke_json(_BOOKING_SYSTEM, user)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM booking intro failed: %s", exc)
        return fallback
    if isinstance(data, dict) and data.get("intro"):
        return {
            "intro": str(data["intro"]).strip(),
            "prep_tip": str(data.get("prep_tip") or fallback["prep_tip"]).strip(),
        }
    return fallback


# ---------------------------------------------------------------------------
# HITL approval email
# ---------------------------------------------------------------------------
_HITL_SYSTEM = """You write a short, professional alert message to a lab manager who needs to
review a booking that was flagged by LODE's safety gate. Be specific about
the risk. Two sentences max. Return JSON only:
{ "intro": "<2 sentences>" }"""


def hitl_intro(
    researcher: str,
    instrument: str,
    alert_title: str,
    alert_text: str,
    reasons: list[str],
) -> str:
    fallback = (
        "A booking request has been flagged by the LODE safety gate and requires "
        f"your manual review before it can be confirmed. {alert_title or 'Please review the details below.'}"
    )
    if not has_llm():
        return fallback
    user = (
        f"Researcher: {researcher}\nInstrument: {instrument}\n"
        f"Alert title: {alert_title}\nAlert text: {alert_text}\n"
        f"Refusal reasons: {'; '.join(reasons)}\n"
    )
    try:
        data = invoke_json(_HITL_SYSTEM, user)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM HITL intro failed: %s", exc)
        return fallback
    if isinstance(data, dict) and data.get("intro"):
        return str(data["intro"]).strip()
    return fallback


# ---------------------------------------------------------------------------
# Work-order email
# ---------------------------------------------------------------------------
_WO_SYSTEM = """You write a short maintenance alert to lab facilities. Be specific about the
instrument and the trigger. Two sentences max. Return JSON only:
{ "intro": "<2 sentences>" }"""


def work_order_intro(instrument: str, issue: str, severity: str, triggered_by: str) -> str:
    fallback = (
        "LODE's Post-Run Analyzer has generated a maintenance work order following a recent "
        "session. Immediate scheduling of maintenance is recommended."
    )
    if not has_llm():
        return fallback
    user = (f"Instrument: {instrument}\nIssue: {issue}\nSeverity: {severity}\n"
            f"Triggered by: {triggered_by}\n")
    try:
        data = invoke_json(_WO_SYSTEM, user)
    except Exception:
        return fallback
    if isinstance(data, dict) and data.get("intro"):
        return str(data["intro"]).strip()
    return fallback


# ---------------------------------------------------------------------------
# Monthly report
# ---------------------------------------------------------------------------
_MONTHLY_SYSTEM = """You write a short executive summary for a monthly lab utilization report at
Colorado School of Mines Shared Instrumentation Facility. Be specific about
the numbers. Two sentences max. Return JSON only:
{ "intro": "<2 sentences>", "insights": ["...", "...", "..."] }
Provide 3 short insights (≤ 20 words each)."""


def monthly_intro(
    period: str,
    total_bookings: int,
    sops_generated: int,
    avg_fit: str,
    open_work_orders: int,
    utilization: list[tuple[str, int]],
) -> dict:
    fallback = {
        "intro": (
            f"Here is your automated monthly summary from LODE for {period}. Full details and "
            "charts are available in the attached PDF report."
        ),
        "insights": [
            f"{total_bookings} bookings processed in {period} with avg fit score {avg_fit}/100",
            f"{sops_generated} customized SOPs generated; {open_work_orders} open work orders",
            "Utilization is highest on " + (max(utilization, key=lambda x: x[1])[0] if utilization else "n/a"),
        ],
    }
    if not has_llm():
        return fallback
    util_lines = "\n".join(f"  - {name}: {pct}%" for name, pct in utilization) or "  (none)"
    user = (
        f"Period: {period}\nTotal bookings: {total_bookings}\nSOPs generated: {sops_generated}\n"
        f"Avg fit score: {avg_fit}/100\nOpen work orders: {open_work_orders}\n"
        f"Utilization:\n{util_lines}\n"
    )
    try:
        data = invoke_json(_MONTHLY_SYSTEM, user)
    except Exception:
        return fallback
    if isinstance(data, dict) and data.get("intro"):
        insights = data.get("insights")
        if not isinstance(insights, list) or not insights:
            insights = fallback["insights"]
        return {"intro": str(data["intro"]).strip(),
                "insights": [str(x).strip() for x in insights][:5]}
    return fallback
