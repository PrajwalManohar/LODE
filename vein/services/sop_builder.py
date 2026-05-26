"""LLM-driven SOP content builder.

Produces structured SOP content (sample notes, operating parameters table,
pre-session checklist, numbered procedure, post-run checklist) using the
configured LLM (Gemini → Claude) grounded in RAG chunks. The deterministic
fallback (no LLM) still returns the same shape so the renderer in
`sop_docx.py` does not need to branch.

Output schema (returned dict):
{
  "sample_notes":   str,                  # paragraph customized to sample
  "parameters":     [ {label, value, citation?} ],
  "pre_checklist":  [ {text, citation?}  ],   # customized to sample
  "procedure":      [ {title, detail, citation?} ],  # numbered steps
  "post_checklist": [ {text}             ],
  "safety_notes":   [ {text, citation?}  ],
  "references":     [ {label, source, section, page} ],   # RAG references
}
"""

from __future__ import annotations

import logging
from typing import Optional

from vein.agents.llm import has_llm, invoke_json
from vein.models.experiment import BookingOption, ExperimentContext, InstrumentFit
from vein.rag.indexer import query_corpus

logger = logging.getLogger("vein.sop_builder")


# ---------------------------------------------------------------------------
# RAG context block
# ---------------------------------------------------------------------------
def _gather_chunks(ctx: ExperimentContext, fit: InstrumentFit) -> list[dict]:
    query = f"{ctx.material_type} {ctx.analysis_goal} {fit.instrument_name} sample preparation operating parameters"
    chunks = query_corpus(query, n_results=8, instrument_id=fit.instrument_id)
    if len(chunks) < 4:
        chunks += [
            c for c in query_corpus(f"{ctx.material_type} {ctx.analysis_goal}", n_results=4)
            if c not in chunks
        ]
    return chunks[:8]


def _rag_block(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        cite = f"{c.get('source','')}"
        if c.get("section"):
            cite += f", {c['section']}"
        if c.get("page"):
            cite += f", p.{c['page']}"
        lines.append(f"[{i}] {cite}\n    {c.get('text','').strip()}")
    return "\n".join(lines) if lines else "(no RAG matches)"


def _references_from_chunks(chunks: list[dict]) -> list[dict]:
    refs = []
    seen = set()
    for c in chunks:
        key = (c.get("source", ""), c.get("section", ""), c.get("page", ""))
        if key in seen or not c.get("source"):
            continue
        seen.add(key)
        label = c.get("source", "")
        if c.get("section"):
            label += f" — {c['section']}"
        if c.get("page"):
            label += f" (p.{c['page']})"
        refs.append({
            "label": label,
            "source": c.get("source", ""),
            "section": c.get("section", ""),
            "page": c.get("page", ""),
        })
    return refs


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------
_SYSTEM = """You are LODE's SOP Authoring Agent at Colorado School of Mines.

You produce highly customized, instrument-specific Standard Operating
Procedures grounded ONLY in the provided RAG excerpts. Every operating
parameter, checklist item, procedure step, and safety note that comes from a
RAG excerpt MUST include a `citation` field with the exact source / section /
page from that excerpt (e.g. "Bruker D8 Advance Manual, 5.1, p.89").

Be specific to THIS booking — reference the actual material, sample
dimensions, coating status, deadline, and researcher group. Avoid generic
placeholders.

Return JSON ONLY (no prose, no markdown fences) with this shape:
{
  "sample_notes": "<one short paragraph (2-3 sentences) customized to the sample>",
  "parameters": [ {"label": "...", "value": "...", "citation": "..."} ],
  "pre_checklist": [ {"text": "...", "citation": "..."} ],
  "procedure":     [ {"title": "Step name", "detail": "...", "citation": "..."} ],
  "post_checklist":[ {"text": "..."} ],
  "safety_notes":  [ {"text": "...", "citation": "..."} ]
}
- 4-6 parameter rows (numeric where possible).
- 4-7 checklist items in pre_checklist, each ≤ 25 words.
- 5-9 numbered procedure steps with a short title + a sentence-or-two detail.
- 3-5 post_checklist items.
- 2-4 safety notes."""


def _ctx_block(ctx: ExperimentContext, fit: InstrumentFit, booking: BookingOption) -> str:
    return (
        f"Researcher: {ctx.researcher_name or '—'} ({ctx.research_group or '—'})\n"
        f"Instrument: {fit.instrument_name} (id={fit.instrument_id})\n"
        f"Material: {ctx.material_type or '—'}\n"
        f"Analysis goal: {ctx.analysis_goal or '—'}\n"
        f"Sample form / size: {ctx.sample_dimensions or '—'}\n"
        f"Surface condition: {ctx.surface_condition or '—'}\n"
        f"Coating status: {ctx.coating_status or '—'}\n"
        f"Urgency / deadline: {ctx.urgency} / {ctx.deadline or '—'}\n"
        f"Hazardous materials flagged: {', '.join(ctx.hazardous_materials) or 'none'}\n"
        f"Fit rationale: {fit.rationale}\n"
        f"Booking window: {booking.start_time:%Y-%m-%d %H:%M} – {booking.end_time:%H:%M}\n"
        f"Prep window starts: {booking.prep_start:%Y-%m-%d %H:%M}\n"
    )


# ---------------------------------------------------------------------------
# Deterministic fallback content
# ---------------------------------------------------------------------------
def _fallback_content(ctx: ExperimentContext, fit: InstrumentFit, booking: BookingOption,
                      chunks: list[dict]) -> dict:
    material = ctx.material_type or "specimen"
    goal = ctx.analysis_goal or "analysis"
    cite_text = lambda c: (
        f"{c.get('source','')}{(' ' + c['section']) if c.get('section') else ''}"
        f"{(', p.' + c['page']) if c.get('page') else ''}"
    )
    params, pre, proc, post, safety = [], [], [], [], []

    # Pick a few chunks to back the structured content.
    primary = chunks[0] if chunks else {}
    secondary = chunks[1] if len(chunks) > 1 else {}

    if fit.instrument_id == "xrd-d8":
        params = [
            {"label": "Radiation", "value": "Cu Kα" if "chalcopyrite" in material.lower() else "Co Kα",
             "citation": cite_text(primary)},
            {"label": "2θ range", "value": "10–80°" if "chalcopyrite" in material.lower() else "30–100°",
             "citation": cite_text(primary)},
            {"label": "Step size", "value": "0.02°", "citation": cite_text(primary)},
            {"label": "Count time", "value": "2 s / step", "citation": cite_text(primary)},
            {"label": "Tube current", "value": "≤ 40 mA", "citation": cite_text(secondary)},
        ]
    elif fit.instrument_id == "sem-jeol":
        params = [
            {"label": "Accelerating voltage", "value": "10–20 kV", "citation": cite_text(primary)},
            {"label": "Coating",               "value": "Carbon, 5–10 nm" if "uncoated" in (ctx.coating_status + ctx.surface_condition).lower() else "Not required",
             "citation": cite_text(primary)},
            {"label": "Working distance",      "value": "10 mm", "citation": cite_text(primary)},
            {"label": "Spot size",             "value": "Auto (medium)", "citation": ""},
        ]
    else:
        params = [
            {"label": "Mode", "value": "Standard", "citation": ""},
            {"label": "Duration", "value": f"{fit.run_duration_minutes} min", "citation": ""},
        ]

    if fit.prep_time_minutes:
        pre.append({"text": f"Carbon coat {ctx.sample_dimensions or 'specimens'} at Station 2B "
                            f"(~{fit.prep_time_minutes} min)", "citation": cite_text(primary)})
    pre.extend([
        {"text": f"Confirm safety training for {fit.instrument_name} is current", "citation": ""},
        {"text": f"Arrive by {booking.prep_start:%H:%M} for warm-up and prep", "citation": ""},
        {"text": f"Review SDS for {material} and lab EH&S guidelines",
         "citation": cite_text(secondary) if secondary else ""},
        {"text": f"Bring USB drive labelled with research group", "citation": ""},
    ])

    proc = [
        {"title": "Warm-up",       "detail": f"Power on the instrument and complete its warm-up cycle (~{max(15, fit.run_duration_minutes // 6)} min).",
         "citation": cite_text(secondary) if secondary else ""},
        {"title": "Load sample",   "detail": f"Mount {material} ({ctx.sample_dimensions or 'as supplied'}). Verify surface level and stage clearance.",
         "citation": cite_text(primary)},
        {"title": "Configure",     "detail": f"Apply parameters above for {goal}.",
         "citation": cite_text(primary)},
        {"title": "Acquire data",  "detail": f"Run the planned scan / image series for {goal}. Monitor for saturation or charging.",
         "citation": ""},
        {"title": "Export",        "detail": "Save raw files to lab server under your group folder.",
         "citation": ""},
        {"title": "Shutdown",      "detail": "Follow instrument-specific shutdown checklist in the lab binder.",
         "citation": ""},
    ]

    post = [
        {"text": "Submit LODE post-run report with actual parameters + quality rating"},
        {"text": "Log instrument hours and any anomalies in the maintenance log"},
        {"text": "Backup raw data to research group share within 24 hours"},
        {"text": "Notify lab manager of any DET-SAT, VAC-LOW, or charging issues"},
    ]

    safety = [
        {"text": f"Handle {material} per Mines EH&S guidelines.",
         "citation": cite_text(secondary) if secondary else ""},
        {"text": "PPE: safety glasses (and gloves when handling powders).", "citation": ""},
    ]
    if ctx.hazardous_materials:
        safety.append({"text": "Hazardous materials flagged — coordinate with EH&S before session.",
                       "citation": ""})

    notes = (f"This SOP is customized for {ctx.researcher_name or 'the researcher'}'s {goal} "
             f"on {material}. {'Sample prep (' + str(fit.prep_time_minutes) + ' min) included before session. ' if fit.prep_time_minutes else ''}"
             f"Cited RAG sources are listed at the end of this document.")

    return {
        "sample_notes": notes,
        "parameters": params,
        "pre_checklist": pre,
        "procedure": proc,
        "post_checklist": post,
        "safety_notes": safety,
        "references": _references_from_chunks(chunks),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_sop_content(
    ctx: ExperimentContext,
    fit: InstrumentFit,
    booking: BookingOption,
) -> dict:
    chunks = _gather_chunks(ctx, fit)
    refs = _references_from_chunks(chunks)

    if not has_llm():
        content = _fallback_content(ctx, fit, booking, chunks)
        content["references"] = refs
        return content

    prompt = (
        "BOOKING CONTEXT:\n" + _ctx_block(ctx, fit, booking)
        + "\n\nRAG CITATION EXCERPTS (cite by the [n] source label exactly as shown):\n"
        + _rag_block(chunks)
        + "\n\nNow produce the JSON SOP content."
    )
    try:
        data = invoke_json(_SYSTEM, prompt, temperature=0.25)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM SOP build failed (%s); using fallback", exc)
        data = {}

    if not isinstance(data, dict) or "procedure" not in data:
        content = _fallback_content(ctx, fit, booking, chunks)
    else:
        # Normalize / clamp shape.
        content = {
            "sample_notes": str(data.get("sample_notes") or "").strip(),
            "parameters":   _coerce_list(data.get("parameters"), ("label", "value")),
            "pre_checklist":_coerce_list(data.get("pre_checklist"), ("text",)),
            "procedure":    _coerce_list(data.get("procedure"), ("title", "detail")),
            "post_checklist":_coerce_list(data.get("post_checklist"), ("text",)),
            "safety_notes": _coerce_list(data.get("safety_notes"), ("text",)),
        }
        if not content["sample_notes"]:
            content["sample_notes"] = _fallback_content(ctx, fit, booking, chunks)["sample_notes"]

    content["references"] = refs
    return content


def _coerce_list(items, required_keys) -> list[dict]:
    out: list[dict] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict):
            if all(k in item for k in required_keys) and any(item.get(k) for k in required_keys):
                out.append({k: ("" if item.get(k) is None else str(item.get(k))) for k in
                            list(required_keys) + ["citation"]})
        elif isinstance(item, str) and "text" in required_keys:
            out.append({"text": item, "citation": ""})
    return out
